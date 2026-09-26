#!/usr/bin/env python3
"""
Hybrid retrieval over local LanceDB (vector + BM25 / FTS via RRF).

See docs/technical_stack.md — LanceDB is the search plane; DuckDB is analytics.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import lancedb
from fastembed import TextEmbedding
from lancedb.rerankers import RRFReranker

from marine_claims_ai.paths import DEFAULT_LANCE_DIR

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LANCE_TABLE = "precedents"
DOMAINS = ("jmat", "psc", "repair", "civil_court", "civil_synthetic", "jtsb")

def embed_query(query: str) -> list[float]:
    model = TextEmbedding(model_name=EMBED_MODEL)
    return list(map(float, next(model.embed([query]))))


def search(
    lance_dir: str,
    query: str,
    domain: str | None,
    trade_code: str | None,
    top_k: int,
) -> list[dict]:
    if not os.path.isdir(lance_dir):
        raise FileNotFoundError(
            f"LanceDB not found: {lance_dir}. Run: uv run python scripts/init_duckdb_vector.py --force"
        )

    db = lancedb.connect(lance_dir)
    listed = db.list_tables()
    if hasattr(listed, "tables"):
        names = list(listed.tables or [])
    elif isinstance(listed, list):
        names = listed
    else:
        names = list(db.table_names())
    if LANCE_TABLE not in names:
        raise FileNotFoundError(f"Table '{LANCE_TABLE}' missing in {lance_dir}")

    table = db.open_table(LANCE_TABLE)
    qvec = embed_query(query)

    filters: list[str] = []
    if domain:
        filters.append(f"domain = '{domain}'")
    if trade_code:
        filters.append(f"trade_code = '{trade_code}'")
    where = " AND ".join(filters) if filters else None

    reranker = RRFReranker()
    builder = table.search(query_type="hybrid").vector(qvec).text(query).rerank(reranker=reranker)
    if where:
        builder = builder.where(where, prefilter=True)
    hits = builder.limit(top_k).to_list()

    out = []
    for h in hits:
        out.append(
            {
                "id": h.get("id"),
                "domain": h.get("domain"),
                "title": h.get("title"),
                "category": h.get("category"),
                "trade_code": h.get("trade_code"),
                "risk_tier": h.get("risk_tier"),
                "cost_jpy": h.get("cost_jpy"),
                "fault_split_text": h.get("fault_split_text"),
                "awarded_jpy": h.get("awarded_jpy"),
                "source_url": h.get("source_url"),
                "score": h.get("_relevance_score") or h.get("_distance"),
                "snippet": (h.get("text") or "")[:240],
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lance-dir", default=str(DEFAULT_LANCE_DIR))
    parser.add_argument("--query", required=True)
    parser.add_argument("--domain", choices=DOMAINS, default=None)
    parser.add_argument("--trade-code", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        hits = search(args.lance_dir, args.query, args.domain, args.trade_code, args.top_k)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2, default=str))
        return 0

    if not hits:
        print("No matches.")
        return 0

    print(f"Query: {args.query!r}  domain={args.domain or '*'}  top_k={args.top_k}  (LanceDB hybrid)")
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
