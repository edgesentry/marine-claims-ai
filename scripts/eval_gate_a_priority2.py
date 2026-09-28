#!/usr/bin/env python3
"""CLI: Gate A Priority 2 integrated harness (A5–A7)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marine_claims_ai.benchmarks.gate_a_priority2 import run_gate_a_priority2
from marine_claims_ai.paths import DEFAULT_DATASET_DIR, DEFAULT_LOG_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Path to config/gate_a_priority2.json")
    parser.add_argument(
        "--dataset-dir",
        default=str(DEFAULT_DATASET_DIR),
        help="Directory for optional source_file resolution (JMAT PDFs/HTML)",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path for full report JSON (prefer _data/benchmarks/)",
    )
    parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Exit 1 when overall_pass is false (A6 zero-tol + A5/A7 accuracy)",
    )
    parser.add_argument(
        "--fail-on-scale",
        action="store_true",
        help="Exit 2 when scale_incomplete (N below Issue #59 targets)",
    )
    args = parser.parse_args()

    report = run_gate_a_priority2(
        config_path=args.config,
        dataset_dir=args.dataset_dir,
    )
    gate = report["gate"]
    scale = report["scale"]
    a5a6 = report["metrics"]["A5_A6"]
    a7 = report["metrics"]["A7"]

    print("=== Gate A Priority 2 ===")
    print(
        f"overall_pass={gate['overall_pass']} zero_tol={gate['zero_tolerance_pass']} "
        f"agr={gate['situation_agreement']:.1%} inv={gate['critical_role_inversions']} "
        f"civil_acc={gate['civil_accuracy']:.1%} w10={gate['fault_ratio_within_10pt_rate']:.1%}"
    )
    print(
        f"A5/A6: cases_run={a5a6.get('cases_run')} ext={a5a6.get('extraction_rate')} "
        f"counts={a5a6.get('situation_counts')}"
    )
    print(
        f"A7: mode={a7.get('primary_mode')} scored={a7.get('scored')} "
        f"catalog_fr={a7.get('catalog_with_fault_ratio')}"
    )
    print(
        f"scale_incomplete={scale['scale_incomplete']} "
        f"jmat={scale['jmat_cases']} ot/ho/cr="
        f"{scale['overtaking']}/{scale['head_on']}/{scale['crossing']} "
        f"civil={scale['civil_cases']}"
    )
    print(f"log_dir={DEFAULT_LOG_DIR}")

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        slim = {k: v for k, v in report.items() if not k.startswith("_")}
        out.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] wrote {out}")

    if args.fail_on_gate and not gate["overall_pass"]:
        return 1
    if args.fail_on_scale and scale["scale_incomplete"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
