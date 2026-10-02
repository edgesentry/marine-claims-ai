/**
 * Issue #93 — Stage A extraction accuracy harness & CI gates.
 *
 * Separate from Gate A / Stage B rule agreement. Fails CI on Stage A regression.
 * Included in `npm run stage-a` (and `npm test`).
 */
import { describe, expect, it } from "vitest";
import {
  formatStageAReport,
  loadStageAGates,
  loadStageAGoldCases,
  runStageAEval,
} from "../src/benchmarks/stageAEval";

describe("Stage A gold fixtures (Issue #93)", () => {
  it("loads public Zero-Dataset gold with required UCs and tags", () => {
    const cases = loadStageAGoldCases();
    expect(cases.length).toBeGreaterThanOrEqual(12);
    const ucs = new Set(cases.map((c) => c.uc));
    expect(ucs.has("colregs")).toBe(true);
    expect(ucs.has("psc")).toBe(true);
    expect(ucs.has("rule_d5")).toBe(true);
    expect(cases.some((c) => c.tags?.includes("degraded"))).toBe(true);
    expect(cases.some((c) => c.tags?.includes("multilingual"))).toBe(true);
    expect(cases.some((c) => c.expect_abstain)).toBe(true);
  });

  it("loads gate thresholds from config/stage_a_eval.json", () => {
    const cfg = loadStageAGates();
    expect(cfg.gates.min_schema_valid_rate).toBe(1);
    expect(cfg.gates.min_field_exact_match_rate).toBeGreaterThanOrEqual(0.85);
    expect(cfg.gates.min_abstain_precision).toBe(1);
    expect(cfg.gates.degraded?.min_field_exact_match_rate).toBeLessThan(0.85);
  });
});

describe("Stage A eval harness (Issue #93)", () => {
  it("passes overall + degraded + multilingual gates", () => {
    const report = runStageAEval();
    expect(report.overall_pass, formatStageAReport(report)).toBe(true);
    expect(report.overall.schema_valid_rate).toBe(1);
    expect(report.overall.abstain_precision).toBe(1);
    expect(report.overall.abstain_recall).toBe(1);
    expect(report.degraded.field_exact_match_rate).toBeGreaterThanOrEqual(0.4);
    expect(report.multilingual.stage_b_agreement_rate).toBe(1);
  });

  it("reports before/after-style subset metrics for epic #85 citation", () => {
    const report = runStageAEval();
    // Snapshot-style numbers epic #85 can cite (flexibility × precision).
    expect(report.overall.cases).toBeGreaterThanOrEqual(12);
    expect(report.overall.field_exact_match_rate).toBeGreaterThanOrEqual(0.85);
    expect(report.overall.grounding_pass_rate).toBeGreaterThanOrEqual(0.9);
    expect(report.overall.stage_b_agreement_rate).toBeGreaterThanOrEqual(0.9);
    // Degraded OCR (#45/#94) remains the flexibility gap — tracked, not ignored.
    expect(report.degraded.cases).toBeGreaterThanOrEqual(1);
    expect(report.degraded.field_exact_match_rate).toBeLessThan(1);
    expect(report.multilingual.field_exact_match_rate).toBe(1);
  });
});
