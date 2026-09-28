#!/usr/bin/env python3
"""CLI: Gate A Priority 1 integrated harness (A1–A4, A8)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marine_claims_ai.benchmarks.gate_a_priority1 import run_gate_a_priority1
from marine_claims_ai.paths import DEFAULT_DATASET_DIR, DEFAULT_LOG_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Path to config/gate_a_priority1.json")
    parser.add_argument(
        "--dataset-dir",
        default=str(DEFAULT_DATASET_DIR),
        help="Directory with public PDFs / Field 3 JSON",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path for full report JSON (prefer _data/ or _logs/)",
    )
    parser.add_argument(
        "--bid-count",
        type=int,
        default=None,
        help="Override bid-notice corpus size (default: count _inputs/repairs/bids/*.pdf)",
    )
    parser.add_argument(
        "--skip-pdf-span",
        action="store_true",
        help="Skip A4 PDF span checks (CI without large PDFs)",
    )
    parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Exit 1 when overall_pass is false (zero-tolerance + agreement + A8)",
    )
    parser.add_argument(
        "--fail-on-scale",
        action="store_true",
        help="Exit 1 when scale_incomplete (N below issue targets)",
    )
    args = parser.parse_args()

    report = run_gate_a_priority1(
        config_path=args.config,
        dataset_dir=args.dataset_dir,
        include_pdf_span=not args.skip_pdf_span,
        bid_count=args.bid_count,
    )
    gate = report["gate"]
    scale = report["scale"]

    print("=== Gate A Priority 1 ===")
    print(
        f"overall_pass={gate['overall_pass']} zero_tol={gate['zero_tolerance_pass']} "
        f"agreement={gate['mean_agreement']:.1%} cfa={gate['critical_false_accept_total']} "
        f"d5_err={gate['rule_d5_reconciliation_error_jpy']} fab={gate['fabricated_line_items']}"
    )
    a8 = report["metrics"]["A8"]
    if a8.get("skipped"):
        print(f"A8: SKIPPED ({a8.get('reason')})")
    else:
        print(f"A8: MAPE={a8.get('mape_pct')}% pass={a8.get('pass')}")
    print(
        f"scale_incomplete={scale['scale_incomplete']} "
        f"vessels={scale['vessels_run']} items={scale['line_items']} bids={scale['bid_notices']}"
    )
    print(f"log_dir={DEFAULT_LOG_DIR}")

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        # Drop bulky case gold if present
        slim = dict(report)
        a1 = dict(slim["metrics"]["A1_A2"])
        a1.pop("cases", None)
        slim["metrics"] = {**slim["metrics"], "A1_A2": a1}
        out.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] wrote {out}")

    if args.fail_on_gate and not gate["overall_pass"]:
        return 1
    if args.fail_on_scale and scale["scale_incomplete"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
