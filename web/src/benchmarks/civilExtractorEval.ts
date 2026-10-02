/**
 * Offline civil judgment extractor evaluation (WASM / Zero-Dataset safe).
 * Port of marine_claims_ai.benchmarks.civil_extractor_eval.evaluate_offline_snippets.
 */
import snippetsDefault from "../../tests/fixtures/civil_offline_snippets.json";
import {
  extractFromJudgment,
  extractionMatchesGold,
} from "../ingest/civilJudgmentExtractor";

export interface OfflineSnippet {
  id?: string;
  case_id?: number | null;
  text: string;
  fault_ratio?: string | null;
  claimed_repair_jpy?: number | null;
  awarded_damages_jpy?: number | null;
  disallowed_jpy?: number | null;
}

function scoreCase(
  text: string,
  gold: Record<string, unknown>,
): Record<string, unknown> {
  const extracted = extractFromJudgment(text);
  const match = extractionMatchesGold(extracted, gold);
  return {
    extracted: {
      fault_ratio: extracted.fault_ratio,
      claimed_repair_jpy: extracted.claimed_repair_jpy,
      awarded_damages_jpy: extracted.awarded_damages_jpy,
      disallowed_jpy: extracted.disallowed_jpy,
      holding_excerpt: extracted.holding_excerpt,
    },
    match,
  };
}

function summarizeFaultRatioTolerance(
  results: Array<Record<string, unknown>>,
): {
  fault_ratio_within_10pt_scored: number;
  fault_ratio_within_10pt_passed: number;
  fault_ratio_within_10pt_rate: number;
} {
  let scored = 0;
  let within = 0;
  for (const r of results) {
    const match = (r.match as Record<string, unknown> | undefined) || {};
    const w = match.fault_ratio_within_10pt;
    if (w === null || w === undefined) {
      if ("fault_ratio_ok" in r) continue;
      continue;
    }
    scored += 1;
    if (w) within += 1;
  }
  const rate = scored ? within / scored : 0.0;
  return {
    fault_ratio_within_10pt_scored: scored,
    fault_ratio_within_10pt_passed: within,
    fault_ratio_within_10pt_rate: rate,
  };
}

export function evaluateOfflineSnippets(
  snippets?: OfflineSnippet[] | null,
): Record<string, unknown> {
  const list =
    snippets !== undefined && snippets !== null
      ? snippets
      : (snippetsDefault as OfflineSnippet[]);
  const results: Array<Record<string, unknown>> = [];
  let passed = 0;
  for (const snip of list) {
    const gold = {
      fault_ratio: snip.fault_ratio ?? null,
      claimed_repair_jpy: snip.claimed_repair_jpy ?? null,
      awarded_damages_jpy: snip.awarded_damages_jpy ?? null,
      disallowed_jpy: snip.disallowed_jpy ?? null,
    };
    const scored = scoreCase(String(snip.text), gold);
    const match = scored.match as Record<string, unknown>;
    const ok = Boolean(match.all_ok);
    if (ok) passed += 1;
    results.push({
      id: snip.id,
      case_id: snip.case_id ?? null,
      ok,
      ...scored,
    });
  }
  const total = results.length;
  const accuracy = total ? passed / total : 0.0;
  const tol = summarizeFaultRatioTolerance(results);
  return {
    mode: "offline_snippets",
    total,
    passed,
    failed: total - passed,
    accuracy,
    ...tol,
    results,
  };
}
