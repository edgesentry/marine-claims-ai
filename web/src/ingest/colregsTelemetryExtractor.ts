/**
 * COLREGS Stage A telemetry extraction from judgment / JMAT / JTSB narratives (#91).
 * Parses headings, relative/true bearings, and optional speeds into EncounterGeometry fields.
 */
import { normalizeDeg, type EncounterGeometry } from "../engines/colregs";
import type { GroundingRef } from "../schemas";
import {
  normalizeJudgmentText,
  parseKanjiInt,
} from "./civilJudgmentExtractor";

export interface TelemetryField {
  value: number;
  source_quote: string;
  confidence: number;
}

export interface ColregsTelemetryExtract {
  heading_a: TelemetryField | null;
  heading_b: TelemetryField | null;
  /** Relative bearing A→B as stated (右舷前 = +, 左舷前 = toward port). */
  relative_bearing_a_to_b: TelemetryField | null;
  /** True bearing when stated directly, or derived from heading_a + relative. */
  true_bearing_a_to_b: TelemetryField | null;
  speed_a_kn: TelemetryField | null;
  speed_b_kn: TelemetryField | null;
}

const COMPASS_DEG: Record<string, number> = {
  北: 0,
  北北東: 22.5,
  北東: 45,
  東北東: 67.5,
  東: 90,
  東南東: 112.5,
  南東: 135,
  南南東: 157.5,
  南: 180,
  南南西: 202.5,
  南西: 225,
  西南西: 247.5,
  西: 270,
  西北西: 292.5,
  北西: 315,
  北北西: 337.5,
};

/** Longer names first so 北北東 matches before 北. */
const COMPASS_NAMES = Object.keys(COMPASS_DEG).sort(
  (a, b) => b.length - a.length,
);

const DEGREE_TOKEN =
  "([0-9０-９〇零○一二三四五六七八九十百]+(?:\\.[0-9０-９]+)?)";

function parseDegreeToken(raw: string): number | null {
  const t = raw.trim();
  if (!t) return null;
  if (/^[0-9０-９]+(?:\.[0-9０-９]+)?$/.test(t)) {
    const n = Number(
      t.replace(/[０-９]/g, (ch) =>
        String.fromCharCode(ch.charCodeAt(0) - 0xff10 + 0x30),
      ),
    );
    return Number.isFinite(n) ? n : null;
  }
  return parseKanjiInt(t);
}

function compassToDeg(name: string, micro?: string | null): number | null {
  const base = COMPASS_DEG[name];
  if (base == null) return null;
  if (!micro) return base;
  // 北東の微北 → halfway toward north from NE (NNE ≈ 22.5)
  if (micro === "北") return normalizeDeg(base - 22.5);
  if (micro === "東") return normalizeDeg(base + 22.5);
  if (micro === "南") return normalizeDeg(base + 22.5);
  if (micro === "西") return normalizeDeg(base - 22.5);
  return base;
}

function field(
  value: number,
  quote: string,
  confidence = 0.85,
): TelemetryField {
  return {
    value: normalizeDeg(value),
    source_quote: quote.trim().slice(0, 240),
    confidence,
  };
}

function matchHeading(
  text: string,
  vessel: "a" | "b",
): TelemetryField | null {
  const labels =
    vessel === "a"
      ? ["本船Ａ", "本船A", "本船ａ", "船舶Ａ", "船舶A", "Ａ船", "A船"]
      : ["相手船Ｂ", "相手船B", "相手船ｂ", "船舶Ｂ", "船舶B", "Ｂ船", "B船", "相手船"];

  for (const label of labels) {
    const numeric = new RegExp(
      `${label}[^。\\n]{0,24}針路\\s*${DEGREE_TOKEN}\\s*度`,
    );
    const m = numeric.exec(text);
    if (m) {
      const deg = parseDegreeToken(m[1]!);
      if (deg != null) return field(deg, m[0]!);
    }

    for (const name of COMPASS_NAMES) {
      const compass = new RegExp(
        `${label}[^。\\n]{0,24}針路\\s*(${name})(?:の微([東西南北]))?`,
      );
      const cm = compass.exec(text);
      if (cm) {
        const deg = compassToDeg(cm[1]!, cm[2] ?? null);
        if (deg != null) return field(deg, cm[0]!, 0.8);
      }
    }
  }
  return null;
}

function matchRelativeBearing(text: string): TelemetryField | null {
  const starboard = new RegExp(
    `右舷前(?:約)?\\s*${DEGREE_TOKEN}\\s*度`,
  );
  const port = new RegExp(`左舷前(?:約)?\\s*${DEGREE_TOKEN}\\s*度`);
  const ahead = /(ほとんど)?船首方向/;

  const sm = starboard.exec(text);
  if (sm) {
    const d = parseDegreeToken(sm[1]!);
    if (d != null) return field(d, sm[0]!, 0.85);
  }

  const pm = port.exec(text);
  if (pm) {
    const d = parseDegreeToken(pm[1]!);
    if (d != null) return field(normalizeDeg(-d), pm[0]!, 0.85);
  }

  const am = ahead.exec(text);
  if (am) return field(0, am[0]!, am[1] ? 0.75 : 0.8);

  return null;
}

