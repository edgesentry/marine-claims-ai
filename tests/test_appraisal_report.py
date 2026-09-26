from __future__ import annotations

from marine_claims_ai.appraisal.report import render_preliminary_survey_report


def test_render_preliminary_survey_report_sections():
    summary = {
        "casualty_profile": {
            "vessel_name": "M/V Test",
            "incident_type": "Collision",
            "incident_date": "2024-01-01",
            "incident_location": "Tokyo Bay",
            "damaged_components": ["球状船首", "外板"],
            "source_pdf": "fixture.pdf",
        },
        "total_claimed_jpy": 1_000_000,
        "total_approved_jpy": 250_000,
        "total_excluded_jpy": 750_000,
        "leakage_prevention_rate_pct": 75.0,
        "pricing_note": "unit-price heuristics note",
    }
    items = [
        {
            "id": 1,
            "status": "COVERED",
            "approved_amount": 100_000,
            "description": "船体外板高圧清水洗浄",
            "reason": "hull",
        },
        {
            "id": 2,
            "status": "APPORTIONED (50%)",
            "approved_amount": 150_000,
            "description": "船体入出渠及び滞渠",
            "reason": "50%",
        },
        {
            "id": 3,
            "status": "EXCLUDED (便乗修理)",
            "approved_amount": 0,
            "description": "カロリーファイヤー開放",
            "reason": "watertight barrier",
        },
    ]
    md = render_preliminary_survey_report(summary, items, report_date="2026-09-26")
    assert "Preliminary Survey & Claims Adjustment Report" in md
    assert "M/V Test" in md
    assert "unit-price heuristics note" in md
    assert "船体外板高圧清水洗浄" in md
    assert "カロリーファイヤー開放" in md
    assert "watertight barrier" in md
    assert "750,000" in md
