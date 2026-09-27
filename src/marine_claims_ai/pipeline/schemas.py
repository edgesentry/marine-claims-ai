"""Pydantic schemas for exact-span grounded repair specification extraction (Gate A / A4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PdfBBox(BaseModel):
    """PDF page-space bounding box for UI highlighting (PDF user space units)."""

    model_config = ConfigDict(extra="forbid")

    x0: float
    y0: float
    x1: float
    y1: float


class GroundedRepairItem(BaseModel):
    """Repair line item whose ``source_quote`` is verified against PDF text (A4)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    category: str = ""
    num: str = ""
    description: str
    estimated_cost: int = 0
    source_quote: str = Field(
        ...,
        description="Contiguous span verified to appear in the source PDF text (possibly after light normalization).",
    )
    page_number: int | None = Field(
        default=None,
        description="1-based PDF page index when known; null if unavailable.",
    )
    pdf_coordinates: PdfBBox | None = Field(
        default=None,
        description="Bounding box for UI highlight; null when the PDF yields no coordinates.",
    )

    def to_legacy_dict(self) -> dict:
        """Shape expected by ``evaluate_claims_dynamically`` / existing appraisal callers."""
        return {
            "id": self.id,
            "category": self.category,
            "num": self.num,
            "description": self.description,
            "estimated_cost": self.estimated_cost,
            "source_quote": self.source_quote,
            "page_number": self.page_number,
            "pdf_coordinates": (
                self.pdf_coordinates.model_dump() if self.pdf_coordinates is not None else None
            ),
        }


class ExactSpanExtractResult(BaseModel):
    """Outcome of span-validated extraction (fabricated rows never appear in ``items``)."""

    model_config = ConfigDict(extra="forbid")

    items: list[GroundedRepairItem]
    rejected: list[dict] = Field(default_factory=list)
    pdf_path: str = ""
    pdf_text_chars: int = 0

    @property
    def fabricated_line_items(self) -> int:
        """A4 metric: count of rows discarded for failing exact-span grounding."""
        return len(self.rejected)

    def legacy_items(self) -> list[dict]:
        return [item.to_legacy_dict() for item in self.items]
