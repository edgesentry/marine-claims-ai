/**
 * In-browser OCR for image-only / scanned PDFs (Issue #94).
 * Renders pages with pdf.js, recognizes with Tesseract.js (jpn+eng).
 * Traineddata + WASM are same-origin under public/ for airplane mode.
 */
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { createWorker, type Worker } from "tesseract.js";
import tesseractWorkerUrl from "tesseract.js/dist/worker.min.js?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

export type PdfExtractionSource = "text_layer" | "ocr";

export interface OcrPageResult {
  page: number;
  text: string;
  confidence: number;
}

export interface OcrPdfResult {
  text: string;
  pages: OcrPageResult[];
  source: "ocr";
  /** Mean page confidence in 0–1 (Tesseract reports 0–100). */
  meanConfidence: number;
}

export interface ExtractPdfWithOcrResult {
  text: string;
  source: PdfExtractionSource;
  /** Present when source === "ocr". */
  meanConfidence?: number;
  pages?: OcrPageResult[];
  /** Set when OCR was attempted and failed (network / WASM / empty). */
  error?: string;
}

export interface OcrProgress {
  status: string;
  progress: number;
}

const MAX_OCR_PAGES = 12;
/** Keep moderate for browser memory; synthetic A4 @ 1.5 is enough for yen lines. */
const RENDER_SCALE = 1.5;

/** Stage A document confidence when text came from OCR (below document_min → HUMAN_REVIEW). */
export const OCR_STAGE_A_CONFIDENCE = 0.52;

/** Text-layer PDF uploads (existing demo default). */
export const TEXT_LAYER_STAGE_A_CONFIDENCE = 0.65;

function publicBase(): string {
  const base = import.meta.env.BASE_URL || "./";
  return base.endsWith("/") ? base : `${base}/`;
}

function resolvePublic(rel: string): string {
  // Ensure directory paths end with `/` so tesseract.js joins filenames correctly.
  const href = new URL(rel, new URL(publicBase(), window.location.href)).href;
  if (rel.endsWith("/") || /\.[a-z0-9]+$/i.test(rel.split("/").pop() || "")) {
    return href;
  }
  return href.endsWith("/") ? href : `${href}/`;
}

let sharedWorker: Worker | null = null;
let workerPromise: Promise<Worker> | null = null;

async function getOcrWorker(
  onProgress?: (p: OcrProgress) => void,
): Promise<Worker> {
  if (sharedWorker) return sharedWorker;
  if (workerPromise) return workerPromise;

  workerPromise = (async () => {
    const workerUrl = new URL(tesseractWorkerUrl, window.location.href).href;
    const worker = await createWorker("jpn+eng", 1, {
      workerPath: workerUrl,
      corePath: resolvePublic("tesseract"),
      langPath: resolvePublic("tessdata"),
      workerBlobURL: false,
      logger: (m) => {
        if (typeof m.progress === "number" && onProgress) {
          onProgress({
            status: String(m.status || "ocr"),
            progress: m.progress,
          });
        }
      },
    });
    sharedWorker = worker;
    return worker;
  })();

  try {
    return await workerPromise;
  } catch (err) {
    workerPromise = null;
    sharedWorker = null;
    console.error("[ocr] createWorker failed", err);
    throw err;
  }
}

/** Terminate cached worker (tests / teardown). */
export async function terminateOcrWorker(): Promise<void> {
  if (sharedWorker) {
    await sharedWorker.terminate();
    sharedWorker = null;
  }
  workerPromise = null;
}

/**
 * Render PDF pages to canvases and OCR them.
 * Requires a browser (canvas + Worker). Node/Vitest should mock this module.
 */
export async function ocrPdfPages(
  file: File | ArrayBuffer,
  opts?: {
    maxPages?: number;
    onProgress?: (p: OcrProgress) => void;
  },
): Promise<OcrPdfResult> {
  const data = file instanceof File ? await file.arrayBuffer() : file;
  const doc = await pdfjs.getDocument({ data }).promise;
  const maxPages = Math.min(doc.numPages, opts?.maxPages ?? MAX_OCR_PAGES);
  const worker = await getOcrWorker(opts?.onProgress);

  const pages: OcrPageResult[] = [];
  const textParts: string[] = [];

  for (let i = 1; i <= maxPages; i++) {
    opts?.onProgress?.({
      status: `render_page_${i}`,
      progress: (i - 1) / maxPages,
    });
    const page = await doc.getPage(i);
    const viewport = page.getViewport({ scale: RENDER_SCALE });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D context unavailable for OCR");

    await page.render({ canvasContext: ctx, viewport }).promise;
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error("canvas.toBlob failed"))),
        "image/png",
      );
    });

    const ret = await worker.recognize(blob);
    const text = (ret.data.text || "").trim();
    const confidence = Math.max(0, Math.min(100, Number(ret.data.confidence) || 0));
    pages.push({ page: i, text, confidence });
    if (text) textParts.push(text);
  }

  const meanRaw =
    pages.length > 0
      ? pages.reduce((s, p) => s + p.confidence, 0) / pages.length
      : 0;

  return {
    text: textParts.join("\n\n"),
    pages,
    source: "ocr",
    meanConfidence: meanRaw / 100,
  };
}

/**
 * Prefer PDF text layer; fall back to in-browser OCR when empty (Issue #94).
 * Inject `extractText` / `ocr` in Vitest to avoid canvas + WASM.
 */
export async function extractPdfTextWithOcr(
  file: File | ArrayBuffer,
  opts: {
    extractText: (f: File | ArrayBuffer) => Promise<string>;
    ocr?: typeof ocrPdfPages;
    onProgress?: (p: OcrProgress) => void;
  },
): Promise<ExtractPdfWithOcrResult> {
  const text = await opts.extractText(file);
  if (text.trim()) {
    return { text, source: "text_layer" };
  }

  const runOcr = opts.ocr ?? ocrPdfPages;
  try {
    const ocr = await runOcr(file, { onProgress: opts.onProgress });
    if (!ocr.text.trim()) {
      return {
        text: "",
        source: "ocr",
        meanConfidence: ocr.meanConfidence,
        pages: ocr.pages,
        error: "ocr_empty",
      };
    }
    return {
      text: ocr.text,
      source: "ocr",
      meanConfidence: ocr.meanConfidence,
      pages: ocr.pages,
    };
  } catch (err) {
    console.error("[ocr] extractPdfTextWithOcr failed", err);
    return {
      text: "",
      source: "ocr",
      meanConfidence: 0,
      pages: [],
      error: err instanceof Error ? err.message : "ocr_failed",
    };
  }
}

/** Map extraction source → Stage A confidence for #89 gate. */
export function stageAConfidenceForSource(
  source: PdfExtractionSource,
): number {
  return source === "ocr"
    ? OCR_STAGE_A_CONFIDENCE
    : TEXT_LAYER_STAGE_A_CONFIDENCE;
}
