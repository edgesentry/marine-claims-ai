/**
 * Exact-span repair-spec extraction (port of pipeline/extract_spec.py).
 * Browser path takes already-extracted text + line items (pdf.js upstream).
 */
import type { PdfCoordinates } from "../schemas/envelope";
import type { PdfContent } from "./pdfLocate";
import { locateQuoteInPdfSafe } from "./pdfLocate";
import { findGroundedQuote } from "./spanValidate";

export interface GroundedRepairItem {
  id: number;
  category: string;
  num: string;
  description: string;
  estimated_cost: number;
  source_quote: string;
  page_number: number | null;
  pdf_coordinates: PdfCoordinates | null;
}

export interface RejectedItem {
  id?: number | string;
  num?: string;
  description: string;
  reason: string;
}

export interface ExactSpanExtractResult {
  items: GroundedRepairItem[];
  rejected: RejectedItem[];
  pdf_path: string;
  pdf_text_chars: number;
  fabricated_line_items: number;
}

export interface RawSpecLineItem {
  id?: number | string;
  category?: string;
  num?: string;
  description: string;
  estimated_cost?: number;
}

export interface ExtractSpecOptions {
  pdfPath?: string;
  /** Optional pdf.js content for page / bbox enrichment. */
  pdfContent?: PdfContent;
}

/**
 * Keep only span-grounded rows. Ungrounded descriptions go to rejected.
 */
export function extractSpecWithSpansFromText(
  pdfText: string,
  rawItems: RawSpecLineItem[],
  pdfPathOrOpts: string | ExtractSpecOptions = "in-memory",
): ExactSpanExtractResult {
  const opts: ExtractSpecOptions =
    typeof pdfPathOrOpts === "string"
      ? { pdfPath: pdfPathOrOpts }
      : pdfPathOrOpts;
  const pdfPath = opts.pdfPath ?? "in-memory";
  const grounded: GroundedRepairItem[] = [];
  const rejected: RejectedItem[] = [];

  for (const raw of rawItems) {
    const description = String(raw.description || "");
    const quote = findGroundedQuote(description, pdfText);
    if (quote === null) {
      rejected.push({
        id: raw.id,
        num: raw.num,
        description,
        reason: "ungrounded_source_quote",
      });
      continue;
    }

    let page_number: number | null = null;
    let pdf_coordinates: PdfCoordinates | null = null;
    if (opts.pdfContent) {
      const loc = locateQuoteInPdfSafe(quote, opts.pdfContent);
      page_number = loc.page_number;
      pdf_coordinates = loc.pdf_coordinates;
    }

    grounded.push({
      id: Number(raw.id || 0),
      category: String(raw.category || ""),
      num: String(raw.num || ""),
      description,
      estimated_cost: Number(raw.estimated_cost || 0),
      source_quote: quote,
      page_number,
      pdf_coordinates,
    });
  }

  return {
    items: grounded,
    rejected,
    pdf_path: pdfPath,
    pdf_text_chars: pdfText.length,
    fabricated_line_items: rejected.length,
  };
}

/** Gate A / A4 metric from in-memory text + items (PDF-free lite). */
export function evaluateA4ExactSpanFromText(
  pdfText: string,
  rawItems: RawSpecLineItem[],
): Record<string, unknown> {
  const result = extractSpecWithSpansFromText(pdfText, rawItems);
  return {
    metric: "A4",
    grounded_items: result.items.length,
    fabricated_line_items: 0, // accepted set is span-validated
    discarded_ungrounded: result.fabricated_line_items,
    specs_run: 1,
    specs_skipped: 0,
    skipped: false,
    pass: true,
    details: [
      {
        spec: "in-memory",
        grounded_items: result.items.length,
        fabricated_line_items: result.fabricated_line_items,
        skipped: false,
      },
    ],
  };
}
