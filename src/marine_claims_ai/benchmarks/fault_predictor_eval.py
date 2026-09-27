"""
Leave-one-out MAE evaluation for fault-ratio prediction vs civil catalog gold.

Target (Issue #44): Mean Absolute Error on primary-side percentage ≤ 10 pp
against the 36 certified rows in ``config/civil_precedent_catalog.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from marine_claims_ai.analytics.fault_predictor import (
    parse_fault_ratio,
    predict_fault_ratio,
)
from marine_claims_ai.ingest.civil import load_catalog
from marine_claims_ai.paths import DEFAULT_CIVIL_CATALOG_PATH


def seed_narrative(seed: dict[str, Any]) -> str:
    """Build evaluation narrative from catalog seed fields."""
    facts = str(seed.get("input_facts") or "").strip()
    holding = str(seed.get("holding") or "").strip()
    if facts and holding and len(facts) < 80:
        return f"{facts} {holding}".strip()
    return facts or holding


def evaluate_catalog_mae(
    catalog_path: str | Path | None = None,
    *,
    leave_one_out: bool = True,
) -> dict[str, Any]:
    """
    Compare ``predict_fault_ratio`` to gold ``fault_ratio`` on every catalog seed.

    MAE is the mean of ``|pred_primary - gold_primary|`` in percentage points.
    """
    path = Path(catalog_path) if catalog_path else DEFAULT_CIVIL_CATALOG_PATH
    seeds = load_catalog(path)
    rows: list[dict[str, Any]] = []
    abs_errors: list[float] = []

    for seed in seeds:
        gold = seed.get("fault_ratio")
        if not gold:
            continue
        try:
            gold_a, _ = parse_fault_ratio(str(gold))
        except ValueError:
            continue
        narrative = seed_narrative(seed)
        exclude = seed.get("case_id") if leave_one_out else None
        pred = predict_fault_ratio(
            narrative,
            None,
            catalog_path=path,
            exclude_case_id=exclude,
        )
        err = abs(pred.primary_pct - gold_a)
        abs_errors.append(float(err))
        rows.append(
            {
                "case_id": seed.get("case_id"),
                "title": seed.get("title"),
                "gold": str(gold),
                "predicted": pred.fault_ratio,
                "abs_error_pp": err,
                "situation": pred.situation,
                "baseline": pred.baseline_ratio,
                "rule_adjusted": pred.rule_adjusted_ratio,
                "knn": pred.knn_ratio,
                "modifiers": [m.modifier_id for m in pred.modifiers],
            }
        )

    mae = sum(abs_errors) / len(abs_errors) if abs_errors else 0.0
    return {
        "catalog_path": str(path),
        "n": len(abs_errors),
        "mae_pp": mae,
        "max_abs_error_pp": max(abs_errors) if abs_errors else 0.0,
        "leave_one_out": leave_one_out,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CIVIL_CATALOG_PATH),
        help="Path to civil_precedent_catalog.json",
    )
    parser.add_argument(
        "--max-mae",
        type=float,
        default=10.0,
        help="Fail if MAE exceeds this many percentage points (default: 10)",
    )
    parser.add_argument(
        "--no-leave-one-out",
        action="store_true",
        help="Allow identity matches (default is leave-one-out)",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args(argv)

    report = evaluate_catalog_mae(
        args.catalog,
        leave_one_out=not args.no_leave_one_out,
    )
    mae = float(report["mae_pp"])
    ok = mae <= float(args.max_mae)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"fault_predictor MAE={mae:.2f}pp on n={report['n']} "
            f"(max={report['max_abs_error_pp']:.0f}pp, "
            f"leave_one_out={report['leave_one_out']}) "
            f"gate={args.max_mae} → {'PASS' if ok else 'FAIL'}"
        )
        worst = sorted(report["rows"], key=lambda r: -r["abs_error_pp"])[:5]
        if worst:
            print("worst cases:")
            for row in worst:
                print(
                    f"  case_id={row['case_id']} gold={row['gold']} "
                    f"pred={row['predicted']} err={row['abs_error_pp']:.0f}pp "
                    f"mods={row['modifiers']}"
                )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
