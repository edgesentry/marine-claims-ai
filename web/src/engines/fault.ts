/**
 * Fault-ratio prediction with hashed embeddings + cosine similarity.
 * Browser path can also query DuckDB list_cosine_similarity over Parquet.
 */

import type { EncounterGeometry, EncounterSituation } from "./colregs";
import { classifyEncounter } from "./colregs";

export interface FaultRules {
  baselines: Record<string, string>;
  blend: {
    rule_weight: number;
    knn_weight: number;
    min_knn_score: number;
    top_k: number;
    round_to_pp: number;
    clamp_primary_min: number;
    clamp_primary_max: number;
  };
  modifiers: Array<{
    id: string;
    patterns: string[];
    delta_primary_pp: number;
    citation: string;
  }>;
}

export interface ModifierHit {
  modifier_id: string;
  delta_primary_pp: number;
  citation: string;
  matched_pattern: string;
}

export interface PrecedentMatch {
  case_id: string;
  title: string;
  fault_ratio: string;
  score: number;
}

export interface FaultPrediction {
  fault_ratio: string;
  primary_pct: number;
  secondary_pct: number;
  baseline_ratio: string;
  situation: string;
  role_a: string | null;
  role_b: string | null;
  rule_adjusted_ratio: string;
  knn_ratio: string | null;
  modifiers: ModifierHit[];
  matches: PrecedentMatch[];
  rationale: string;
  rule_citations: string[];
}

const DIM = 384;
const TOKEN_RE = /[\w\u3040-\u30ff\u3400-\u9fff]+/gu;
const BILATERAL_TRIGGERS = new Set(["fog", "mutual_fault"]);
const BILATERAL_POSITIVE_IDS = new Set(["lookout", "radar", "sound_signals", "speed"]);

export function tokenize(text: string): string[] {
  const out: string[] = [];
  const m = text.match(TOKEN_RE) || [];
  for (const t of m) {
    if (t.length >= 2) out.push(t.toLowerCase());
  }
  return out;
}

/** MD5-free FNV-1a hash for stable token → dimension mapping. */
function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export function hashEmbed(text: string): number[] {
  const vec = new Array<number>(DIM).fill(0);
  const toks = tokenize(text);
  if (!toks.length) return vec;
  for (const tok of toks) {
    const h = fnv1a(tok);
    const idx = h % DIM;
    const sign = (h >> 8) & 1 ? 1 : -1;
    vec[idx]! += sign;
  }
  let norm = 0;
  for (const v of vec) norm += v * v;
  norm = Math.sqrt(norm) || 1;
  return vec.map((v) => v / norm);
}

export function cosineSimilarity(a: number[], b: number[]): number {
  let dot = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) dot += a[i]! * b[i]!;
  return dot;
}

export function parseFaultRatio(ratio: string): [number, number] {
  const parts = ratio.split(":").map((x) => parseInt(x.trim(), 10));
  if (parts.length !== 2 || parts.some((x) => Number.isNaN(x))) {
    throw new Error(`bad fault ratio: ${ratio}`);
  }
  return [parts[0]!, parts[1]!];
}

export function formatFaultRatio(primary: number): string {
  return `${primary}:${100 - primary}`;
}

export function extractModifiers(narrative: string, rules: FaultRules): ModifierHit[] {
  const text = narrative || "";
  const textLower = text.toLowerCase();
  const hits: ModifierHit[] = [];
  for (const mod of rules.modifiers) {
    let matched: string | null = null;
    for (const pat of mod.patterns) {
      if (textLower.includes(pat.toLowerCase()) || text.includes(pat)) {
        matched = pat;
        break;
      }
    }
    if (!matched) continue;
    hits.push({
      modifier_id: mod.id,
      delta_primary_pp: mod.delta_primary_pp,
      citation: mod.citation,
      matched_pattern: matched,
    });
  }
  const hitIds = new Set(hits.map((h) => h.modifier_id));
  if ([...hitIds].some((id) => BILATERAL_TRIGGERS.has(id))) {
    return hits.map((hit) =>
      hit.modifier_id &&
      BILATERAL_POSITIVE_IDS.has(hit.modifier_id) &&
      hit.delta_primary_pp > 0
        ? { ...hit, delta_primary_pp: 0 }
        : hit,
    );
  }
  return hits;
}

export function applyModifierDeltas(
  baselinePrimary: number,
  modifiers: ModifierHit[],
  clampMin: number,
  clampMax: number,
): number {
  let primary = baselinePrimary;
  for (const hit of modifiers) primary += hit.delta_primary_pp;
  return Math.max(clampMin, Math.min(clampMax, primary));
}

export function roundPrimaryPp(primary: number, step: number): number {
  if (step <= 0) return Math.round(primary);
  return Math.round(primary / step) * step;
}

export interface CatalogSeed {
  case_id: string;
  title: string;
  court?: string;
  input_facts?: string;
  holding?: string;
  fault_ratio?: string;
  embedding?: number[];
  /** PDF upload: civil judgment vs JTSB / MAIA accident report. */
  document_kind?: "judgment" | "jtsb";
}

