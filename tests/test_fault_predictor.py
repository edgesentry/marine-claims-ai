"""Unit tests for end-to-end collision fault-ratio prediction (Issue #44)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marine_claims_ai.analytics import FaultPrediction, predict_fault_ratio
from marine_claims_ai.analytics.fault_predictor import (
    apply_modifier_deltas,
    baseline_ratio_for,
    extract_modifiers,
    format_fault_ratio,
    infer_situation_from_text,
    parse_fault_ratio,
)
from marine_claims_ai.benchmarks.fault_predictor_eval import evaluate_catalog_mae
from marine_claims_ai.legal.colregs_engine import EncounterGeometry, EncounterSituation

REPO_ROOT = Path(__file__).resolve().parents[1]
GEOM_PATH = REPO_ROOT / "config" / "collision_geometries.json"


def _crossing_geometry() -> EncounterGeometry:
    data = json.loads(GEOM_PATH.read_text(encoding="utf-8"))
    case = next(c for c in data["cases"] if c.get("expected_situation") == "crossing")
    return EncounterGeometry(
        heading_a_deg=float(case["heading_a_deg"]),
        heading_b_deg=float(case["heading_b_deg"]),
        true_bearing_a_to_b_deg=float(case["true_bearing_a_to_b_deg"]),
    )


def test_parse_and_format_fault_ratio():
    assert parse_fault_ratio("70:30") == (70, 30)
    assert format_fault_ratio(65) == "65:35"
    with pytest.raises(ValueError):
        parse_fault_ratio("70-30")
    with pytest.raises(ValueError):
        parse_fault_ratio("60:50")


def test_infer_crossing_from_narrative():
    sit = infer_situation_from_text("貨物船同士が横切る態勢で接近し衝突した。")
    assert sit == EncounterSituation.CROSSING
    assert baseline_ratio_for(sit) == "80:20"


def test_fog_radar_modifiers_emit_citations():
    narrative = (
        "霧中において双方とも霧中信号を吹鳴せず、レーダー映像を捕捉しながら"
        "安全な速力への減速を怠った。"
    )
    hits = extract_modifiers(narrative)
    ids = {h.modifier_id for h in hits}
    assert "fog" in ids
    assert "radar" in ids or "sound_signals" in ids or "speed" in ids
    assert all(h.citation for h in hits)
    adjusted = apply_modifier_deltas(80, hits)
    assert 50 <= adjusted <= 95


def test_predict_with_crossing_geometry_is_audit_defensible():
    geom = _crossing_geometry()
    narrative = (
        "貨物船同士が横切る態勢で接近した際、避航船側が見張り・避航を怠り衝突した。"
    )
    pred = predict_fault_ratio(narrative, geom)
    assert isinstance(pred, FaultPrediction)
    assert pred.situation == "crossing"
    assert pred.baseline_ratio == "80:20"
    assert pred.fault_ratio.count(":") == 1
    primary, secondary = parse_fault_ratio(pred.fault_ratio)
    assert primary + secondary == 100
    assert pred.role_a is not None
    assert pred.rationale
    # Lookout modifier should surface as an itemized citation.
    assert any(m.modifier_id == "lookout" for m in pred.modifiers) or pred.rule_citations


def test_predict_accepts_geometry_dict():
    geom = _crossing_geometry()
    pred = predict_fault_ratio(
        "横切る態勢で衝突",
        geom.model_dump(),
    )
    assert pred.situation == "crossing"


def test_catalog_leave_one_out_mae_within_ten_pp():
    report = evaluate_catalog_mae(leave_one_out=True)
    assert report["n"] >= 36
    assert report["mae_pp"] <= 10.0, (
        f"MAE={report['mae_pp']:.2f}pp exceeds 10pp gate; "
        f"worst={[r for r in sorted(report['rows'], key=lambda x: -x['abs_error_pp'])[:3]]}"
    )
