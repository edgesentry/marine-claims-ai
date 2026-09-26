#!/usr/bin/env python3
"""
Hybrid search over the local marine_claims.duckdb (SQL filters + cosine similarity).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import duckdb
from fastembed import TextEmbedding

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DB_PATH = os.path.join(_REPO_ROOT, "_inputs", "marine_claims.duckdb")
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DOMAINS = ("jmat", "psc", "repair", "civil_court")


def embed_query(query: str) -> list[float]:
    model = TextEmbedding(model_name=EMBED_MODEL)
    vectors = list(model.embed([query]))
    return list(map(float, vectors[0]))


def search(
    db_path: str,
    query: str,
    domain: str | None,
    trade_code: str | None,
    max_cost_jpy: int | None,
    top_k: int,
) -> list[dict]:
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"DB not found: {db_path}. Run: uv run python scripts/init_duckdb_vector.py"
        )

    qvec = embed_query(query)
    filters = ["1=1"]
    params: list = [qvec]

    if domain:
        filters.append("domain = ?")
        params.append(domain)
    if trade_code:
        filters.append("trade_code = ?")
        params.append(trade_code)
    if max_cost_jpy is not None:
        filters.append("(cost_jpy IS NULL OR cost_jpy <= ?)")
        params.append(max_cost_jpy)

    where = " AND ".join(filters)
    params.append(top_k)

    sql = f"""
        SELECT
            id,
            domain,
            title,
            category,
            trade_code,
            risk_tier,
            cost_jpy,
            fault_split_text,
            awarded_jpy,
            claimed_repair_jpy,
            disallowed_jpy,
            source_url,
            array_cosine_similarity(embedding, ?::FLOAT[384]) AS score,
            left(text_for_embed, 240) AS snippet
        FROM precedents
        WHERE {where}
        ORDER BY score DESC
        LIMIT ?
    """

    con = duckdb.connect(db_path, read_only=True)
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--query", required=True)
    parser.add_argument("--domain", choices=DOMAINS, default=None)
    parser.add_argument("--trade-code", default=None)
    parser.add_argument("--max-cost-jpy", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    args = parser.parse_args()

    try:
        hits = search(
            args.db_path,
            args.query,
            args.domain,
            args.trade_code,
            args.max_cost_jpy,
            args.top_k,
        )
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2, default=str))
        return 0

    if not hits:
        print("No matches.")
        return 0

    print(f"Query: {args.query!r}  domain={args.domain or '*'}  top_k={args.top_k}")
    print("-" * 80)
    for i, h in enumerate(hits, start=1):
        score = h.get("score")
        score_s = f"{float(score):.4f}" if score is not None else "n/a"
        print(f"{i}. [{h.get('domain')}] {h.get('id')}  score={score_s}")
        print(f"   title: {h.get('title')}")
        if h.get("trade_code"):
            print(f"   trade_code: {h.get('trade_code')}  cost_jpy: {h.get('cost_jpy')}")
        if h.get("fault_split_text"):
            print(f"   fault: {h.get('fault_split_text')}  awarded_jpy: {h.get('awarded_jpy')}")
        print(f"   snippet: {h.get('snippet')}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
