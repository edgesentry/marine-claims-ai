/**
 * Exact Span grounding gate before Stage B (Issue #88).
 * Shape validation stays in assertValidForStageB; this enforces source grounding
 * unless an explicit paste_bypass mode is set.
 */
import { quoteInText } from "./spanValidate";
import type { GroundingRef } from "../schemas/envelope";
import type {
  ColregsExtraction,
  ExtractionResult,
  PscExtraction,
  RuleD5Extraction,
} from "../schemas/validate";

export type GroundingMode = "require_span" | "paste_bypass";

export class GroundingValidationError extends Error {
  readonly missingFields: string[];

  constructor(message: string, missingFields: string[] = []) {
    super(message);
    this.name = "GroundingValidationError";
    this.missingFields = missingFields;
  }
}

export interface GroundingGateOptions {
  mode?: GroundingMode;
  /** When set, each required source_quote must appear in this text. */
  sourceText?: string;
}

function groundedFields(grounding: GroundingRef[]): Set<string> {
  const fields = new Set<string>();
  for (const g of grounding) {
    if (g.field && g.source_quote?.trim()) fields.add(g.field);
  }
  return fields;
}

function requiredRuleD5Fields(extraction: RuleD5Extraction): string[] {
  // PDF-derived line ids are `pdf-*`. Synthetic UI injects (dock-1, hull-1, …)
  // are completed by repairItemsToRuleDLines and are not Exact-Span critical.
  return extraction.payload.lines
    .filter((ln) => String(ln.id).startsWith("pdf-"))
    .map((ln) => `lines.${ln.id}`);
}

function requiredColregsFields(extraction: ColregsExtraction): string[] {
  const fields: string[] = [];
  const p = extraction.payload;
  if (p.facts_excerpt?.trim()) fields.push("facts_excerpt");
  if (p.ruling_excerpt?.trim()) fields.push("ruling_excerpt");
  // Telemetry extracted from narrative (#91) — require grounding when present.
  const telemetryKeys = [
    "geometry.heading_a_deg",
    "geometry.heading_b_deg",
    "geometry.true_bearing_a_to_b_deg",
    "geometry.speed_a_kn",
    "geometry.speed_b_kn",
    "geometry.range_nm",
  ] as const;
  for (const key of telemetryKeys) {
    if (extraction.grounding.some((g) => g.field === key)) {
      fields.push(key);
    }
  }
  return fields;
}

function requiredPscFields(extraction: PscExtraction): string[] {
  return extraction.payload.deficiencies.map((_, i) => `deficiencies.${i}.code`);
}

export function criticalFieldsFor(extraction: ExtractionResult): string[] {
  switch (extraction.schema_id) {
    case "rule_d5.v1":
      return requiredRuleD5Fields(extraction);
    case "colregs.v1":
      return requiredColregsFields(extraction);
    case "psc.v1":
      return requiredPscFields(extraction);
  }
}

/**
 * Reject Stage B entry when critical fields lack grounding (or fail span check).
 * `paste_bypass` skips all checks (hand-pasted JSON / fixtures / synthetic UI).
 */
export function assertGroundingForStageB(
  extraction: ExtractionResult,
  opts: GroundingGateOptions = {},
): ExtractionResult {
  const mode = opts.mode ?? "require_span";
  if (mode === "paste_bypass") return extraction;

  const required = criticalFieldsFor(extraction);
  if (!required.length) return extraction;

  const present = groundedFields(extraction.grounding);
  const missing = required.filter((f) => !present.has(f));
  if (missing.length) {
    throw new GroundingValidationError(
      `Ungrounded critical fields for Stage B (${extraction.schema_id}): ${missing.join(", ")}`,
      missing,
    );
  }

  const sourceText = opts.sourceText;
  if (sourceText != null && sourceText.length > 0) {
    const bad: string[] = [];
    for (const g of extraction.grounding) {
      if (!g.field || !required.includes(g.field)) continue;
      if (!quoteInText(g.source_quote, sourceText)) {
        bad.push(g.field);
      }
    }
    if (bad.length) {
      throw new GroundingValidationError(
        `source_quote not grounded in source text: ${bad.join(", ")}`,
        bad,
      );
    }
  }

  return extraction;
}
