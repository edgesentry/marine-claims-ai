/**
 * Document-type auto-router (Issue #86).
 * Heuristic Tier-1 classifier before UC extractors / Stage B.
 * Optional SLM (#77) is out of scope — reserved via ClassifierBackend.
 */

export const DOCUMENT_TYPES = [
  "repair_spec",
  "civil_judgment",
  "jmat_ruling",
  "jtsb_report",
  "psc_inspection",
  "unknown",
] as const;

export type DocumentType = (typeof DOCUMENT_TYPES)[number];

/** Known types only (excludes unknown). */
export type KnownDocumentType = Exclude<DocumentType, "unknown">;

export type DemoTab = "uc2" | "uc3" | "psc";

export type ClassifierBackend = "heuristic" | "slm"; // slm = future #77

export interface DocumentClassification {
  type: DocumentType;
  confidence: number;
  signals: string[];
  scores: Partial<Record<KnownDocumentType, number>>;
  backend: ClassifierBackend;
}

export type RouteBlockReason = "ok" | "unknown" | "tab_mismatch";

export interface RouteDecision {
  allowed: boolean;
  reason: RouteBlockReason;
  detected: DocumentType;
  effective: DocumentType;
  confidence: number;
  signals: string[];
}

/** Tab → document types that may run Stage B without override. */
export const TAB_ALLOWED_TYPES: Record<DemoTab, ReadonlySet<KnownDocumentType>> = {
  uc2: new Set(["repair_spec"]),
  uc3: new Set(["civil_judgment", "jmat_ruling", "jtsb_report"]),
  psc: new Set(["psc_inspection"]),
};

const HEAD_CHARS = 12_000;
const MIN_CONFIDENCE = 0.45;
/** If runner-up is within this fraction of the top score → ambiguous → unknown. */
const AMBIGUITY_RATIO = 0.85;

interface PatternRule {
  type: KnownDocumentType;
  weight: number;
  label: string;
  pattern: RegExp;
}

const RULES: PatternRule[] = [
  // repair_spec
  { type: "repair_spec", weight: 3, label: "drydock", pattern: /dry\s*dock|ドライドック|入渠|滞渠/i },
  {
    type: "repair_spec",
    weight: 3,
    label: "repair_spec",
    pattern: /repair\s+specification|修繕仕様|工事仕様|仕様書|見積/i,
  },
  {
    type: "repair_spec",
    weight: 2,
    label: "shipyard_works",
    pattern: /【甲板部】|【機関部】|ケレン|外板|塗装工事|船底/i,
  },
  {
    type: "repair_spec",
    weight: 2,
    label: "yen_line_items",
    pattern: /(?:¥|￥|円)\s*[\d,]+|[\d,]{4,}\s*円/,
  },
  {
    type: "repair_spec",
    weight: 1,
    label: "work_item_table",
    pattern: /工事番号|摘要|単価|数量|estimated\s*cost/i,
  },

  // civil_judgment
  {
    type: "civil_judgment",
    weight: 3,
    label: "court",
    pattern: /裁判所|地方裁判所|高等裁判所|Supreme\s+Court|District\s+Court/i,
  },
  { type: "civil_judgment", weight: 3, label: "judgment", pattern: /判決|主文|判示|judgment|holding/i },
  {
    type: "civil_judgment",
    weight: 2,
    label: "fault_ratio",
    pattern: /過失割合|原告|被告|損害賠償|fault\s*ratio/i,
  },
  { type: "civil_judgment", weight: 1, label: "civil_case", pattern: /民事|訴訟|訴え/i },

  // jmat_ruling
  {
    type: "jmat_ruling",
    weight: 4,
    label: "jmat",
    pattern: /海難審判|海難審判所|Japan\s+Marine\s+Accident\s+Tribunal|JMAT/i,
  },
  { type: "jmat_ruling", weight: 3, label: "adjudication", pattern: /裁決|審決|裁決書/i },
  {
    type: "jmat_ruling",
    weight: 2,
    label: "tribunal_parties",
    pattern: /受審人|指定海難関係人|海技士/i,
  },

  // jtsb_report
  {
    type: "jtsb_report",
    weight: 4,
    label: "jtsb",
    pattern: /運輸安全委員会|Japan\s+Transport\s+Safety\s+Board|JTSB/i,
  },
  {
    type: "jtsb_report",
    weight: 3,
    label: "accident_investigation",
    pattern: /船舶事故調査|Marine\s+Accident\s+Investigation|事故調査報告書/i,
  },
  { type: "jtsb_report", weight: 2, label: "cause_section", pattern: /＜原因＞|原因認定|本事故は、/ },
  {
    type: "jtsb_report",
    weight: 1,
    label: "safety_recs",
    pattern: /再発防止|安全勧告|意見/i,
  },

  // psc_inspection
  {
    type: "psc_inspection",
    weight: 3,
    label: "mou",
    pattern: /Tokyo\s+MOU|Paris\s+MOU|ポートステート|Port\s+State\s+Control|PSC/i,
  },
  {
    type: "psc_inspection",
    weight: 3,
    label: "deficiency",
    pattern: /deficiency|deficiencies|欠陥|不適合|detain(?:ion|ed)?/i,
  },
  {
    type: "psc_inspection",
    weight: 2,
    label: "code_rows",
    pattern: /\b(?:0[1-9]|1[0-5])\d{3}\b/,
  },
  {
    type: "psc_inspection",
    weight: 2,
    label: "action_codes",
    pattern: /action(?:_|\s*)(?:taken|code)|是正|コード\s*1[567]|code\s*1[567]/i,
  },
  {
    type: "psc_inspection",
    weight: 1,
    label: "conventions",
    pattern: /\bSOLAS\b|\bMARPOL\b|\bISM\b|\bSTCW\b/i,
  },
];

