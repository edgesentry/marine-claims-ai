"""Unit tests for Gate A Priority 2 harness (offline / Zero-Dataset)."""

from __future__ import annotations

import json
from pathlib import Path

from marine_claims_ai.benchmarks.gate_a_priority2 import (
    evaluate_a7_civil,
    load_gate_config,
    run_gate_a_priority2,
    scale_status,
)


def test_load_gate_config_defaults():
    cfg = load_gate_config()
    assert cfg["gates"]["max_critical_role_inversions"] == 0
    assert cfg["gates"]["min_situation_agreement"] == 0.9
    assert cfg["gates"]["min_civil_extraction_accuracy"] == 0.9
    assert cfg["gates"]["min_fault_ratio_within_10pt"] == 0.8
    assert cfg["scale_targets"]["min_jmat_cases"] == 100
    assert cfg["scale_targets"]["min_civil_cases"] == 60


def test_scale_incomplete_when_below_targets():
    s = scale_status(
        jmat_cases=12,
        situation_counts={"crossing": 6, "head_on": 3, "overtaking": 3},
        civil_cases=36,
        targets={
            "min_jmat_cases": 100,
            "min_overtaking": 25,
            "min_head_on": 25,
            "min_crossing": 50,
            "min_civil_cases": 60,
        },
    )
    assert s["scale_incomplete"] is True


def test_scale_complete_at_targets():
    s = scale_status(
        jmat_cases=100,
        situation_counts={"crossing": 50, "head_on": 25, "overtaking": 25},
        civil_cases=60,
        targets={
            "min_jmat_cases": 100,
            "min_overtaking": 25,
            "min_head_on": 25,
            "min_crossing": 50,
            "min_civil_cases": 60,
        },
    )
    assert s["scale_incomplete"] is False


def test_a7_offline_meets_thresholds():
    a7 = evaluate_a7_civil(gates={
        "min_civil_extraction_accuracy": 0.9,
        "min_fault_ratio_within_10pt": 0.8,
    })
    assert a7["pass"] is True
    assert a7["accuracy"] >= 0.9
    assert a7["fault_ratio_within_10pt_rate"] >= 0.8


def test_run_gate_a_priority2_zero_tol_and_accuracy(tmp_path: Path):
    """Default tracked gold must pass A6=0 and A5/A7 accuracy (scale may be incomplete)."""
    report = run_gate_a_priority2(dataset_dir=tmp_path)
    assert report["gate"]["zero_tolerance_pass"] is True
    assert report["gate"]["critical_role_inversions"] == 0
    assert report["gate"]["accuracy_pass"] is True
    assert report["gate"]["overall_pass"] is True
    assert report["metrics"]["A5_A6"]["situation_agreement"] >= 0.9
    assert report["metrics"]["A7"]["pass"] is True

    # Write config override with tiny scale targets to prove scale_complete path
    cfg = load_gate_config()
    cfg = dict(cfg)
    cfg["scale_targets"] = {
        "min_jmat_cases": 1,
        "min_overtaking": 0,
        "min_head_on": 0,
        "min_crossing": 0,
        "min_civil_cases": 1,
    }
    gate_path = tmp_path / "gate.json"
    gate_path.write_text(json.dumps(cfg), encoding="utf-8")
    report2 = run_gate_a_priority2(config_path=gate_path, dataset_dir=tmp_path)
    assert report2["scale"]["scale_incomplete"] is False
    assert report2["gate"]["overall_pass"] is True
