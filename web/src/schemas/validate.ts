/**
 * Validate Stage A ExtractionResult envelopes before Stage B.
 */
import { z } from "zod";
import {
  ExtractionEnvelopeBaseSchema,
  type SchemaId,
} from "./envelope";
import { RuleD5PayloadSchema, type RuleD5Payload } from "./ruleD5";
import { ColregsPayloadSchema, type ColregsPayload } from "./colregs";
import { PscPayloadSchema, type PscPayload } from "./psc";

const RuleD5ExtractionSchema = ExtractionEnvelopeBaseSchema.extend({
  schema_id: z.literal("rule_d5.v1"),
  payload: RuleD5PayloadSchema,
});

const ColregsExtractionSchema = ExtractionEnvelopeBaseSchema.extend({
  schema_id: z.literal("colregs.v1"),
  payload: ColregsPayloadSchema,
});

const PscExtractionSchema = ExtractionEnvelopeBaseSchema.extend({
  schema_id: z.literal("psc.v1"),
  payload: PscPayloadSchema,
});

export const ExtractionResultSchema = z.discriminatedUnion("schema_id", [
  RuleD5ExtractionSchema,
  ColregsExtractionSchema,
  PscExtractionSchema,
]);

export type ExtractionResult = z.infer<typeof ExtractionResultSchema>;
export type RuleD5Extraction = z.infer<typeof RuleD5ExtractionSchema>;
export type ColregsExtraction = z.infer<typeof ColregsExtractionSchema>;
export type PscExtraction = z.infer<typeof PscExtractionSchema>;

export type PayloadFor<S extends SchemaId> = S extends "rule_d5.v1"
  ? RuleD5Payload
  : S extends "colregs.v1"
    ? ColregsPayload
    : PscPayload;

export class ExtractionValidationError extends Error {
  readonly issues: Array<{ path: PropertyKey[]; message: string; code?: string }>;

  constructor(
    message: string,
    issues: Array<{ path: PropertyKey[]; message: string; code?: string }>,
  ) {
    super(message);
    this.name = "ExtractionValidationError";
    this.issues = issues;
  }
}

export function safeParseExtraction(
  input: unknown,
): ReturnType<typeof ExtractionResultSchema.safeParse> {
  return ExtractionResultSchema.safeParse(input);
}

export function parseExtraction(input: unknown): ExtractionResult {
  const result = ExtractionResultSchema.safeParse(input);
  if (!result.success) {
    throw new ExtractionValidationError(
      `Invalid ExtractionResult: ${result.error.issues.map((i) => i.message).join("; ")}`,
      result.error.issues,
    );
  }
  return result.data;
}

/**
 * Gate for Stage B: reject invalid envelopes so scorers never see bad JSON.
 * Does not block on optional `abstain` — Issue #89 confidence gate / UI handles that.
 */
export function assertValidForStageB(input: unknown): ExtractionResult {
  return parseExtraction(input);
}

export function isRuleD5Extraction(r: ExtractionResult): r is RuleD5Extraction {
  return r.schema_id === "rule_d5.v1";
}

export function isColregsExtraction(r: ExtractionResult): r is ColregsExtraction {
  return r.schema_id === "colregs.v1";
}

export function isPscExtraction(r: ExtractionResult): r is PscExtraction {
  return r.schema_id === "psc.v1";
}
