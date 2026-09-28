"""Gate A Priority 2 integrated benchmark harness (A5–A7)."""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from marine_claims_ai.benchmarks.civil_extractor_eval import (
    evaluate_catalog_holdings,
    evaluate_offline_snippets,
)
from marine_claims_ai.benchmarks.colregs_e2e_eval import evaluate_all as evaluate_colregs_e2e
from marine_claims_ai.ingest.civil import (
    GATE_A_SCALE_TARGET_CIVIL_CASES,
    catalog_stats,
    load_catalog,
)
from marine_claims_ai.paths import DEFAULT_DATASET_DIR, DEFAULT_LOG_DIR, REPO_ROOT

DEFAULT_GATE_CONFIG = REPO_ROOT / "config" / "gate_a_priority2.json"

logger = logging.getLogger("marine_claims_ai.gate_a_priority2")


def load_gate_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_GATE_CONFIG
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


def setup_gate_logging(log_dir: Path | None = None) -> Path:
    root = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "colregs_civil_eval.log"
    if not any(
        isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(log_path)
        for h in logger.handlers
    ):
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
        logger.setLevel(logging.INFO)
    return log_path


def _resolve_repo_path(rel: str | Path | None, default: Path) -> Path:
    if not rel:
        return default
    p = Path(rel)
    if p.is_absolute():
        return p
    return REPO_ROOT / p


def evaluate_a5_a6_colregs(
    *,
    jmat_config: str | Path | None = None,
    dataset_dir: Path,
    gates: dict[str, Any],
) -> dict[str, Any]:
    """A5 situation accuracy + A6 critical role inversion (from COLREGS E2E)."""
    report = evaluate_colregs_e2e(config_path=jmat_config, dataset_dir=dataset_dir)
    e2e_gate = report.get("gate") or {}
    min_agr = float(gates.get("min_situation_agreement") or 0.9)
    max_inv = int(gates.get("max_critical_role_inversions") or 0)
    min_ext = float(gates.get("min_extraction_rate") or 0.9)

    agr = float(e2e_gate.get("situation_agreement") or 0.0)
    inv = int(e2e_gate.get("critical_role_inversions") or 0)
    ext = float(e2e_gate.get("extraction_rate") or 0.0)
    cases_run = int(e2e_gate.get("cases_run") or 0)

    situation_counts: Counter[str] = Counter()
    for case in report.get("cases") or []:
        if case.get("skipped"):
            continue
        exp = case.get("expected_situation")
        if exp:
            situation_counts[str(exp)] += 1

    a5_pass = cases_run == 0 or agr >= min_agr
    a6_pass = inv <= max_inv
    ext_pass = cases_run == 0 or ext >= min_ext

    return {
        "metric": "A5_A6",
        "cases_configured": e2e_gate.get("cases_configured"),
        "cases_run": cases_run,
        "extraction_rate": ext,
        "situation_agreement": agr,
        "critical_role_inversions": inv,
        "situation_counts": dict(situation_counts),
        "a5_pass": a5_pass,
        "a6_pass": a6_pass,
        "extraction_pass": ext_pass,
        "pass": a5_pass and a6_pass and ext_pass,
        "cases": report.get("cases"),
        "thresholds": {
            "min_situation_agreement": min_agr,
            "max_critical_role_inversions": max_inv,
            "min_extraction_rate": min_ext,
        },
    }


def evaluate_a7_civil(
    *,
    civil_catalog: str | Path | None = None,
    gates: dict[str, Any],
) -> dict[str, Any]:
    """A7 civil fault-ratio / yen extraction (offline snippets + catalog holdings)."""
    min_acc = float(gates.get("min_civil_extraction_accuracy") or 0.9)
    min_w10 = float(gates.get("min_fault_ratio_within_10pt") or 0.8)

    offline = evaluate_offline_snippets()
    seeds = load_catalog(civil_catalog) if civil_catalog else load_catalog()
    holdings = evaluate_catalog_holdings(seeds)

    # Prefer holdings when they score enough cases; else offline snippets.
    primary = holdings if int(holdings.get("scored") or 0) >= 5 else offline
    accuracy = float(primary.get("accuracy") or 0.0)
    w10 = float(primary.get("fault_ratio_within_10pt_rate") or 0.0)
    scored = int(primary.get("scored") or primary.get("total") or 0)

    accuracy_pass = scored == 0 or accuracy >= min_acc
    w10_pass = (
        int(primary.get("fault_ratio_within_10pt_scored") or 0) == 0 or w10 >= min_w10
    )

    stats = catalog_stats(seeds)

    return {
        "metric": "A7",
        "primary_mode": primary.get("mode"),
        "scored": scored,
        "accuracy": accuracy,
        "fault_ratio_within_10pt_rate": w10,
        "catalog_total": stats["total"],
        "catalog_with_fault_ratio": stats["non_synthetic_with_fault_ratio"],
        "offline": {
            "accuracy": offline.get("accuracy"),
            "total": offline.get("total"),
            "fault_ratio_within_10pt_rate": offline.get("fault_ratio_within_10pt_rate"),
        },
        "holdings": {
            "accuracy": holdings.get("accuracy"),
            "scored": holdings.get("scored"),
            "fault_ratio_within_10pt_rate": holdings.get("fault_ratio_within_10pt_rate"),
        },
        "accuracy_pass": accuracy_pass,
        "within_10pt_pass": w10_pass,
        "pass": accuracy_pass and w10_pass,
        "thresholds": {
            "min_civil_extraction_accuracy": min_acc,
            "min_fault_ratio_within_10pt": min_w10,
        },
    }


