/**
 * Multilingual label → language-agnostic UC schema enums (Issue #90).
 * Lexicon Tier-1; optional SLM backend reserved for #77 (falls back to lexicon).
 */
import { detectDocumentLanguage, type DocumentLanguage } from "./detectLanguage";
import {
  matchCriticalSystemPhrase,
  matchDockingContext,
  matchPscActionPhrase,
  matchRepairPhrase,
  matchSituationLabel,
  type RepairLexiconHit,
} from "./lexicon";

export type { DocumentLanguage };
export { detectDocumentLanguage };

/** Normalize backend: lexicon is default; slm reserved for Issue #77. */
export type NormalizeBackend = "lexicon" | "slm";

export interface NormalizeOptions {
  backend?: NormalizeBackend;
}

function resolveBackend(opts?: NormalizeOptions): NormalizeBackend {
  const b = opts?.backend ?? "lexicon";
  // SLM path not implemented (#77) — always fall back to lexicon.
  return b === "slm" ? "lexicon" : "lexicon";
}

export function normalizeRepairPhrase(
  text: string,
  opts?: NormalizeOptions,
): RepairLexiconHit | null {
  resolveBackend(opts);
  return matchRepairPhrase(text);
}

export function normalizeDockingContext(
  text: string,
  opts?: NormalizeOptions,
): "casualty_immediate" | "deferred_to_routine" | null {
  resolveBackend(opts);
  return matchDockingContext(text)?.docking_context ?? null;
}

export function normalizeSituationLabel(
  text: string,
  opts?: NormalizeOptions,
): "head_on" | "overtaking" | "crossing" | "safe_passing" | null {
  resolveBackend(opts);
  return matchSituationLabel(text)?.situation ?? null;
}

export function normalizePscActionPhrase(
  text: string,
  opts?: NormalizeOptions,
): string | null {
  resolveBackend(opts);
  return matchPscActionPhrase(text)?.action_code ?? null;
}

export function normalizeCriticalSystemPhrase(
  text: string,
  opts?: NormalizeOptions,
): string | null {
  resolveBackend(opts);
  return matchCriticalSystemPhrase(text)?.critical_system ?? null;
}
