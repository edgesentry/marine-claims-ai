/**
 * Locate grounded quotes in extracted PDF content (no pdf.js dependency).
 */
import type { PdfCoordinates } from "../schemas/envelope";
import { normalizeSpanText, quoteInText } from "./spanValidate";

export interface PdfTextItem {
  str: string;
  bbox: PdfCoordinates;
}

export interface PdfPageContent {
  page: number;
  items: PdfTextItem[];
  text: string;
}

export interface PdfContent {
  text: string;
  pages: PdfPageContent[];
}

/** Locate a grounded quote; return page + union bbox when item spans match. */
export function locateQuoteInPdfSafe(
  quote: string,
  content: PdfContent,
): { page_number: number | null; pdf_coordinates: PdfCoordinates | null } {
  const q = (quote || "").trim();
  if (!q) return { page_number: null, pdf_coordinates: null };

  for (const page of content.pages) {
    if (!quoteInText(q, page.text)) continue;

    const nQuote = normalizeSpanText(q);
    if (!nQuote) {
      return { page_number: page.page, pdf_coordinates: null };
    }

    const matched: PdfTextItem[] = [];
    let accNorm = "";
    for (const item of page.items) {
      const piece = normalizeSpanText(item.str);
      if (!piece) continue;
      accNorm += piece;
      matched.push(item);
      if (accNorm.includes(nQuote)) break;
    }

    if (!matched.length || !normalizeSpanText(page.text).includes(nQuote)) {
      return { page_number: page.page, pdf_coordinates: null };
    }
    if (!accNorm.includes(nQuote)) {
      return { page_number: page.page, pdf_coordinates: null };
    }

    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    for (const m of matched) {
      x0 = Math.min(x0, m.bbox.x0);
      y0 = Math.min(y0, m.bbox.y0);
      x1 = Math.max(x1, m.bbox.x1);
      y1 = Math.max(y1, m.bbox.y1);
    }
    return {
      page_number: page.page,
      pdf_coordinates: { page: page.page, x0, y0, x1, y1 },
    };
  }

  if (quoteInText(q, content.text)) {
    return { page_number: null, pdf_coordinates: null };
  }
  return { page_number: null, pdf_coordinates: null };
}
