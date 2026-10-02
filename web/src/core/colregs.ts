/**
 * Shared COLREGS Stage A → Stage B runner (PWA + CLI via web/src/core).
 */
import {
  classifyEncounter,
  type EncounterGeometry,
  type EncounterVerdict,
} from "../engines/colregs";
import {
  predictFaultRatio,
  type CatalogSeed,
  type FaultRules,
  type FaultPrediction,
} from "../engines/fault";
import {
  buildColregsExtraction,
  geometryFromExtraction,
  type ColregsExtraction,
  type GroundingRef,
} from "../schemas";

export interface ColregsRunInput {
  geometry: EncounterGeometry;
  factsExcerpt?: string;
  rulingExcerpt?: string;
  title?: string;
  faultRatioHint?: string;
  documentKind?: "judgment" | "jtsb";
  situationCandidates?: Array<{
    situation: "head_on" | "overtaking" | "crossing" | "safe_passing";
    confidence: number;
  }>;
  confidence?: number;
  grounding?: GroundingRef[];
  rules?: FaultRules | null;
  seeds?: CatalogSeed[];
}

export interface ColregsRunResult {
  extraction: ColregsExtraction;
  geometry: EncounterGeometry;
  verdict: EncounterVerdict;
  fault_ratio: string;
  prediction: FaultPrediction | null;
}

export function runColregs(input: ColregsRunInput): ColregsRunResult {
  const autoGrounding: GroundingRef[] = [];
  if (input.factsExcerpt) {
    autoGrounding.push({
      field: "facts_excerpt",
      source_quote: input.factsExcerpt.slice(0, 240),
    });
  }
  if (input.rulingExcerpt) {
    autoGrounding.push({
      field: "ruling_excerpt",
      source_quote: input.rulingExcerpt.slice(0, 240),
    });
  }
  const grounding = input.grounding ?? autoGrounding;

  const extraction = buildColregsExtraction({
    geometry: input.geometry,
    factsExcerpt: input.factsExcerpt,
    rulingExcerpt: input.rulingExcerpt,
    faultRatioHint: input.faultRatioHint,
    documentKind: input.documentKind,
    situationCandidates: input.situationCandidates,
    confidence: input.confidence ?? 0.6,
    grounding,
  });
  const geometry = geometryFromExtraction(extraction);
  const verdict = classifyEncounter(geometry);
  const narrative =
    extraction.payload.facts_excerpt ||
    extraction.payload.ruling_excerpt ||
    input.title ||
    "";
  const prediction =
    input.rules != null
      ? predictFaultRatio(
          narrative,
          input.rules,
          input.seeds ?? [],
          geometry,
        )
      : null;
  const fault_ratio =
    input.faultRatioHint ||
    extraction.payload.fault_ratio_hint ||
    prediction?.fault_ratio ||
    "70:30";
  return { extraction, geometry, verdict, fault_ratio, prediction };
}
