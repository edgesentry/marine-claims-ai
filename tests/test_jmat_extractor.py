"""Offline unit tests for JMAT telemetry extraction (ingest).

COLREGS situation/role gates live in ``web/tests/gateAPriority2.test.ts``.
"""

from __future__ import annotations

from marine_claims_ai.ingest.jmat_extractor import (
    extract_headings,
    extract_relative_bearing,
    extract_ruling_article,
    extract_telemetry,
    normalize_maritime_text,
)


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


def test_geometry_roundtrip_fields():
    facts = (
        "本船Ａは針路０００度、速力約１１ノットで進行中、"
        "右舷前約４５度に相手船Ｂを視認した。相手船Ｂは針路２７０度であった。"
    )
    ext = extract_telemetry(facts, "第１５条")
    geom = ext.to_encounter_geometry()
    assert geom is not None
    assert geom.heading_a_deg == 0.0
    assert geom.heading_b_deg == 270.0
    assert geom.true_bearing_a_to_b_deg == 45.0