def scale_status(
    *,
    jmat_cases: int,
    situation_counts: dict[str, int],
    civil_cases: int,
    targets: dict[str, Any],
) -> dict[str, Any]:
    min_jmat = int(targets.get("min_jmat_cases") or 100)
    min_ot = int(targets.get("min_overtaking") or 25)
    min_ho = int(targets.get("min_head_on") or 25)
    min_cr = int(targets.get("min_crossing") or 50)
    min_civil = int(
        targets.get("min_civil_cases") or GATE_A_SCALE_TARGET_CIVIL_CASES
    )
    ot = int(situation_counts.get("overtaking") or 0)
    ho = int(situation_counts.get("head_on") or 0)
    cr = int(situation_counts.get("crossing") or 0)
    incomplete = (
        jmat_cases < min_jmat
        or ot < min_ot
        or ho < min_ho
        or cr < min_cr
        or civil_cases < min_civil
    )
    return {
        "scale_incomplete": incomplete,
        "jmat_cases": jmat_cases,
        "overtaking": ot,
        "head_on": ho,
        "crossing": cr,
        "civil_cases": civil_cases,
        "targets": {
            "min_jmat_cases": min_jmat,
            "min_overtaking": min_ot,
            "min_head_on": min_ho,
            "min_crossing": min_cr,
            "min_civil_cases": min_civil,
        },
    }


def run_gate_a_priority2(
    *,
    config_path: str | Path | None = None,
    dataset_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Run Gate A Priority 2 metrics A5–A7.

    A6 (critical role inversions = 0) is zero-tolerance on whatever corpus is
    present. Scale shortfalls set ``scale_incomplete``. When scale is incomplete,
    A5/A7 accuracy gates still apply on the available corpus; overall_pass
    requires A6 plus A5/A7 accuracy on scored cases.
    """
    setup_gate_logging()
    gate_cfg = load_gate_config(config_path)
    gates = gate_cfg.get("gates") or {}
    root = Path(dataset_dir) if dataset_dir else DEFAULT_DATASET_DIR

    jmat_cfg = _resolve_repo_path(
        gate_cfg.get("jmat_collision_config"),
        REPO_ROOT / "config" / "jmat_collision_eval.json",
    )
    civil_cfg = _resolve_repo_path(
        gate_cfg.get("civil_catalog"),
        REPO_ROOT / "config" / "civil_precedent_catalog.json",
    )

    a5a6 = evaluate_a5_a6_colregs(
        jmat_config=jmat_cfg,
        dataset_dir=root,
        gates=gates,
    )
    a7 = evaluate_a7_civil(civil_catalog=civil_cfg, gates=gates)

    zero_tol_pass = bool(a5a6.get("a6_pass"))
    accuracy_pass = bool(a5a6.get("a5_pass")) and bool(a5a6.get("extraction_pass")) and bool(
        a7.get("pass")
    )

    scale = scale_status(
        jmat_cases=int(a5a6.get("cases_run") or 0),
        situation_counts=dict(a5a6.get("situation_counts") or {}),
        civil_cases=int(a7.get("catalog_with_fault_ratio") or 0),
        targets=gate_cfg.get("scale_targets") or {},
    )

    # Zero-tolerance (A6) always required. A5/A7 accuracy required on present corpus.
    overall = zero_tol_pass and accuracy_pass

    report = {
        "config_version": gate_cfg.get("version"),
        "dataset_dir": str(root),
        "metrics": {
            "A5_A6": {k: v for k, v in a5a6.items() if k != "cases"},
            "A7": a7,
        },
        "scale": scale,
        "gate": {
            "zero_tolerance_pass": zero_tol_pass,
            "accuracy_pass": accuracy_pass,
            "overall_pass": overall,
            "situation_agreement": a5a6.get("situation_agreement"),
            "critical_role_inversions": a5a6.get("critical_role_inversions"),
            "civil_accuracy": a7.get("accuracy"),
            "fault_ratio_within_10pt_rate": a7.get("fault_ratio_within_10pt_rate"),
            "thresholds": gates,
        },
        # Keep case detail available for debugging / json-out slim path
        "_cases": a5a6.get("cases"),
    }
    logger.info(
        "Gate A Priority2 overall_pass=%s zero_tol=%s scale_incomplete=%s "
        "agr=%.4f inv=%s civil_acc=%.4f w10=%.4f",
        overall,
        zero_tol_pass,
        scale["scale_incomplete"],
        float(a5a6.get("situation_agreement") or 0.0),
        a5a6.get("critical_role_inversions"),
        float(a7.get("accuracy") or 0.0),
        float(a7.get("fault_ratio_within_10pt_rate") or 0.0),
    )
    return report
