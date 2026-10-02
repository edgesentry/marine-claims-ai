/**
 * Tier-1 adapters: map existing heuristic outputs into validated ExtractionResult envelopes.
 */
import type { DockingContext, RepairLineItem } from "../engines/ruleD5";
import type { EncounterGeometry } from "../engines/colregs";
import type { NormalizedDeficiency } from "../engines/psc";
import type { GroundingRef } from "./envelope";
import {
  assertGroundingForStageB,
  type GroundingMode,
} from "../pipeline/groundingGate";
import {
  applyConfidenceGate,
  resolveConfidenceMode,
  type ConfidenceMode,
} from "../pipeline/confidenceGate";
import type { ConfidenceThresholds } from "../config/confidenceThresholds";
import {
  assertValidForStageB,
  type ColregsExtraction,
  type ExtractionResult,
  type PscExtraction,
  type RuleD5Extraction,
} from "./validate";
import type { PscDeficiencyExtract } from "./psc";

function clampConfidence(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

function deficiencyToExtract(d: NormalizedDeficiency): PscDeficiencyExtract {
  return {
    code: d.code,
    action_code: d.action_code,
    description: d.description,
    inspection_date: d.inspection_date,
    mou_id: d.mou_id,
  };
}

export interface ExtractionBuildOpts {
  groundingMode?: GroundingMode;
  sourceText?: string;
  confidenceMode?: ConfidenceMode;
  field_confidence?: Record<string, number>;
  thresholds?: ConfidenceThresholds;
}

function gateEnvelope(
  envelope: unknown,
  opts: ExtractionBuildOpts,
): ExtractionResult {
  const shape = assertValidForStageB(envelope);
  const grounded = assertGroundingForStageB(shape, {
    mode: opts.groundingMode ?? "require_span",
    sourceText: opts.sourceText,
  });
  const confidenceMode = resolveConfidenceMode(
    opts.groundingMode,
    opts.confidenceMode,
  );
  return applyConfidenceGate(grounded, {
    mode: confidenceMode,
    thresholds: opts.thresholds,
  });
}

export function buildRuleD5Extraction(opts: {
  dockingContext: DockingContext;
  lines: RepairLineItem[];
  assumeStatutoryOwnerWork?: boolean;
  confidence?: number;
  field_confidence?: Record<string, number>;
  grounding?: GroundingRef[];
  groundingMode?: GroundingMode;
  confidenceMode?: ConfidenceMode;
  sourceText?: string;
  thresholds?: ConfidenceThresholds;
}): RuleD5Extraction {
  const envelope = {
    schema_id: "rule_d5.v1" as const,
    confidence: clampConfidence(opts.confidence ?? 0.6),
    grounding: opts.grounding ?? [],
    field_confidence: opts.field_confidence,
    payload: {
      docking_context: opts.dockingContext,
      lines: opts.lines.map((ln) => ({
        id: ln.id,
        cost: ln.cost,
        trade_code: ln.trade_code,
        work_party: ln.work_party ?? undefined,
        necessity: ln.necessity,
        title: ln.title,
      })),
      assume_statutory_owner_work: opts.assumeStatutoryOwnerWork,
    },
  };
  return gateEnvelope(envelope, opts) as RuleD5Extraction;
}

export function buildColregsExtraction(opts: {
  geometry: EncounterGeometry;
  factsExcerpt?: string;
  rulingExcerpt?: string;
  faultRatioHint?: string;
  documentKind?: "judgment" | "jtsb";
  situationCandidates?: Array<{
    situation: "head_on" | "overtaking" | "crossing" | "safe_passing";
    confidence: number;
  }>;
  confidence?: number;
  field_confidence?: Record<string, number>;
  grounding?: GroundingRef[];
  groundingMode?: GroundingMode;
  confidenceMode?: ConfidenceMode;
  sourceText?: string;
  thresholds?: ConfidenceThresholds;
}): ColregsExtraction {
  const envelope = {
    schema_id: "colregs.v1" as const,
    confidence: clampConfidence(opts.confidence ?? 0.5),
    grounding: opts.grounding ?? [],
    field_confidence: opts.field_confidence,
    payload: {
      geometry: {
        heading_a_deg: opts.geometry.heading_a_deg,
        heading_b_deg: opts.geometry.heading_b_deg,
        true_bearing_a_to_b_deg: opts.geometry.true_bearing_a_to_b_deg,
        power_driven_a: opts.geometry.power_driven_a,
        power_driven_b: opts.geometry.power_driven_b,
        range_nm: opts.geometry.range_nm,
        speed_a_kn: opts.geometry.speed_a_kn,
        speed_b_kn: opts.geometry.speed_b_kn,
      },
      facts_excerpt: opts.factsExcerpt,
      ruling_excerpt: opts.rulingExcerpt,
      situation_candidates: opts.situationCandidates,
      fault_ratio_hint: opts.faultRatioHint,
      document_kind: opts.documentKind,
    },
  };
  return gateEnvelope(envelope, opts) as ColregsExtraction;
}

export function buildPscExtraction(opts: {
  deficiencies: NormalizedDeficiency[] | PscDeficiencyExtract[];
  prior?: NormalizedDeficiency[] | PscDeficiencyExtract[] | null;
  lookbackMonths?: number;
  cicWeights?: Record<string, number> | null;
  mouId?: string | null;
  confidence?: number;
  field_confidence?: Record<string, number>;
  grounding?: GroundingRef[];
  groundingMode?: GroundingMode;
  confidenceMode?: ConfidenceMode;
  sourceText?: string;
  thresholds?: ConfidenceThresholds;
}): PscExtraction {
  const toExtract = (
    rows: Array<NormalizedDeficiency | PscDeficiencyExtract>,
  ): PscDeficiencyExtract[] =>
    rows.map((r) =>
      "severity_weight" in r
        ? deficiencyToExtract(r as NormalizedDeficiency)
        : {
            code: r.code,
            action_code: r.action_code ?? null,
            description: r.description,
            inspection_date: r.inspection_date ?? null,
            mou_id: r.mou_id ?? null,
          },
    );

  const envelope = {
    schema_id: "psc.v1" as const,
    confidence: clampConfidence(opts.confidence ?? 0.7),
    grounding: opts.grounding ?? [],
    field_confidence: opts.field_confidence,
    payload: {
      deficiencies: toExtract(opts.deficiencies),
      prior_deficiencies: opts.prior?.length ? toExtract(opts.prior) : undefined,
      lookback_months: opts.lookbackMonths,
      cic_weights: opts.cicWeights ?? undefined,
      mou_id: opts.mouId ?? undefined,
    },
  };
  return gateEnvelope(envelope, opts) as PscExtraction;
}

/** Map validated Rule D5 payload back to engine RepairLineItem[]. */
export function ruleD5LinesFromExtraction(
  extraction: RuleD5Extraction,
): RepairLineItem[] {
  return extraction.payload.lines.map((ln) => ({
    id: ln.id,
    cost: ln.cost,
    trade_code: ln.trade_code,
    work_party: ln.work_party ?? null,
    necessity: ln.necessity,
    title: ln.title,
  }));
}

export function geometryFromExtraction(
  extraction: ColregsExtraction,
): EncounterGeometry {
  return { ...extraction.payload.geometry };
}

/**
 * Validate any unknown JSON (e.g. SLM/LLM output) as an ExtractionResult.
 * Throws ExtractionValidationError on failure.
 * Grounding mode defaults to paste_bypass so raw envelope shape checks stay #87-compatible;
 * callers that need Exact Span should pass groundingMode + sourceText via build* or assertGroundingForStageB.
 * Confidence defaults to bypass with paste_bypass (Issue #89).
 */
export function gateExtraction(
  input: unknown,
  opts: ExtractionBuildOpts = {},
): ExtractionResult {
  return gateEnvelope(input, {
    groundingMode: opts.groundingMode ?? "paste_bypass",
    sourceText: opts.sourceText,
    confidenceMode: opts.confidenceMode,
    thresholds: opts.thresholds,
  });
}
