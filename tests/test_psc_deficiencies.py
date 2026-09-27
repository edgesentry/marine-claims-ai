"""Unit tests for Paris/Tokyo MOU PSC deficiency parsing and seaworthiness scoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marine_claims_ai.adapters import JapanJurisdictionAdapter, PolicyForm, PSCDeficiency
from marine_claims_ai.ingest.psc_deficiencies import (
    NormalizedDeficiency,
    load_psc_fixtures,
    parse_inspection_record,
    score_fixture_case,
    score_seaworthiness,
    to_adapter_deficiencies,
)
from marine_claims_ai.ontology.psc import (
    ACTION_CODE_SEVERITY,
    ACTION_DETENTION,
    ACTION_RECTIFY,
    DEFICIENCY_CATEGORY_MAP,
    action_severity,
    category_prefix,
    convention_for_code,
    critical_system_id,
    is_detention_action,
    lookup_category,
    normalize_action_code,
    normalize_deficiency_code,
)

# Tracked under config/ (Zero-Dataset JSON allowlist); not tests/fixtures/.
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "config" / "psc_inspection_fixtures.json"


@pytest.fixture(scope="module")
def fixtures() -> dict:
    return load_psc_fixtures(FIXTURE_PATH)


def _case_by_id(fixtures: dict, case_id: str) -> dict:
    for case in fixtures["cases"]:
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def test_fixture_file_is_valid_json():
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert len(raw["cases"]) >= 5


def test_071_is_fire_safety_not_navigation():
    entry = DEFICIENCY_CATEGORY_MAP["071"]
    assert entry["label"] == "Fire safety"
    assert entry["convention"] == "SOLAS"
    assert entry["chapter"] == "II-2"
    assert "Navigation" not in entry["label"]
    assert convention_for_code("07106") == "SOLAS II-2"
    assert convention_for_code("10104") == "SOLAS V"
    assert DEFICIENCY_CATEGORY_MAP["101"]["label"] == "Safety of Navigation"


def test_action_code_severity_weights():
    assert ACTION_CODE_SEVERITY[ACTION_DETENTION] == 1.0
    assert ACTION_CODE_SEVERITY[ACTION_RECTIFY] == 0.5
    assert ACTION_CODE_SEVERITY["15"] == 0.4
    assert ACTION_CODE_SEVERITY["16"] == 0.25
    assert action_severity("Code 30") == 1.0
    assert action_severity(None) == 0.1
    assert is_detention_action("30") is True
    assert is_detention_action("17") is False


def test_normalize_codes_accept_aliases():
    assert normalize_deficiency_code("Code 04102") == "04102"
    assert normalize_deficiency_code("04102") == "04102"
    assert category_prefix("04102") == "041"
    assert normalize_action_code("Code 17") == "17"
    assert lookup_category("15150")["convention"] == "ISM"


def test_normalize_prefers_five_digit_over_item_index():
    assert normalize_deficiency_code("Item 12: 04102") == "04102"
    assert normalize_deficiency_code("No. 10 - 07106") == "07106"
    assert normalize_deficiency_code("07.106") == "07106"
    assert normalize_deficiency_code("071-06") == "07106"


def test_ism_keyword_requires_word_boundary():
    assert critical_system_id(None, "ISM non-conformity on SMS") == "ism"
    assert critical_system_id(None, "valve mechanism defective") is None
    assert critical_system_id(None, "governor mechanism") is None
    assert critical_system_id(None, "transmission") is None
    assert critical_system_id(None, "steering gear jammed") == "steering_gear"


def test_parse_paris_and_tokyo_field_aliases(fixtures: dict):
    paris = _case_by_id(fixtures, "paris_detention_emergency_fire_pump")
    tokyo = _case_by_id(fixtures, "tokyo_navigation_gyro")
    paris_rows = parse_inspection_record(paris["inspection"])
    tokyo_rows = parse_inspection_record(tokyo["inspection"])
    assert len(paris_rows) == 2
    assert paris_rows[0].code == "04102"
    assert paris_rows[0].action_code == "30"
    assert paris_rows[0].critical_system == "emergency_fire_pump"
    assert len(tokyo_rows) == 1
    assert tokyo_rows[0].code == "10104"
    assert tokyo_rows[0].prefix == "101"
    assert tokyo_rows[0].category_label == "Safety of Navigation"


def test_fire_safety_fixture_not_classified_as_navigation(fixtures: dict):
    case = _case_by_id(fixtures, "tokyo_fire_safety_not_navigation")
    report = score_fixture_case(case)
    assert report.detention_present is False
    assert len(report.deficiencies) == 1
    d = report.deficiencies[0]
    assert d.prefix == "071"
    assert d.category_label == "Fire safety"
    assert d.convention == "SOLAS II-2"
    assert "Navigation" not in (d.category_label or "")


def test_detention_score_and_adapter_bridge(fixtures: dict):
    case = _case_by_id(fixtures, "paris_detention_emergency_fire_pump")
    report = score_fixture_case(case)
    assert report.detention_present is True
    assert report.defect_score >= 1.0
    assert any(d.critical_system == "emergency_fire_pump" for d in report.deficiencies)
    adapter_rows = to_adapter_deficiencies(report.deficiencies)
    assert all(isinstance(r, PSCDeficiency) for r in adapter_rows)
    assert any(r.severity == "detention" for r in adapter_rows)

    warranty = JapanJurisdictionAdapter().evaluate_seaworthiness_warranty(
        adapter_rows,
        PolicyForm.NK_HULL,
    )
    assert warranty.breached is True


def test_repeat_ism_critical_flag(fixtures: dict):
    case = _case_by_id(fixtures, "repeat_ism_major")
    report = score_fixture_case(case)
    assert report.detention_present is True
    assert report.repeat_critical_flags == ["ism"]
    assert report.defect_score >= 1.5
    assert report.deficiencies[0].is_repeat_critical is True


def test_cic_weights_boost_score(fixtures: dict):
    case = _case_by_id(fixtures, "cic_weight_fire_campaign")
    boosted = score_fixture_case(case)
    baseline = score_fixture_case({**case, "cic_weights": {}})
    assert boosted.defect_score == pytest.approx(1.0)
    assert baseline.defect_score == pytest.approx(0.5)
    assert boosted.defect_score > baseline.defect_score


def test_steering_alias_parsing(fixtures: dict):
    case = _case_by_id(fixtures, "paris_steering_code17")
    rows = parse_inspection_record(case["inspection"])
    assert len(rows) == 1
    assert rows[0].code == "02105"
    assert rows[0].action_code == "17"
    assert rows[0].critical_system == "steering_gear"


def test_propulsion_and_marpol_citations(fixtures: dict):
    case = _case_by_id(fixtures, "propulsion_auxiliary")
    report = score_fixture_case(case)
    conventions = {d.convention for d in report.deficiencies}
    assert "SOLAS II-1" in conventions
    assert "MARPOL Annex I" in conventions
    assert report.detention_present is False


def test_score_seaworthiness_empty():
    report = score_seaworthiness([])
    assert report.defect_score == 0.0
    assert report.detention_present is False
    assert report.deficiencies == []


def test_repeat_lookback_in_window_boosts():
    """Prior critical hit within 24 months applies repeat_mult = 1.5."""
    current = [
        NormalizedDeficiency(
            code="15109",
            action_code="30",
            description="ISM repeat",
            inspection_date="2024-06-15",
            critical_system="ism",
            severity_weight=1.0,
            category_weight=1.0,
        )
    ]
    prior = [
        NormalizedDeficiency(
            code="15150",
            action_code="17",
            description="ISM prior",
            inspection_date="2023-06-01",  # ~12.5 months before
            critical_system="ism",
            severity_weight=0.5,
            category_weight=1.0,
        )
    ]
    report = score_seaworthiness(current, prior=prior)
    assert report.deficiencies[0].is_repeat_critical is True
    assert report.repeat_critical_flags == ["ism"]
    assert report.defect_score == pytest.approx(1.5)


def test_repeat_lookback_out_of_window_no_boost():
    """Stale prior outside the default 24-month window must not inflate the score."""
    current = [
        NormalizedDeficiency(
            code="15109",
            action_code="30",
            description="ISM current",
            inspection_date="2024-06-15",
            critical_system="ism",
            severity_weight=1.0,
            category_weight=1.0,
        )
    ]
    prior = [
        NormalizedDeficiency(
            code="15150",
            action_code="17",
            description="ISM stale",
            inspection_date="2021-06-01",  # ~36 months before
            critical_system="ism",
            severity_weight=0.5,
            category_weight=1.0,
        )
    ]
    report = score_seaworthiness(current, prior=prior)
    assert report.deficiencies[0].is_repeat_critical is False
    assert report.repeat_critical_flags == []
    assert report.defect_score == pytest.approx(1.0)


def test_repeat_lookback_missing_prior_date_still_counts():
    """Prior without a date still counts when the current inspection is dated."""
    current = [
        NormalizedDeficiency(
            code="04102",
            action_code="17",
            description="Emergency fire pump",
            inspection_date="2024-06-15",
            critical_system="emergency_fire_pump",
            severity_weight=0.5,
            category_weight=1.0,
        )
    ]
    prior = [
        NormalizedDeficiency(
            code="04102",
            action_code="17",
            description="Emergency fire pump prior",
            inspection_date=None,
            critical_system="emergency_fire_pump",
            severity_weight=0.5,
            category_weight=1.0,
        )
    ]
    report = score_seaworthiness(current, prior=prior)
    assert report.deficiencies[0].is_repeat_critical is True
    assert report.defect_score == pytest.approx(0.75)  # 1.0 * 0.5 * 1.5


def test_normalized_deficiency_is_frozen_extra_forbid():
    d = NormalizedDeficiency(code="10104", action_code="16", description="Gyro")
    with pytest.raises(Exception):
        NormalizedDeficiency(code="10104", unexpected="x")  # type: ignore[call-arg]
    assert d.code == "10104"
