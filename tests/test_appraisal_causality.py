from __future__ import annotations

from marine_claims_ai.appraisal.negative_patterns import ACTION_APPROVED, format_citation
from marine_claims_ai.appraisal.pipeline import evaluate_claims_dynamically
from marine_claims_ai.ontology.compartments import (
    any_damage_allows_repair,
    infer_repair_zone,
    validate_claims_causality,
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
    """Keep causality tests independent of FastEmbed / NPL thresholds."""

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


_NOOP_SCORER = _NoOpNplScorer()


def _item(item_id: int, desc: str, cost: int, category: str = "【甲板部】") -> dict:
    return {
        "id": item_id,
        "category": category,
        "num": str(item_id),
        "description": desc,
        "estimated_cost": cost,
    }


def test_infer_repair_zone_maps_false_accept_hotspots():
    assert infer_repair_zone("カロリーファイヤー（給湯設備）開放掃除洗浄復旧耐圧") == "machinery"
    assert infer_repair_zone("減速機入出力側、クラッチ陸揚げ点検整備受検", "【機関部】") == "machinery"
    assert infer_repair_zone("プロペラ軸及び翼取り外し開放、研磨、掃除、各部点検") == "propulsion"
    assert infer_repair_zone("船体外板・船側外板高圧清水洗浄") == "hull_mid"


def test_claims_causality_blocks_bow_to_machinery_and_distant_propulsion():
    assert validate_claims_causality("球状船首", "機関室")["valid"] is False
    assert validate_claims_causality("球状船首", "推進器")["valid"] is False
    assert validate_claims_causality("球状船首", "推進器")["reason"] == (
        "beyond_casualty_propagation_limit"
    )
    assert validate_claims_causality("球状船首", "外板")["valid"] is True


def test_bow_collision_excludes_machinery_propulsion_calorifier():
    items = [
        _item(1, "船体入出渠及び滞渠", 4_300_000),
        _item(2, "船体外板・船側外板高圧清水洗浄", 450_000),
        _item(3, "錨鎖庫内清掃、発錆部手入れ、タールエポキシ塗装", 1_200_000),
        _item(9, "汚物処理装置（バウスラスター室、機関室）タンク内部清掃", 1_200_000),
        _item(59, "減速機入出力側、クラッチ陸揚げ点検整備受検", 1_200_000, "【機関部】"),
        _item(76, "プロペラ軸及び翼取り外し開放、研磨、掃除、各部点検", 1_200_000),
        _item(81, "カロリーファイヤー（給湯設備）開放掃除洗浄復旧耐圧", 350_000, "【機関部】"),
    ]
    analyzed, summary = evaluate_claims_dynamically(items, BOW_CASUALTY, scorer=_NOOP_SCORER)
    by_id = {x["id"]: x for x in analyzed}

    assert by_id[1]["status"] == "APPORTIONED (50%)"
    assert by_id[1]["approved_amount"] == 2_150_000
    assert by_id[2]["status"] == "COVERED"
    assert "EXCLUDED" in by_id[3]["status"]
    assert "EXCLUDED" in by_id[9]["status"]
    assert "EXCLUDED" in by_id[59]["status"]
    assert "EXCLUDED" in by_id[76]["status"]
    assert "EXCLUDED" in by_id[81]["status"]
    assert summary["pricing_note"]
    # Red-flag fields always present even when NPL is a no-op
    assert "red_flag_similarity" in by_id[59]
    assert by_id[59]["recommended_action"] == ACTION_APPROVED


def test_bare_paint_keyword_does_not_cover_calorifier():
    items = [_item(1, "カロリーファイヤー塗装洗浄", 350_000, "【機関部】")]
    analyzed, _ = evaluate_claims_dynamically(items, BOW_CASUALTY, scorer=_NOOP_SCORER)
    assert "EXCLUDED" in analyzed[0]["status"]
    assert analyzed[0].get("ontology", {}).get("valid") is False


def test_bow_machinery_emits_npl_citation_fields():
    """Ontology excludes machinery; NPL still attaches similarity citation fields."""
    citation = format_citation(0.894, "ENG-01")

    class _HighScorer:
        def score_description(self, description: str, category: str | None = None) -> dict:
            del description, category
            return {
                "red_flag_similarity": 0.894,
                "matched_pattern_id": "npl-eng-01",
                "matched_trade_code": "ENG-01",
                "matched_pattern_text": "主機関シリンダヘッド及びピストン抜出開放点検",
                "citation": citation,
                "recommended_action": "Disallowed",
            }

    items = [_item(1, "主機関ピストン抜出開放点検", 4_800_000, "【機関部】")]
    analyzed, _ = evaluate_claims_dynamically(items, BOW_CASUALTY, scorer=_HighScorer())
    assert "EXCLUDED" in analyzed[0]["status"]
    assert analyzed[0]["red_flag_similarity"] == 0.894
    assert analyzed[0]["matched_trade_code"] == "ENG-01"
    assert analyzed[0]["citation"] == citation


def test_any_damage_allows_adjacent_hull():
    result = any_damage_allows_repair(["球状船首"], "外板")
    assert result["valid"] is True
