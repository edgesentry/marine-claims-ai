#!/usr/bin/env python3
"""
Rebuild local open-core indexes from cached public JSON.

Pipeline:
  Polars normalize → DuckDB (precedents + embeddings + analytics VIEW)

Binary artifacts under ``_data/duckdb/`` are gitignored and never committed.
Aligned with the offline PWA: hashed 384-dim embeddings (same as web hashEmbed).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import duckdb
import polars as pl

from marine_claims_ai.analytics.drydock_sql import DRYDOCK_APPORTIONMENT_VIEW_SQL
from marine_claims_ai.index.embed import EMBED_DIM, embed_texts
from marine_claims_ai.paths import DEFAULT_DATASET_DIR, DEFAULT_DUCK_PATH

PRECEDENTS_TABLE = "precedents"


def load_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_json_first(dataset_dir: str, *names: str):
    """Load the first existing JSON among candidate filenames (new name, then legacy)."""
    for name in names:
        data = load_json(os.path.join(dataset_dir, name))
        if data is not None:
            return data, name
    return None, None


def rows_from_sources(dataset_dir: str) -> list[dict]:
    rows: list[dict] = []

    jmat, jmat_name = load_json_first(
        dataset_dir,
        "benchmark_field1_jmat_cases.json",
        "benchmark_field1_jmat_20cases.json",
    )
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
    if jmat_name:
        print(f"[INFO] Loaded JMAT from {jmat_name}")

    psc, _ = load_json_first(
        dataset_dir,
        "benchmark_field2_psc_flags.json",
        "benchmark_field2_psc_20flags.json",
    )
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

    repair, _ = load_json_first(
        dataset_dir,
        "benchmark_field3_repair_packages.json",
        "benchmark_field3_repair_20packages.json",
    )
    if isinstance(repair, list):
        concurrent_trades = {"ENG", "VALVE", "SAFE", "PROP"}
        for p in repair:
            trade = p.get("trade_code") or ""
            text = f"{p.get('category', '')} {p.get('name', '')} trade_code={trade}".strip()
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

    civil_syn = load_json(os.path.join(dataset_dir, "benchmark_court_civil_synthetic.json"))
    if isinstance(civil_syn, list):
        for c in civil_syn:
            text = (
                f"[synthetic] {c.get('input_facts', '')}\n{c.get('holding', '')}\n"
                f"fault_ratio={c.get('fault_ratio', '')}"
            ).strip()
            if not text:
                continue
            rows.append(
                {
                    "id": f"civil-syn-{c.get('case_id')}",
                    "domain": "civil_synthetic",
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

    jtsb = load_json(os.path.join(dataset_dir, "benchmark_jtsb_collision_cases.json"))
    if isinstance(jtsb, list):
        for c in jtsb:
            text = (
                f"{c.get('input_facts', '')}\n"
                f"accident_type={c.get('accident_type', '')} place={c.get('place', '')}"
            ).strip()
            if not text:
                continue
            rows.append(
                {
                    "id": f"jtsb-{c.get('case_id')}",
                    "domain": "jtsb",
                    "title": c.get("title") or "",
                    "source_url": c.get("url") or "",
                    "category": c.get("accident_type") or "",
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

    return rows


def normalize_with_polars(rows: list[dict]) -> pl.DataFrame:
    """Typed Arrow-backed frame for DuckDB."""
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


def build_duckdb(duck_path: str, df: pl.DataFrame, force: bool) -> None:
    """Write precedents (vector search) + line_items analytics into one DuckDB file."""
    if os.path.exists(duck_path):
        if not force:
            print(f"[SKIP] DuckDB already exists: {duck_path}")
            return
        os.remove(duck_path)

    os.makedirs(os.path.dirname(duck_path) or ".", exist_ok=True)

    print(f"[EMBED] Hash-embedding {df.height} passages (dim={EMBED_DIM}, PWA-aligned)...")
    vectors = embed_texts(df["text"].to_list())
    if any(len(v) != EMBED_DIM for v in vectors):
        raise RuntimeError(f"Expected embedding dim {EMBED_DIM}")

    precedents = df.with_columns(pl.Series("embedding", vectors))
    analytics = df.drop("text") if "text" in df.columns else df

    con = duckdb.connect(duck_path)
    try:
        con.register("precedents_df", precedents.to_arrow())
        con.execute(
            f"CREATE TABLE {PRECEDENTS_TABLE} AS SELECT * FROM precedents_df"
        )
        con.register("analytics_df", analytics.to_arrow())
        con.execute("CREATE TABLE line_items AS SELECT * FROM analytics_df")
        con.execute(DRYDOCK_APPORTIONMENT_VIEW_SQL)
        counts = con.execute(
            f"SELECT domain, COUNT(*) FROM {PRECEDENTS_TABLE} GROUP BY domain ORDER BY domain"
        ).fetchall()
        print(f"[OK] DuckDB -> {duck_path}")
        for domain, n in counts:
            print(f"  {domain}: {n}")
    finally:
        con.close()


# Back-compat alias used by older tests / callers
def build_duckdb_analytics(duck_path: str, df: pl.DataFrame, force: bool) -> None:
    build_duckdb(duck_path, df, force=force)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--duck-path", default=str(DEFAULT_DUCK_PATH))
    parser.add_argument(
        "--lance-dir",
        default=None,
        help="Deprecated (LanceDB removed). Ignored if passed.",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.lance_dir:
        print("[WARN] --lance-dir ignored; LanceDB was removed. Use DuckDB only.", file=sys.stderr)

    rows = rows_from_sources(args.data_dir)
    if not rows:
        print("[ERROR] No rows. Run scripts/fetch_public_datasets.py first.", file=sys.stderr)
        return 1

    print(f"[POLARS] Normalizing {len(rows)} rows")
    df = normalize_with_polars(rows)
    build_duckdb(args.duck_path, df, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
