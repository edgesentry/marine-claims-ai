"""Public appraisal accuracy eval: provisional gold vs pipeline predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marine_claims_ai.paths import DEFAULT_DATASET_DIR, REPO_ROOT

DEFAULT_EVAL_CONFIG = REPO_ROOT / "config" / "public_appraisal_eval.json"

STATUS_BUCKETS = ("COVERED", "APPORTIONED", "REVIEW", "EXCLUDED", "OTHER")


def load_eval_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_EVAL_CONFIG
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("cases"), list):
        raise ValueError(f"Invalid public appraisal eval config: {cfg_path}")
    return data


def normalize_status_bucket(status: str | None) -> str:
    s = str(status or "")
    if "APPORTIONED" in s:
        return "APPORTIONED"
    if "COVERED" in s:
        return "COVERED"
    if "REVIEW" in s:
        return "REVIEW"
    if "EXCLUDED" in s:
        return "EXCLUDED"
    return "OTHER"


def item_key(item: dict[str, Any]) -> str:
    num = str(item.get("num") or item.get("id") or "")
    desc = str(item.get("description") or "").strip()
    return f"{num}::{desc[:80]}"


# --- Provisional gold v1 (independent of pipeline.py) -------------------------

_GOLD_OUTER_HULL = ("船体外板", "船側外板", "船底外板")
_GOLD_DRYDOCK = ("入出渠", "滞渠")
_GOLD_MACHINERY = (
    "主機関",
    "ピストン",
    "吸排気弁",
    "燃料噴射弁",
    "発電機関",
    "カロリーファイヤー",
    "汚物処理",
    "減速機",
    "クラッチ",
    "シリンダー",
)
_GOLD_PROPULSION = ("プロペラ軸", "プロペラ、軸", "推進器")


def assign_provisional_gold_status(
    description: str,
    damaged_zones: list[str],
    *,
    category: str = "",
) -> str:
    """
    Founder provisional gold v1 for public docs.

    Intentionally implemented separately from appraisal.pipeline so agreement is a
    real regression signal (policy drift / parser regressions), not a tautology.
    """
    desc = description or ""
    zones = set(damaged_zones or [])
    has_hull = bool(zones & {"外板", "球状船首", "貨物タンク", "タンク", "甲板"})
    has_prop = bool(zones & {"推進器", "舵"})
    has_mach = bool(zones & {"機関室"})

    if any(k in desc for k in _GOLD_DRYDOCK):
        return "APPORTIONED"

    # Bow thruster primary work (before generic propeller rules).
    if "バウスラスター" in desc and "機関室" not in desc and "汚物処理" not in desc:
        if desc.strip().startswith("バウスラスター") or "バウスラスター プロペラ" in desc:
            return "REVIEW" if "球状船首" in zones else "EXCLUDED"

    if any(k in desc for k in _GOLD_MACHINERY) or (
        "機関" in (category or "") and any(k in desc for k in ("ポンプ", "弁", "開放"))
    ):
        return "COVERED" if has_mach else "EXCLUDED"

    if any(k in desc for k in _GOLD_PROPULSION):
        return "COVERED" if has_prop else "EXCLUDED"

    if any(k in desc for k in _GOLD_OUTER_HULL):
        return "COVERED" if has_hull else "EXCLUDED"

    return "EXCLUDED"


def attach_provisional_gold(
    items: list[dict[str, Any]],
    damaged_zones: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        row["gold_status"] = assign_provisional_gold_status(
            str(item.get("description") or ""),
            damaged_zones,
            category=str(item.get("category") or ""),
        )
        out.append(row)
    return out


def is_critical_false_accept(
    *,
    gold_bucket: str,
    pred_bucket: str,
    description: str,
    critical_substrings: list[str],
    damaged_zones: list[str],
) -> bool:
    """COVERED/REVIEW on critical machinery/shaft when gold says EXCLUDE and no machinery damage."""
    if gold_bucket != "EXCLUDED":
        return False
    if pred_bucket not in {"COVERED", "REVIEW"}:
        return False
    if "機関室" in (damaged_zones or []):
        return False
    desc = description or ""
    return any(s in desc for s in critical_substrings)


def score_predictions(
    items: list[dict[str, Any]],
    *,
    damaged_zones: list[str],
    critical_substrings: list[str],
) -> dict[str, Any]:
    """Compare pipeline statuses to provisional gold on the same item list."""
    labeled = attach_provisional_gold(items, damaged_zones)
    total = 0
    agree = 0
    false_accept = 0
    false_reject = 0
    critical_fa = 0
    disagreements: list[dict[str, Any]] = []

    for row in labeled:
        gold = normalize_status_bucket(row.get("gold_status"))
        pred = normalize_status_bucket(row.get("status"))
        if gold == "OTHER" or pred == "OTHER":
            continue
        total += 1
        if gold == pred:
            agree += 1
        else:
            disagreements.append(
                {
                    "key": item_key(row),
                    "gold": gold,
                    "pred": pred,
                    "description": str(row.get("description") or "")[:120],
                }
            )
            # FA: paid when gold excludes; FR: excluded when gold covers/apportions/review
            if gold == "EXCLUDED" and pred in {"COVERED", "REVIEW", "APPORTIONED"}:
                false_accept += 1
            if gold in {"COVERED", "APPORTIONED", "REVIEW"} and pred == "EXCLUDED":
                false_reject += 1
        if is_critical_false_accept(
            gold_bucket=gold,
            pred_bucket=pred,
            description=str(row.get("description") or ""),
            critical_substrings=critical_substrings,
            damaged_zones=damaged_zones,
        ):
            critical_fa += 1

    agreement = (agree / total) if total else 0.0
    return {
        "items_scored": total,
        "agreement": round(agreement, 4),
        "false_accept": false_accept,
        "false_reject": false_reject,
        "critical_false_accept": critical_fa,
        "disagreements_sample": disagreements[:25],
        "gold_rows": labeled,
    }


def evaluate_case_dicts(
    *,
    case: dict[str, Any],
    predicted_items: list[dict[str, Any]],
    damaged_zones: list[str],
    critical_substrings: list[str],
) -> dict[str, Any]:
    metrics = score_predictions(
        predicted_items,
        damaged_zones=damaged_zones,
        critical_substrings=critical_substrings,
    )
    return {
        "case_id": case.get("case_id"),
        "title": case.get("title"),
        "damaged_zones": damaged_zones,
        "items_predicted": len(predicted_items),
        **{k: v for k, v in metrics.items() if k != "gold_rows"},
        "gold_rows": metrics["gold_rows"],
    }


def run_case_from_pdfs(
    case: dict[str, Any],
    *,
    dataset_dir: Path,
    critical_substrings: list[str],
) -> dict[str, Any]:
    from marine_claims_ai.appraisal.pipeline import (
        evaluate_claims_dynamically,
        extract_casualty_profile,
        extract_repair_items,
    )

    casualty = dataset_dir / str(case["casualty_pdf"])
    spec = dataset_dir / str(case["spec_pdf"])
    if not casualty.is_file() or not spec.is_file():
        return {
            "case_id": case.get("case_id"),
            "title": case.get("title"),
            "skipped": True,
            "reason": "missing_pdf",
            "casualty_pdf": str(casualty),
            "spec_pdf": str(spec),
        }

    profile = extract_casualty_profile(str(casualty))
    items = extract_repair_items(str(spec))
    analyzed, summary = evaluate_claims_dynamically(items, profile)
    zones = list(profile.get("damaged_components") or [])
    result = evaluate_case_dicts(
        case=case,
        predicted_items=analyzed,
        damaged_zones=zones,
        critical_substrings=critical_substrings,
    )
    result["skipped"] = False
    result["summary"] = {
        "total_claimed_jpy": summary.get("total_claimed_jpy"),
        "total_approved_jpy": summary.get("total_approved_jpy"),
        "total_excluded_jpy": summary.get("total_excluded_jpy"),
        "leakage_prevention_rate_pct": summary.get("leakage_prevention_rate_pct"),
        "pricing_note": summary.get("pricing_note"),
    }
    result["casualty_profile"] = profile
    return result


def gate_report(case_results: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]:
    runnable = [c for c in case_results if not c.get("skipped")]
    critical_fa = sum(int(c.get("critical_false_accept") or 0) for c in runnable)
    agreements = [float(c["agreement"]) for c in runnable if c.get("items_scored")]
    mean_agreement = round(sum(agreements) / len(agreements), 4) if agreements else 0.0
    min_cases = int(gates.get("min_cases_with_pdfs") or 0)
    max_cfa = int(gates.get("max_critical_false_accepts") or 0)
    min_agr = float(gates.get("min_status_agreement") or 0.0)
    return {
        "cases_configured": len(case_results),
        "cases_run": len(runnable),
        "cases_skipped": len(case_results) - len(runnable),
        "mean_agreement": mean_agreement,
        "critical_false_accept_total": critical_fa,
        "pass_min_cases": len(runnable) >= min_cases,
        "pass_critical_fa": critical_fa <= max_cfa,
        "pass_agreement": mean_agreement >= min_agr if runnable else False,
        "overall_pass": (
            len(runnable) >= min_cases
            and critical_fa <= max_cfa
            and (mean_agreement >= min_agr if runnable else False)
        ),
        "gates": gates,
    }


def evaluate_all(
    *,
    config_path: str | Path | None = None,
    dataset_dir: str | Path | None = None,
) -> dict[str, Any]:
    cfg = load_eval_config(config_path)
    root = Path(dataset_dir) if dataset_dir else DEFAULT_DATASET_DIR
    critical = list(cfg.get("critical_exclude_substrings") or [])
    results = [
        run_case_from_pdfs(case, dataset_dir=root, critical_substrings=critical)
        for case in cfg["cases"]
    ]
    # Strip bulky gold_rows from top-level aggregate unless caller keeps them
    slim = []
    for r in results:
        row = dict(r)
        row.pop("gold_rows", None)
        slim.append(row)
    return {
        "config_version": cfg.get("version"),
        "dataset_dir": str(root),
        "cases": slim,
        "gate": gate_report(results, cfg.get("gates") or {}),
        "_full_cases": results,
    }
