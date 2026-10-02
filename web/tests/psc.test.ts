import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  DEFICIENCY_CATEGORY_MAP,
  conventionForCode,
  criticalSystemId,
  normalizeActionCode,
  normalizeDeficiencyCode,
  parseInspectionRecord,
  parsePscCsvInput,
  riskBandForReport,
  scoreFixtureCase,
  scoreSeaworthiness,
  type NormalizedDeficiency,
  type PscFixturesFile,
} from "../src/engines/psc";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = resolve(__dirname, "../../config/psc_inspection_fixtures.json");

function loadFixtures(): PscFixturesFile {
  return JSON.parse(readFileSync(FIXTURE_PATH, "utf-8")) as PscFixturesFile;
}

function caseById(fixtures: PscFixturesFile, id: string) {
  const c = fixtures.cases.find((x) => x.id === id);
  if (!c) throw new Error(`missing fixture ${id}`);
  return c;
}

describe("PSC taxonomy", () => {
  it("071 is Fire safety, not navigation; 101 is Safety of Navigation", () => {
    expect(DEFICIENCY_CATEGORY_MAP["071"]!.label).toBe("Fire safety");
    expect(conventionForCode("07106")).toBe("SOLAS II-2");
    expect(DEFICIENCY_CATEGORY_MAP["101"]!.label).toBe("Safety of Navigation");
    expect(conventionForCode("10104")).toBe("SOLAS V");
  });

  it("normalizes codes and action aliases", () => {
    expect(normalizeDeficiencyCode("Item 12: 04102")).toBe("04102");
    expect(normalizeDeficiencyCode("07.106")).toBe("07106");
    expect(normalizeActionCode("Code 30")).toBe("30");
    expect(criticalSystemId(null, "ISM non-conformity")).toBe("ism");
    expect(criticalSystemId(null, "valve mechanism defective")).toBeNull();
  });
});

describe("PSC scoring + lookback", () => {
  const fixtures = loadFixtures();

  it("detention fixture → critical band and Code 30", () => {
    const report = scoreFixtureCase(caseById(fixtures, "paris_detention_emergency_fire_pump"));
    expect(report.detention_present).toBe(true);
    expect(report.defect_score).toBeGreaterThanOrEqual(1.0);
    expect(report.risk_band).toBe("critical");
    expect(report.deficiencies.some((d) => d.action_code === "30")).toBe(true);
  });

  it("repeat_ism_major at 24 months → repeat + critical", () => {
    const report = scoreFixtureCase(caseById(fixtures, "repeat_ism_major"), {
      lookbackMonths: 24,
    });
    expect(report.detention_present).toBe(true);
    expect(report.repeat_critical_flags).toEqual(["ism"]);
    expect(report.defect_score).toBeGreaterThanOrEqual(1.5);
    expect(report.risk_band).toBe("critical");
    expect(report.deficiencies[0]!.is_repeat_critical).toBe(true);
  });

  it("shrink lookback to 6 months → repeat flag clears", () => {
    const report = scoreFixtureCase(caseById(fixtures, "repeat_ism_major"), {
      lookbackMonths: 6,
    });
    expect(report.deficiencies[0]!.is_repeat_critical).toBe(false);
    expect(report.repeat_critical_flags).toEqual([]);
    expect(report.defect_score).toBeCloseTo(1.0, 5);
    expect(report.risk_band).toBe("critical"); // still Code 30
  });

  it("lookback out of default 24-month window does not boost", () => {
    const current: NormalizedDeficiency[] = [
      {
        code: "15109",
        action_code: "30",
        description: "ISM current",
        inspection_date: "2024-06-15",
        mou_id: null,
        prefix: "151",
        convention: "ISM SOLAS IX",
        category_label: "ISM",
        citation: null,
        severity_weight: 1.0,
        category_weight: 1.0,
        critical_system: "ism",
        contribution: 0,
        is_repeat_critical: false,
      },
    ];
    const prior: NormalizedDeficiency[] = [
      {
        ...current[0]!,
        code: "15150",
        action_code: "17",
        description: "ISM stale",
        inspection_date: "2021-06-01",
        severity_weight: 0.5,
      },
    ];
    const report = scoreSeaworthiness(current, { prior });
    expect(report.deficiencies[0]!.is_repeat_critical).toBe(false);
    expect(report.defect_score).toBeCloseTo(1.0, 5);
  });

  it("fire safety fixture is not navigation", () => {
    const report = scoreFixtureCase(caseById(fixtures, "tokyo_fire_safety_not_navigation"));
    const d = report.deficiencies[0]!;
    expect(d.prefix).toBe("071");
    expect(d.category_label).toBe("Fire safety");
    expect(d.convention).toBe("SOLAS II-2");
  });

  it("risk bands: elevated for critical system without detention", () => {
    const report = scoreFixtureCase(caseById(fixtures, "paris_steering_code17"));
    expect(report.detention_present).toBe(false);
    expect(report.deficiencies[0]!.critical_system).toBe("steering_gear");
    expect(report.risk_band).toBe("elevated");
  });

  it("riskBandForReport thresholds", () => {
    expect(
      riskBandForReport({ defectScore: 0.1, detentionPresent: false, hasCriticalSystem: false }),
    ).toBe("low");
    expect(
      riskBandForReport({ defectScore: 0.5, detentionPresent: false, hasCriticalSystem: false }),
    ).toBe("elevated");
    expect(
      riskBandForReport({ defectScore: 0.1, detentionPresent: true, hasCriticalSystem: false }),
    ).toBe("critical");
  });
});

describe("PSC paste parsers", () => {
  it("parses simple CSV", () => {
    const rows = parsePscCsvInput(
      [
        "deficiency_code,action_taken,nature,inspection_date",
        "04102,30,Emergency fire pump,2024-03-12",
      ].join("\n"),
    );
    expect(rows).toHaveLength(1);
    expect(rows[0]!.code).toBe("04102");
    expect(rows[0]!.action_code).toBe("30");
    expect(rows[0]!.critical_system).toBe("emergency_fire_pump");
  });

  it("parses inspection JSON shape", () => {
    const fixtures = loadFixtures();
    const tokyo = caseById(fixtures, "tokyo_navigation_gyro");
    const rows = parseInspectionRecord(tokyo.inspection as Record<string, unknown>);
    expect(rows).toHaveLength(1);
    expect(rows[0]!.code).toBe("10104");
    expect(rows[0]!.prefix).toBe("101");
  });
});
