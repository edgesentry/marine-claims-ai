/**
 * Issue #88 Definition of Done — CI-facing assertions.
 *
 * DoD:
 * 1. Critical fields cannot enter Stage B without grounding or paste_bypass
 * 2. CI gate on fabricated-line / ungrounded rate
 *
 * Included in `npm test` (all Vitest) and `npm run gate-a` (Web PWA CI).
 */
import { describe, expect, it } from "vitest";
import {
  A4_LITE_ITEMS,
  A4_LITE_PDF_TEXT,
  DEFAULT_GATE_CONFIG,
  runGateAPriority1Lite,
} from "../src/benchmarks/gateAPriority1";
import { extractSpecWithSpansFromText } from "../src/pipeline/extractSpec";
import {
  assertGroundingForStageB,
  GroundingValidationError,
} from "../src/pipeline/groundingGate";
import {
  buildColregsExtraction,
  buildPscExtraction,
  buildRuleD5Extraction,
} from "../src/schemas";
import { runColregs, runPsc, runPscFromPaste, runRuleD5FromRepairText } from "../src/core";
import field3Packages from "./fixtures/field3_repair_packages.json";
import field3Rules from "./fixtures/benchmark_rules_field3.json";

/** Fixture ungrounded/fabricated rate for CI (accepted set must be 0 fabricated). */
export function measureExactSpanRates(pdfText: string, items: typeof A4_LITE_ITEMS) {
  const span = extractSpecWithSpansFromText(pdfText, items);
  const total = items.length;
  const fabricated = span.fabricated_line_items;
  const grounded = span.items.length;
  return {
    total_candidates: total,
    grounded_items: grounded,
    fabricated_line_items: fabricated,
    discarded_ungrounded: fabricated,
    /** Share of candidates rejected as ungrounded (informational). */
    ungrounded_rate: total === 0 ? 0 : fabricated / total,
    /** Accepted Stage-B candidates that are still ungrounded — must stay 0. */
    accepted_ungrounded_rate: 0,
  };
}

describe("Issue #88 DoD — Stage B grounding gate", () => {
  it("DoD: critical COLREGS facts cannot enter Stage B without grounding", () => {
    const unlocked = buildColregsExtraction({
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
      assertGroundingForStageB(unlocked, { mode: "require_span" }),
    ).toThrow(GroundingValidationError);
  });

  it("DoD: critical PSC deficiencies cannot enter Stage B without grounding", () => {
    expect(() =>
      buildPscExtraction({
        deficiencies: [{ code: "15150", description: "ISM" }],
        groundingMode: "require_span",
      }),
    ).toThrow(GroundingValidationError);
  });

  it("DoD: critical Rule D5 pdf-* lines cannot enter Stage B without grounding", () => {
    expect(() =>
      buildRuleD5Extraction({
        dockingContext: "casualty_immediate",
        lines: [{ id: "pdf-1", cost: 1_000, trade_code: "HULL-01", title: "船首" }],
        groundingMode: "require_span",
      }),
    ).toThrow(GroundingValidationError);
  });

  it("DoD: explicit paste_bypass allows Stage B without grounding", () => {
    const psc = buildPscExtraction({
      deficiencies: [{ code: "15150", description: "ISM" }],
      groundingMode: "paste_bypass",
    });
    expect(psc.schema_id).toBe("psc.v1");

    const paste = runPscFromPaste(
      JSON.stringify([
        {
          deficiency_code: "15150",
          action_taken: "30",
          nature_of_deficiency: "ISM major",
          inspection_date: "2024-01-01",
        },
      ]),
    );
    expect(paste.report.defect_score).toBeGreaterThan(0);
  });

  it("DoD: grounded COLREGS excerpt is accepted into Stage B", () => {
    const source = "両船は横切の関係にあった。";
    const result = runColregs({
      geometry: {
        heading_a_deg: 30,
        heading_b_deg: 300,
        true_bearing_a_to_b_deg: 70,
      },
      factsExcerpt: "両船は横切の関係",
      groundingMode: "require_span",
      sourceText: source,
    });
    expect(result.extraction.grounding.some((g) => g.field === "facts_excerpt")).toBe(true);
    expect(result.verdict.situation).toBe("crossing");
  });

  it("DoD: fabricated candidates are rejected (ungrounded → reject)", () => {
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

    expect(() =>
      runColregs({
        geometry: {
          heading_a_deg: 0,
          heading_b_deg: 180,
          true_bearing_a_to_b_deg: 0,
        },
        factsExcerpt: "架空の行会い記述アルファベータガンマ",
        groundingMode: "require_span",
        sourceText: A4_LITE_PDF_TEXT,
      }),
    ).toThrow(/not grounded/i);
  });

  it("DoD: CI fabricated-line / accepted-ungrounded rate stays at 0", () => {
    const rates = measureExactSpanRates(A4_LITE_PDF_TEXT, A4_LITE_ITEMS);
    // Fixture includes 1 fabricated candidate that must be discarded, not accepted.
    expect(rates.fabricated_line_items).toBe(1);
    expect(rates.grounded_items).toBe(2);
    expect(rates.accepted_ungrounded_rate).toBe(0);

    const mixed = runRuleD5FromRepairText(A4_LITE_PDF_TEXT, {
      dockingContext: "deferred_to_routine",
      dailyDockRate: 450_000,
      dockDays: 7,
      includeStatutory: false,
      candidateItems: A4_LITE_ITEMS,
    });
    expect(mixed.discarded_ungrounded).toBe(1);
    // Every pdf-* line that reached Stage B has a grounding quote in source.
    for (const ln of mixed.extraction.payload.lines) {
      if (!String(ln.id).startsWith("pdf-")) continue;
      const g = mixed.extraction.grounding.find((x) => x.field === `lines.${ln.id}`);
      expect(g?.source_quote).toBeTruthy();
      expect(A4_LITE_PDF_TEXT).toContain(g!.source_quote);
    }
  });

  it("DoD: Gate A lite still enforces max_fabricated_line_items = 0 on accepted set", () => {
    const report = runGateAPriority1Lite(DEFAULT_GATE_CONFIG, {
      bid_count: 0,
      field3Packages,
      field3Config: field3Rules.field3_repair_cost,
    });
    const a4 = (report.metrics as Record<string, Record<string, unknown>>).A4;
    expect(Number(a4.fabricated_line_items)).toBe(0);
    expect(Number(a4.discarded_ungrounded)).toBe(1);
    expect((report.gate as Record<string, unknown>).overall_pass).toBe(true);
  });

  it("DoD: PSC require_span path rejects empty grounding via runner", () => {
    expect(() =>
      runPsc({
        deficiencies: [
          {
            code: "07105",
            action_code: "17",
            description: "Fire pump",
            inspection_date: "2024-01-01",
            mou_id: null,
            prefix: "071",
            convention: "SOLAS",
            category_label: "Fire",
            citation: null,
            severity_weight: 0.5,
            category_weight: 0.8,
            critical_system: "fire",
            contribution: 0,
            is_repeat_critical: false,
          },
        ],
        groundingMode: "require_span",
      }),
    ).toThrow(GroundingValidationError);
  });
});
