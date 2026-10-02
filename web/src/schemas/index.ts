/**
 * Stage A extraction contracts shared by Tier 1–3 (Issue #87).
 */
export {
  SCHEMA_IDS,
  SchemaIdSchema,
  PdfCoordinatesSchema,
  GroundingRefSchema,
  FieldConfidenceSchema,
  AbstainSchema,
  ExtractionEnvelopeBaseSchema,
  type SchemaId,
  type PdfCoordinates,
  type GroundingRef,
  type Abstain,
} from "./envelope";

export {
  DockingContextSchema,
  WorkPartySchema,
  OwnerNecessitySchema,
  RepairLineSchema,
  RuleD5PayloadSchema,
  type RuleD5Payload,
  type RepairLinePayload,
} from "./ruleD5";

export {
  EncounterSituationSchema,
  DocumentKindSchema,
  EncounterGeometrySchema,
  SituationCandidateSchema,
  ColregsPayloadSchema,
  type ColregsPayload,
  type EncounterGeometryPayload,
} from "./colregs";

export {
  PscDeficiencyExtractSchema,
  PscPayloadSchema,
  type PscPayload,
  type PscDeficiencyExtract,
} from "./psc";

export {
  ExtractionResultSchema,
  ExtractionValidationError,
  safeParseExtraction,
  parseExtraction,
  assertValidForStageB,
  isRuleD5Extraction,
  isColregsExtraction,
  isPscExtraction,
  type ExtractionResult,
  type RuleD5Extraction,
  type ColregsExtraction,
  type PscExtraction,
} from "./validate";

export {
  extractionJsonSchema,
  payloadJsonSchema,
  allExtractionJsonSchema,
  guidedDecodeSpec,
  allSchemaIds,
  type GuidedDecodeSpec,
  type JsonSchemaObject,
} from "./jsonSchema";

export {
  buildRuleD5Extraction,
  buildColregsExtraction,
  buildPscExtraction,
  ruleD5LinesFromExtraction,
  geometryFromExtraction,
  gateExtraction,
} from "./adapters";

export {
  assertGroundingForStageB,
  criticalFieldsFor,
  GroundingValidationError,
  type GroundingMode,
  type GroundingGateOptions,
} from "../pipeline/groundingGate";

export {
  assessConfidence,
  applyConfidenceGate,
  assertConfidenceForStageB,
  logAbstain,
  resolveConfidenceMode,
  ConfidenceValidationError,
  type ConfidenceMode,
  type ConfidenceGateOptions,
  type ConfidenceAssessment,
} from "../pipeline/confidenceGate";
