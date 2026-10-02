/**
 * Stage A confidence thresholds (Issue #89).
 *
 * Engineering defaults for demos and CI — not statutory cut-offs and not
 * legal opinion thresholds. Override per schema_id when needed.
 */
import type { SchemaId } from "../schemas/envelope";

export interface ConfidenceThresholds {
  /** Document-level confidence must be >= this under enforce mode. */
  document_min: number;
  /** Critical fields with field_confidence entries must be >= this. */
  field_min: number;
}

/** Global engineering defaults (not statutory). */
export const DEFAULT_CONFIDENCE_THRESHOLDS: ConfidenceThresholds = {
  document_min: 0.7,
  field_min: 0.6,
};

/** Optional per-UC overrides (still engineering defaults). */
export const CONFIDENCE_THRESHOLDS_BY_SCHEMA: Partial<
  Record<SchemaId, Partial<ConfidenceThresholds>>
> = {
  // Keep defaults; slots reserved for future UC-specific tuning.
};

export function thresholdsForSchema(schemaId: SchemaId): ConfidenceThresholds {
  const override = CONFIDENCE_THRESHOLDS_BY_SCHEMA[schemaId] ?? {};
  return {
    document_min: override.document_min ?? DEFAULT_CONFIDENCE_THRESHOLDS.document_min,
    field_min: override.field_min ?? DEFAULT_CONFIDENCE_THRESHOLDS.field_min,
  };
}
