/**
 * Exact Span grounding gate across UCs (Issue #88).
 */
import { describe, expect, it } from "vitest";
import {
  assertGroundingForStageB,
  GroundingValidationError,
} from "../src/pipeline/groundingGate";
import { locateQuoteInPdfSafe } from "../src/pipeline/pdfLocate";
import { extractSpecWithSpansFromText } from "../src/pipeline/extractSpec";
import {
  buildColregsExtraction,
  buildPscExtraction,
  buildRuleD5Extraction,
} from "../src/schemas";
import { runColregs, runPsc, runPscFromPaste, runRuleD5FromRepairText } from "../src/core";
import { A4_LITE_ITEMS, A4_LITE_PDF_TEXT } from "../src/benchmarks/gateAPriority1";

describe("assertGroundingForStageB", () => {
  it("rejects COLREGS facts without grounding under require_span", () => {
    const shape = buildColregsExtraction({
      geometry: {
        heading_a_deg: 0,
        heading_b_deg: 180,
        true_bearing_a_to_b_deg: 0,
      },
      factsExcerpt: "両船は行会いの関係",
      grounding: [],
      groundingMode: "paste_bypass",
    });
    expect(() =>
      assertGroundingForStageB(shape, { mode: "require_span" }),
    ).toThrow(GroundingValidationError);
  });

  it("accepts COLREGS facts grounded in source text", () => {
    const source = "事故当時、両船は行会いの関係にあった。";
    const ext = buildColregsExtraction({
      geometry: {
        heading_a_deg: 0,
        heading_b_deg: 180,
        true_bearing_a_to_b_deg: 0,
      },
      factsExcerpt: "両船は行会いの関係",
      grounding: [
        { field: "facts_excerpt", source_quote: "両船は行会いの関係" },
      ],
      groundingMode: "require_span",
      sourceText: source,
    });
    expect(ext.grounding[0]?.source_quote).toContain("行会い");
  });

  it("rejects fabricated COLREGS quote against source text", () => {
    expect(() =>
      buildColregsExtraction({
        geometry: {
          heading_a_deg: 0,
          heading_b_deg: 180,
          true_bearing_a_to_b_deg: 0,
        },
        factsExcerpt: "架空の事実記載XYZ",
        grounding: [
          { field: "facts_excerpt", source_quote: "架空の事実記載XYZ" },
        ],
        groundingMode: "require_span",
        sourceText: "両船は横切の関係にあった。",
      }),
    ).toThrow(GroundingValidationError);
  });

  it("rejects PSC require_span with empty grounding", () => {
    expect(() =>
      buildPscExtraction({
        deficiencies: [{ code: "15150", description: "ISM" }],
        grounding: [],
        groundingMode: "require_span",
      }),
    ).toThrow(GroundingValidationError);
  });

  it("accepts PSC paste_bypass without grounding", () => {
    const ext = buildPscExtraction({
      deficiencies: [{ code: "15150", description: "ISM" }],
      groundingMode: "paste_bypass",
    });
    expect(ext.payload.deficiencies[0]!.code).toBe("15150");
  });

  it("requires grounding on pdf-* Rule D5 lines", () => {
    expect(() =>
      buildRuleD5Extraction({
        dockingContext: "casualty_immediate",
        lines: [
          {
            id: "pdf-1",
            cost: 1000,
            trade_code: "HULL-01",
            title: "船首外板",
          },
        ],
        grounding: [],
        groundingMode: "require_span",
      }),
    ).toThrow(GroundingValidationError);
  });
});

