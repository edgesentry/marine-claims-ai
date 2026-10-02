/**
 * Shared core runners (PWA + CLI) — Issue #87 Stage A gate + Stage B score.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  runColregs,
  runPscFixture,
  runRuleD5,
  runRuleD5Synthetic,
} from "../src/core";
import type { PscFixturesFile } from "../src/engines/psc";

const __dirname = dirname(fileURLToPath(import.meta.url));

describe("core runners", () => {
  it("runRuleD5Synthetic returns gated envelope + apportionment", () => {
    const result = runRuleD5Synthetic({
      dockingContext: "deferred_to_routine",
      dailyDockRate: 450_000,
      dockDays: 7,
      includeStatutory: true,
      hireRate: 800_000,
      legacyLeadDays: 14,
      aiLeadMinutes: 30,
    });
    expect(result.status).toBe("scored");
    if (result.status !== "scored") return;
    expect(result.extraction.schema_id).toBe("rule_d5.v1");
    expect(result.apportionment.lines.length).toBeGreaterThan(0);
    expect(result.apportionment.insurer_total + result.apportionment.owner_total).toBe(
      result.apportionment.claimed_total,
    );
  });

  it("runRuleD5 rejects empty lines via schema", () => {
    expect(() =>
      runRuleD5({
        dockingContext: "casualty_immediate",
        lines: [],
      }),
    ).toThrow(/Invalid ExtractionResult|at least/i);
  });

  it("runColregs classifies head-on geometry", () => {
    const result = runColregs({
      geometry: {
        heading_a_deg: 0,
        heading_b_deg: 180,
        true_bearing_a_to_b_deg: 0,
      },
      factsExcerpt: "両船は行会いの関係",
    });
    expect(result.status).toBe("scored");
    if (result.status !== "scored") return;
    expect(result.extraction.schema_id).toBe("colregs.v1");
    expect(result.verdict.situation).toBe("head_on");
  });

  it("runPscFixture scores bundled fixture through Stage A", () => {
    const path = resolve(__dirname, "../../config/psc_inspection_fixtures.json");
    const fixtures = JSON.parse(readFileSync(path, "utf-8")) as PscFixturesFile;
    const fixture = fixtures.cases.find((c) => c.id === "repeat_ism_major");
    expect(fixture).toBeTruthy();
    const result = runPscFixture(fixture!, { lookbackMonths: 24 });
    expect(result.status).toBe("scored");
    if (result.status !== "scored") return;
    expect(result.extraction.schema_id).toBe("psc.v1");
    expect(result.report.defect_score).toBeGreaterThan(0);
  });
});
