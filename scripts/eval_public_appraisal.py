#!/usr/bin/env python3
"""CLI: evaluate public appraisal accuracy (provisional gold vs pipeline)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marine_claims_ai.benchmarks.public_appraisal_eval import evaluate_all
from marine_claims_ai.paths import DEFAULT_DATASET_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config/public_appraisal_eval.json",
    )
    parser.add_argument(
        "--dataset-dir",
        default=str(DEFAULT_DATASET_DIR),
        help="Directory containing public PDFs (default: _inputs/poc_datasets)",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write full metrics JSON (under _inputs recommended)",
    )
    parser.add_argument(
        "--write-gold-dir",
        default=None,
        help="If set, write per-case provisional gold JSON dumps for human review",
    )
    parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Exit 1 when configured Week-1 gates are not met",
    )
    args = parser.parse_args()

    report = evaluate_all(config_path=args.config, dataset_dir=args.dataset_dir)
    full_cases = report.pop("_full_cases", [])

    if args.write_gold_dir:
        out_dir = Path(args.write_gold_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for case in full_cases:
            if case.get("skipped"):
                continue
            path = out_dir / f"{case['case_id']}_gold.json"
            payload = {
                "case_id": case["case_id"],
                "damaged_zones": case.get("damaged_zones"),
                "items": [
                    {
                        "key": f"{i.get('num')}::{str(i.get('description') or '')[:80]}",
                        "num": i.get("num"),
                        "description": i.get("description"),
                        "gold_status": i.get("gold_status"),
                        "pred_status": i.get("status"),
                    }
                    for i in case.get("gold_rows") or []
                ],
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[gold] wrote {path}")

    print("=== Public appraisal accuracy (provisional gold v1) ===")
    for case in report["cases"]:
        if case.get("skipped"):
            print(f"- {case.get('case_id')}: SKIPPED ({case.get('reason')})")
            continue
        print(
            f"- {case.get('case_id')}: agreement={case.get('agreement'):.1%} "
            f"FA={case.get('false_accept')} FR={case.get('false_reject')} "
            f"criticalFA={case.get('critical_false_accept')} "
            f"n={case.get('items_scored')}"
        )
    gate = report["gate"]
    print(
        f"GATE mean_agreement={gate['mean_agreement']:.1%} "
        f"criticalFA={gate['critical_false_accept_total']} "
        f"cases_run={gate['cases_run']} overall_pass={gate['overall_pass']}"
    )

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] wrote {out}")

    if args.fail_on_gate and not gate["overall_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
