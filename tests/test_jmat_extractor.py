"""Offline unit tests for JMAT telemetry extraction and COLREGS E2E gates."""

from __future__ import annotations

import json

from marine_claims_ai.benchmarks.colregs_e2e_eval import (
    evaluate_all,
    gate_report,
    is_critical_role_inversion,
    run_case,
)
from marine_claims_ai.ingest.jmat_extractor import (
    extract_headings,
    extract_relative_bearing,
    extract_ruling_article,
    extract_telemetry,
    normalize_maritime_text,
)
from marine_claims_ai.legal.colregs_engine import classify_encounter
from marine_claims_ai.paths import REPO_ROOT


def test_normalize_fullwidth_and_halfwidth_katakana():
    raw = "針路０４５度、速力約１２ﾉｯﾄ"
    t = normalize_maritime_text(raw)
    assert "045" in t or "45" in t
    assert "ノット" in t
    assert "ﾉ" not in t


def test_extract_numeric_headings_and_starboard_bow():
    text = (
        "本船Ａは針路０４５度、速力約１２ノットで進行中、"
        "右舷前約３０度に相手船Ｂを視認し、相手船Ｂは針路３００度であった。"
    )
    ext = extract_telemetry(text, "海上衝突予防法第１５条")
    assert ext.extraction_ok
    assert ext.heading_a_deg == 45.0
    assert ext.heading_b_deg == 300.0
    assert ext.relative_bearing_a_to_b_deg == 30.0
    assert ext.speed_a_kn == 12.0
    assert ext.ruling_article == 15


def test_compass_and_micro_north():
    text = "本船Ａは針路北東の微北で進行中、右舷前約３５度に相手船Ｂを視認した。相手船Ｂは針路北西であった。"
    ha, hb = extract_headings(normalize_maritime_text(text))
    assert ha == 40.0  # 北東(45) + 微北(-5)
    assert hb == 315.0  # 北西
    assert extract_relative_bearing(normalize_maritime_text(text)) == 35.0


def test_port_bow_and_phrase_bearings():
    assert extract_relative_bearing(normalize_maritime_text("左舷前約６０度に他船を認めた。")) == 300.0
    assert extract_relative_bearing("船首方向に相手船を視認した。") == 0.0
    assert extract_relative_bearing("ほとんど船首方向に認めた。") == 0.0
    assert extract_relative_bearing("右舷正横に他船あり。") == 90.0
    assert extract_relative_bearing("左舷正横後から接近。") == 225.0


def test_article_fullwidth():
    assert extract_ruling_article("海上衝突予防法第１５条に規定する") == 15
    assert extract_ruling_article("第14条の行会い") == 14
    assert extract_ruling_article("第１３条追越し") == 13


def test_geometry_roundtrip_crossing():
    facts = (
        "本船Ａは針路０００度、速力約１１ノットで進行中、"
        "右舷前約４５度に相手船Ｂを視認した。相手船Ｂは針路２７０度であった。"
    )
    ext = extract_telemetry(facts, "第１５条")
    geom = ext.to_encounter_geometry()
    assert geom is not None
    verdict = classify_encounter(geom)
    assert verdict.situation.value == "crossing"
    assert verdict.role_a is not None
    assert verdict.role_a.value == "give_way"


def test_shift_jis_legacy_mojibake_resilience_via_nfkc():
    """Half-width katakana + fullwidth digits survive NFKC normalization."""
    messy = "本船Ａは針路０９０度ﾃﾞ進行、右舷前約７０度に相手船Ｂ。相手船Ｂは針路０００度。"
    ext = extract_telemetry(messy, "第１５条")
    assert ext.extraction_ok
    assert ext.heading_a_deg == 90.0
    assert ext.heading_b_deg == 0.0
    assert "ノット" in normalize_maritime_text("速力１２ﾉｯﾄ")


def test_role_inversion_detector():
    assert is_critical_role_inversion(
        expected_situation="crossing",
        predicted_situation="crossing",
        expected_role_a="give_way",
        expected_role_b="stand_on",
        predicted_role_a="stand_on",
        predicted_role_b="give_way",
    )
    assert not is_critical_role_inversion(
        expected_situation="head_on",
        predicted_situation="head_on",
        expected_role_a="give_way",
        expected_role_b="give_way",
        predicted_role_a="give_way",
        predicted_role_b="give_way",
    )


def test_gate_fails_on_inversion():
    cases = [
        {
            "skipped": False,
            "extraction_ok": True,
            "situation_match": True,
            "critical_role_inversion": True,
        }
    ]
    gate = gate_report(
        cases,
        {
            "min_cases_run": 1,
            "min_extraction_rate": 0.9,
            "min_situation_agreement": 0.9,
            "max_critical_role_inversions": 0,
        },
    )
    assert gate["overall_pass"] is False
    assert gate["pass_role_inversions"] is False


def test_catalog_e2e_offline():
    report = evaluate_all()
    gate = report["gate"]
    assert gate["cases_run"] >= 10
    assert gate["extraction_rate"] >= 0.9
    assert gate["situation_agreement"] >= 0.9
    assert gate["critical_role_inversions"] == 0
    assert gate["overall_pass"] is True


def test_catalog_has_all_three_articles():
    cfg_path = REPO_ROOT / "config" / "jmat_collision_eval.json"
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    articles = {c["expected_article"] for c in data["cases"]}
    assert articles >= {13, 14, 15}
    situations = {c["expected_situation"] for c in data["cases"]}
    assert situations >= {"head_on", "crossing", "overtaking"}


def test_run_case_embedded():
    case = {
        "case_id": "unit_head_on",
        "facts_text": (
            "本船Ａは針路０００度で進行中、船首方向に相手船Ｂを視認した。"
            "相手船Ｂは針路１８０度であった。"
        ),
        "ruling_text": "第１４条",
        "expected_situation": "head_on",
        "expected_role_a": "give_way",
        "expected_role_b": "give_way",
        "expected_article": 14,
    }
    result = run_case(case, dataset_dir=REPO_ROOT / "_inputs" / "poc_datasets")
    assert result["extraction_ok"]
    assert result["situation_match"]
    assert result["critical_role_inversion"] is False
