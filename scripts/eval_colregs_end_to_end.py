#!/usr/bin/env python3
"""CLI: end-to-end COLREGS accuracy from raw JMAT/JTSB-style narratives (Issue #39)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marine_claims_ai.benchmarks.colregs_e2e_eval import evaluate_all
from marine_claims_ai.paths import DEFAULT_DATASET_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config/jmat_collision_eval.json",
    )
    parser.add_argument(
        "--dataset-dir",
        default=str(DEFAULT_DATASET_DIR),
        help="Directory for optional source_file PDFs/text (default: _inputs/poc_datasets)",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write full metrics JSON",
    )
    parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Exit 1 when configured gates are not met",
    )
    args = parser.parse_args()

    report = evaluate_all(config_path=args.config, dataset_dir=args.dataset_dir)
    gate = report["gate"]

    print("=== COLREGS E2E accuracy (JMAT/JTSB narrative → classify) ===")
    print()
    print("| case_id | extract | situation | roles | inversion |")
    print("| --- | --- | --- | --- | --- |")
    for case in report["cases"]:
        if case.get("skipped"):
            print(
                f"| {case.get('case_id')} | SKIP | — | — | — |"
                f" ({case.get('reason')})"
            )
            continue
        ext = "OK" if case.get("extraction_ok") else "FAIL"
        sit = (
            f"{case.get('predicted_situation')}=={case.get('expected_situation')}"
            if case.get("extraction_ok")
            else "—"
        )
        if case.get("situation_match"):
            sit_mark = "MATCH"
        elif case.get("extraction_ok"):
            sit_mark = "MISS"
        else:
            sit_mark = "—"
        roles = f"{case.get('predicted_role_a')}/{case.get('predicted_role_b')}"
        inv = "YES" if case.get("critical_role_inversion") else "no"
        print(
            f"| {case.get('case_id')} | {ext} | {sit_mark} ({sit}) | {roles} | {inv} |"
        )

    print()
    print(
        f"**Extraction Rate**: {gate['extraction_rate']:.1%} "
        f"({gate['cases_run']} runnable)"
    )
    print(
        f"**E2E Situation Accuracy**: {gate['situation_agreement']:.1%} "
        f"(matches={gate['situation_matches']})"
    )
    print(f"**Critical Role Inversions**: {gate['critical_role_inversions']}")
    print(
        f"**GATE** cases_run={gate['cases_run']} "
        f"overall_pass={gate['overall_pass']}"
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
