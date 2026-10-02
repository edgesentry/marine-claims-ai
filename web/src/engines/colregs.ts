/**
 * COLREGS Rules 13–15 encounter geometry (port of colregs_engine.py).
 */

export const OVERTAKING_ABAFT_BEAM_DEG = 22.5;
export const OVERTAKING_RELATIVE_BEARING_MIN_DEG = 90.0 + OVERTAKING_ABAFT_BEAM_DEG; // 112.5
export const OVERTAKING_RELATIVE_BEARING_MAX_DEG = 360.0 - OVERTAKING_RELATIVE_BEARING_MIN_DEG; // 247.5
export const HEAD_ON_COURSE_TOLERANCE_DEG = 5.0;
export const HEAD_ON_BEARING_TOLERANCE_DEG = 5.0;

export const RULE_13 = "COLREGS Rule 13 / 海上衝突予防法 第13条";
export const RULE_14 = "COLREGS Rule 14 / 海上衝突予防法 第14条";
export const RULE_15 = "COLREGS Rule 15 / 海上衝突予防法 第15条";
export const RULE_16 = "COLREGS Rule 16 / 海上衝突予防法 第16条";
export const RULE_17 = "COLREGS Rule 17 / 海上衝突予防法 第17条";

export type EncounterSituation = "head_on" | "overtaking" | "crossing" | "safe_passing";
export type VesselRole = "give_way" | "stand_on";

export interface EncounterGeometry {
  heading_a_deg: number;
  heading_b_deg: number;
  true_bearing_a_to_b_deg: number;
  power_driven_a?: boolean;
  power_driven_b?: boolean;
  range_nm?: number | null;
  speed_a_kn?: number | null;
  speed_b_kn?: number | null;
}

export interface EncounterVerdict {
  situation: EncounterSituation;
  role_a: VesselRole | null;
  role_b: VesselRole | null;
  relative_bearing_a_to_b_deg: number;
  relative_bearing_b_to_a_deg: number;
  course_difference_deg: number;
  bearing_starboard_a: boolean;
  mutual_starboard_alteration: boolean;
  rule_citations: string[];
  cpa_nm: number | null;
  tcpa_min: number | null;
}

export function normalizeDeg(angle: number): number {
  return ((angle % 360) + 360) % 360;
}

export function angularDistanceDeg(a: number, b: number): number {
  return Math.min(normalizeDeg(a - b), normalizeDeg(b - a));
}

export function relativeBearingDeg(trueBearing: number, heading: number): number {
  return normalizeDeg(trueBearing - heading);
}

export function courseDifferenceDeg(headingA: number, headingB: number): number {
  return normalizeDeg(Math.abs(normalizeDeg(headingA) - normalizeDeg(headingB)));
}

export function reciprocalBearingDeg(trueBearing: number): number {
  return normalizeDeg(trueBearing + 180.0);
}

export function isOvertaking(aspectAngle: number): boolean {
  const theta = normalizeDeg(aspectAngle);
  return (
    OVERTAKING_RELATIVE_BEARING_MIN_DEG < theta && theta < OVERTAKING_RELATIVE_BEARING_MAX_DEG
  );
}

export function isHeadOn(courseDiff: number, relativeBearing: number): boolean {
  const dpsi = normalizeDeg(courseDiff);
  const nearlyReciprocal = Math.abs(dpsi - 180.0) <= HEAD_ON_COURSE_TOLERANCE_DEG;
  const nearlyAhead = angularDistanceDeg(relativeBearing, 0.0) <= HEAD_ON_BEARING_TOLERANCE_DEG;
  return nearlyReciprocal && nearlyAhead;
}

export function isCrossing(courseDiff: number, relativeBearing: number): boolean {
  const dpsi = normalizeDeg(courseDiff);
  const theta = normalizeDeg(relativeBearing);
  if (Math.abs(dpsi - 180.0) <= HEAD_ON_COURSE_TOLERANCE_DEG) return false;
  if (angularDistanceDeg(dpsi, 0.0) <= HEAD_ON_COURSE_TOLERANCE_DEG) return false;
  if (isOvertaking(theta)) return false;
  return (
    theta <= OVERTAKING_RELATIVE_BEARING_MIN_DEG || theta >= OVERTAKING_RELATIVE_BEARING_MAX_DEG
  );
}

export function bearingStarboard(relativeBearing: number): boolean {
  const theta = normalizeDeg(relativeBearing);
  return 0.0 < theta && theta < 180.0;
}

function velocityComponents(speedKn: number, headingDeg: number): [number, number] {
  const rad = (normalizeDeg(headingDeg) * Math.PI) / 180;
  return [speedKn * Math.sin(rad), speedKn * Math.cos(rad)];
}

