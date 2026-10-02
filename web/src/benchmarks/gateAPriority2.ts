/**
 * Gate A Priority 2 lite — COLREGS situation accuracy (A5/A6) + civil A7 offline.
 */
import { classifyEncounter, type EncounterGeometry } from "../engines/colregs";
import { evaluateOfflineSnippets } from "./civilExtractorEval";

export interface ColregsCaseFixture {
  case_id?: string;
  heading_a_deg: number;
  heading_b_deg: number;
  true_bearing_a_to_b_deg: number;
  expected_situation: string;
  expected_role_a?: string;
  expected_role_b?: string;
}

export function evaluateA5A6FromGeometries(
  cases: ColregsCaseFixture[],
  gates: { min_situation_agreement?: number; max_critical_role_inversions?: number } = {},
): Record<string, unknown> {
  const minAgr = gates.min_situation_agreement ?? 0.9;
  const maxInv = gates.max_critical_role_inversions ?? 0;
  let run = 0;
  let agree = 0;
  let inversions = 0;
  const details: Array<Record<string, unknown>> = [];

  for (const c of cases) {
    const geometry: EncounterGeometry = {
      heading_a_deg: c.heading_a_deg,
      heading_b_deg: c.heading_b_deg,
      true_bearing_a_to_b_deg: c.true_bearing_a_to_b_deg,
      speed_a_kn: 12,
      speed_b_kn: 10,
      range_nm: 1,
    };
    const verdict = classifyEncounter(geometry);
    run += 1;
    const sitOk = verdict.situation === c.expected_situation;
    if (sitOk) agree += 1;
    let inv = false;
    if (c.expected_role_a && c.expected_role_b && verdict.role_a && verdict.role_b) {
      // Critical role inversion: both roles swapped vs expected
      if (
        verdict.role_a === c.expected_role_b &&
        verdict.role_b === c.expected_role_a &&
        c.expected_role_a !== c.expected_role_b
      ) {
        inv = true;
        inversions += 1;
      }
    }
    details.push({
      case_id: c.case_id,
      expected_situation: c.expected_situation,
      predicted_situation: verdict.situation,
      sit_ok: sitOk,
      role_inversion: inv,
    });
  }

  const agr = run ? agree / run : 0;
  const a5Pass = run === 0 || agr >= minAgr;
  const a6Pass = inversions <= maxInv;
  return {
    metric: "A5_A6",
    cases_run: run,
    situation_agreement: Math.round(agr * 10000) / 10000,
    critical_role_inversions: inversions,
    a5_pass: a5Pass,
    a6_pass: a6Pass,
    pass: a5Pass && a6Pass,
    details,
  };
}

/**
 * A7 civil extraction — offline snippets only (WASM / Zero-Dataset primary mode).
 */
export function evaluateA7Civil(
  gates: {
    min_civil_extraction_accuracy?: number;
    min_fault_ratio_within_10pt?: number;
  } = {},
): Record<string, unknown> {
  const minAcc = gates.min_civil_extraction_accuracy ?? 0.9;
  const minW10 = gates.min_fault_ratio_within_10pt ?? 0.8;

  const offline = evaluateOfflineSnippets();
  const accuracy = Number(offline.accuracy ?? 0);
  const w10 = Number(offline.fault_ratio_within_10pt_rate ?? 0);
  const scored = Number(offline.total ?? 0);

  const accuracyPass = scored === 0 || accuracy >= minAcc;
  const w10Scored = Number(offline.fault_ratio_within_10pt_scored ?? 0);
  const within10ptPass = w10Scored === 0 || w10 >= minW10;

  return {
    metric: "A7",
    primary_mode: "offline_snippets",
    scored,
    accuracy,
    fault_ratio_within_10pt_rate: w10,
    offline: {
      accuracy: offline.accuracy,
      total: offline.total,
      fault_ratio_within_10pt_rate: offline.fault_ratio_within_10pt_rate,
    },
    accuracy_pass: accuracyPass,
    within_10pt_pass: within10ptPass,
    pass: accuracyPass && within10ptPass,
    thresholds: {
      min_civil_extraction_accuracy: minAcc,
      min_fault_ratio_within_10pt: minW10,
    },
  };
}

export function runGateAPriority2Lite(
  geometries: ColregsCaseFixture[],
): Record<string, unknown> {
  const a5a6 = evaluateA5A6FromGeometries(geometries);
  const a7 = evaluateA7Civil();
  const zeroTol = Boolean(a5a6.a6_pass);
  return {
    mode: "lite_fixture",
    metrics: { A5_A6: a5a6, A7: a7 },
    gate: {
      zero_tolerance_pass: zeroTol,
      overall_pass: Boolean(a5a6.pass) && Boolean(a7.pass),
      situation_agreement: a5a6.situation_agreement,
      critical_role_inversions: a5a6.critical_role_inversions,
    },
  };
}
