"""End-to-end COLREGS eval: raw JMAT/JTSB narrative → telemetry → classify."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marine_claims_ai.ingest.jmat_extractor import extract_telemetry
from marine_claims_ai.ingest.pdf_text import pdf_to_text
from marine_claims_ai.legal.colregs_engine import classify_encounter
from marine_claims_ai.paths import DEFAULT_DATASET_DIR, REPO_ROOT

DEFAULT_EVAL_CONFIG = REPO_ROOT / "config" / "jmat_collision_eval.json"


def load_eval_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_EVAL_CONFIG
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("cases"), list):
        raise ValueError(f"Invalid JMAT collision eval config: {cfg_path}")
    return data


def resolve_case_texts(
    case: dict[str, Any],
    *,
    dataset_dir: Path,
) -> tuple[str, str, str | None]:
    """
    Load facts / ruling text for a case.

    Prefers optional ``source_file`` under dataset_dir when present; otherwise
    uses embedded ``facts_text`` / ``ruling_text`` (Zero-Dataset offline path).
    """
    facts = str(case.get("facts_text") or "")
    ruling = str(case.get("ruling_text") or "")
    source_note: str | None = "embedded"

    source_file = case.get("source_file")
    if source_file:
        path = dataset_dir / str(source_file)
        if path.is_file():
            if path.suffix.lower() == ".pdf":
                facts = pdf_to_text(str(path)) or facts
            else:
                facts = path.read_text(encoding="utf-8", errors="replace")
            source_note = str(path)
        else:
            # Embedded fallback still runnable; mark note only.
            source_note = f"missing_source:{path}"

    if not facts.strip() and not ruling.strip():
        return "", "", "empty"
    return facts, ruling, source_note


def is_critical_role_inversion(
    *,
    expected_situation: str,
    predicted_situation: str,
    expected_role_a: str | None,
    expected_role_b: str | None,
    predicted_role_a: str | None,
    predicted_role_b: str | None,
) -> bool:
    """
    True when situation matches but give-way / stand-on roles are swapped.

    Head-on (both give_way) cannot invert. Safe-passing / missing roles skip.
    """
    if predicted_situation != expected_situation:
        return False
    if expected_situation == "head_on":
        return False
    roles = {expected_role_a, expected_role_b}
    if roles != {"give_way", "stand_on"}:
        return False
    if predicted_role_a is None or predicted_role_b is None:
        return False
    return (
        predicted_role_a == expected_role_b
        and predicted_role_b == expected_role_a
        and predicted_role_a != expected_role_a
    )


def run_case(case: dict[str, Any], *, dataset_dir: Path) -> dict[str, Any]:
    case_id = case.get("case_id")
    facts, ruling, source_note = resolve_case_texts(case, dataset_dir=dataset_dir)
    if source_note == "empty":
        return {
            "case_id": case_id,
            "title": case.get("title"),
            "skipped": True,
            "reason": "empty_text",
        }

    extraction = extract_telemetry(facts, ruling)
    expected_situation = case.get("expected_situation")
    expected_role_a = case.get("expected_role_a")
    expected_role_b = case.get("expected_role_b")
    expected_article = case.get("expected_article")

    result: dict[str, Any] = {
        "case_id": case_id,
        "title": case.get("title"),
        "skipped": False,
        "source": source_note,
        "extraction_ok": extraction.extraction_ok,
        "extraction": extraction.to_dict(),
        "expected_situation": expected_situation,
        "expected_role_a": expected_role_a,
        "expected_role_b": expected_role_b,
        "expected_article": expected_article,
        "predicted_situation": None,
        "predicted_role_a": None,
        "predicted_role_b": None,
        "predicted_article": extraction.ruling_article,
        "situation_match": False,
        "article_match": False,
        "critical_role_inversion": False,
        "rule_citations": [],
    }

    geom = extraction.to_encounter_geometry()
    if geom is None:
        return result

    verdict = classify_encounter(geom)
    pred_sit = verdict.situation.value
    pred_ra = verdict.role_a.value if verdict.role_a else None
    pred_rb = verdict.role_b.value if verdict.role_b else None

    result["predicted_situation"] = pred_sit
    result["predicted_role_a"] = pred_ra
    result["predicted_role_b"] = pred_rb
    result["rule_citations"] = list(verdict.rule_citations)
    result["situation_match"] = pred_sit == expected_situation
    if expected_article is not None and extraction.ruling_article is not None:
        result["article_match"] = int(extraction.ruling_article) == int(expected_article)
    result["critical_role_inversion"] = is_critical_role_inversion(
        expected_situation=str(expected_situation or ""),
        predicted_situation=pred_sit,
        expected_role_a=expected_role_a,
        expected_role_b=expected_role_b,
        predicted_role_a=pred_ra,
        predicted_role_b=pred_rb,
    )
    return result


def gate_report(case_results: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]:
    runnable = [c for c in case_results if not c.get("skipped")]
    n = len(runnable)
    extracted = sum(1 for c in runnable if c.get("extraction_ok"))
    matched = sum(1 for c in runnable if c.get("situation_match"))
    inversions = sum(1 for c in runnable if c.get("critical_role_inversion"))

    extraction_rate = round(extracted / n, 4) if n else 0.0
    # E2E situation accuracy among extracted cases (fallback: runnable)
    scored = [c for c in runnable if c.get("extraction_ok")]
    sn = len(scored)
    situation_agreement = (
        round(sum(1 for c in scored if c.get("situation_match")) / sn, 4) if sn else 0.0
    )

    min_cases = int(gates.get("min_cases_run") or 0)
    min_ext = float(gates.get("min_extraction_rate") or 0.0)
    min_agr = float(gates.get("min_situation_agreement") or 0.0)
    max_inv = int(gates.get("max_critical_role_inversions") or 0)

    pass_cases = n >= min_cases
    pass_ext = extraction_rate >= min_ext if n else False
    pass_agr = situation_agreement >= min_agr if sn else False
    pass_inv = inversions <= max_inv

    return {
        "cases_configured": len(case_results),
        "cases_run": n,
        "cases_skipped": len(case_results) - n,
        "extraction_rate": extraction_rate,
        "situation_agreement": situation_agreement,
        "situation_matches": matched,
        "critical_role_inversions": inversions,
        "pass_min_cases": pass_cases,
        "pass_extraction_rate": pass_ext,
        "pass_situation_agreement": pass_agr,
        "pass_role_inversions": pass_inv,
        "overall_pass": pass_cases and pass_ext and pass_agr and pass_inv,
        "gates": gates,
    }


def evaluate_all(
    *,
    config_path: str | Path | None = None,
    dataset_dir: str | Path | None = None,
) -> dict[str, Any]:
    cfg = load_eval_config(config_path)
    root = Path(dataset_dir) if dataset_dir else DEFAULT_DATASET_DIR
    results = [run_case(case, dataset_dir=root) for case in cfg["cases"]]
    return {
        "config_version": cfg.get("version"),
        "dataset_dir": str(root),
        "cases": results,
        "gate": gate_report(results, cfg.get("gates") or {}),
    }
