"""Offline unit tests for civil judgment fault-ratio / yen extraction."""

from __future__ import annotations

import pytest

from marine_claims_ai.benchmarks.civil_extractor_eval import (
    OFFLINE_GOLD_SNIPPETS,
    evaluate_offline_snippets,
)
from marine_claims_ai.ingest.civil_judgment_extractor import (
    best_fault_ratio,
    extract_from_judgment,
    extract_negligence_holding,
    parse_kanji_int,
    parse_yen_token,
)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("六五", 65),
        ("八〇", 80),
        ("三五", 35),
        ("三十五", 35),
        ("六十五", 65),
        ("十", 10),
        ("百二十", 120),
        ("八〇七万二三三五", 8_072_335),
        ("一一七〇万五〇〇〇", 11_705_000),
        ("一億〇三九〇万三〇〇〇", 103_903_000),
        ("65", 65),
        ("６５", 65),
    ],
)
def test_parse_kanji_int(token: str, expected: int):
    assert parse_kanji_int(token) == expected


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("8,072,335円", 8_072_335),
        ("八〇七万二三三五円", 8_072_335),
        ("１１７０５０００円", 11_705_000),
        ("一一七〇万五〇〇〇円", 11_705_000),
    ],
)
def test_parse_yen_token(token: str, expected: int):
    assert parse_yen_token(token) == expected


def test_arabic_and_kanji_fault_pairs():
    assert best_fault_ratio("過失割合は 65対35 である。") == "65:35"
    assert best_fault_ratio("過失割合を八〇対二〇と認めるのが相当である。") == "80:20"
    assert best_fault_ratio("責任割合を建昌65・有漁丸35と判示。") == "65:35"


def test_middle_dot_and_named_tenths():
    text = "両船の責任割合は、建昌六・五、有漁丸三・五である。"
    assert best_fault_ratio(text) == "65:35"
    text2 = "その責任割合はしんえい丸八、金宝丸二である。"
    assert best_fault_ratio(text2) == "80:20"


def test_percent_and_wari():
    assert best_fault_ratio("建昌の責任割合は前記のとおり六五パーセントである。") == "65:35"
    assert best_fault_ratio("責任割合を七五％と認定した。") == "75:25"
    assert best_fault_ratio("原告の過失割合を三割と認めるのが相当である。") == "30:70"


def test_shuin_ichin_and_hassei_fallback():
    assert best_fault_ratio("本件はAが主因でありBが一因をなす。") == "70:30"
    text = (
        "本件衝突は、見張り不十分によって発生したが、"
        "協力動作をとらなかったことも一因をなすものである。"
    )
    assert best_fault_ratio(text) == "70:30"


def test_monetary_labeled_extraction():
    text = (
        "請求額は 20,000,000円、認容額は 12,345,678円、否認は 3,000,000円 とした。"
    )
    out = extract_from_judgment(text)
    assert out.claimed_repair_jpy == 20_000_000
    assert out.awarded_damages_jpy == 12_345_678
    assert out.disallowed_jpy == 3_000_000


def test_kanji_yen_from_public_judgment_phrasing():
    text = (
        "請求額は八〇七万二三三五円であり、"
        "認容額は一一七〇万五〇〇〇円とした。"
        "建昌の責任割合は六五パーセントである。"
    )
    out = extract_from_judgment(text)
    assert out.fault_ratio == "65:35"
    assert out.claimed_repair_jpy == 8_072_335
    assert out.awarded_damages_jpy == 11_705_000


def test_negligence_holding_excerpt():
    text = (
        "事実認定の詳細は別紙のとおりである。"
        "過失相殺について検討するに、双方に見張り不十分があり、"
        "過失割合は六五対三五と認めるのが相当である。"
        "よって主文のとおり判決する。"
    )
    excerpt = extract_negligence_holding(text)
    assert excerpt is not None
    assert "過失相殺" in excerpt or "過失割合" in excerpt
    assert best_fault_ratio(excerpt or "") == "65:35"


def test_offline_snippet_suite_meets_dod():
    report = evaluate_offline_snippets(OFFLINE_GOLD_SNIPPETS)
    assert report["total"] >= 8
    assert report["accuracy"] >= 0.90, report
    failed = [r for r in report["results"] if not r["ok"]]
    assert failed == [], failed