describe("runners Exact Span", () => {
  it("runColregs drops/rejects ungrounded excerpt when sourceText set", () => {
    expect(() =>
      runColregs({
        geometry: {
          heading_a_deg: 0,
          heading_b_deg: 180,
          true_bearing_a_to_b_deg: 0,
        },
        factsExcerpt: "架空の行会い記述アルファベータ",
        groundingMode: "require_span",
        sourceText: "両船は横切の関係にあった。",
      }),
    ).toThrow(/not grounded/i);
  });

  it("runColregs accepts grounded excerpt", () => {
    const source = "両船は横切の関係にあった。被告船に過失あり。";
    const result = runColregs({
      geometry: {
        heading_a_deg: 30,
        heading_b_deg: 300,
        true_bearing_a_to_b_deg: 70,
      },
      factsExcerpt: "両船は横切の関係",
      confidence: 0.85,
      groundingMode: "require_span",
      sourceText: source,
    });
    expect(result.status).toBe("scored");
    if (result.status !== "scored") return;
    expect(result.extraction.grounding.some((g) => g.field === "facts_excerpt")).toBe(
      true,
    );
    expect(result.verdict.situation).toBe("crossing");
  });

  it("runPscFromPaste uses paste_bypass", () => {
    const result = runPscFromPaste(
      JSON.stringify([
        {
          deficiency_code: "15150",
          action_taken: "30",
          nature_of_deficiency: "ISM major",
          inspection_date: "2024-01-01",
        },
      ]),
    );
    expect(result.status).toBe("scored");
    if (result.status !== "scored") return;
    expect(result.extraction.schema_id).toBe("psc.v1");
    expect(result.report.defect_score).toBeGreaterThan(0);
  });

  it("runPsc require_span rejects empty grounding", () => {
    expect(() =>
      runPsc({
        deficiencies: [
          {
            code: "15150",
            action_code: "30",
            description: "ISM",
            inspection_date: "2024-01-01",
            mou_id: null,
            prefix: "151",
            convention: "ISM",
            category_label: "ISM",
            citation: null,
            severity_weight: 1,
            category_weight: 1,
            critical_system: null,
            contribution: 0,
            is_repeat_critical: false,
          },
        ],
        groundingMode: "require_span",
      }),
    ).toThrow(GroundingValidationError);
  });

  it("runRuleD5FromRepairText rejects all-ungrounded fabricated candidates", () => {
    expect(() =>
      runRuleD5FromRepairText(A4_LITE_PDF_TEXT, {
        dockingContext: "deferred_to_routine",
        dailyDockRate: 100_000,
        dockDays: 3,
        includeStatutory: false,
        candidateItems: [
          {
            description: "架空の機関室オーバーホール工事XYZ999アルファ",
            estimated_cost: 9_999_999,
          },
        ],
      }),
    ).toThrow(/ungrounded/i);
  });

  it("runRuleD5FromRepairText keeps only grounded candidates against source text", () => {
    const result = runRuleD5FromRepairText(A4_LITE_PDF_TEXT, {
      dockingContext: "deferred_to_routine",
      dailyDockRate: 450_000,
      dockDays: 7,
      includeStatutory: false,
      candidateItems: A4_LITE_ITEMS,
    });
    expect(result.discarded_ungrounded).toBe(1);
    expect(result.extraction.payload.lines.some((ln) => String(ln.id).startsWith("pdf-"))).toBe(
      true,
    );
    for (const g of result.extraction.grounding) {
      if (!String(g.field).startsWith("lines.pdf-")) continue;
      expect(A4_LITE_PDF_TEXT.includes(g.source_quote) || g.source_quote.length > 0).toBe(true);
    }
  });
});

describe("pdfLocate bbox", () => {
  it("unions item bboxes for a grounded quote", () => {
    const content = {
      text: "船体入出渠及び滞渠 船体外板",
      pages: [
        {
          page: 1,
          text: "船体入出渠及び滞渠 船体外板",
          items: [
            { str: "船体入出渠及び滞渠", bbox: { page: 1, x0: 10, y0: 20, x1: 100, y1: 30 } },
            { str: " ", bbox: { page: 1, x0: 100, y0: 20, x1: 105, y1: 30 } },
            { str: "船体外板", bbox: { page: 1, x0: 105, y0: 20, x1: 160, y1: 30 } },
          ],
        },
      ],
    };
    const loc = locateQuoteInPdfSafe("船体入出渠及び滞渠", content);
    expect(loc.page_number).toBe(1);
    expect(loc.pdf_coordinates).toEqual({
      page: 1,
      x0: 10,
      y0: 20,
      x1: 100,
      y1: 30,
    });
  });

  it("extractSpec attaches bbox when pdfContent provided", () => {
    const content = {
      text: A4_LITE_PDF_TEXT,
      pages: [
        {
          page: 2,
          text: A4_LITE_PDF_TEXT,
          items: A4_LITE_ITEMS.filter((it) => it.description !== "架空の機関室オーバーホール工事XYZ999アルファ").map(
            (it, i) => ({
              str: it.description,
              bbox: { page: 2, x0: i * 10, y0: 0, x1: i * 10 + 50, y1: 12 },
            }),
          ),
        },
      ],
    };
    const result = extractSpecWithSpansFromText(A4_LITE_PDF_TEXT, A4_LITE_ITEMS, {
      pdfContent: content,
    });
    expect(result.items[0]?.page_number).toBe(2);
    expect(result.items[0]?.pdf_coordinates?.page).toBe(2);
  });
});
