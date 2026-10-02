/**
 * Issue #102 Definition of Done — CI-facing assertions.
 *
 * DoD:
 * - Switching JMAT catalog cases updates displayed heading/bearing to match
 *   the geometry used for Stage B, without enabling override
 * - No change to Stage B classification or role-inversion gate behavior
 *
 * Included in `npm test` and `npm run gate-a`.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { runColregs } from "../src/core";
import {
  CIVIL_7_DISPLAY_DEFAULTS,
  geometryForCatalogCase,
  resolveDisplayDegrees,
} from "../src/demo/catalogGeometry";
import {
  extractColregsTelemetry,
  isCompleteTelemetry,
  telemetryToGeometry,
} from "../src/ingest/colregsTelemetryExtractor";

interface JmatCase {
  case_id: string;
  facts_text: string;
  ruling_text?: string;
  expected_situation: string;
  expected_role_a: string | null;
  expected_role_b: string | null;
}

function loadJmatCases(): JmatCase[] {
  const path = resolve(
    import.meta.dirname,
    "../../config/jmat_collision_eval.json",
  );
  const raw = JSON.parse(readFileSync(path, "utf8")) as { cases: JmatCase[] };
  return raw.cases;
}

describe("Issue #102 DoD — sync display geometry with narrative", () => {
  it("DoD: case switch updates display degrees to match Stage B geometry", () => {
    const cases = loadJmatCases();
    const kii = cases.find((c) => c.case_id === "crossing_kii_starboard_giveway");
    const port = cases.find((c) => c.case_id === "crossing_port_standon");
    expect(kii).toBeTruthy();
    expect(port).toBeTruthy();

    // Stale slider defaults (demo 30/300/70) must not stick after switching to port stand-on.
    const staleSlider = { headingA: 30, headingB: 300, bearingAb: 70 };

    const displayKii = resolveDisplayDegrees({
      caseId: kii!.case_id,
      jmatCases: cases,
    });
    expect(displayKii).toEqual({ headingA: 30, headingB: 300, bearingAb: 70 });

    const displayPort = resolveDisplayDegrees({
      caseId: port!.case_id,
      jmatCases: cases,
    });
    // Narrative: 000° / 090° / port-bow ≈ 300° true bearing (see extractor tests).
    expect(displayPort.headingA).toBe(0);
    expect(displayPort.headingB).toBe(90);
    expect(displayPort.bearingAb).toBe(300);

    const stageBPort = geometryForCatalogCase({
      caseId: port!.case_id,
      overrideGeom: false,
      slider: staleSlider,
      jmatCases: cases,
    });
    expect(stageBPort.heading_a_deg).toBe(displayPort.headingA);
    expect(stageBPort.heading_b_deg).toBe(displayPort.headingB);
    expect(stageBPort.true_bearing_a_to_b_deg).toBe(displayPort.bearingAb);

    // Override remains off: scoring still comes from narrative, not stale slider.
    const run = runColregs({
      geometry: stageBPort,
      factsExcerpt: port!.facts_text,
      rulingExcerpt: port!.ruling_text,
      groundingMode: "paste_bypass",
      confidenceMode: "bypass",
      confidence: 0.9,
    });
    expect(run.status).toBe("scored");
    if (run.status !== "scored") return;
    expect(run.verdict.situation).toBe(port!.expected_situation);
    expect(run.verdict.role_a).toBe(port!.expected_role_a);
    expect(run.verdict.role_b).toBe(port!.expected_role_b);
  });

  it("DoD: civil_7 catalog display resets to demo defaults", () => {
    const d = resolveDisplayDegrees({
      caseId: "civil_7",
      jmatCases: loadJmatCases(),
    });
    expect(d).toEqual(CIVIL_7_DISPLAY_DEFAULTS);
  });

  it("DoD: upload preserveDegrees keeps extracted triad", () => {
    const extracted = { headingA: 12, headingB: 200, bearingAb: 45 };
    const d = resolveDisplayDegrees({
      caseId: "civil_7",
      jmatCases: [],
      preserveDegrees: extracted,
    });
    expect(d).toEqual(extracted);
  });

  it("DoD: role inversion remains 0 when display sync matches narrative geometry", () => {
    const cases = loadJmatCases().filter(
      (c) =>
        isCompleteTelemetry(extractColregsTelemetry(c.facts_text)) &&
        c.expected_role_a != null,
    );
    expect(cases.length).toBeGreaterThan(0);

    let inversions = 0;
    for (const c of cases) {
      const display = resolveDisplayDegrees({
        caseId: c.case_id,
        jmatCases: cases,
      });
      const geom = telemetryToGeometry(extractColregsTelemetry(c.facts_text), {
        speed_a_kn: 12,
        speed_b_kn: 10,
        range_nm: 1,
      });
      expect(geom).toBeTruthy();
      expect(display.headingA).toBe(geom!.heading_a_deg);
      expect(display.headingB).toBe(geom!.heading_b_deg);
      expect(display.bearingAb).toBe(geom!.true_bearing_a_to_b_deg);

      const run = runColregs({
        geometry: geom!,
        factsExcerpt: c.facts_text,
        rulingExcerpt: c.ruling_text,
        groundingMode: "paste_bypass",
        confidenceMode: "bypass",
        confidence: 0.9,
      });
      if (run.status !== "scored") continue;
      if (
        run.verdict.role_a !== c.expected_role_a ||
        run.verdict.role_b !== c.expected_role_b
      ) {
        inversions += 1;
      }
    }
    expect(inversions).toBe(0);
  });
});
