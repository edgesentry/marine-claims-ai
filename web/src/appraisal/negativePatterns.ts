/**
 * Negative Pattern Library scoring (port of appraisal/negative_patterns.py).
 * Default embed uses hashEmbed (FNV); inject MiniLM-compatible embedFn for parity.
 */
import { hashEmbed } from "../engines/fault";
import {
  ACTION_APPROVED,
  ACTION_APPORTIONED,
  ACTION_DISALLOWED,
  type NplScore,
  type NplScorer,
} from "./pipeline";

export { ACTION_APPROVED, ACTION_APPORTIONED, ACTION_DISALLOWED };

export type EmbedFn = (texts: string[]) => number[][];

export interface NplPattern {
  id?: string;
  trade_code?: string;
  category?: string;
  text?: string;
  anchor_tokens?: string[];
  source?: string;
}

export interface NplLibrary {
  description?: string;
  thresholds?: { disallow_min?: number; apportion_min?: number };
  patterns: NplPattern[];
}

export interface PatternMatch {
  pattern_id: string;
  trade_code: string;
  text: string;
  source: string;
  similarity: number;
}

export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length || !a.length) return 0;
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    const x = a[i]!;
    const y = b[i]!;
    dot += x * y;
    normA += x * x;
    normB += y * y;
  }
  if (normA <= 0 || normB <= 0) return 0;
  const sim = dot / (Math.sqrt(normA) * Math.sqrt(normB));
  if (sim < 0) return 0;
  if (sim > 1) return 1;
  return sim;
}

export function actionForSimilarity(
  similarity: number,
  disallowMin = 0.8,
  apportionMin = 0.5,
): string {
  if (similarity >= disallowMin) return ACTION_DISALLOWED;
  if (similarity >= apportionMin) return ACTION_APPORTIONED;
  return ACTION_APPROVED;
}

export function formatCitation(similarity: number, tradeCode: string): string {
  const pct = Math.round(similarity * 1000) / 10;
  return (
    `Matched with ${pct}% similarity to public standard periodic maintenance ` +
    `item ${tradeCode}`
  );
}

export function normalizeCategory(category: string | null | undefined): string | null {
  if (category == null) return null;
  let text = String(category).trim();
  if (!text) return null;
  text = text.replace(/【/g, "").replace(/】/g, "").trim();
  return text || null;
}

export function patternPassesGates(
  pattern: NplPattern,
  description: string,
  category?: string | null,
): boolean {
  const anchors = pattern.anchor_tokens || [];
  if (anchors.length && !anchors.some((tok) => tok && description.includes(tok))) {
    return false;
  }
  const itemCat = normalizeCategory(category);
  const patternCat = normalizeCategory(pattern.category);
  if (itemCat && patternCat && itemCat !== patternCat) return false;
  return true;
}

export function normalizeLibrary(data: NplLibrary): NplLibrary {
  if (!data.patterns || !Array.isArray(data.patterns)) {
    throw new Error("Invalid negative pattern library (missing patterns)");
  }
  const thresholds = data.thresholds || {};
  return {
    ...data,
    thresholds: {
      disallow_min: Number(thresholds.disallow_min ?? 0.8),
      apportion_min: Number(thresholds.apportion_min ?? 0.5),
    },
  };
}

function defaultEmbed(texts: string[]): number[][] {
  return texts.map((t) => hashEmbed(t));
}

export class NegativePatternScorer implements NplScorer {
  library: NplLibrary;
  patterns: NplPattern[];
  disallowMin: number;
  apportionMin: number;
  private embedFn: EmbedFn;
  private patternVectors: number[][] | null = null;

  constructor(
    library: NplLibrary,
    opts: { embedFn?: EmbedFn } = {},
  ) {
    this.library = normalizeLibrary(library);
    this.patterns = [...(this.library.patterns || [])];
    this.disallowMin = Number(this.library.thresholds?.disallow_min ?? 0.8);
    this.apportionMin = Number(this.library.thresholds?.apportion_min ?? 0.5);
    this.embedFn = opts.embedFn || defaultEmbed;
  }

  private ensurePatternVectors(): number[][] {
    if (this.patternVectors === null) {
      const texts = this.patterns.map((p) => String(p.text || ""));
      this.patternVectors = texts.length ? this.embedFn(texts) : [];
      if (this.patternVectors.length !== this.patterns.length) {
        throw new Error("Embedding count does not match pattern count");
      }
    }
    return this.patternVectors;
  }

  bestMatch(description: string, category?: string | null): PatternMatch | null {
    const text = (description || "").trim();
    if (!text || !this.patterns.length) return null;
    const vectors = this.ensurePatternVectors();
    const queryVec = this.embedFn([text])[0]!;
    const ranked: Array<[number, number]> = [];
    for (let i = 0; i < vectors.length; i++) {
      ranked.push([cosineSimilarity(queryVec, vectors[i]!), i]);
    }
    ranked.sort((a, b) => b[0]! - a[0]!);
    for (const [sim, idx] of ranked) {
      const pattern = this.patterns[idx!]!;
      if (!patternPassesGates(pattern, text, category)) continue;
      return {
        pattern_id: String(pattern.id || ""),
        trade_code: String(pattern.trade_code || ""),
        text: String(pattern.text || ""),
        source: String(pattern.source || ""),
        similarity: sim!,
      };
    }
    return null;
  }

  score_description(description: string, category?: string | null): NplScore {
    const match = this.bestMatch(description, category);
    if (!match) {
      return {
        red_flag_similarity: 0,
        matched_pattern_id: null,
        matched_trade_code: null,
        matched_pattern_text: null,
        citation: null,
        recommended_action: ACTION_APPROVED,
      };
    }
    const action = actionForSimilarity(
      match.similarity,
      this.disallowMin,
      this.apportionMin,
    );
    return {
      red_flag_similarity: Math.round(match.similarity * 10000) / 10000,
      matched_pattern_id: match.pattern_id,
      matched_trade_code: match.trade_code,
      matched_pattern_text: match.text,
      citation: formatCitation(match.similarity, match.trade_code),
      recommended_action: action,
    };
  }
}

export function scoreLineItems(
  items: Array<Record<string, unknown>>,
  scorer: NegativePatternScorer,
): Array<Record<string, unknown>> {
  return items.map((item) => {
    const fields = scorer.score_description(
      String(item.description || ""),
      item.category as string | null | undefined,
    );
    return { ...item, ...fields };
  });
}

/** Build scorer from library JSON (hashEmbed by default). */
export function createNplScorer(
  library: NplLibrary,
  embedFn?: EmbedFn,
): NegativePatternScorer {
  return new NegativePatternScorer(library, { embedFn });
}
