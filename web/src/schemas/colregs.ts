/**
 * COLREGS Stage A payload (schema_id: colregs.v1).
 * Geometry feeds classifyEncounter; excerpts feed predictFaultRatio.
 */
import { z } from "zod";

export const EncounterSituationSchema = z.enum([
  "head_on",
  "overtaking",
  "crossing",
  "safe_passing",
]);

export const DocumentKindSchema = z.enum(["judgment", "jtsb"]);

export const EncounterGeometrySchema = z.object({
  heading_a_deg: z.number().finite(),
  heading_b_deg: z.number().finite(),
  true_bearing_a_to_b_deg: z.number().finite(),
  power_driven_a: z.boolean().optional(),
  power_driven_b: z.boolean().optional(),
  range_nm: z.number().finite().nullable().optional(),
  speed_a_kn: z.number().finite().nullable().optional(),
  speed_b_kn: z.number().finite().nullable().optional(),
});

export const SituationCandidateSchema = z.object({
  situation: EncounterSituationSchema,
  confidence: z.number().min(0).max(1),
});

export const ColregsPayloadSchema = z.object({
  geometry: EncounterGeometrySchema,
  facts_excerpt: z.string().optional(),
  ruling_excerpt: z.string().optional(),
  situation_candidates: z.array(SituationCandidateSchema).optional(),
  fault_ratio_hint: z.string().optional(),
  document_kind: DocumentKindSchema.optional(),
});

export type ColregsPayload = z.infer<typeof ColregsPayloadSchema>;
export type EncounterGeometryPayload = z.infer<typeof EncounterGeometrySchema>;
