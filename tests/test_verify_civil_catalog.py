from __future__ import annotations

from marine_claims_ai.ci.verify_civil_catalog import (
    fault_ratio_evidenced,
    is_generic_portal,
    is_verifiable_document_url,
    kanji_percent_numbers,
    title_overlap,
    yen_evidenced,
)


def test_generic_and_verifiable_urls():
    assert is_generic_portal("https://www.courts.go.jp/") is True
    assert is_verifiable_document_url("https://www.courts.go.jp/assets/x.pdf") is True
    assert is_verifiable_document_url("https://yuhikaku.com/articles/-/110") is True
    assert is_verifiable_document_url("https://www.courts.go.jp/") is False


def test_kanji_percent_and_fault():
    text = "建昌の責任割合は前記のとおり六五パーセントである"
    assert 65 in kanji_percent_numbers(text)
    assert fault_ratio_evidenced("65:35", text) is True
    assert fault_ratio_evidenced("70:30", "本件は主因であり一因をなす") is True


def test_title_and_yen():
    assert title_overlap("漁船第一安洋丸沈没事件", "漁船第一安洋丸沈没事件について") is True
    court = {"source_type": "court_pdf", "awarded_damages_jpy": 11705000}
    assert yen_evidenced(court, "損害賠償債権の約四〇パーセント") is True
    assert yen_evidenced(court, "") is False