const FILENAME_HINTS: Array<{ type: KnownDocumentType; weight: number; label: string; pattern: RegExp }> = [
  { type: "repair_spec", weight: 2, label: "filename_repair", pattern: /repair|drydock|仕様|見積|tender/i },
  { type: "civil_judgment", weight: 2, label: "filename_judgment", pattern: /judgment|判決|civil/i },
  { type: "jmat_ruling", weight: 2, label: "filename_jmat", pattern: /jmat|裁決|海難審判/i },
  { type: "jtsb_report", weight: 2, label: "filename_jtsb", pattern: /jtsb|事故調査|maia/i },
  { type: "psc_inspection", weight: 2, label: "filename_psc", pattern: /psc|deficiency|mou/i },
];

function emptyScores(): Record<KnownDocumentType, number> {
  return {
    repair_spec: 0,
    civil_judgment: 0,
    jmat_ruling: 0,
    jtsb_report: 0,
    psc_inspection: 0,
  };
}

/**
 * Classify document text (and optional filename) into a UC document type.
 * Low confidence or near-ties become `unknown` so Stage B never runs silently.
 */
export function classifyDocument(
  text: string,
  opts?: { filename?: string; headChars?: number },
): DocumentClassification {
  const head = String(text || "").slice(0, opts?.headChars ?? HEAD_CHARS);
  const scores = emptyScores();
  const signals: string[] = [];

  for (const rule of RULES) {
    if (!rule.pattern.test(head)) continue;
    scores[rule.type] += rule.weight;
    signals.push(`${rule.type}:${rule.label}`);
  }

  const filename = opts?.filename?.trim();
  if (filename) {
    for (const hint of FILENAME_HINTS) {
      if (!hint.pattern.test(filename)) continue;
      scores[hint.type] += hint.weight;
      signals.push(`${hint.type}:${hint.label}`);
    }
  }

  const ranked = (Object.entries(scores) as Array<[KnownDocumentType, number]>)
    .filter(([, s]) => s > 0)
    .sort((a, b) => b[1] - a[1]);

  if (ranked.length === 0) {
    return {
      type: "unknown",
      confidence: 0,
      signals,
      scores,
      backend: "heuristic",
    };
  }

  const [topType, topScore] = ranked[0]!;
  const secondScore = ranked[1]?.[1] ?? 0;
  const total = ranked.reduce((acc, [, s]) => acc + s, 0);
  const confidence = topScore / Math.max(total, 1);

  const ambiguous = secondScore > 0 && secondScore / topScore >= AMBIGUITY_RATIO;
  if (ambiguous || confidence < MIN_CONFIDENCE || topScore < 3) {
    return {
      type: "unknown",
      confidence,
      signals: [...signals, ambiguous ? "ambiguous_tie" : "low_confidence"],
      scores,
      backend: "heuristic",
    };
  }

  return {
    type: topType,
    confidence,
    signals,
    scores,
    backend: "heuristic",
  };
}

export function isKnownDocumentType(type: DocumentType): type is KnownDocumentType {
  return type !== "unknown";
}

export function tabAllowsType(tab: DemoTab, type: DocumentType): boolean {
  if (!isKnownDocumentType(type)) return false;
  return TAB_ALLOWED_TYPES[tab].has(type);
}

/**
 * Resolve whether Stage B may run for this tab.
 * Override (when a known type) always wins; otherwise detected type must be tab-allowed.
 */
export function resolveDocumentRoute(
  tab: DemoTab,
  classification: DocumentClassification,
  override?: DocumentType | null,
): RouteDecision {
  const detected = classification.type;
  const effective =
    override && isKnownDocumentType(override) ? override : detected;

  if (!isKnownDocumentType(effective)) {
    return {
      allowed: false,
      reason: "unknown",
      detected,
      effective,
      confidence: classification.confidence,
      signals: classification.signals,
    };
  }

  if (!tabAllowsType(tab, effective)) {
    return {
      allowed: false,
      reason: "tab_mismatch",
      detected,
      effective,
      confidence: classification.confidence,
      signals: classification.signals,
    };
  }

  return {
    allowed: true,
    reason: "ok",
    detected,
    effective,
    confidence: classification.confidence,
    signals: classification.signals,
  };
}

/** True when Stage B must not run (unknown or tab mismatch without valid override). */
export function shouldAbstainFromStageB(decision: RouteDecision): boolean {
  return !decision.allowed;
}

export function documentTypeLabel(type: DocumentType, lang: "en" | "ja" = "en"): string {
  const labels: Record<DocumentType, { en: string; ja: string }> = {
    repair_spec: { en: "Repair specification", ja: "修繕仕様書" },
    civil_judgment: { en: "Civil judgment", ja: "民事判決" },
    jmat_ruling: { en: "JMAT ruling", ja: "海難審判裁決" },
    jtsb_report: { en: "JTSB investigation report", ja: "運輸安全委員会報告書" },
    psc_inspection: { en: "PSC inspection", ja: "PSC 検査" },
    unknown: { en: "Unknown", ja: "不明" },
  };
  return labels[type][lang];
}
