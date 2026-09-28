"""Unit tests for Gate A Priority 1 harness (no giant PDFs required)."""

from __future__ import annotations

from marine_claims_ai.benchmarks.gate_a_priority1 import (
    evaluate_a3_rule_d5_pipeline,
    evaluate_a3_rule_d5_synthetic,
    load_gate_config,
    run_gate_a_priority1,
    scale_status,
)


def test_load_gate_config_defaults():
    cfg = load_gate_config()
    assert cfg["gates"]["max_critical_false_accepts"] == 0
    assert cfg["gates"]["max_rule_d5_reconciliation_error_jpy"] == 0
    assert cfg["gates"]["min_status_agreement"] == 0.85


def test_a3_synthetic_and_pipeline_zero_error():
    syn = evaluate_a3_rule_d5_synthetic()
    pipe = evaluate_a3_rule_d5_pipeline()
    assert syn["pass"] and syn["reconciliation_error_jpy"] == 0
    assert pipe["pass"] and pipe["reconciliation_error_jpy"] == 0


def test_scale_incomplete_when_below_targets():
    s = scale_status(
        grounded_items=100,
        cases_run=3,
        bid_count=1,
        targets={"min_vessels": 10, "min_line_items": 2500, "min_bid_notices": 20},
    )
    assert s["scale_incomplete"] is True


def test_run_gate_a_skip_pdf_span_passes_zero_tolerance(tmp_path):
    """CI-friendly path: synthetic A3 + skip PDF span; missing PDFs skip A1 cases."""
    report = run_gate_a_priority1(
        dataset_dir=tmp_path,
        include_pdf_span=False,
        bid_count=0,
    )
    assert report["gate"]["zero_tolerance_pass"] is True
    assert report["gate"]["rule_d5_reconciliation_error_jpy"] == 0
    assert report["gate"]["critical_false_accept_total"] == 0
    assert report["scale"]["scale_incomplete"] is True
