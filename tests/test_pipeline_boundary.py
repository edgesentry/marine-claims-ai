"""Gate A / A2 physical-boundary validator (pipeline.boundary)."""

from __future__ import annotations

from marine_claims_ai.appraisal.negative_patterns import ACTION_APPROVED
from marine_claims_ai.appraisal.pipeline import evaluate_claims_dynamically
from marine_claims_ai.pipeline.boundary import (
    DEFAULT_CRITICAL_SUBSTRINGS,
    check_repair_boundary,
    count_critical_false_accepts,
    is_bow_machinery_false_accept,
)

BOW_CASUALTY = {
    "vessel_name": "テスト船",
    "incident_type": "衝突",
    "incident_date": "2024-01-01",
    "incident_location": "試験海域",
    "damaged_components": ["球状船首", "外板"],
    "damage_evidence": ["球状船首擦過"],
    "source_pdf": "fixture.pdf",
}


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


def _item(item_id: int, desc: str, cost: int, category: str = "【機関部】") -> dict:
    return {
        "id": item_id,
        "category": category,
        "num": str(item_id),
        "description": desc,
        "estimated_cost": cost,
    }


def test_check_repair_boundary_blocks_bow_to_machinery():
    result = check_repair_boundary(
        ["球状船首", "外板"],
        "主機関ピストン抜出開放点検",
        category="【機関部】",
    )
    assert result["repair_zone"] == "machinery"
    assert result["valid"] is False


def test_check_repair_boundary_allows_outer_hull_on_bow():
    result = check_repair_boundary(
        ["球状船首", "外板"],
        "船体外板・船側外板高圧清水洗浄",
        category="【甲板部】",
    )
    assert result["repair_zone"] == "hull_mid"
    assert result["valid"] is True


def test_is_bow_machinery_false_accept_detects_critical_fa():
    assert (
        is_bow_machinery_false_accept(
            damaged_components=["球状船首"],
            description="カロリーファイヤー開放掃除",
            predicted_status="COVERED",
            gold_status="EXCLUDED",
        )
        is True
    )
    assert (
        is_bow_machinery_false_accept(
            damaged_components=["球状船首"],
            description="カロリーファイヤー開放掃除",
            predicted_status="EXCLUDED (便乗修理)",
            gold_status="EXCLUDED",
        )
        is False
    )


def test_bow_collision_pipeline_critical_fa_is_zero():
    """DoD: bow damage × machinery/shaft → Critical FA = 0 after pipeline."""
    items = [
        _item(1, "船体入出渠及び滞渠", 4_300_000, "【甲板部】"),
        _item(2, "船体外板・船側外板高圧清水洗浄", 450_000, "【甲板部】"),
        _item(59, "減速機入出力側、クラッチ陸揚げ点検整備受検", 1_200_000),
        _item(76, "プロペラ軸及び翼取り外し開放、研磨、掃除、各部点検", 1_200_000),
        _item(81, "カロリーファイヤー（給湯設備）開放掃除洗浄復旧耐圧", 350_000),
        _item(90, "主機関ピストン抜出開放点検", 4_800_000),
    ]
    analyzed, _ = evaluate_claims_dynamically(
        items, BOW_CASUALTY, scorer=_NoOpNplScorer()
    )
    golded = []
    for row in analyzed:
        golded.append(
            {
                **row,
                # Independent gold: machinery/shaft on bow casualty → EXCLUDED
                "gold_status": (
                    "EXCLUDED"
                    if any(s in row["description"] for s in DEFAULT_CRITICAL_SUBSTRINGS)
                    else row["status"]
                ),
            }
        )
    assert count_critical_false_accepts(
        golded, damaged_components=BOW_CASUALTY["damaged_components"]
    ) == 0
    for row in analyzed:
        if any(s in row["description"] for s in DEFAULT_CRITICAL_SUBSTRINGS):
            assert "EXCLUDED" in row["status"], row["description"]
