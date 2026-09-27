"""Unit tests for COLREGS Rules 13–15 encounter geometry engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marine_claims_ai.legal.colregs_engine import (
    HEAD_ON_COURSE_TOLERANCE_DEG,
    OVERTAKING_ABAFT_BEAM_DEG,
    OVERTAKING_RELATIVE_BEARING_MIN_DEG,
    EncounterGeometry,
    EncounterSituation,
    VesselRole,
    classify_encounter,
    course_difference_deg,
    cpa_tcpa_nm_min,
    is_crossing,
    is_head_on,
    is_overtaking,
    relative_bearing_deg,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "collision_geometries.json"


def _load_cases() -> list[dict]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return list(data["cases"])


CASES = _load_cases()


def test_fixture_has_at_least_twenty_cases():
    assert len(CASES) >= 20


def test_statutory_overtaking_threshold_constants():
    """Art. 13 / Rule 13: 22.5° abaft beam → 112.5° relative from ahead."""
    assert OVERTAKING_ABAFT_BEAM_DEG == 22.5
    assert OVERTAKING_RELATIVE_BEARING_MIN_DEG == 112.5


@pytest.mark.parametrize(
    ("true_bearing", "heading", "expected"),
    [
        (0.0, 0.0, 0.0),
        (90.0, 0.0, 90.0),
        (0.0, 90.0, 270.0),
        (350.0, 10.0, 340.0),
    ],
)
def test_relative_bearing_formula(true_bearing: float, heading: float, expected: float):
    assert relative_bearing_deg(true_bearing, heading) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("ha", "hb", "expected"),
    [
        (0.0, 180.0, 180.0),
        (90.0, 275.0, 185.0),
        (10.0, 350.0, 340.0),
    ],
)
def test_course_difference_formula(ha: float, hb: float, expected: float):
    assert course_difference_deg(ha, hb) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("aspect", "expected"),
    [
        (112.5, False),  # not "more than" 22.5° abaft
        (112.5001, True),
        (180.0, True),
        (247.4999, True),
        (247.5, False),
        (90.0, False),
        (0.0, False),
    ],
)
def test_is_overtaking_sector(aspect: float, expected: bool):
    assert is_overtaking(aspect) is expected


def test_is_head_on_uses_engineering_tolerance():
    assert is_head_on(180.0, 0.0) is True
    assert is_head_on(180.0 + HEAD_ON_COURSE_TOLERANCE_DEG, 0.0) is True
    assert is_head_on(180.0 + HEAD_ON_COURSE_TOLERANCE_DEG + 0.1, 0.0) is False
    assert is_head_on(180.0, HEAD_ON_COURSE_TOLERANCE_DEG + 0.1) is False


def test_is_crossing_excludes_parallel_and_overtaking():
    assert is_crossing(90.0, 45.0) is True
    assert is_crossing(0.0, 45.0) is False
    assert is_crossing(180.0, 45.0) is False
    assert is_crossing(90.0, 180.0) is False


def test_classify_deterministic():
    g = EncounterGeometry(heading_a_deg=0.0, heading_b_deg=270.0, true_bearing_a_to_b_deg=45.0)
    a = classify_encounter(g)
    b = classify_encounter(g)
    assert a == b
    assert a.situation == EncounterSituation.CROSSING
    assert a.role_a == VesselRole.GIVE_WAY
    assert a.role_b == VesselRole.STAND_ON


def test_cpa_tcpa_head_on_closing():
    cpa, tcpa = cpa_tcpa_nm_min(
        range_nm=2.0,
        relative_bearing_a_to_b_deg=0.0,
        heading_a_deg=0.0,
        heading_b_deg=180.0,
        speed_a_kn=10.0,
        speed_b_kn=10.0,
    )
    assert cpa is not None and tcpa is not None
    assert cpa == pytest.approx(0.0, abs=1e-6)
    assert tcpa == pytest.approx(6.0, abs=1e-3)  # 2 nmi / 20 kn → 0.1 h = 6 min


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_fixture_geometries(case: dict):
    verdict = classify_encounter(
        EncounterGeometry(
            heading_a_deg=case["heading_a_deg"],
            heading_b_deg=case["heading_b_deg"],
            true_bearing_a_to_b_deg=case["true_bearing_a_to_b_deg"],
        )
    )
    assert verdict.situation.value == case["expected_situation"]
    assert (verdict.role_a.value if verdict.role_a else None) == case["expected_role_a"]
    assert (verdict.role_b.value if verdict.role_b else None) == case["expected_role_b"]
    assert verdict.mutual_starboard_alteration is case["expected_mutual_starboard"]


def test_fixture_covers_all_quadrants():
    quadrants = {c["quadrant"] for c in CASES}
    required = {
        "head_on",
        "crossing_starboard",
        "crossing_port",
        "overtaking_starboard",
        "overtaking_port",
        "overtaking_astern",
        "safe_passing",
    }
    assert required <= quadrants
