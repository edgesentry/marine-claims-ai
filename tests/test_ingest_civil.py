from __future__ import annotations

from marine_claims_ai.ingest.public_datasets import (
    CIVIL_COURT_SEEDS,
    _enrich_from_pdf_text,
)


def test_civil_court_seeds_meet_minimum_count():
    assert len(CIVIL_COURT_SEEDS) >= 10
    assert all("case_id" in s and "fault_ratio" in s for s in CIVIL_COURT_SEEDS)


def test_enrich_from_pdf_text_extracts_ratio_and_amounts():
    seed = {
        "case_id": 99,
        "input_facts": "基礎事実",
        "fault_ratio": None,
        "awarded_damages_jpy": None,
    }
    text = "責任割合は 70:30 である。認容額は 12,345,678円 とした。"
    out = _enrich_from_pdf_text(seed, text)
    assert out["fault_ratio"] == "70:30"
    assert out["awarded_damages_jpy"] == 12345678
    assert "[pdf_excerpt]" in out["input_facts"]
