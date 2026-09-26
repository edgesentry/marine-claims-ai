#!/usr/bin/env python3
"""
Rebuild local open-core indexes from cached public JSON.

Pipeline (see docs/technical_stack.md):
  Polars normalize → LanceDB hybrid index (vector + BM25) → DuckDB analytical tables

Binary artifacts under _inputs/ and .lancedb/ are gitignored and never committed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import duckdb
import lancedb
import polars as pl
from fastembed import TextEmbedding

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DATASET_DIR = os.path.join(_REPO_ROOT, "_inputs", "poc_datasets")
DEFAULT_LANCE_DIR = os.path.join(_REPO_ROOT, ".lancedb")
DEFAULT_DUCK_PATH = os.path.join(_REPO_ROOT, "_inputs", "marine_claims.duckdb")
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384
LANCE_TABLE = "precedents"


def load_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rows_from_sources(dataset_dir: str) -> list[dict]:
    rows: list[dict] = []

    jmat = load_json(os.path.join(dataset_dir, "benchmark_field1_jmat_20cases.json"))
    if isinstance(jmat, list):
        for c in jmat:
            text = f"{c.get('input_facts', '')}\n{c.get('ground_truth_ruling', '')}".strip()
            if not text:
                continue
            rows.append(
                {
                    "id": f"jmat-{c.get('case_id')}",
                    "domain": "jmat",
                    "title": c.get("title") or "",
                    "source_url": c.get("url") or "",
                    "category": "",
                    "trade_code": "",
                    "risk_tier": "",
                    "cost_jpy": None,
                    "fault_split_text": "",
                    "awarded_jpy": None,
                    "claimed_repair_jpy": None,
                    "disallowed_jpy": None,
                    "casualty_related": True,
                    "text": text,
                }
            )
    else:
        print(f"[WARN] Missing JMAT JSON under {dataset_dir}")

    psc = load_json(os.path.join(dataset_dir, "benchmark_field2_psc_20flags.json"))
    if isinstance(psc, list):
        for f in psc:
            flag = f.get("flag_state") or ""
            tier = f.get("ground_truth_risk_tier") or ""
            text = (
                f"Flag state {flag}. Detention rate {f.get('ground_truth_detention_rate_pct')}%. "
                f"Risk tier {tier}."
            )
            rows.append(
                {
                    "id": f"psc-{f.get('rank')}",
                    "domain": "psc",
                    "title": flag,
                    "source_url": "",
                    "category": "",
                    "trade_code": "",
                    "risk_tier": tier,
                    "cost_jpy": None,
                    "fault_split_text": "",
                    "awarded_jpy": None,
                    "claimed_repair_jpy": None,
                    "disallowed_jpy": None,
                    "casualty_related": False,
                    "text": text,
                }
            )

    repair = load_json(os.path.join(dataset_dir, "benchmark_field3_repair_20packages.json"))
    if isinstance(repair, list):
        concurrent_trades = {"ENG", "VALVE", "SAFE"}
        for p in repair:
            trade = p.get("trade_code") or ""
            text = f"{p.get('category', '')} {p.get('name', '')} trade_code={trade}".strip()
            # Statutory / machinery open-ups are concurrent-maintenance candidates
            concurrent = any(trade.startswith(t) for t in concurrent_trades)
            rows.append(
                {
                    "id": f"repair-{p.get('pkg_id')}",
                    "domain": "repair",
                    "title": p.get("name") or "",
                    "source_url": "",
                    "category": p.get("category") or "",
                    "trade_code": trade,
                    "risk_tier": "",
                    "cost_jpy": p.get("ground_truth_cost_jpy"),
                    "fault_split_text": "",
                    "awarded_jpy": None,
                    "claimed_repair_jpy": None,
                    "disallowed_jpy": None,
                    "casualty_related": not concurrent,
                    "text": text,
                }
            )

    civil = load_json(os.path.join(dataset_dir, "benchmark_court_civil_cases.json"))
    if isinstance(civil, list):
        for c in civil:
            text = (
                f"{c.get('input_facts', '')}\n{c.get('holding', '')}\n"
                f"fault_ratio={c.get('fault_ratio', '')}"
            ).strip()
            if not text:
                continue
            rows.append(
                {
                    "id": f"civil-{c.get('case_id')}",
                    "domain": "civil_court",
                    "title": c.get("title") or "",
                    "source_url": c.get("url") or "",
                    "category": c.get("court") or "",
                    "trade_code": "",
                    "risk_tier": "",
                    "cost_jpy": c.get("awarded_damages_jpy"),
                    "fault_split_text": c.get("fault_ratio") or "",
                    "awarded_jpy": c.get("awarded_damages_jpy"),
                    "claimed_repair_jpy": c.get("claimed_repair_jpy"),
                    "disallowed_jpy": c.get("disallowed_jpy"),
                    "casualty_related": True,
                    "text": text,
                }
            )
    else:
        print("[INFO] No civil court JSON yet (optional Field 4)")

    return rows


def normalize_with_polars(rows: list[dict]) -> pl.DataFrame:
    """Typed Arrow-backed frame for zero-copy handoff to LanceDB / DuckDB."""
    df = pl.DataFrame(rows)
    return df.with_columns(
        [
            pl.col("id").cast(pl.Utf8),
            pl.col("domain").cast(pl.Utf8),
            pl.col("title").cast(pl.Utf8).fill_null(""),
            pl.col("source_url").cast(pl.Utf8).fill_null(""),
            pl.col("category").cast(pl.Utf8).fill_null(""),
            pl.col("trade_code").cast(pl.Utf8).fill_null(""),
            pl.col("risk_tier").cast(pl.Utf8).fill_null(""),
            pl.col("cost_jpy").cast(pl.Int64),
            pl.col("fault_split_text").cast(pl.Utf8).fill_null(""),
            pl.col("awarded_jpy").cast(pl.Int64),
            pl.col("claimed_repair_jpy").cast(pl.Int64),
            pl.col("disallowed_jpy").cast(pl.Int64),
            pl.col("casualty_related").cast(pl.Boolean),
            pl.col("text").cast(pl.Utf8),
        ]
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = TextEmbedding(model_name=EMBED_MODEL)
    return [list(map(float, v)) for v in model.embed(texts)]


def _table_names(db) -> list[str]:
    tables = db.list_tables()
    if hasattr(tables, "tables"):
        return list(tables.tables or [])
    if isinstance(tables, list):
        return [t if isinstance(t, str) else getattr(t, "name", str(t)) for t in tables]
    # Fallback for older clients
    try:
        return list(db.table_names())
    except Exception:
        return []


def build_lancedb(lance_dir: str, df: pl.DataFrame, force: bool) -> None:
    if force and os.path.isdir(lance_dir):
        shutil.rmtree(lance_dir)
    os.makedirs(lance_dir, exist_ok=True)

    print(f"[EMBED] Encoding {df.height} passages with {EMBED_MODEL}...")
    vectors = embed_texts(df["text"].to_list())
    if any(len(v) != EMBED_DIM for v in vectors):
        raise RuntimeError(f"Expected embedding dim {EMBED_DIM}")

    records = df.to_dicts()
    for row, vec in zip(records, vectors, strict=True):
        row["vector"] = vec

    db = lancedb.connect(lance_dir)
    if LANCE_TABLE in _table_names(db) and not force:
        print(f"[SKIP] LanceDB table '{LANCE_TABLE}' exists (pass --force)")
        return

    print(f"[LANCE] Writing table '{LANCE_TABLE}' -> {lance_dir}")
    table = db.create_table(LANCE_TABLE, data=records, mode="overwrite")
    from lancedb.index import FTS

    table.create_index("text", config=FTS(), replace=True)
    print(f"[OK] LanceDB rows={table.count_rows()}")


def build_duckdb_analytics(duck_path: str, df: pl.DataFrame, force: bool) -> None:
    """DuckDB holds analytical / apportionment tables — not vector search."""
    if os.path.exists(duck_path):
        if not force:
            print(f"[SKIP] DuckDB already exists: {duck_path}")
            return
        os.remove(duck_path)

    os.makedirs(os.path.dirname(duck_path), exist_ok=True)
    # Drop vector intent; keep typed financial / triage columns
    analytics = df.drop("text") if "text" in df.columns else df

    con = duckdb.connect(duck_path)
    try:
        con.register("analytics_df", analytics.to_arrow())
        con.execute("CREATE TABLE line_items AS SELECT * FROM analytics_df")
        # Convenience view for 50/50 drydock math demos
        con.execute(
            """
            CREATE OR REPLACE VIEW drydock_apportionment AS
            SELECT
                id,
                domain,
                title,
                trade_code,
                cost_jpy,
                casualty_related,
                CASE
                    WHEN domain = 'repair' AND casualty_related THEN cost_jpy
                    WHEN domain = 'repair' AND NOT casualty_related THEN 0
                    ELSE NULL
                END AS insurer_share_jpy,
                CASE
                    WHEN domain = 'repair' AND casualty_related THEN 0
                    WHEN domain = 'repair' AND NOT casualty_related THEN cost_jpy
                    ELSE NULL
                END AS owner_share_jpy,
                CASE
                    WHEN domain = 'repair' THEN CAST(cost_jpy AS DOUBLE) * 0.5
                    ELSE NULL
                END AS drydock_fee_5050_jpy
            FROM line_items
            """
        )
        counts = con.execute(
            "SELECT domain, COUNT(*) FROM line_items GROUP BY domain ORDER BY domain"
        ).fetchall()
        print(f"[OK] DuckDB analytics -> {duck_path}")
        for domain, n in counts:
            print(f"  {domain}: {n}")
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=DEFAULT_DATASET_DIR)
    parser.add_argument("--lance-dir", default=DEFAULT_LANCE_DIR)
    parser.add_argument("--duck-path", default=DEFAULT_DUCK_PATH)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    rows = rows_from_sources(args.data_dir)
    if not rows:
        print("[ERROR] No rows. Run scripts/fetch_public_datasets.py first.", file=sys.stderr)
        return 1

    print(f"[POLARS] Normalizing {len(rows)} rows")
    df = normalize_with_polars(rows)
    build_lancedb(args.lance_dir, df, force=args.force)
    build_duckdb_analytics(args.duck_path, df, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
