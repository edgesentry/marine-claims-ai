/**
 * Confidence gate unit tests (Issue #89).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  assessConfidence,
  applyConfidenceGate,
  assertConfidenceForStageB,
  logAbstain,
  resolveConfidenceMode,
  ConfidenceValidationError,
} from "../src/pipeline/confidenceGate";
import { buildRuleD5Extraction, buildColregsExtraction } from "../src/schemas";

describe("resolveConfidenceMode", () => {
  it("defaults paste_bypass → bypass and require_span → enforce", () => {
    expect(resolveConfidenceMode("paste_bypass")).toBe("bypass");
    expect(resolveConfidenceMode("require_span")).toBe("enforce");
    expect(resolveConfidenceMode("require_span", "confirmed")).toBe("confirmed");
  });
});

describe("assessConfidence / applyConfidenceGate", () => {
  it("stamps HUMAN_REVIEW_REQUIRED when document confidence is below min", () => {
    const unlocked = buildRuleD5Extraction({
      dockingContext: "casualty_immediate",
      lines: [{ id: "pdf-1", cost: 1000, trade_code: "HULL-01", title: "船首" }],
      confidence: 0.65,
      grounding: [{ field: "lines.pdf-1", source_quote: "船首" }],
      groundingMode: "paste_bypass",
      confidenceMode: "bypass",
    });
    const gated = applyConfidenceGate(unlocked, { mode: "enforce" });
    expect(gated.abstain?.code).toBe("HUMAN_REVIEW_REQUIRED");
    expect(gated.field_confidence?.["lines.pdf-1"]).toBeGreaterThan(0);
    const assessment = assessConfidence(gated);
    expect(assessment.ok).toBe(false);
    expect(assessment.reason_codes).toContain("document_below_min");
  });

  it("passes when document confidence meets engineering default", () => {
    const extraction = buildRuleD5Extraction({
      dockingContext: "casualty_immediate",
      lines: [{ id: "dock-1", cost: 1000, trade_code: "DOCK-01", title: "滞渠" }],
      confidence: 0.85,
      groundingMode: "paste_bypass",
    });
    expect(extraction.abstain).toBeUndefined();
    expect(assessConfidence(extraction).ok).toBe(true);
  });

  it("assertConfidenceForStageB throws under enforce when abstain set", () => {
    const low = buildColregsExtraction({
      geometry: {
        heading_a_deg: 0,
        heading_b_deg: 180,
        true_bearing_a_to_b_deg: 0,
      },
      confidence: 0.4,
      groundingMode: "paste_bypass",
      confidenceMode: "bypass",
    });
    const withAbstain = applyConfidenceGate(low, { mode: "enforce" });
    expect(() =>
      assertConfidenceForStageB(withAbstain, { mode: "enforce" }),
    ).toThrow(ConfidenceValidationError);
    expect(
      assertConfidenceForStageB(withAbstain, { mode: "confirmed" }).confidence,
    ).toBe(0.4);
  });

  it("flags field_below_min when critical field_confidence is low", () => {
    const base = buildRuleD5Extraction({
      dockingContext: "casualty_immediate",
      lines: [{ id: "pdf-1", cost: 1000, trade_code: "HULL-01", title: "船首" }],
      confidence: 0.9,
      grounding: [{ field: "lines.pdf-1", source_quote: "船首" }],
      field_confidence: { "lines.pdf-1": 0.2 },
      groundingMode: "paste_bypass",
      confidenceMode: "bypass",
    });
    const assessment = assessConfidence(base);
    expect(assessment.ok).toBe(false);
    expect(assessment.reason_codes.some((c) => c.startsWith("field_below_min:"))).toBe(
      true,
    );
  });
});

describe("logAbstain Zero-Dataset hygiene", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("logs reason codes and numeric confidence only (no source quotes)", () => {
    const spy = vi.spyOn(console, "info").mockImplementation(() => {});
    logAbstain({
      schema_id: "rule_d5.v1",
      document_confidence: 0.65,
      reason_codes: ["document_below_min"],
    });
    expect(spy).toHaveBeenCalledTimes(1);
    const payload = String(spy.mock.calls[0]?.[0] ?? "");
    expect(payload).toContain("stage_a_abstain");
    expect(payload).toContain("document_below_min");
    expect(payload).not.toMatch(/船首|source_quote|hull plating/i);
  });
});
