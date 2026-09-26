#!/usr/bin/env python3
"""
Build a local DuckDB database with hybrid (relational + vector) search over public benchmarks.

The DuckDB file is written under _inputs/ (gitignored) and must never be committed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import duckdb
from fastembed import TextEmbedding

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DATASET_DIR = os.path.join(_REPO_ROOT, "_inputs", "poc_datasets")
DEFAULT_DB_PATH = os.path.join(_REPO_ROOT, "_inputs", "marine_claims.duckdb")
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384


SCHEMA_SQL = f"""
CREATE TABLE precedents (
    id VARCHAR PRIMARY KEY,
    domain VARCHAR NOT NULL,
    title VARCHAR,
    source_url VARCHAR,
    category VARCHAR,
    trade_code VARCHAR,
    risk_tier VARCHAR,
    cost_jpy BIGINT,
    fault_split_text VARCHAR,
    awarded_jpy BIGINT,
    claimed_repair_jpy BIGINT,
    disallowed_jpy BIGINT,
    text_for_embed VARCHAR NOT NULL,
    embedding FLOAT[{EMBED_DIM}]
);
"""


def load_json(path: str) -> list | dict | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rows_from_jmat(cases: list[dict]) -> list[dict]:
    rows = []
    for c in cases:
        facts = (c.get("input_facts") or "").strip()
        ruling = (c.get("ground_truth_ruling") or "").strip()
        text = f"{facts}\n{ruling}".strip()
        if not text:
            continue
        rows.append(
            {
                "id": f"jmat-{c.get('case_id')}",
                "domain": "jmat",
                "title": c.get("title"),
                "source_url": c.get("url"),
                "category": None,
                "trade_code": None,
                "risk_tier": None,
                "cost_jpy": None,
                "fault_split_text": None,
                "awarded_jpy": None,
                "claimed_repair_jpy": None,
                "disallowed_jpy": None,
                "text_for_embed": text,
            }
        )
    return rows


def rows_from_psc(flags: list[dict]) -> list[dict]:
    rows = []
    for f in flags:
        flag = f.get("flag_state") or ""
        tier = f.get("ground_truth_risk_tier") or ""
        rate = f.get("ground_truth_detention_rate_pct")
        text = (
            f"Flag state {flag}. Detention rate {rate}%. Risk tier {tier}. "
            f"Inspections {f.get('input_inspections_count')}, "
            f"detentions {f.get('ground_truth_detentions_count')}."
        )
        rows.append(
            {
                "id": f"psc-{f.get('rank')}",
                "domain": "psc",
                "title": flag,
                "source_url": None,
                "category": None,
                "trade_code": None,
                "risk_tier": tier,
                "cost_jpy": None,
                "fault_split_text": None,
                "awarded_jpy": None,
                "claimed_repair_jpy": None,
                "disallowed_jpy": None,
                "text_for_embed": text,
            }
        )
    return rows


def rows_from_repair(packages: list[dict]) -> list[dict]:
    rows = []
    for p in packages:
        name = p.get("name") or ""
        category = p.get("category") or ""
        trade = p.get("trade_code") or ""
        text = f"{category} {name} trade_code={trade}".strip()
        rows.append(
            {
                "id": f"repair-{p.get('pkg_id')}",
                "domain": "repair",
                "title": name,
                "source_url": None,
                "category": category,
                "trade_code": trade,
                "risk_tier": None,
                "cost_jpy": p.get("ground_truth_cost_jpy"),
                "fault_split_text": None,
                "awarded_jpy": None,
                "claimed_repair_jpy": None,
                "disallowed_jpy": None,
                "text_for_embed": text,
            }
        )
    return rows


def rows_from_civil(cases: list[dict]) -> list[dict]:
    rows = []
    for c in cases:
        facts = (c.get("input_facts") or "").strip()
        holding = (c.get("holding") or c.get("ground_truth_holding") or "").strip()
        fault = c.get("fault_ratio") or ""
        text = f"{facts}\n{holding}\nfault_ratio={fault}".strip()
        if not text or text == f"fault_ratio={fault}":
            continue
        rows.append(
            {
                "id": f"civil-{c.get('case_id')}",
                "domain": "civil_court",
                "title": c.get("title") or f"{c.get('court', '')} {c.get('date', '')}".strip(),
                "source_url": c.get("url"),
                "category": c.get("court"),
                "trade_code": None,
                "risk_tier": None,
                "cost_jpy": c.get("awarded_damages_jpy"),
                "fault_split_text": fault or None,
                "awarded_jpy": c.get("awarded_damages_jpy"),
                "claimed_repair_jpy": c.get("claimed_repair_jpy"),
                "disallowed_jpy": c.get("disallowed_jpy"),
                "text_for_embed": text,
            }
        )
    return rows


def collect_rows(dataset_dir: str) -> list[dict]:
    rows: list[dict] = []

    jmat = load_json(os.path.join(dataset_dir, "benchmark_field1_jmat_20cases.json"))
    if isinstance(jmat, list):
        rows.extend(rows_from_jmat(jmat))
    else:
        print(f"[WARN] Missing or invalid JMAT JSON under {dataset_dir}")

    psc = load_json(os.path.join(dataset_dir, "benchmark_field2_psc_20flags.json"))
    if isinstance(psc, list):
        rows.extend(rows_from_psc(psc))
    else:
        print(f"[WARN] Missing or invalid PSC JSON under {dataset_dir}")

    repair = load_json(os.path.join(dataset_dir, "benchmark_field3_repair_20packages.json"))
    if isinstance(repair, list):
        rows.extend(rows_from_repair(repair))
    else:
        print(f"[WARN] Missing or invalid repair JSON under {dataset_dir}")

    civil = load_json(os.path.join(dataset_dir, "benchmark_court_civil_cases.json"))
    if isinstance(civil, list):
        rows.extend(rows_from_civil(civil))
    else:
        print("[INFO] No civil court JSON yet (optional Field 4)")

    return rows


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = TextEmbedding(model_name=EMBED_MODEL)
    vectors = list(model.embed(texts))
    return [list(map(float, v)) for v in vectors]


def build_db(db_path: str, rows: list[dict], force: bool) -> None:
    if os.path.exists(db_path):
        if not force:
            print(f"[SKIP] DB already exists: {db_path} (pass --force to rebuild)")
            return
        os.remove(db_path)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    texts = [r["text_for_embed"] for r in rows]
    print(f"[EMBED] Encoding {len(texts)} passages with {EMBED_MODEL}...")
    embeddings = embed_texts(texts)

    con = duckdb.connect(db_path)
    try:
        con.execute(SCHEMA_SQL)
        insert_sql = """
            INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for row, emb in zip(rows, embeddings, strict=True):
            if len(emb) != EMBED_DIM:
                raise RuntimeError(f"Expected embedding dim {EMBED_DIM}, got {len(emb)}")
            con.execute(
                insert_sql,
                [
                    row["id"],
                    row["domain"],
                    row["title"],
                    row["source_url"],
                    row["category"],
                    row["trade_code"],
                    row["risk_tier"],
                    row["cost_jpy"],
                    row["fault_split_text"],
                    row["awarded_jpy"],
                    row["claimed_repair_jpy"],
                    row["disallowed_jpy"],
                    row["text_for_embed"],
                    emb,
                ],
            )
        counts = con.execute(
            "SELECT domain, COUNT(*) FROM precedents GROUP BY domain ORDER BY domain"
        ).fetchall()
        print(f"[OK] Wrote {db_path}")
        for domain, n in counts:
            print(f"  {domain}: {n}")
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=DEFAULT_DATASET_DIR)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    rows = collect_rows(args.data_dir)
    if not rows:
        print("[ERROR] No rows to ingest. Run scripts/fetch_public_datasets.py first.", file=sys.stderr)
        return 1

    print(f"[INGEST] Collected {len(rows)} rows from {args.data_dir}")
    build_db(args.db_path, rows, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
