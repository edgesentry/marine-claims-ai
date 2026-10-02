/**
 * Document / field confidence gate before Stage B (Issue #89).
 * Shape (#87) and Exact Span (#88) stay separate; this stamps HUMAN_REVIEW_REQUIRED
 * abstention and blocks scorers under enforce mode unless confirmed/bypass.
 */
import {
  thresholdsForSchema,
  type ConfidenceThresholds,
} from "../config/confidenceThresholds";
import type { ExtractionResult } from "../schemas/validate";
import type { GroundingMode } from "./groundingGate";
import { criticalFieldsFor } from "./groundingGate";

export type ConfidenceMode = "enforce" | "confirmed" | "bypass";

export class ConfidenceValidationError extends Error {
  readonly reasonCodes: string[];

  constructor(message: string, reasonCodes: string[] = []) {
    super(message);
    this.name = "ConfidenceValidationError";
    this.reasonCodes = reasonCodes;
  }
}

export interface ConfidenceGateOptions {
  mode?: ConfidenceMode;
  thresholds?: ConfidenceThresholds;
  /**
   * When true, skip apply/assert (used after explicit user Confirm & score).
   * Prefer passing mode: "confirmed" instead.
   */
  skip?: boolean;
}

export interface ConfidenceAssessment {
  ok: boolean;
  document_confidence: number;
  document_min: number;
  field_min: number;
  reason_codes: string[];
  /** Human-readable summary for abstain.reason (no source quotes). */
  reason: string;
  field_failures: Array<{ field: string; confidence: number }>;
}

const GROUNDED_FIELD_CONFIDENCE = 0.8;

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

/**
 * Default confidenceMode from groundingMode: paste/fixtures bypass confidence;
 * document paths enforce.
 */
export function resolveConfidenceMode(
  groundingMode: GroundingMode | undefined,
  explicit?: ConfidenceMode,
): ConfidenceMode {
  if (explicit) return explicit;
  if (groundingMode === "paste_bypass") return "bypass";
  return "enforce";
}

function situationFieldConfidence(extraction: ExtractionResult): Record<string, number> {
  const out: Record<string, number> = {};
  if (extraction.schema_id !== "colregs.v1") return out;
  const cands = extraction.payload.situation_candidates;
  if (!cands?.length) return out;
  const top = [...cands].sort((a, b) => b.confidence - a.confidence)[0];
  if (top) out["situation_candidates"] = clamp01(top.confidence);
  return out;
}

/** Fill missing field_confidence for critical fields (Tier-1 heuristics). */
export function enrichFieldConfidence(
  extraction: ExtractionResult,
): Record<string, number> {
  const existing = { ...(extraction.field_confidence ?? {}) };
  const grounded = new Set(
    extraction.grounding
      .filter((g) => g.field && g.source_quote?.trim())
      .map((g) => g.field as string),
  );
  const doc = clamp01(extraction.confidence);
  for (const field of criticalFieldsFor(extraction)) {
    if (existing[field] != null) continue;
    existing[field] = grounded.has(field) ? GROUNDED_FIELD_CONFIDENCE : doc;
  }
  Object.assign(existing, situationFieldConfidence(extraction));
  return existing;
}

export function assessConfidence(
  extraction: ExtractionResult,
  thresholds?: ConfidenceThresholds,
): ConfidenceAssessment {
  const t = thresholds ?? thresholdsForSchema(extraction.schema_id);
  const document_confidence = clamp01(extraction.confidence);
  const reason_codes: string[] = [];
  const field_failures: Array<{ field: string; confidence: number }> = [];

  if (document_confidence < t.document_min) {
    reason_codes.push("document_below_min");
  }

  const fieldMap = enrichFieldConfidence(extraction);
  const critical = new Set(criticalFieldsFor(extraction));
  for (const [field, conf] of Object.entries(fieldMap)) {
    if (!critical.has(field) && field !== "situation_candidates") continue;
    if (conf < t.field_min) {
      reason_codes.push(`field_below_min:${field}`);
      field_failures.push({ field, confidence: conf });
    }
  }

  const ok = reason_codes.length === 0;
  const reason = ok
    ? "ok"
    : [
        `HUMAN_REVIEW_REQUIRED (${extraction.schema_id})`,
        `document=${document_confidence.toFixed(2)} min=${t.document_min.toFixed(2)}`,
        ...reason_codes,
      ].join("; ");

  return {
    ok,
    document_confidence,
    document_min: t.document_min,
    field_min: t.field_min,
    reason_codes,
    reason,
    field_failures,
  };
}

/**
 * Stamp field_confidence and optional abstain. Does not throw — payload stays
 * available for the human-review UI.
 */
export function applyConfidenceGate(
  extraction: ExtractionResult,
  opts: ConfidenceGateOptions = {},
): ExtractionResult {
  const mode = opts.mode ?? "enforce";
  if (mode === "bypass" || mode === "confirmed" || opts.skip) {
    const field_confidence = enrichFieldConfidence(extraction);
    const { abstain: _drop, ...rest } = extraction;
    void _drop;
    return { ...rest, field_confidence } as ExtractionResult;
  }

  const thresholds = opts.thresholds ?? thresholdsForSchema(extraction.schema_id);
  const field_confidence = enrichFieldConfidence(extraction);
  const withFields = { ...extraction, field_confidence } as ExtractionResult;
  const assessment = assessConfidence(withFields, thresholds);

  if (assessment.ok) {
    const { abstain: _drop, ...rest } = withFields;
    void _drop;
    return rest as ExtractionResult;
  }

  logAbstain({
    schema_id: extraction.schema_id,
    document_confidence: assessment.document_confidence,
    reason_codes: assessment.reason_codes,
  });

  return {
    ...withFields,
    abstain: {
      code: "HUMAN_REVIEW_REQUIRED",
      reason: assessment.reason,
    },
  } as ExtractionResult;
}

/**
 * Reject Stage B entry when enforce mode sees abstain / below-threshold confidence.
 */
export function assertConfidenceForStageB(
  extraction: ExtractionResult,
  opts: ConfidenceGateOptions = {},
): ExtractionResult {
  const mode = opts.mode ?? "enforce";
  if (mode === "bypass" || mode === "confirmed" || opts.skip) {
    return extraction;
  }

  const thresholds = opts.thresholds ?? thresholdsForSchema(extraction.schema_id);
  const assessment = assessConfidence(extraction, thresholds);
  if (extraction.abstain?.code === "HUMAN_REVIEW_REQUIRED" || !assessment.ok) {
    throw new ConfidenceValidationError(
      extraction.abstain?.reason ?? assessment.reason,
      assessment.reason_codes.length
        ? assessment.reason_codes
        : ["HUMAN_REVIEW_REQUIRED"],
    );
  }
  return extraction;
}

/**
 * Safe abstain telemetry: reason codes + numeric confidence only.
 * Never log source_quote, PDF text, or other Zero-Dataset content.
 */
export function logAbstain(event: {
  schema_id: string;
  document_confidence: number;
  reason_codes: string[];
}): void {
  // Structured, quote-free log for demos / local debug.
  console.info(
    JSON.stringify({
      event: "stage_a_abstain",
      schema_id: event.schema_id,
      document_confidence: event.document_confidence,
      reason_codes: event.reason_codes,
    }),
  );
}
