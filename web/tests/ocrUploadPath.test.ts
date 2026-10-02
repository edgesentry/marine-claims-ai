/**
 * Issue #94 — OCR fallback into Rule D5 Stage A (mocked Tesseract; no WASM in CI).
 *
 * DoD: empty text layer → OCR text → schema-valid repair lines with HUMAN_REVIEW.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { runRuleD5FromRepairText } from "../src/core";
import {
  extractPdfTextWithOcr,
  OCR_STAGE_A_CONFIDENCE,
  stageAConfidenceForSource,
  TEXT_LAYER_STAGE_A_CONFIDENCE,
  type OcrPdfResult,
} from "../src/pdf/ocrPages";
import { extractRepairItemsFromText } from "../src/pdf/repairLines";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SYNTHETIC_OCR_TEXT = readFileSync(
  resolve(__dirname, "fixtures/ocr_scan_synthetic/repair_lines.txt"),
  "utf8",
);

describe("Issue #94 — OCR upload path", () => {
  it("prefers text layer when present (no OCR call)", async () => {
    let ocrCalls = 0;
    const result = await extractPdfTextWithOcr(new ArrayBuffer(0), {
      extractText: async () => "甲板部 外板補修 100,000円",
      ocr: async () => {
        ocrCalls += 1;
        throw new Error("OCR should not run");
      },
    });
    expect(result.source).toBe("text_layer");
    expect(result.text).toContain("外板");
    expect(ocrCalls).toBe(0);
    expect(stageAConfidenceForSource(result.source)).toBe(
      TEXT_LAYER_STAGE_A_CONFIDENCE,
    );
  });

  it("falls back to OCR when text layer is empty", async () => {
    const fakeOcr: OcrPdfResult = {
      text: SYNTHETIC_OCR_TEXT,
      pages: [{ page: 1, text: SYNTHETIC_OCR_TEXT, confidence: 72 }],
      source: "ocr",
      meanConfidence: 0.72,
    };
    const result = await extractPdfTextWithOcr(new ArrayBuffer(0), {
      extractText: async () => "   \n  ",
      ocr: async () => fakeOcr,
    });
    expect(result.source).toBe("ocr");
    expect(result.text).toContain("球状船首");
    expect(result.meanConfidence).toBeCloseTo(0.72);
    expect(stageAConfidenceForSource(result.source)).toBe(
      OCR_STAGE_A_CONFIDENCE,
    );
  });

  it("returns explicit error when OCR yields empty text", async () => {
    const result = await extractPdfTextWithOcr(new ArrayBuffer(0), {
      extractText: async () => "",
      ocr: async () => ({
        text: "",
        pages: [],
        source: "ocr",
        meanConfidence: 0,
      }),
    });
    expect(result.text.trim()).toBe("");
    expect(result.error).toBe("ocr_empty");
  });

  it("returns error when OCR throws (no silent Stage B)", async () => {
    const result = await extractPdfTextWithOcr(new ArrayBuffer(0), {
      extractText: async () => "",
      ocr: async () => {
        throw new Error("wasm_missing");
      },
    });
    expect(result.text).toBe("");
    expect(result.error).toContain("wasm_missing");
  });

  it("DoD: synthetic OCR fixture → schema-valid lines + HUMAN_REVIEW", () => {
    const items = extractRepairItemsFromText(SYNTHETIC_OCR_TEXT);
    expect(items.length).toBeGreaterThan(0);

    const run = runRuleD5FromRepairText(SYNTHETIC_OCR_TEXT, {
      dockingContext: "casualty_immediate",
      dailyDockRate: 860_000,
      dockDays: 5,
      includeStatutory: true,
      confidence: OCR_STAGE_A_CONFIDENCE,
    });

    expect(run.extraction.schema_id).toBe("rule_d5.v1");
    expect(run.extraction.payload.lines.length).toBeGreaterThan(0);
    expect(run.extraction.confidence).toBe(OCR_STAGE_A_CONFIDENCE);
    expect(run.status).toBe("abstain");
    if (run.status !== "abstain") return;
    expect(run.extraction.abstain?.code).toBe("HUMAN_REVIEW_REQUIRED");
    expect("apportionment" in run).toBe(false);
  });

  it("normalizes OCR yen noise (dot thousands / F9)", async () => {
    const { normalizeOcrYenText, extractRepairItemsFromText: extract } =
      await import("../src/pdf/repairLines");
    expect(normalizeOcrYenText("塗装工事 850.000円")).toContain("850,000");
    expect(normalizeOcrYenText("外板 1200000F9")).toContain("円");
    const items = extract("甲板部 塗装工事 850.000円\n機関部 ピストン 3500000円");
    expect(items.length).toBeGreaterThanOrEqual(2);
    expect(items.some((it) => it.estimated_cost === 850_000)).toBe(true);
  });
});
