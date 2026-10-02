/**
 * Catalog / narrative geometry for COLREGS UC3 display sync (Issue #102).
 *
 * Stage B already scores from narrative via extractColregsTelemetry; this module
 * resolves the degrees that disabled heading/bearing inputs should show so they
 * match the geometry used for scoring.
 */
import type { EncounterGeometry } from "../engines/colregs";
import {
  extractColregsTelemetry,
  telemetryToGeometry,
} from "../ingest/colregsTelemetryExtractor";

export type CatalogJmatCase = {
  case_id: string;
  facts_text?: string;
  expected_situation?: string;
};

export type DisplayDegrees = {
  headingA: number;
  headingB: number;
  bearingAb: number;
};

/** Demo defaults for the civil_7 catalog seed (not upload). */
export const CIVIL_7_DISPLAY_DEFAULTS: DisplayDegrees = {
  headingA: 30,
  headingB: 300,
  bearingAb: 70,
};

const SITUATION_DEFAULTS: Record<string, [number, number, number]> = {
  head_on: [0, 180, 0],
  overtaking: [0, 0, 180],
  crossing: [0, 270, 45],
};

/**
 * Degrees to show in disabled heading/bearing fields when override is off.
 * Does not consult slider state — callers skip sync while override is on.
 */
export function resolveDisplayDegrees(opts: {
  caseId: string;
  jmatCases: CatalogJmatCase[];
  /** When true, keep caller-supplied degrees (upload extract already synced). */
  preserveDegrees?: DisplayDegrees | null;
}): DisplayDegrees {
  if (opts.caseId === "civil_7") {
    if (opts.preserveDegrees) return { ...opts.preserveDegrees };
    return { ...CIVIL_7_DISPLAY_DEFAULTS };
  }

  const jmat = opts.jmatCases.find((c) => c.case_id === opts.caseId);
  if (jmat?.facts_text) {
    const extracted = telemetryToGeometry(
      extractColregsTelemetry(jmat.facts_text),
      { speed_a_kn: 12, speed_b_kn: 10, range_nm: 1 },
    );
    if (extracted) {
      return {
        headingA: extracted.heading_a_deg,
        headingB: extracted.heading_b_deg,
        bearingAb: extracted.true_bearing_a_to_b_deg,
      };
    }
  }

  const sit = jmat?.expected_situation || "crossing";
  const [a, b, brg] = SITUATION_DEFAULTS[sit] || SITUATION_DEFAULTS.crossing!;
  return { headingA: a, headingB: b, bearingAb: brg };
}

/**
 * Encounter geometry for Stage B scoring (mirrors former main.ts geometryForCase).
 */
export function geometryForCatalogCase(opts: {
  caseId: string;
  overrideGeom: boolean;
  slider: DisplayDegrees;
  jmatCases: CatalogJmatCase[];
  speed_a_kn?: number;
  speed_b_kn?: number;
  range_nm?: number;
}): EncounterGeometry {
  const speed_a_kn = opts.speed_a_kn ?? 12;
  const speed_b_kn = opts.speed_b_kn ?? 10;

  if (opts.overrideGeom || opts.caseId === "civil_7") {
    return {
      heading_a_deg: opts.slider.headingA,
      heading_b_deg: opts.slider.headingB,
      true_bearing_a_to_b_deg: opts.slider.bearingAb,
      speed_a_kn,
      speed_b_kn,
      range_nm: opts.range_nm ?? 0.8,
    };
  }

  const display = resolveDisplayDegrees({
    caseId: opts.caseId,
    jmatCases: opts.jmatCases,
  });
  return {
    heading_a_deg: display.headingA,
    heading_b_deg: display.headingB,
    true_bearing_a_to_b_deg: display.bearingAb,
    speed_a_kn,
    speed_b_kn,
    range_nm: opts.range_nm ?? 1,
  };
}
