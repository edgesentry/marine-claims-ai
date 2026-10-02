/**
 * Client-side PDF text + bbox extraction (browser / Vite).
 * Repair heuristics live in repairLines.ts.
 */
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { PdfCoordinates } from "../schemas/envelope";
import type { PdfContent, PdfPageContent, PdfTextItem } from "../pipeline/pdfLocate";
import { locateQuoteInPdfSafe } from "../pipeline/pdfLocate";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

export type { PdfContent, PdfPageContent, PdfTextItem };
export { locateQuoteInPdfSafe };

function itemBBox(
  page: number,
  transform: number[],
  width: number,
  height: number,
): PdfCoordinates {
  const x = transform[4] ?? 0;
  const y = transform[5] ?? 0;
  const sx = Math.hypot(transform[0] ?? 0, transform[1] ?? 0) || 1;
  const sy = Math.hypot(transform[2] ?? 0, transform[3] ?? 0) || height || 1;
  const w = width > 0 ? width : sx * Math.max(1, height || 1);
  const h = height > 0 ? height : sy;
  return {
    page,
    x0: x,
    y0: y,
    x1: x + w,
    y1: y + h,
  };
}

/** Full text + per-item bboxes (Issue #88). */
export async function extractPdfContent(
  file: File | ArrayBuffer,
): Promise<PdfContent> {
  const data = file instanceof File ? await file.arrayBuffer() : file;
  const doc = await pdfjs.getDocument({ data }).promise;
  const pages: PdfPageContent[] = [];
  const textParts: string[] = [];

  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const content = await page.getTextContent();
    const items: PdfTextItem[] = [];
    const lineParts: string[] = [];

    for (const raw of content.items) {
      if (!("str" in raw)) continue;
      const str = String(raw.str ?? "");
      if (!str) continue;
      const transform = Array.isArray(raw.transform)
        ? (raw.transform as number[])
        : [1, 0, 0, 1, 0, 0];
      const width = typeof raw.width === "number" ? raw.width : 0;
      const height = typeof raw.height === "number" ? raw.height : 0;
      items.push({
        str,
        bbox: itemBBox(i, transform, width, height),
      });
      lineParts.push(str);
    }

    const text = lineParts.join(" ");
    pages.push({ page: i, items, text });
    textParts.push(text);
  }

  return { text: textParts.join("\n"), pages };
}

/** Back-compat: concatenated PDF text only. */
export async function extractPdfText(file: File | ArrayBuffer): Promise<string> {
  const content = await extractPdfContent(file);
  return content.text;
}

export {
  extractRepairItemsFromText,
  repairItemsToRuleDLines,
  syntheticUc2Lines,
  type ExtractedItem,
} from "./repairLines";
