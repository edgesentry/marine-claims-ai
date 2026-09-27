"""Pipeline integration tests for AAA Rule D5 drydock dues (Gate A / A3)."""

from __future__ import annotations

from marine_claims_ai.analytics.rule_d_solver import ApportionmentRule, DockingContext
from marine_claims_ai.appraisal.negative_patterns import ACTION_APPROVED
from marine_claims_ai.appraisal.pipeline import evaluate_claims_dynamically


class _NoOpNplScorer:
    def score_description(self, description: str, category: str | None = None) -> dict:
        del description, category
        return {
            "red_flag_similarity": 0.0,
            "matched_pattern_id": None,
            "matched_trade_code": None,
            "matched_pattern_text": None,
            "citation": None,
            "recommended_action": ACTION_APPROVED,
        }


BOW = {
    "vessel_name": "テスト船",
    "incident_type": "衝突",
    "incident_date": "2024-01-01",
    "incident_location": "試験海域",
    "damaged_components": ["球状船首", "外板"],
    "damage_evidence": ["球状船首擦過"],
    "source_pdf": "fixture.pdf",
}


def _item(iid: int, desc: str, cost: int, category: str = "【甲板部】") -> dict:
    return {
        "id": iid,
        "category": category,
        "num": str(iid),
        "description": desc,
        "estimated_cost": cost,
    }


def test_pipeline_rule_d5_5050_reconciliation_zero_jpy():
    items = [
        _item(1, "船体入出渠及び滞渠", 4_300_000),
        _item(2, "船体外板・船側外板高圧清水洗浄", 450_000),
        _item(3, "JG定期検査立会", 550_000),
    ]
    analyzed, summary = evaluate_claims_dynamically(
        items,
        BOW,
        scorer=_NoOpNplScorer(),
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
        assume_statutory_owner_work=True,
    )
    dock = next(x for x in analyzed if "入出渠" in x["description"])
    assert dock["apportionment_rule"] == ApportionmentRule.RULE_D5_50_50.value
    assert dock["status"] == "APPORTIONED (50%)"
    assert dock["insurer_share"] + dock["owner_share"] == dock["estimated_cost"]
    assert dock["approved_amount"] == dock["insurer_share"]
    assert summary["rule_d5_reconciliation_error_jpy"] == 0


def test_pipeline_rule_d5_100_uw_when_no_statutory():
    items = [
        _item(1, "船体入出渠及び滞渠", 4_300_000),
        _item(2, "船体外板・船側外板高圧清水洗浄", 450_000),
    ]
    analyzed, summary = evaluate_claims_dynamically(
        items,
        BOW,
        scorer=_NoOpNplScorer(),
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
        assume_statutory_owner_work=False,
    )
    dock = next(x for x in analyzed if "入出渠" in x["description"])
    assert dock["apportionment_rule"] == ApportionmentRule.RULE_D5_100_UNDERWRITER.value
    assert dock["status"] == "COVERED"
    assert dock["insurer_share"] == 4_300_000
    assert dock["owner_share"] == 0
    assert dock["insurer_share"] + dock["owner_share"] == dock["estimated_cost"]
    assert summary["rule_d5_reconciliation_error_jpy"] == 0
