/**
 * Document language detection for Stage A (Issue #90).
 * Script-ratio heuristic only — no full-document MT.
 */

export type DocumentLanguage = "ja" | "en" | "mixed" | "unknown";

const CJK_RE = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g;
const LATIN_WORD_RE = /[A-Za-z]{2,}/g;

/**
 * Detect dominant document language from character / word counts.
 * Used as metadata only; normalization still runs via lexicon on any language.
 */
export function detectDocumentLanguage(text: string): DocumentLanguage {
  const raw = text || "";
  if (!raw.trim()) return "unknown";

  const cjk = raw.match(CJK_RE)?.length ?? 0;
  const latinWords = raw.match(LATIN_WORD_RE)?.length ?? 0;
  const total = cjk + latinWords;
  if (total === 0) return "unknown";

  const cjkRatio = cjk / total;
  const latinRatio = latinWords / total;

  // Both scripts present → mixed unless one side overwhelms.
  if (cjk > 0 && latinWords > 0) {
    if (cjkRatio >= 0.85) return "ja";
    if (latinRatio >= 0.85) return "en";
    return "mixed";
  }
  if (cjkRatio >= 0.55) return "ja";
  if (latinRatio >= 0.55) return "en";
  if (cjk > 0) return "ja";
  if (latinWords > 0) return "en";
  return "unknown";
}
