"""Exact-span extraction pipeline (Gate A Priority 1 / metric A4)."""

from marine_claims_ai.pipeline.extract_spec import extract_spec_with_spans
from marine_claims_ai.pipeline.schemas import (
    ExactSpanExtractResult,
    GroundedRepairItem,
    PdfBBox,
)
from marine_claims_ai.pipeline.span_validate import (
    SpanValidationError,
    assert_quote_in_text,
    find_grounded_quote,
    normalize_span_text,
    quote_in_text,
)

__all__ = [
    "ExactSpanExtractResult",
    "GroundedRepairItem",
    "PdfBBox",
    "SpanValidationError",
    "assert_quote_in_text",
    "extract_spec_with_spans",
    "find_grounded_quote",
    "normalize_span_text",
    "quote_in_text",
]
