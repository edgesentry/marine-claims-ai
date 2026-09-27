"""Offline tests for JMAT Field 1 charset decoding and section extraction."""

from __future__ import annotations

import pytest

from marine_claims_ai.ingest.public_datasets import (
    decode_jmat_html,
    field1_case_issues,
    parse_jmat_case_html,
)


def _page(body: str, charset: str = "Shift_JIS") -> str:
    return (
        "<html><head>"
        f'<meta http-equiv="Content-Type" content="text/html; charset={charset}">'
        "</head><body>"
        f"{body}"
        "</body></html>"
    )


def test_cp932_nec_row_decodes_and_extracts_facts():
    """0x87 0x40 is ① in CP932 and illegal in strict shift_jis."""
    html = _page(
        "<p>主文 本件衝突は、あたごが動静監視不十分で発生した。</p>"
        "<p>理由 (事実） ①事実の経過 護衛艦あたごは針路を保ち清徳丸と衝突した。</p>"
    )
    raw = html.encode("cp932")
    with pytest.raises(UnicodeDecodeError):
        raw.decode("shift_jis")

    decoded = decode_jmat_html(raw, "text/html")
    assert "①事実の経過" in decoded
    assert "\ufffd" not in decoded

    parsed = parse_jmat_case_html(raw, "text/html")
    assert "①事実の経過" in parsed["input_facts"]
    assert "護衛艦あたご" in parsed["input_facts"]
    assert "本件衝突は" in parsed["ground_truth_ruling"]
    assert field1_case_issues(parsed) == []


def test_spaced_headings_and_html_entities():
    html = _page(
        "<p>主 文 本件遭難は、船頭の過失&amp;船主の改造によって発生した。</p>"
        "<p>理 由 （事 実） 内郷丸は相模湖で転覆した。</p>"
    )
    raw = html.encode("cp932")
    parsed = parse_jmat_case_html(raw, "text/html")
    assert "内郷丸は相模湖で転覆した" in parsed["input_facts"]
    assert "船頭の過失&船主の改造" in parsed["ground_truth_ruling"]
    assert "理 由" not in parsed["ground_truth_ruling"]


def test_utf8_ignore_mojibake_fails_sanity():
    source = "理由 (事実） ①事実の経過 護衛艦あたごは針路を保ち清徳丸と衝突した。"
    garbled = source.encode("cp932").decode("utf-8", errors="ignore")
    facts = (garbled + " ") * 5
    assert len(facts) > 80
    issues = field1_case_issues({"input_facts": facts, "ground_truth_ruling": garbled})
    assert any("CJK fraction" in item for item in issues)

    readable = "護衛艦あたごは針路を保ち清徳丸と衝突した。" * 3
    assert field1_case_issues({"input_facts": readable, "ground_truth_ruling": "主文 本件衝突は発生した。"}) == []
    flagged = field1_case_issues({"input_facts": readable + "\ufffd", "ground_truth_ruling": ""})
    assert any("U+FFFD" in item for item in flagged)
    flagged = field1_case_issues({"input_facts": readable + "\x01", "ground_truth_ruling": ""})
    assert any("C0 control" in item for item in flagged)


def test_utf8_index_still_decodes():
    raw = "<html><head><meta charset=UTF-8></head><body>日本の重大海難</body></html>".encode("utf-8")
    assert decode_jmat_html(raw, "text/html") == raw.decode("utf-8")
