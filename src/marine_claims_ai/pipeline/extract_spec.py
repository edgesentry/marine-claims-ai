"""Exact-span repair-spec extractor wrapping ``appraisal.pipeline.extract_repair_items``."""

from __future__ import annotations

from pathlib import Path

from marine_claims_ai.appraisal.pipeline import extract_repair_items
from marine_claims_ai.ingest.pdf_text import pdf_to_text
from marine_claims_ai.pipeline.schemas import ExactSpanExtractResult, GroundedRepairItem
from marine_claims_ai.pipeline.span_validate import find_grounded_quote


def extract_spec_with_spans(spec_pdf_path: str | Path) -> ExactSpanExtractResult:
    """Parse a drydock repair specification PDF and keep only span-grounded rows.

    Fabricated / ungroundable descriptions are discarded (never returned in
    ``items``). Bounding boxes are left ``null`` when the PDF yields no
    coordinates (``pdftotext`` path has no bbox).
    """
    path = Path(spec_pdf_path)
    pdf_text = pdf_to_text(str(path))
    raw_items = extract_repair_items(str(path)) if path.is_file() else []

    grounded: list[GroundedRepairItem] = []
    rejected: list[dict] = []

    for raw in raw_items:
        description = str(raw.get("description") or "")
        quote = find_grounded_quote(description, pdf_text)
        if quote is None:
            rejected.append(
                {
                    "id": raw.get("id"),
                    "num": raw.get("num"),
                    "description": description,
                    "reason": "ungrounded_source_quote",
                }
            )
            continue
        grounded.append(
            GroundedRepairItem(
                id=int(raw.get("id") or 0),
                category=str(raw.get("category") or ""),
                num=str(raw.get("num") or ""),
                description=description,
                estimated_cost=int(raw.get("estimated_cost") or 0),
                source_quote=quote,
                page_number=None,
                pdf_coordinates=None,
            )
        )

    return ExactSpanExtractResult(
        items=grounded,
        rejected=rejected,
        pdf_path=str(path),
        pdf_text_chars=len(pdf_text),
    )
