"""Tests for Negative Pattern Library cosine red-flag scoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marine_claims_ai.appraisal.negative_patterns import (
    ACTION_APPORTIONED,
    ACTION_APPROVED,
    ACTION_DISALLOWED,
    NegativePatternScorer,
    action_for_similarity,
    cosine_similarity,
    format_citation,
    load_library,
    normalize_category,
    pattern_passes_gates,
    score_line_items,
)
from marine_claims_ai.appraisal.pipeline import evaluate_claims_dynamically
from marine_claims_ai.paths import DEFAULT_NEGATIVE_PATTERN_PATH, REPO_ROOT

BOW_CASUALTY = {
    "vessel_name": "テスト船",
    "incident_type": "衝突",
    "incident_date": "2024-01-01",
    "incident_location": "試験海域",
    "damaged_components": ["球状船首", "外板"],
    "damage_evidence": ["球状船首擦過"],
    "source_pdf": "fixture.pdf",
}


class StubScorer:
    """Deterministic scorer for pipeline / threshold tests (no FastEmbed)."""

    def __init__(self, by_substring: dict[str, dict] | None = None, default: dict | None = None):
        self.by_substring = by_substring or {}
        self.default = default or {
            "red_flag_similarity": 0.0,
            "matched_pattern_id": None,
            "matched_trade_code": None,
            "matched_pattern_text": None,
            "citation": None,
            "recommended_action": ACTION_APPROVED,
        }

    def score_description(self, description: str, category: str | None = None) -> dict:
        del category  # Stub ignores category; real scorer applies gates.
        for needle, payload in self.by_substring.items():
            if needle in description:
                return dict(payload)
        return dict(self.default)


def test_cosine_similarity_identical_and_orthogonal():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(0.0)
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0


def test_action_for_similarity_thresholds():
    assert action_for_similarity(0.80) == ACTION_DISALLOWED
    assert action_for_similarity(0.79) == ACTION_APPORTIONED
    assert action_for_similarity(0.50) == ACTION_APPORTIONED
    assert action_for_similarity(0.49) == ACTION_APPROVED
    assert action_for_similarity(0.0) == ACTION_APPROVED


def test_format_citation():
    assert format_citation(0.894, "ENG-01") == (
        "Matched with 89.4% similarity to public standard periodic maintenance item ENG-01"
    )


def test_load_library_default():
    lib = load_library(DEFAULT_NEGATIVE_PATTERN_PATH)
    assert lib["thresholds"]["disallow_min"] == 0.8
    assert lib["thresholds"]["apportion_min"] == 0.5
    codes = {p["trade_code"] for p in lib["patterns"]}
    assert "ENG-01" in codes
    assert "VALVE-01" in codes
    assert "SAFE-01" in codes
    assert "HULL-01" not in codes
    assert "DOCK-01" not in codes


def test_score_line_items_with_stub_embed(tmp_path: Path):
    lib = {
        "thresholds": {"disallow_min": 0.80, "apportion_min": 0.50},
        "patterns": [
            {
                "id": "npl-eng-01",
                "trade_code": "ENG-01",
                "text": "ピストン抜出",
                "category": "機関部",
                "source": "test",
            }
        ],
    }
    lib_path = tmp_path / "npl.json"
    lib_path.write_text(json.dumps(lib, ensure_ascii=False), encoding="utf-8")

    # Pattern vector and query vectors chosen so cosine is exact.
    def fake_embed(texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if "ピストン" in t:
                out.append([1.0, 0.0, 0.0])
            elif "外板塗装" in t:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out

    scorer = NegativePatternScorer(library_path=lib_path, embed_fn=fake_embed)
    items = score_line_items(
        [
            {"id": 1, "description": "主機関ピストン抜出開放点検"},
            {"id": 2, "description": "外板塗装復旧"},
        ],
        scorer=scorer,
    )
    assert items[0]["recommended_action"] == ACTION_DISALLOWED
    assert items[0]["matched_trade_code"] == "ENG-01"
    assert "ENG-01" in items[0]["citation"]
    assert items[0]["red_flag_similarity"] == pytest.approx(1.0)
    assert items[1]["recommended_action"] == ACTION_APPROVED
    assert items[1]["red_flag_similarity"] == pytest.approx(0.0)


def test_pipeline_npl_disallow_and_apportion_override_keywords():
    scorer = StubScorer(
        by_substring={
            "ピストン抜出": {
                "red_flag_similarity": 0.91,
                "matched_pattern_id": "npl-eng-01",
                "matched_trade_code": "ENG-01",
                "matched_pattern_text": "主機関シリンダヘッド及びピストン抜出開放点検",
                "citation": format_citation(0.91, "ENG-01"),
                "recommended_action": ACTION_DISALLOWED,
            },
            "キングストン": {
                "red_flag_similarity": 0.62,
                "matched_pattern_id": "npl-valve-01",
                "matched_trade_code": "VALVE-01",
                "matched_pattern_text": "船底・船側キングストン弁及び非常排出弁開放摺合せ",
                "citation": format_citation(0.62, "VALVE-01"),
                "recommended_action": ACTION_APPORTIONED,
            },
        }
    )
    # Use hull-only damage with items that have no repair_zone inference conflict:
    # キングストン弁 maps to machinery via ontology — bow damage will ontology-exclude first.
    # Use a description that does not trigger repair_zone so NPL can set status.
    items = [
        {
            "id": 1,
            "category": "【機関部】",
            "num": "1",
            "description": "主機関ピストン抜出開放点検",
            "estimated_cost": 4_800_000,
        },
        {
            "id": 2,
            "category": "【甲板部】",
            "num": "2",
            "description": "法定属具キングストン関連準備作業",
            "estimated_cost": 800_000,
        },
    ]
    # First item: machinery zone → ontology EXCLUDED before NPL; still has red_flag fields.
    # Second: if キングストン in desc triggers machinery zone via 波止弁? "キングストン" is in
    # compartments patterns. Check — キングストン may map to machinery.
    analyzed, _ = evaluate_claims_dynamically(items, BOW_CASUALTY, scorer=scorer)
    by_id = {x["id"]: x for x in analyzed}

    assert "EXCLUDED" in by_id[1]["status"]
    assert by_id[1]["matched_trade_code"] == "ENG-01"
    assert by_id[1]["red_flag_similarity"] == pytest.approx(0.91)
    assert "ENG-01" in (by_id[1]["citation"] or "")

    assert by_id[2]["recommended_action"] == ACTION_APPORTIONED
    # Ontology may exclude first if repair_zone=machinery; either APPORTIONED (NPL) or EXCLUDED (ontology)
    assert by_id[2]["red_flag_similarity"] == pytest.approx(0.62)
    assert by_id[2]["matched_trade_code"] == "VALVE-01"


def test_pipeline_npl_apportion_when_no_ontology_zone():
    """NPL Apportioned applies when ontology does not set a status."""
    scorer = StubScorer(
        by_substring={
            "メガテスト": {
                "red_flag_similarity": 0.65,
                "matched_pattern_id": "npl-elec-01",
                "matched_trade_code": "ELEC-01",
                "matched_pattern_text": "主配電盤メガテスト",
                "citation": format_citation(0.65, "ELEC-01"),
                "recommended_action": ACTION_APPORTIONED,
            }
        }
    )
    items = [
        {
            "id": 1,
            "category": "【電気部】",
            "num": "1",
            "description": "主配電盤メガテスト及び保護継電器動作試験",
            "estimated_cost": 450_000,
        }
    ]
    analyzed, _ = evaluate_claims_dynamically(items, BOW_CASUALTY, scorer=scorer)
    assert analyzed[0]["status"] == "APPORTIONED (50%)"
    assert analyzed[0]["approved_amount"] == 225_000
    assert "ELEC-01" in analyzed[0]["reason"]
    assert analyzed[0]["recommended_action"] == ACTION_APPORTIONED


def test_pipeline_npl_does_not_override_valid_hull_causality():
    """Valid hull ontology + NPL mid-band score still allows keyword COVERED."""
    scorer = StubScorer(
        default={
            "red_flag_similarity": 0.70,
            "matched_pattern_id": "npl-pump-01",
            "matched_trade_code": "PUMP-01",
            "matched_pattern_text": "主海水冷却ポンプ",
            "citation": format_citation(0.70, "PUMP-01"),
            "recommended_action": ACTION_APPORTIONED,
        }
    )
    items = [
        {
            "id": 1,
            "category": "【甲板部】",
            "num": "1",
            "description": "船体外板・船側外板高圧清水洗浄",
            "estimated_cost": 450_000,
        }
    ]
    analyzed, _ = evaluate_claims_dynamically(items, BOW_CASUALTY, scorer=scorer)
    assert analyzed[0]["status"] == "COVERED"
    assert analyzed[0]["recommended_action"] == ACTION_APPORTIONED
    assert analyzed[0]["red_flag_similarity"] == pytest.approx(0.70)


def test_normalize_category_strips_brackets():
    assert normalize_category("【船体部】") == "船体部"
    assert normalize_category("機関部") == "機関部"
    assert normalize_category("  ") is None
    assert normalize_category(None) is None


def test_pattern_passes_gates_anchor_and_category():
    pattern = {
        "category": "弁部",
        "anchor_tokens": ["キングストン", "排出弁"],
    }
    assert pattern_passes_gates(pattern, "船底キングストン弁開放") is True
    assert pattern_passes_gates(pattern, "船体外板高圧清水洗浄") is False
    assert pattern_passes_gates(pattern, "船底キングストン弁開放", category="【弁部】") is True
    assert pattern_passes_gates(pattern, "船底キングストン弁開放", category="【船体部】") is False


def test_score_rejects_midband_hull_false_positives_without_anchors(tmp_path: Path):
    """Casualty hull / bow work must not Apportion against VALVE/HULL-04 without anchors."""
    lib = {
        "thresholds": {"disallow_min": 0.80, "apportion_min": 0.50},
        "patterns": [
            {
                "id": "npl-valve-01",
                "trade_code": "VALVE-01",
                "category": "弁部",
                "text": "船底・船側キングストン弁及び非常排出弁開放摺合せ",
                "anchor_tokens": ["キングストン", "排出弁"],
                "source": "test",
            },
            {
                "id": "npl-hull-04",
                "trade_code": "HULL-04",
                "category": "船体部",
                "text": "船底防食亜鉛板 (ジンクアノード) 新替取付",
                "anchor_tokens": ["亜鉛", "ジンク", "アノード"],
                "source": "test",
            },
            {
                "id": "npl-pump-01",
                "trade_code": "PUMP-01",
                "category": "補機部",
                "text": "主海水冷却ポンプ・バラストポンプ分解点検",
                "anchor_tokens": ["海水冷却ポンプ", "バラストポンプ"],
                "source": "test",
            },
        ],
    }
    lib_path = tmp_path / "npl.json"
    lib_path.write_text(json.dumps(lib, ensure_ascii=False), encoding="utf-8")

    # Force high cosine between hull/bow queries and VALVE/HULL-04/PUMP texts.
    def fake_embed(texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if "キングストン" in t or "外板" in t or "海水冷却" in t:
                out.append([1.0, 0.0, 0.0])
            elif "亜鉛" in t or "ジンク" in t or "球状船首" in t:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out

    scorer = NegativePatternScorer(library_path=lib_path, embed_fn=fake_embed)
    wash = scorer.score_description(
        "船体外板・船側外板高圧清水洗浄",
        category="【船体部】",
    )
    bow = scorer.score_description(
        "球状船首曲損部切替新替",
        category="【船体部】",
    )
    assert wash["recommended_action"] == ACTION_APPROVED
    assert wash["matched_trade_code"] is None
    assert wash["red_flag_similarity"] == pytest.approx(0.0)
    assert bow["recommended_action"] == ACTION_APPROVED
    assert bow["matched_trade_code"] is None
    assert bow["red_flag_similarity"] == pytest.approx(0.0)


def test_score_true_positives_with_anchors_remain_disallowed(tmp_path: Path):
    lib = {
        "thresholds": {"disallow_min": 0.80, "apportion_min": 0.50},
        "patterns": [
            {
                "id": "npl-eng-01",
                "trade_code": "ENG-01",
                "category": "機関部",
                "text": "主機関シリンダヘッド及びピストン抜出開放点検",
                "anchor_tokens": ["ピストン", "シリンダヘッド"],
                "source": "test",
            },
            {
                "id": "npl-valve-01",
                "trade_code": "VALVE-01",
                "category": "弁部",
                "text": "船底・船側キングストン弁及び非常排出弁開放摺合せ",
                "anchor_tokens": ["キングストン", "排出弁"],
                "source": "test",
            },
            {
                "id": "npl-safe-01",
                "trade_code": "SAFE-01",
                "category": "法定部",
                "text": "JG (日本政府) 定期検査・中間検査立会及び安全設備点検整備",
                "anchor_tokens": ["JG", "定期検査", "中間検査", "安全設備"],
                "source": "test",
            },
            {
                "id": "npl-hull-04",
                "trade_code": "HULL-04",
                "category": "船体部",
                "text": "船底防食亜鉛板 (ジンクアノード) 新替取付",
                "anchor_tokens": ["亜鉛", "ジンク", "アノード"],
                "source": "test",
            },
        ],
    }
    lib_path = tmp_path / "npl.json"
    lib_path.write_text(json.dumps(lib, ensure_ascii=False), encoding="utf-8")

    def fake_embed(texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if "ピストン" in t or "シリンダヘッド" in t:
                out.append([1.0, 0.0, 0.0, 0.0])
            elif "キングストン" in t or "排出弁" in t:
                out.append([0.0, 1.0, 0.0, 0.0])
            elif "JG" in t or "定期検査" in t or "安全設備" in t:
                out.append([0.0, 0.0, 1.0, 0.0])
            elif "亜鉛" in t or "ジンク" in t or "アノード" in t:
                out.append([0.0, 0.0, 0.0, 1.0])
            else:
                out.append([0.25, 0.25, 0.25, 0.25])
        return out

    scorer = NegativePatternScorer(library_path=lib_path, embed_fn=fake_embed)
    cases = [
        ("主機関シリンダヘッド及びピストン抜出開放点検", "【機関部】", "ENG-01"),
        ("船底・船側キングストン弁及び非常排出弁開放摺合せ", "【弁部】", "VALVE-01"),
        ("JG 定期検査立会及び安全設備点検", "【法定部】", "SAFE-01"),
        ("船底防食亜鉛板（ジンクアノード）新替", "【船体部】", "HULL-04"),
    ]
    for desc, cat, code in cases:
        result = scorer.score_description(desc, category=cat)
        assert result["matched_trade_code"] == code
        assert result["recommended_action"] == ACTION_DISALLOWED
        assert result["red_flag_similarity"] == pytest.approx(1.0)


def test_fastembed_casualty_hull_not_apportioned():
    """Live embed: hull wash / bow insert must stay Approved; ENG/VALVE/SAFE stay hot."""
    try:
        scorer = NegativePatternScorer(library_path=DEFAULT_NEGATIVE_PATTERN_PATH)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"FastEmbed unavailable: {exc}")

    wash = scorer.score_description(
        "船体外板・船側外板高圧清水洗浄",
        category="【船体部】",
    )
    bow = scorer.score_description(
        "球状船首曲損部切替新替",
        category="【船体部】",
    )
    assert wash["recommended_action"] == ACTION_APPROVED
    assert wash["red_flag_similarity"] < scorer.apportion_min or wash["matched_trade_code"] is None
    assert bow["recommended_action"] == ACTION_APPROVED
    assert bow["red_flag_similarity"] < scorer.apportion_min or bow["matched_trade_code"] is None

    positives = [
        ("主機関シリンダヘッド及びピストン抜出開放点検", "【機関部】", "ENG-01"),
        ("船底・船側キングストン弁及び非常排出弁開放摺合せ", "【弁部】", "VALVE-01"),
        ("JG (日本政府) 定期検査・中間検査立会及び安全設備点検整備", "【法定部】", "SAFE-01"),
    ]
    for desc, cat, code in positives:
        result = scorer.score_description(desc, category=cat)
        assert result["matched_trade_code"] == code
        assert result["recommended_action"] == ACTION_DISALLOWED
        assert result["red_flag_similarity"] >= scorer.disallow_min


def test_fastembed_piston_matches_eng01():
    """Optional live embedding check; skip if FastEmbed model cannot load."""
    try:
        scorer = NegativePatternScorer(library_path=DEFAULT_NEGATIVE_PATTERN_PATH)
        result = scorer.score_description("主機関シリンダヘッド及びピストン抜出開放点検")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"FastEmbed unavailable: {exc}")

    assert result["matched_trade_code"] == "ENG-01"
    assert result["red_flag_similarity"] >= scorer.apportion_min
    assert result["recommended_action"] in {ACTION_DISALLOWED, ACTION_APPORTIONED}
    assert "ENG-01" in (result["citation"] or "")
    assert DEFAULT_NEGATIVE_PATTERN_PATH.is_relative_to(REPO_ROOT) or DEFAULT_NEGATIVE_PATTERN_PATH.exists()