export function cpaTcpaNmMin(
  rangeNm: number,
  relativeBearingAtoB: number,
  headingA: number,
  headingB: number,
  speedA: number,
  speedB: number,
): [number | null, number | null] {
  if (rangeNm < 0) throw new Error("range_nm must be non-negative");
  const theta = normalizeDeg(relativeBearingAtoB);
  const bodyE = rangeNm * Math.sin((theta * Math.PI) / 180);
  const bodyN = rangeNm * Math.cos((theta * Math.PI) / 180);
  const hdg = (normalizeDeg(headingA) * Math.PI) / 180;
  const posE = bodyE * Math.cos(hdg) + bodyN * Math.sin(hdg);
  const posN = -bodyE * Math.sin(hdg) + bodyN * Math.cos(hdg);
  const [vaE, vaN] = velocityComponents(speedA, headingA);
  const [vbE, vbN] = velocityComponents(speedB, headingB);
  const relE = vbE - vaE;
  const relN = vbN - vaN;
  const relSpeedSq = relE * relE + relN * relN;
  if (relSpeedSq < 1e-12) return [null, null];
  const tcpaH = -(posE * relE + posN * relN) / relSpeedSq;
  const cpaE = posE + relE * tcpaH;
  const cpaN = posN + relN * tcpaH;
  return [Math.hypot(cpaE, cpaN), tcpaH * 60.0];
}

export function classifyEncounter(geometry: EncounterGeometry): EncounterVerdict {
  const relA = relativeBearingDeg(geometry.true_bearing_a_to_b_deg, geometry.heading_a_deg);
  const bearingBtoA = reciprocalBearingDeg(geometry.true_bearing_a_to_b_deg);
  const relB = relativeBearingDeg(bearingBtoA, geometry.heading_b_deg);
  const dpsi = courseDifferenceDeg(geometry.heading_a_deg, geometry.heading_b_deg);
  const starboardA = bearingStarboard(relA);

  let cpaNm: number | null = null;
  let tcpaMin: number | null = null;
  if (
    geometry.range_nm != null &&
    geometry.speed_a_kn != null &&
    geometry.speed_b_kn != null
  ) {
    [cpaNm, tcpaMin] = cpaTcpaNmMin(
      geometry.range_nm,
      relA,
      geometry.heading_a_deg,
      geometry.heading_b_deg,
      geometry.speed_a_kn,
      geometry.speed_b_kn,
    );
  }

  const bothPower = (geometry.power_driven_a ?? true) && (geometry.power_driven_b ?? true);

  if (isOvertaking(relB)) {
    return {
      situation: "overtaking",
      role_a: "give_way",
      role_b: "stand_on",
      relative_bearing_a_to_b_deg: relA,
      relative_bearing_b_to_a_deg: relB,
      course_difference_deg: dpsi,
      bearing_starboard_a: starboardA,
      mutual_starboard_alteration: false,
      rule_citations: [RULE_13, RULE_16, RULE_17],
      cpa_nm: cpaNm,
      tcpa_min: tcpaMin,
    };
  }

  if (isOvertaking(relA)) {
    return {
      situation: "overtaking",
      role_a: "stand_on",
      role_b: "give_way",
      relative_bearing_a_to_b_deg: relA,
      relative_bearing_b_to_a_deg: relB,
      course_difference_deg: dpsi,
      bearing_starboard_a: starboardA,
      mutual_starboard_alteration: false,
      rule_citations: [RULE_13, RULE_16, RULE_17],
      cpa_nm: cpaNm,
      tcpa_min: tcpaMin,
    };
  }

  if (bothPower && isHeadOn(dpsi, relA)) {
    return {
      situation: "head_on",
      role_a: "give_way",
      role_b: "give_way",
      relative_bearing_a_to_b_deg: relA,
      relative_bearing_b_to_a_deg: relB,
      course_difference_deg: dpsi,
      bearing_starboard_a: starboardA,
      mutual_starboard_alteration: true,
      rule_citations: [RULE_14],
      cpa_nm: cpaNm,
      tcpa_min: tcpaMin,
    };
  }

  if (bothPower && isCrossing(dpsi, relA)) {
    const roleA: VesselRole = starboardA ? "give_way" : "stand_on";
    const roleB: VesselRole = starboardA ? "stand_on" : "give_way";
    return {
      situation: "crossing",
      role_a: roleA,
      role_b: roleB,
      relative_bearing_a_to_b_deg: relA,
      relative_bearing_b_to_a_deg: relB,
      course_difference_deg: dpsi,
      bearing_starboard_a: starboardA,
      mutual_starboard_alteration: false,
      rule_citations: [RULE_15, RULE_16, RULE_17],
      cpa_nm: cpaNm,
      tcpa_min: tcpaMin,
    };
  }

  return {
    situation: "safe_passing",
    role_a: null,
    role_b: null,
    relative_bearing_a_to_b_deg: relA,
    relative_bearing_b_to_a_deg: relB,
    course_difference_deg: dpsi,
    bearing_starboard_a: starboardA,
    mutual_starboard_alteration: false,
    rule_citations: [],
    cpa_nm: cpaNm,
    tcpa_min: tcpaMin,
  };
}
