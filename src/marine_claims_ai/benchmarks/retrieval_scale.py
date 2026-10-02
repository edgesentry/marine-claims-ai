"""Fixed-query retrieval scale evaluation (hit@k) over local DuckDB."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from marine_claims_ai.index import search as search_mod
from marine_claims_ai.paths import DEFAULT_DATASET_DIR, DEFAULT_DUCK_PATH, REPO_ROOT

DEFAULT_QUERIES = REPO_ROOT / "config" / "retrieval_eval_queries.json"
DEFAULT_REPORT = DEFAULT_DATASET_DIR / "retrieval_scale_report.json"


def load_queries(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def hit_at_k(
    hits: list[dict],
    expected_domains: list[str] | None,
    expected_id_prefixes: list[str] | None,
    k: int,
) -> bool:
    """True if any of the top-k hits matches expected domain or id prefix."""
    top = hits[:k]
    for h in top:
        domain = h.get("domain") or ""
        hid = h.get("id") or ""
        if expected_domains and domain in expected_domains:
            return True
        if expected_id_prefixes and any(hid.startswith(p) for p in expected_id_prefixes):
            return True
    return False


def aggregate_hit_rates(per_query: list[dict], k_values: list[int]) -> dict[str, float]:
    n = len(per_query) or 1
    out: dict[str, float] = {}
    for k in k_values:
        key = f"hit@{k}"
        out[key] = sum(1 for q in per_query if q.get("hits", {}).get(key)) / n
    return out


def diff_reports(baseline: dict, current: dict) -> dict[str, Any]:
    base_agg = baseline.get("aggregate") or {}
    cur_agg = current.get("aggregate") or {}
    keys = sorted(set(base_agg) | set(cur_agg))
    return {
        k: {
            "baseline": base_agg.get(k),
            "current": cur_agg.get(k),
            "delta": (cur_agg.get(k) or 0) - (base_agg.get(k) or 0),
        }
        for k in keys
    }


def run_eval(
    duck_path: str,
    queries_path: str | Path,
    search_fn=None,
) -> dict[str, Any]:
    cfg = load_queries(queries_path)
    k_values = list(cfg.get("k_values") or [5, 10])
    max_k = max(k_values) if k_values else 10
    search_fn = search_fn or search_mod.search

    per_query: list[dict] = []
    for q in cfg.get("queries") or []:
        query_text = q["query"]
        hits = search_fn(duck_path, query_text, None, None, max_k)
        hit_map = {
            f"hit@{k}": hit_at_k(
                hits,
                q.get("expected_domains"),
                q.get("expected_id_prefixes"),
                k,
            )
            for k in k_values
        }
        per_query.append(
            {
                "id": q.get("id"),
                "query": query_text,
                "hits": hit_map,
                "top_ids": [h.get("id") for h in hits[:max_k]],
                "top_domains": [h.get("domain") for h in hits[:max_k]],
            }
        )

    report = {
        "duck_path": duck_path,
        "queries_path": str(queries_path),
        "k_values": k_values,
        "n_queries": len(per_query),
        "per_query": per_query,
        "aggregate": aggregate_hit_rates(per_query, k_values),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duck-path", default=str(DEFAULT_DUCK_PATH))
    parser.add_argument(
        "--lance-dir",
        default=None,
        help="Deprecated; LanceDB removed. Use --duck-path.",
    )
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES))
    parser.add_argument("--out", default=str(DEFAULT_REPORT))
    parser.add_argument(
        "--baseline",
        default=None,
        help="Optional prior report JSON to compare aggregate hit@k deltas",
    )
    args = parser.parse_args()
    duck_path = args.duck_path
    if args.lance_dir and not args.duck_path:
        duck_path = str(DEFAULT_DUCK_PATH)

    report = run_eval(duck_path, args.queries)
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as f:
            baseline = json.load(f)
        report["delta_vs_baseline"] = diff_reports(baseline, report)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))
    if "delta_vs_baseline" in report:
        print("delta_vs_baseline:")
        print(json.dumps(report["delta_vs_baseline"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