function matchSpeed(text: string, vessel: "a" | "b"): TelemetryField | null {
  const labels =
    vessel === "a"
      ? ["本船Ａ", "本船A", "本船ａ"]
      : ["相手船Ｂ", "相手船B", "相手船ｂ", "相手船"];
  for (const label of labels) {
    const re = new RegExp(
      `${label}[^。\\n]{0,40}速力(?:約)?\\s*${DEGREE_TOKEN}\\s*(?:ノット|ﾉｯﾄ|kn)`,
      "i",
    );
    const m = re.exec(text);
    if (m) {
      const kn = parseDegreeToken(m[1]!);
      if (kn != null) {
        return {
          value: kn,
          source_quote: m[0]!.trim().slice(0, 240),
          confidence: 0.8,
        };
      }
    }
  }
  return null;
}

/** Extract heading / bearing / speed cues from a narrative string. */
export function extractColregsTelemetry(text: string): ColregsTelemetryExtract {
  const t = normalizeJudgmentText(text);
  const heading_a = matchHeading(t, "a");
  const heading_b = matchHeading(t, "b");
  const relative_bearing_a_to_b = matchRelativeBearing(t);

  let true_bearing_a_to_b: TelemetryField | null = null;
  if (heading_a && relative_bearing_a_to_b) {
    const trueDeg = normalizeDeg(
      heading_a.value + relative_bearing_a_to_b.value,
    );
    true_bearing_a_to_b = field(
      trueDeg,
      relative_bearing_a_to_b.source_quote,
      Math.min(heading_a.confidence, relative_bearing_a_to_b.confidence),
    );
  }

  return {
    heading_a,
    heading_b,
    relative_bearing_a_to_b,
    true_bearing_a_to_b,
    speed_a_kn: matchSpeed(t, "a"),
    speed_b_kn: matchSpeed(t, "b"),
  };
}

/** True when the Stage B triad is fully available. */
export function isCompleteTelemetry(ext: ColregsTelemetryExtract): boolean {
  return (
    ext.heading_a != null &&
    ext.heading_b != null &&
    ext.true_bearing_a_to_b != null
  );
}

/** Map a complete extract into EncounterGeometry (optional speeds). */
export function telemetryToGeometry(
  ext: ColregsTelemetryExtract,
  defaults?: Partial<EncounterGeometry>,
): EncounterGeometry | null {
  if (!isCompleteTelemetry(ext)) return null;
  return {
    heading_a_deg: ext.heading_a!.value,
    heading_b_deg: ext.heading_b!.value,
    true_bearing_a_to_b_deg: ext.true_bearing_a_to_b!.value,
    speed_a_kn: ext.speed_a_kn?.value ?? defaults?.speed_a_kn ?? null,
    speed_b_kn: ext.speed_b_kn?.value ?? defaults?.speed_b_kn ?? null,
    range_nm: defaults?.range_nm ?? null,
    power_driven_a: defaults?.power_driven_a,
    power_driven_b: defaults?.power_driven_b,
  };
}

/** Exact Span grounding entries for extracted telemetry fields (#88 / #91). */
export function telemetryGrounding(
  ext: ColregsTelemetryExtract,
): GroundingRef[] {
  const out: GroundingRef[] = [];
  const push = (fieldPath: string, f: TelemetryField | null) => {
    if (!f?.source_quote) return;
    out.push({
      field: fieldPath,
      source_quote: f.source_quote.slice(0, 240),
      page_number: null,
      pdf_coordinates: null,
    });
  };
  push("geometry.heading_a_deg", ext.heading_a);
  push("geometry.heading_b_deg", ext.heading_b);
  push("geometry.true_bearing_a_to_b_deg", ext.true_bearing_a_to_b);
  push("geometry.speed_a_kn", ext.speed_a_kn);
  push("geometry.speed_b_kn", ext.speed_b_kn);
  return out;
}

export function telemetryFieldConfidence(
  ext: ColregsTelemetryExtract,
): Record<string, number> {
  const out: Record<string, number> = {};
  if (ext.heading_a) out["geometry.heading_a_deg"] = ext.heading_a.confidence;
  if (ext.heading_b) out["geometry.heading_b_deg"] = ext.heading_b.confidence;
  if (ext.true_bearing_a_to_b) {
    out["geometry.true_bearing_a_to_b_deg"] =
      ext.true_bearing_a_to_b.confidence;
  }
  if (ext.speed_a_kn) out["geometry.speed_a_kn"] = ext.speed_a_kn.confidence;
  if (ext.speed_b_kn) out["geometry.speed_b_kn"] = ext.speed_b_kn.confidence;
  if (!isCompleteTelemetry(ext)) {
    out.geometry_missing = 0;
  }
  return out;
}

/** Sentinel key stamped when narrative has no numeric encounter geometry (#91 / #89). */
export const GEOMETRY_MISSING_FIELD = "geometry_missing";
