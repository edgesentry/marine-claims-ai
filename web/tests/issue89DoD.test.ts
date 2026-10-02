/**
 * Issue #89 Definition of Done — CI-facing assertions.
 *
 * DoD:
 * 1. Silent wrong Stage B on low-confidence extract is impossible in default path
 * 2. confirmed / bypass can score; enforce abstains
 * 3. Abstain logging never includes Zero-Dataset source quotes
 *
 * Included in `npm test` and `npm run gate-a`.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  A4_LITE_ITEMS,
  A4_LITE_PDF_TEXT,
} from "../src/benchmarks/gateAPriority1";
import {
  applyConfidenceGate,
  logAbstain,
} from "../src/pipeline/confidenceGate";
import {
  runColregs,
  runPscFromPaste,
  runRuleD5,
  runRuleD5FromRepairText,
} from "../src/core";
import { buildRuleD5Extraction } from "../src/schemas";

describe("Issue #89 DoD — confidence abstention", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("DoD: low-confidence Rule D5 PDF path never auto-scores", () => {
    const run = runRuleD5FromRepairText(A4_LITE_PDF_TEXT, {
      dockingContext: "deferred_to_routine",
      dailyDockRate: 450_000,
      dockDays: 7,
      includeStatutory: false,
      candidateItems: A4_LITE_ITEMS,
      // Default document confidence is 0.65 < 0.70 engineering min.
    });
    expect(run.status).toBe("abstain");
    if (run.status !== "abstain") return;
    expect(run.extraction.abstain?.code).toBe("HUMAN_REVIEW_REQUIRED");
    expect(run.extraction.payload.lines.length).toBeGreaterThan(0);
    expect("apportionment" in run).toBe(false);
  });

  it("DoD: confirmed mode allows Stage B after human review", () => {
    const run = runRuleD5FromRepairText(A4_LITE_PDF_TEXT, {
      dockingContext: "deferred_to_routine",
      dailyDockRate: 450_000,
      dockDays: 7,
      includeStatutory: false,
      candidateItems: A4_LITE_ITEMS,
      confidence: 0.65,
      confidenceMode: "confirmed",
    });
    expect(run.status).toBe("scored");
    if (run.status !== "scored") return;
    expect(run.apportionment.claimed_total).toBeGreaterThan(0);
    expect(run.extraction.abstain).toBeUndefined();
  });

  it("DoD: low-confidence COLREGS document path abstains (no verdict)", () => {
    const source = "両船は横切の関係にあった。";
    const run = runColregs({
      geometry: {
        heading_a_deg: 30,
        heading_b_deg: 300,
        true_bearing_a_to_b_deg: 70,
      },
      factsExcerpt: "両船は横切の関係",
      confidence: 0.55,
      groundingMode: "require_span",
      sourceText: source,
    });
    expect(run.status).toBe("abstain");
    if (run.status !== "abstain") return;
    expect(run.extraction.abstain?.code).toBe("HUMAN_REVIEW_REQUIRED");
    expect("verdict" in run).toBe(false);
  });

  it("DoD: paste_bypass / synthetic path still auto-scores (confidence bypass)", () => {
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
    expect(paste.status).toBe("scored");

    const synth = runRuleD5({
      dockingContext: "casualty_immediate",
      lines: [
        { id: "dock-1", cost: 100_000, trade_code: "DOCK-01", title: "滞渠" },
        { id: "hull-1", cost: 50_000, trade_code: "HULL-01", title: "船首" },
      ],
      confidence: 0.85,
      groundingMode: "paste_bypass",
    });
    expect(synth.status).toBe("scored");
  });

  it("DoD: abstain log has no source_quote / raw document text", () => {
    const spy = vi.spyOn(console, "info").mockImplementation(() => {});
    const unlocked = buildRuleD5Extraction({
      dockingContext: "casualty_immediate",
      lines: [{ id: "pdf-1", cost: 1_000, trade_code: "HULL-01", title: "船首外板修繕工事" }],
      confidence: 0.5,
      grounding: [{ field: "lines.pdf-1", source_quote: "船首外板修繕工事" }],
      groundingMode: "paste_bypass",
      confidenceMode: "bypass",
    });
    applyConfidenceGate(unlocked, { mode: "enforce" });
    expect(spy).toHaveBeenCalled();
    const joined = spy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(joined).toContain("stage_a_abstain");
    expect(joined).not.toContain("船首外板修繕工事");
    expect(joined).not.toContain("source_quote");

    logAbstain({
      schema_id: "colregs.v1",
      document_confidence: 0.55,
      reason_codes: ["document_below_min"],
    });
    const last = String(spy.mock.calls.at(-1)?.[0] ?? "");
    expect(last).toContain("document_below_min");
    expect(last).not.toMatch(/両船|横切/);
  });
});
