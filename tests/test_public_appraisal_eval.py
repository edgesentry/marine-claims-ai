from __future__ import annotations

from marine_claims_ai.benchmarks.public_appraisal_eval import (
    assign_provisional_gold_status,
    gate_report,
    is_critical_false_accept,
    normalize_status_bucket,
    score_predictions,
)


def test_normalize_status_bucket():
    assert normalize_status_bucket("APPORTIONED (50%)") == "APPORTIONED"
    assert normalize_status_bucket("EXCLUDED (便乗修理)") == "EXCLUDED"
    assert normalize_status_bucket("REVIEW / PARTIAL") == "REVIEW"
    assert normalize_status_bucket("COVERED") == "COVERED"


def test_provisional_gold_bow_collision_policy():
    zones = ["球状船首", "外板"]
    assert assign_provisional_gold_status("船体入出渠及び滞渠", zones) == "APPORTIONED"
    assert (
        assign_provisional_gold_status("船体外板、船側外板高圧清水洗浄", zones) == "COVERED"
    )
    assert assign_provisional_gold_status("カロリーファイヤー開放掃除", zones) == "EXCLUDED"
    assert assign_provisional_gold_status("プロペラ軸及び翼取り外し", zones) == "EXCLUDED"
    assert (
        assign_provisional_gold_status("バウスラスター プロペラ研磨", zones) == "REVIEW"
    )


def test_critical_false_accept_detection():
    assert is_critical_false_accept(
        gold_bucket="EXCLUDED",
        pred_bucket="COVERED",
        description="カロリーファイヤー開放",
        critical_substrings=["カロリーファイヤー"],
        damaged_zones=["球状船首"],
    )
    assert not is_critical_false_accept(
        gold_bucket="EXCLUDED",
        pred_bucket="EXCLUDED",
        description="カロリーファイヤー開放",
        critical_substrings=["カロリーファイヤー"],
        damaged_zones=["球状船首"],
    )


def test_score_predictions_agreement_and_gates():
    zones = ["球状船首", "外板"]
    items = [
        {
            "num": "2",
            "description": "船体入出渠及び滞渠",
            "category": "【甲板部】",
            "status": "APPORTIONED (50%)",
        },
        {
            "num": "3",
            "description": "船体外板、船側外板高圧清水洗浄",
            "category": "【甲板部】",
            "status": "COVERED",
        },
        {
            "num": "81",
            "description": "カロリーファイヤー開放掃除",
            "category": "【機関部】",
            "status": "EXCLUDED (便乗修理)",
        },
        {
            "num": "99",
            "description": "プロペラ軸及び翼取り外し",
            "category": "【機関部】",
            "status": "COVERED",  # intentional FA for metric check
        },
    ]
    metrics = score_predictions(
        items,
        damaged_zones=zones,
        critical_substrings=["カロリーファイヤー", "プロペラ軸"],
    )
    assert metrics["items_scored"] == 4
    assert metrics["false_accept"] == 1
    assert metrics["critical_false_accept"] == 1
    assert 0.0 < metrics["agreement"] < 1.0

    gate = gate_report(
        [
            {
                "skipped": False,
                "agreement": metrics["agreement"],
                "critical_false_accept": metrics["critical_false_accept"],
                "items_scored": metrics["items_scored"],
            }
        ],
        {"min_cases_with_pdfs": 1, "max_critical_false_accepts": 0, "min_status_agreement": 0.85},
    )
    assert gate["pass_critical_fa"] is False
    assert gate["overall_pass"] is False
