#!/usr/bin/env python3
"""
DuckDB analytical apportionment over local line_items (50/50 drydock + leakage).

Search/retrieval belongs in LanceDB; this script is the financial SQL plane.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import duckdb

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DUCK_PATH = os.path.join(_REPO_ROOT, "_inputs", "marine_claims.duckdb")


def summarize(duck_path: str) -> dict:
    if not os.path.exists(duck_path):
        raise FileNotFoundError(
            f"DuckDB not found: {duck_path}. Run: uv run python scripts/init_duckdb_vector.py --force"
        )

    con = duckdb.connect(duck_path, read_only=True)
    try:
        totals = con.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE domain = 'repair') AS repair_items,
                COALESCE(SUM(cost_jpy) FILTER (WHERE domain = 'repair'), 0) AS claimed_total_jpy,
                COALESCE(SUM(insurer_share_jpy) FILTER (WHERE domain = 'repair'), 0) AS insurer_share_jpy,
                COALESCE(SUM(owner_share_jpy) FILTER (WHERE domain = 'repair'), 0) AS owner_concurrent_jpy,
                COALESCE(SUM(drydock_fee_5050_jpy) FILTER (WHERE domain = 'repair'), 0) AS drydock_5050_pool_jpy
            FROM drydock_apportionment
            """
        ).fetchone()
        leakage = con.execute(
            """
            SELECT id, title, trade_code, cost_jpy
            FROM drydock_apportionment
            WHERE domain = 'repair' AND casualty_related = FALSE
            ORDER BY cost_jpy DESC NULLS LAST
            """
        ).fetchall()
    finally:
        con.close()

    claimed = int(totals[1] or 0)
    insurer = int(totals[2] or 0)
    owner = int(totals[3] or 0)
    return {
        "repair_items": int(totals[0] or 0),
        "claimed_total_jpy": claimed,
        "insurer_share_jpy": insurer,
        "owner_concurrent_jpy": owner,
        "drydock_5050_pool_jpy": int(totals[4] or 0),
        "claims_leakage_prevented_jpy": owner,
        "leakage_items": [
            {"id": r[0], "title": r[1], "trade_code": r[2], "cost_jpy": r[3]} for r in leakage
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duck-path", default=DEFAULT_DUCK_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        summary = summarize(args.duck_path)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print("DuckDB drydock apportionment summary")
    print("-" * 60)
    print(f"repair_items:              {summary['repair_items']}")
    print(f"claimed_total_jpy:         {summary['claimed_total_jpy']:,}")
    print(f"insurer_share_jpy:         {summary['insurer_share_jpy']:,}")
    print(f"owner_concurrent_jpy:      {summary['owner_concurrent_jpy']:,}")
    print(f"drydock_5050_pool_jpy:     {summary['drydock_5050_pool_jpy']:,.0f}")
    print(f"claims_leakage_prevented:  {summary['claims_leakage_prevented_jpy']:,}")
    print("\nConcurrent / leakage candidates:")
    for item in summary["leakage_items"]:
        print(f"  - {item['id']}: {item['title']} ({item['trade_code']}) {item['cost_jpy']:,} JPY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
