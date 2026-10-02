#!/usr/bin/env python3
"""
Retrieval over local DuckDB (vector cosine + keyword ILIKE, fused via RRF).

Offline-PWA aligned: same hashEmbed as ``web/src/engines/fault.ts``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import duckdb

from marine_claims_ai.index.embed import hash_embed, tokenize
from marine_claims_ai.paths import DEFAULT_DUCK_PATH

PRECEDENTS_TABLE = "precedents"
DOMAINS = ("jmat", "psc", "repair", "civil_court", "civil_synthetic", "jtsb")


def _rrf_fuse(
    vector_hits: list[dict],
    keyword_hits: list[dict],
    *,
    top_k: int,
    k: int = 60,
) -> list[dict]:
    scores: dict[str, float] = {}
    rows: dict[str, dict] = {}
    for rank, h in enumerate(vector_hits, start=1):
        hid = str(h.get("id") or "")
        scores[hid] = scores.get(hid, 0.0) + 1.0 / (k + rank)
        rows[hid] = h
    for rank, h in enumerate(keyword_hits, start=1):
        hid = str(h.get("id") or "")
        scores[hid] = scores.get(hid, 0.0) + 1.0 / (k + rank)
        rows.setdefault(hid, h)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    out: list[dict] = []
    for hid, score in ordered[:top_k]:
        row = dict(rows[hid])
        row["score"] = score
        out.append(row)
    return out


def search(
    duck_path: str,
    query: str,
    domain: str | None,
    trade_code: str | None,
    top_k: int,
) -> list[dict]:
    if not os.path.exists(duck_path):
        raise FileNotFoundError(
            f"DuckDB not found: {duck_path}. Run: uv run python scripts/init_duckdb_vector.py --force"
        )

    qvec = hash_embed(query)
    filters: list[str] = []
    params: list[object] = []
    if domain:
        filters.append("domain = ?")
        params.append(domain)
    if trade_code:
        filters.append("trade_code = ?")
        params.append(trade_code)
    where = (" WHERE " + " AND ".join(filters)) if filters else ""

    fetch_n = max(top_k * 3, top_k)
    con = duckdb.connect(duck_path, read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if PRECEDENTS_TABLE not in tables:
            raise FileNotFoundError(
                f"Table '{PRECEDENTS_TABLE}' missing in {duck_path}; rebuild with --force"
            )

        vector_sql = f"""
            SELECT
              id, domain, title, category, trade_code, risk_tier,
              cost_jpy, fault_split_text, awarded_jpy, source_url, text,
              list_cosine_similarity(embedding, ?::FLOAT[]) AS score
            FROM {PRECEDENTS_TABLE}
            {where}
            ORDER BY score DESC NULLS LAST
            LIMIT ?
        """
        vparams = [qvec, *params, fetch_n]
        vresult = con.execute(vector_sql, vparams)
        vcols = [d[0] for d in vresult.description]
        vrows = [dict(zip(vcols, row, strict=True)) for row in vresult.fetchall()]

        tokens = tokenize(query)[:6]
        keyword_hits: list[dict] = []
        if tokens:
            like_clauses = []
            kparams: list[object] = list(params)
            for tok in tokens:
                like_clauses.append("lower(text) LIKE ?")
                kparams.append(f"%{tok.lower()}%")
            kw_where_parts = list(filters)
            kw_where_parts.append("(" + " OR ".join(like_clauses) + ")")
            kw_where = " WHERE " + " AND ".join(kw_where_parts)
            keyword_sql = f"""
                SELECT
                  id, domain, title, category, trade_code, risk_tier,
                  cost_jpy, fault_split_text, awarded_jpy, source_url, text,
                  0.0 AS score
                FROM {PRECEDENTS_TABLE}
                {kw_where}
                LIMIT ?
            """
            kparams.append(fetch_n)
            kresult = con.execute(keyword_sql, kparams)
            kcols = [d[0] for d in kresult.description]
            keyword_hits = [dict(zip(kcols, row, strict=True)) for row in kresult.fetchall()]
    finally:
        con.close()

    fused = _rrf_fuse(vrows, keyword_hits, top_k=top_k)
    out = []
    for h in fused:
        text = h.get("text") or ""
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
                "score": h.get("score"),
                "snippet": text[:240],
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duck-path", default=str(DEFAULT_DUCK_PATH))
    parser.add_argument(
        "--lance-dir",
        default=None,
        help="Deprecated; LanceDB removed. Ignored.",
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--domain", choices=DOMAINS, default=None)
    parser.add_argument("--trade-code", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.lance_dir:
        print("[WARN] --lance-dir ignored; use --duck-path.", file=sys.stderr)

    try:
        hits = search(args.duck_path, args.query, args.domain, args.trade_code, args.top_k)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2, default=str))
        return 0

    if not hits:
        print("No matches.")
        return 0

    print(
        f"Query: {args.query!r}  domain={args.domain or '*'}  "
        f"top_k={args.top_k}  (DuckDB vector+keyword RRF)"
    )
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
