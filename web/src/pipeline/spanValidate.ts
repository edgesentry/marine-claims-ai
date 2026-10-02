/**
 * Exact-span grounding against PDF source text (Gate A / A4).
 * Port of marine_claims_ai.pipeline.span_validate.
 */

/** Minimum grounded quote length after whitespace collapse. */
export const MIN_GROUNDED_NORM_CHARS = 12;

export class SpanValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SpanValidationError";
  }
}

/** Light normalization: NFKC full/half-width + strip all whitespace. */
export function normalizeSpanText(text: string): string {
  return (text || "").normalize("NFKC").replace(/\s+/g, "");
}

/** True if quote appears in pdfText exactly or after light normalization. */
export function quoteInText(quote: string, pdfText: string): boolean {
  if (!(quote || "").trim()) return false;
  if (pdfText.includes(quote)) return true;
  const nQuote = normalizeSpanText(quote);
  if (!nQuote) return false;
  return normalizeSpanText(pdfText).includes(nQuote);
}

/** Throw SpanValidationError unless quote is grounded in pdfText. */
export function assertQuoteInText(quote: string, pdfText: string): void {
  if (!quoteInText(quote, pdfText)) {
    const preview = (quote || "").slice(0, 80);
    throw new SpanValidationError(`source_quote not found in PDF text: ${JSON.stringify(preview)}`);
  }
}

function sliceForNormLen(original: string, normLen: number): string {
  let n = 0;
  for (let i = 0; i < original.length; i++) {
    const piece = normalizeSpanText(original[i]!);
    if (!piece) continue;
    n += piece.length;
    if (n >= normLen) return original.slice(0, i + 1).trim();
  }
  return original.trim();
}

/**
 * Return a contiguous source_quote grounded in pdfText, or null.
 * Prefer the full description; fall back to longest matching normalized prefix.
 */
export function findGroundedQuote(
  description: string,
  pdfText: string,
  minNormChars: number = MIN_GROUNDED_NORM_CHARS,
): string | null {
  const desc = (description || "").trim();
  if (!desc) return null;
  if (quoteInText(desc, pdfText)) return desc;

  const nText = normalizeSpanText(pdfText);
  const nDesc = normalizeSpanText(desc);
  if (!nDesc || !nText) return null;

  let lo = 0;
  let hi = nDesc.length;
  let best = 0;
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (mid && nText.includes(nDesc.slice(0, mid))) {
      best = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }

  if (best < minNormChars) return null;
  const grounded = sliceForNormLen(desc, best);
  if (!grounded || !quoteInText(grounded, pdfText)) return null;
  return grounded;
}
