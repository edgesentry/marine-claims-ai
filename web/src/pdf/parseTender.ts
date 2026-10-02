/**
 * Client-side PDF text extraction (browser / Vite). Repair heuristics live in repairLines.ts.
 */
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

export async function extractPdfText(file: File | ArrayBuffer): Promise<string> {
  const data = file instanceof File ? await file.arrayBuffer() : file;
  const doc = await pdfjs.getDocument({ data }).promise;
  const parts: string[] = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const content = await page.getTextContent();
    const line = content.items
      .map((it) => ("str" in it ? String(it.str) : ""))
      .join(" ");
    parts.push(line);
  }
  return parts.join("\n");
}

export {
  extractRepairItemsFromText,
  repairItemsToRuleDLines,
  syntheticUc2Lines,
  type ExtractedItem,
} from "./repairLines";
