import { describe, expect, it } from "vitest";
import geometries from "./fixtures/collision_geometries.json";
import {
  evaluateA5A6FromGeometries,
  evaluateA7Civil,
  runGateAPriority2Lite,
  type ColregsCaseFixture,
} from "../src/benchmarks/gateAPriority2";

describe("gateAPriority2 COLREGS lite", () => {
  const cases = (geometries.cases as Array<Record<string, unknown>>).map((c) => ({
    case_id: String(c.id ?? ""),
    heading_a_deg: Number(c.heading_a_deg),
    heading_b_deg: Number(c.heading_b_deg),
    true_bearing_a_to_b_deg: Number(c.true_bearing_a_to_b_deg),
    expected_situation: String(c.expected_situation),
    expected_role_a: c.expected_role_a ? String(c.expected_role_a) : undefined,
    expected_role_b: c.expected_role_b ? String(c.expected_role_b) : undefined,
  })) as ColregsCaseFixture[];

  it("A5 situation agreement ≥ 0.9 on geometry fixtures", () => {
    const report = evaluateA5A6FromGeometries(cases);
    expect(Number(report.cases_run)).toBeGreaterThan(0);
    expect(Number(report.situation_agreement)).toBeGreaterThanOrEqual(0.9);
    expect(report.a5_pass).toBe(true);
    expect(Number(report.critical_role_inversions)).toBe(0);
    expect(report.a6_pass).toBe(true);
  });

  it("A7 civil offline extraction passes thresholds", () => {
    const a7 = evaluateA7Civil();
    expect(a7.primary_mode).toBe("offline_snippets");
    expect(Number(a7.accuracy)).toBeGreaterThanOrEqual(0.9);
    expect(Number(a7.fault_ratio_within_10pt_rate)).toBeGreaterThanOrEqual(0.8);
    expect(a7.accuracy_pass).toBe(true);
    expect(a7.within_10pt_pass).toBe(true);
    expect(a7.pass).toBe(true);
  });

  it("lite Gate A P2 overall pass", () => {
    const report = runGateAPriority2Lite(cases);
    expect((report.gate as Record<string, unknown>).overall_pass).toBe(true);
    expect((report.gate as Record<string, unknown>).critical_role_inversions).toBe(0);
    expect((report.metrics as Record<string, unknown>).A7).toBeDefined();
    expect(
      ((report.metrics as Record<string, unknown>).A7 as Record<string, unknown>)
        .pass,
    ).toBe(true);
  });
});
