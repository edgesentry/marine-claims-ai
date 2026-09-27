"""Exact-span grounding against PDF source text (Gate A / A4 anti-hallucination)."""

from __future__ import annotations

import re
import unicodedata

# Minimum grounded quote length after whitespace collapse (blocks tiny accidental hits).
MIN_GROUNDED_NORM_CHARS = 12


class SpanValidationError(ValueError):
    """Raised when a candidate quote cannot be grounded in source PDF text."""


def normalize_span_text(text: str) -> str:
    """Light normalization: NFKC full/half-width + strip all whitespace."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


def quote_in_text(quote: str, pdf_text: str) -> bool:
    """True if ``quote`` appears in ``pdf_text`` exactly or after light normalization."""
    if not (quote or "").strip():
        return False
    if quote in pdf_text:
        return True
    n_quote = normalize_span_text(quote)
    if not n_quote:
        return False
    return n_quote in normalize_span_text(pdf_text)


def assert_quote_in_text(quote: str, pdf_text: str) -> None:
    """Raise ``SpanValidationError`` unless ``quote`` is grounded in ``pdf_text``."""
    if not quote_in_text(quote, pdf_text):
        preview = (quote or "")[:80]
        raise SpanValidationError(f"source_quote not found in PDF text: {preview!r}")


def _slice_for_norm_len(original: str, norm_len: int) -> str:
    """Map a normalized-character length back to an original-string prefix."""
    n = 0
    for i, ch in enumerate(original):
        piece = normalize_span_text(ch)
        if not piece:
            continue
        n += len(piece)
        if n >= norm_len:
            return original[: i + 1].strip()
    return original.strip()


def find_grounded_quote(
    description: str,
    pdf_text: str,
    *,
    min_norm_chars: int = MIN_GROUNDED_NORM_CHARS,
) -> str | None:
    """Return a contiguous ``source_quote`` grounded in ``pdf_text``, or None.

    Prefer the full ``description``. If extractor line-joining introduced gaps
    (headers / page breaks), fall back to the longest matching prefix that still
    appears in the PDF after light normalization.
    """
    desc = (description or "").strip()
    if not desc:
        return None
    if quote_in_text(desc, pdf_text):
        return desc

    n_text = normalize_span_text(pdf_text)
    n_desc = normalize_span_text(desc)
    if not n_desc or not n_text:
        return None

    lo, hi, best = 0, len(n_desc), 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if mid and n_desc[:mid] in n_text:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    if best < min_norm_chars:
        return None
    grounded = _slice_for_norm_len(desc, best)
    if not grounded or not quote_in_text(grounded, pdf_text):
        return None
    return grounded
