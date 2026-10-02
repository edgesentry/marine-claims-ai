/**
 * JSON Schema export + guided-decode hooks for Tier 2 SLM / Tier 3 LLM (Issues #77 / #5).
 * Does not invoke any model; callers pass the returned schema to constrained decoding.
 */
import { z } from "zod";
import type { SchemaId } from "./envelope";
import { SCHEMA_IDS } from "./envelope";
import { ExtractionResultSchema } from "./validate";
import { RuleD5PayloadSchema } from "./ruleD5";
import { ColregsPayloadSchema } from "./colregs";
import { PscPayloadSchema } from "./psc";

const PAYLOAD_SCHEMAS = {
  "rule_d5.v1": RuleD5PayloadSchema,
  "colregs.v1": ColregsPayloadSchema,
  "psc.v1": PscPayloadSchema,
} as const;

const SYSTEM_HINTS: Record<SchemaId, string> = {
  "rule_d5.v1":
    "Emit a single JSON object matching the ExtractionResult envelope with schema_id \"rule_d5.v1\". " +
    "payload.lines must list repair works with numeric cost (JPY). docking_context is casualty_immediate or deferred_to_routine.",
  "colregs.v1":
    "Emit a single JSON object matching the ExtractionResult envelope with schema_id \"colregs.v1\". " +
    "payload.geometry requires heading_a_deg, heading_b_deg, and true_bearing_a_to_b_deg. " +
    "Include facts_excerpt / ruling_excerpt when present in the source.",
  "psc.v1":
    "Emit a single JSON object matching the ExtractionResult envelope with schema_id \"psc.v1\". " +
    "payload.deficiencies requires at least one row with a MOU deficiency code. " +
    "Optional prior_deficiencies support repeat-window scoring.",
};

export type JsonSchemaObject = Record<string, unknown>;

export interface GuidedDecodeSpec {
  schema_id: SchemaId;
  json_schema: JsonSchemaObject;
  system_hint: string;
}

function toJsonSchemaObject(schema: z.ZodType): JsonSchemaObject {
  return z.toJSONSchema(schema) as JsonSchemaObject;
}

/** Full envelope JSON Schema for a given UC (includes payload). */
export function extractionJsonSchema(schemaId: SchemaId): JsonSchemaObject {
  const payload = PAYLOAD_SCHEMAS[schemaId];
  // Discriminated branch for one UC keeps guided decoding focused.
  const branch = z.object({
    schema_id: z.literal(schemaId),
    payload,
    confidence: z.number().min(0).max(1),
    grounding: z
      .array(
        z.object({
          field: z.string().optional(),
          source_quote: z.string().min(1),
          page_number: z.number().int().nullable().optional(),
          pdf_coordinates: z.unknown().nullable().optional(),
        }),
      )
      .default([]),
    abstain: z
      .object({
        code: z.literal("HUMAN_REVIEW_REQUIRED"),
        reason: z.string().min(1),
      })
      .optional(),
  });
  return toJsonSchemaObject(branch);
}

/** Payload-only JSON Schema (useful when the caller wraps the envelope itself). */
export function payloadJsonSchema(schemaId: SchemaId): JsonSchemaObject {
  return toJsonSchemaObject(PAYLOAD_SCHEMAS[schemaId]);
}

/** Union of all ExtractionResult branches (docs / interoperability). */
export function allExtractionJsonSchema(): JsonSchemaObject {
  return toJsonSchemaObject(ExtractionResultSchema);
}

export function guidedDecodeSpec(schemaId: SchemaId): GuidedDecodeSpec {
  return {
    schema_id: schemaId,
    json_schema: extractionJsonSchema(schemaId),
    system_hint: SYSTEM_HINTS[schemaId],
  };
}

export function allSchemaIds(): readonly SchemaId[] {
  return SCHEMA_IDS;
}
