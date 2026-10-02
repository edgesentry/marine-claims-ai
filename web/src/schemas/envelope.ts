/**
 * Shared Stage A ExtractionResult envelope (Issue #87 / #88).
 * Tier 1–3 extractors emit this shape; Stage B scorers only run after validation.
 */
import { z } from "zod";

export const SCHEMA_IDS = ["rule_d5.v1", "colregs.v1", "psc.v1"] as const;
export type SchemaId = (typeof SCHEMA_IDS)[number];

export const SchemaIdSchema = z.enum(SCHEMA_IDS);

/** PDF text-layer / OCR bounding box (Issue #88). */
export const PdfCoordinatesSchema = z.object({
  page: z.number().int().positive(),
  x0: z.number().finite(),
  y0: z.number().finite(),
  x1: z.number().finite(),
  y1: z.number().finite(),
});

export const GroundingRefSchema = z.object({
  field: z.string().optional(),
  source_quote: z.string().min(1),
  page_number: z.number().int().nullable().optional(),
  pdf_coordinates: PdfCoordinatesSchema.nullable().optional(),
});

export const AbstainSchema = z.object({
  code: z.literal("HUMAN_REVIEW_REQUIRED"),
  reason: z.string().min(1),
});

/** Per-field confidence map (payload path → 0..1). Issue #89. */
export const FieldConfidenceSchema = z.record(
  z.string(),
  z.number().min(0).max(1),
);

/** Envelope fields shared by every UC (payload validated separately). */
export const ExtractionEnvelopeBaseSchema = z.object({
  schema_id: SchemaIdSchema,
  confidence: z.number().min(0).max(1),
  grounding: z.array(GroundingRefSchema).default([]),
  field_confidence: FieldConfidenceSchema.optional(),
  abstain: AbstainSchema.optional(),
});

export type PdfCoordinates = z.infer<typeof PdfCoordinatesSchema>;
export type GroundingRef = z.infer<typeof GroundingRefSchema>;
export type FieldConfidence = z.infer<typeof FieldConfidenceSchema>;
export type Abstain = z.infer<typeof AbstainSchema>;