export function knnByCosine(
  narrative: string,
  seeds: CatalogSeed[],
  topK = 3,
): { matches: PrecedentMatch[]; bestScore: number; ratio: string | null } {
  const q = hashEmbed(narrative);
  const scored = seeds.map((s) => {
    const emb = s.embedding ?? hashEmbed(
      [s.title, s.input_facts, s.holding, s.court].filter(Boolean).join(" "),
    );
    return { score: cosineSimilarity(q, emb), seed: s };
  });
  scored.sort((a, b) => b.score - a.score || a.seed.case_id.localeCompare(b.seed.case_id));
  const top = scored.slice(0, Math.max(1, topK));
  const matches: PrecedentMatch[] = top.map(({ score, seed }) => ({
    case_id: seed.case_id,
    title: seed.title,
    fault_ratio: seed.fault_ratio || "",
    score,
  }));
  let weightedSum = 0;
  let weightTotal = 0;
  for (const { score, seed } of top) {
    if (!seed.fault_ratio) continue;
    try {
      const [a] = parseFaultRatio(seed.fault_ratio);
      const w = Math.max(score, 1e-6);
      weightedSum += a * w;
      weightTotal += w;
    } catch {
      /* skip */
    }
  }
  const bestScore = top[0]?.score ?? 0;
  if (weightTotal <= 0) return { matches, bestScore, ratio: null };
  return { matches, bestScore, ratio: formatFaultRatio(Math.round(weightedSum / weightTotal)) };
}

export function predictFaultRatio(
  narrative: string,
  rules: FaultRules,
  seeds: CatalogSeed[],
  geometry?: EncounterGeometry | null,
): FaultPrediction {
  const blend = rules.blend;
  let situation: EncounterSituation = "crossing";
  let roleA: string | null = null;
  let roleB: string | null = null;
  let citations: string[] = [];
  if (geometry) {
    const v = classifyEncounter(geometry);
    situation = v.situation;
    roleA = v.role_a;
    roleB = v.role_b;
    citations = [...v.rule_citations];
  }
  const baseline = rules.baselines[situation] || rules.baselines.unknown || "75:25";
  const [baselinePrimary] = parseFaultRatio(baseline);
  const modifiers = extractModifiers(narrative, rules);
  const rulePrimary = applyModifierDeltas(
    baselinePrimary,
    modifiers,
    blend.clamp_primary_min,
    blend.clamp_primary_max,
  );
  const ruleAdjusted = formatFaultRatio(rulePrimary);
  const { matches, bestScore, ratio: knnRatio } = knnByCosine(
    narrative,
    seeds,
    blend.top_k,
  );
  let knnPrimary: number | null = null;
  if (knnRatio) knnPrimary = parseFaultRatio(knnRatio)[0];

  let blended: number;
  if (knnPrimary == null || bestScore < blend.min_knn_score) {
    blended = rulePrimary;
  } else {
    blended = blend.rule_weight * rulePrimary + blend.knn_weight * knnPrimary;
  }
  const finalPrimary = Math.max(
    blend.clamp_primary_min,
    Math.min(blend.clamp_primary_max, roundPrimaryPp(blended, blend.round_to_pp)),
  );
  const faultRatio = formatFaultRatio(finalPrimary);
  const modBits =
    modifiers.map((m) => `${m.modifier_id}(${m.delta_primary_pp >= 0 ? "+" : ""}${m.delta_primary_pp}pp)`).join(", ") ||
    "none";
  const knnBit =
    knnRatio != null
      ? `kNN=${knnRatio} (score=${bestScore.toFixed(3)}, n=${matches.length})`
      : "kNN=unavailable";

  for (const m of modifiers) {
    if (m.citation && !citations.includes(m.citation)) citations.push(m.citation);
  }

  return {
    fault_ratio: faultRatio,
    primary_pct: finalPrimary,
    secondary_pct: 100 - finalPrimary,
    baseline_ratio: baseline,
    situation,
    role_a: roleA,
    role_b: roleB,
    rule_adjusted_ratio: ruleAdjusted,
    knn_ratio: knnRatio,
    modifiers,
    matches,
    rationale: `Situation=${situation} baseline=${baseline} → rule-adjusted=${ruleAdjusted} via modifiers[${modBits}]; ${knnBit}; blended=${faultRatio}.`,
    rule_citations: citations,
  };
}

/** DuckDB-WASM cosine kNN over civil_precedents.parquet */
export async function knnByDuckDb(
  narrative: string,
  parquetUrl: string,
  topK = 3,
): Promise<{ matches: PrecedentMatch[]; bestScore: number; ratio: string | null }> {
  const { withConnection } = await import("../db/duckdb");
  const q = hashEmbed(narrative);
  const embLiteral = `[${q.join(", ")}]`;
  return withConnection(async (conn) => {
    await conn.query(
      `CREATE OR REPLACE TABLE civil AS SELECT * FROM read_parquet('${parquetUrl}')`,
    );
    const result = await conn.query(`
      SELECT case_id, title, fault_ratio,
             list_cosine_similarity(embedding, ${embLiteral}::FLOAT[]) AS score
      FROM civil
      ORDER BY score DESC, case_id
      LIMIT ${topK}
    `);
    const matches: PrecedentMatch[] = [];
    let weightedSum = 0;
    let weightTotal = 0;
    for (let i = 0; i < result.numRows; i++) {
      const row = result.get(i)!.toJSON() as Record<string, unknown>;
      const score = Number(row.score) || 0;
      const fault = String(row.fault_ratio || "");
      matches.push({
        case_id: String(row.case_id),
        title: String(row.title),
        fault_ratio: fault,
        score,
      });
      if (fault) {
        try {
          const [a] = parseFaultRatio(fault);
          const w = Math.max(score, 1e-6);
          weightedSum += a * w;
          weightTotal += w;
        } catch {
          /* skip */
        }
      }
    }
    const bestScore = matches[0]?.score ?? 0;
    if (weightTotal <= 0) return { matches, bestScore, ratio: null };
    return {
      matches,
      bestScore,
      ratio: formatFaultRatio(Math.round(weightedSum / weightTotal)),
    };
  });
}
