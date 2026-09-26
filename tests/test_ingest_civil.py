from __future__ import annotations

from marine_claims_ai.ingest.civil import (
    catalog_stats,
    enrich_from_text,
    load_catalog,
)
from marine_claims_ai.ingest.public_datasets import CIVIL_COURT_SEEDS


def test_civil_catalog_meets_dod_thresholds():
    seeds = load_catalog()
    stats = catalog_stats(seeds)
    assert stats["non_synthetic_with_fault_ratio"] >= 30
    assert stats["non_synthetic_with_yen"] >= 15
    assert stats["synthetic"] <= 10
    assert all("case_id" in s and "fault_ratio" in s for s in seeds)
    assert any(s.get("source_type") == "court_pdf" for s in seeds)
    assert any(s.get("source_type") == "published_holding" for s in seeds)
    assert len(CIVIL_COURT_SEEDS) == len(seeds)


def test_enrich_from_pdf_text_extracts_ratio_and_amounts():
    seed = {
        "case_id": 99,
        "input_facts": "基礎事実",
        "fault_ratio": None,
        "awarded_damages_jpy": None,
        "claimed_repair_jpy": None,
        "disallowed_jpy": None,
    }
    text = (
        "責任割合は 70:30 である。"
        "請求額は 20,000,000円、認容額は 12,345,678円、否認は 3,000,000円 とした。"
    )
    out = enrich_from_text(seed, text)
    assert out["fault_ratio"] == "70:30"
    assert out["claimed_repair_jpy"] == 20000000
    assert out["awarded_damages_jpy"] == 12345678
    assert out["disallowed_jpy"] == 3000000
    assert "[pdf_excerpt]" in out["input_facts"]


def test_enrich_does_not_overwrite_seed_values():
    seed = {
        "case_id": 1,
        "input_facts": "seed",
        "fault_ratio": "65:35",
        "awarded_damages_jpy": 100,
        "claimed_repair_jpy": 200,
    }
    text = "過失割合 10:90。認容額は 9,999,999円。請求額は 8,888,888円。"
    out = enrich_from_text(seed, text)
    assert out["fault_ratio"] == "65:35"
    assert out["awarded_damages_jpy"] == 100
    assert out["claimed_repair_jpy"] == 200


def test_enrich_main_cause_fallback():
    seed = {"fault_ratio": None, "input_facts": "x"}
    out = enrich_from_text(seed, "本件はAが主因でありBが一因をなす。")
    assert out["fault_ratio"] == "70:30"
