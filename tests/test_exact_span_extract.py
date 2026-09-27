"""Tests for Gate A / A4 exact-span repair-spec extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from marine_claims_ai.paths import DEFAULT_DATASET_DIR, LEGACY_DATASET_DIR
from marine_claims_ai.pipeline import (
    SpanValidationError,
    assert_quote_in_text,
    extract_spec_with_spans,
    find_grounded_quote,
    quote_in_text,
)
from marine_claims_ai.pipeline.schemas import GroundedRepairItem, PdfBBox

SPEC_NAMES = (
    "sample_drydock_repair_specification.pdf",
    "fukuoka_kaiyomaru_spec.pdf",
)


def _resolve_dataset_dir() -> Path | None:
    for base in (DEFAULT_DATASET_DIR, LEGACY_DATASET_DIR):
        if all((base / name).is_file() for name in SPEC_NAMES):
            return base
    return None


@pytest.fixture(scope="module")
def dataset_dir() -> Path:
    root = _resolve_dataset_dir()
    if root is None:
        pytest.skip("public repair-spec PDFs not present under _data/ or _inputs/poc_datasets")
    return root


def test_quote_in_text_accepts_exact_and_whitespace_variants():
    pdf = "船体入出渠及び滞渠\n船体外板高圧清水洗浄"
    assert quote_in_text("船体入出渠及び滞渠", pdf)
    assert quote_in_text("船体入出渠 及び滞渠", pdf)  # joined space vs newline
    assert_quote_in_text("船体外板高圧清水洗浄", pdf)


def test_quote_in_text_rejects_fabricated():
    pdf = "船体入出渠及び滞渠\n船体外板高圧清水洗浄"
    fabricated = "架空の機関室オーバーホール工事XYZ999アルファ"
    assert not quote_in_text(fabricated, pdf)
    with pytest.raises(SpanValidationError):
        assert_quote_in_text(fabricated, pdf)
    assert find_grounded_quote(fabricated, pdf) is None


def test_find_grounded_quote_longest_prefix_when_join_gap():
    # Extractor may concatenate across a header that interrupts the PDF stream.
    pdf = "効力検査関係（１）下記機器の検査\n備考番号工事内訳\n（２）海洋汚染防止"
    description = "効力検査関係（１）下記機器の検査 （２）海洋汚染防止"
    quote = find_grounded_quote(description, pdf)
    assert quote is not None
    assert quote_in_text(quote, pdf)
    assert "効力検査関係" in quote


def test_grounded_repair_item_allows_null_bbox():
    item = GroundedRepairItem(
        id=1,
        category="【甲板部】",
        num="2",
        description="船体入出渠及び滞渠",
        estimated_cost=4_300_000,
        source_quote="船体入出渠及び滞渠",
        page_number=None,
        pdf_coordinates=None,
    )
    assert item.pdf_coordinates is None
    legacy = item.to_legacy_dict()
    assert legacy["source_quote"] == "船体入出渠及び滞渠"
    assert legacy["pdf_coordinates"] is None

    boxed = GroundedRepairItem(
        id=2,
        description="外板",
        source_quote="外板",
        pdf_coordinates=PdfBBox(x0=0.0, y0=0.0, x1=10.0, y1=12.0),
        page_number=1,
    )
    assert boxed.pdf_coordinates is not None
    assert boxed.page_number == 1


def test_extract_spec_rejects_fabricated_when_monkeypatched(monkeypatch, tmp_path: Path):
    pdf_path = tmp_path / "synthetic.txt.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 synthetic placeholder")

    monkeypatch.setattr(
        "marine_claims_ai.pipeline.extract_spec.pdf_to_text",
        lambda _p: "船体入出渠及び滞渠\n船体外板高圧清水洗浄",
    )
    monkeypatch.setattr(
        "marine_claims_ai.pipeline.extract_spec.extract_repair_items",
        lambda _p: [
            {
                "id": 1,
                "category": "【甲板部】",
                "num": "2",
                "description": "船体入出渠及び滞渠",
                "estimated_cost": 4_300_000,
            },
            {
                "id": 2,
                "category": "【機関部】",
                "num": "99",
                "description": "架空の機関室オーバーホール工事XYZ999アルファ",
                "estimated_cost": 9_999_999,
            },
        ],
    )

    result = extract_spec_with_spans(pdf_path)
    assert result.fabricated_line_items == 1
    assert len(result.items) == 1
    assert result.items[0].source_quote == "船体入出渠及び滞渠"
    assert_quote_in_text(result.items[0].source_quote, "船体入出渠及び滞渠\n船体外板高圧清水洗浄")
    assert all(quote_in_text(i.source_quote, "船体入出渠及び滞渠\n船体外板高圧清水洗浄") for i in result.items)


def test_extract_spec_three_public_cases_pass_span_gate(dataset_dir: Path):
    """Existing public appraisal specs: every returned row is span-grounded (A4)."""
    from marine_claims_ai.ingest.pdf_text import pdf_to_text

    for name in SPEC_NAMES:
        path = dataset_dir / name
        result = extract_spec_with_spans(path)
        pdf_text = pdf_to_text(str(path))
        assert result.pdf_text_chars > 0
        assert len(result.items) >= 50, f"{name}: expected substantial extraction"
        # Returned rows must be 100% grounded (fabricated_line_items among output == 0).
        for item in result.items:
            assert_quote_in_text(item.source_quote, pdf_text)
            assert item.pdf_coordinates is None  # pdftotext path: bbox explicitly null
        # Ungrounded layout garbage (if any) is discarded, not passed downstream.
        assert result.fabricated_line_items == len(result.rejected)
        assert result.fabricated_line_items <= 5, f"{name}: unexpected mass rejection"
