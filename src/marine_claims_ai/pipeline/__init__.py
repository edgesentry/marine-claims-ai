"""Gate A Priority 1 pipeline helpers (Exact Span A4, physical boundary A2)."""

from marine_claims_ai.pipeline.boundary import (
    DEFAULT_CRITICAL_SUBSTRINGS,
    check_repair_boundary,
    count_critical_false_accepts,
    is_bow_machinery_false_accept,
)
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
    "DEFAULT_CRITICAL_SUBSTRINGS",
    "ExactSpanExtractResult",
    "GroundedRepairItem",
    "PdfBBox",
    "SpanValidationError",
    "assert_quote_in_text",
    "check_repair_boundary",
    "count_critical_false_accepts",
    "extract_spec_with_spans",
    "find_grounded_quote",
    "is_bow_machinery_false_accept",
    "normalize_span_text",
    "quote_in_text",
]
