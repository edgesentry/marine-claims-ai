/**
 * PSC Stage A payload (schema_id: psc.v1).
 * Extractor-facing fields only; severity/category weights are Stage B derived.
 */
import { z } from "zod";

/** Pre-normalization deficiency row (code required). */
export const PscDeficiencyExtractSchema = z.object({
  code: z.string().min(1),
  action_code: z.string().nullable().optional(),
  description: z.string().optional(),
  inspection_date: z.string().nullable().optional(),
  mou_id: z.string().nullable().optional(),
});

export const PscPayloadSchema = z.object({
  deficiencies: z.array(PscDeficiencyExtractSchema).min(1),
  prior_deficiencies: z.array(PscDeficiencyExtractSchema).optional(),
  lookback_months: z.number().int().positive().optional(),
  cic_weights: z.record(z.string(), z.number()).optional(),
  mou_id: z.string().nullable().optional(),
});

export type PscPayload = z.infer<typeof PscPayloadSchema>;
export type PscDeficiencyExtract = z.infer<typeof PscDeficiencyExtractSchema>;
