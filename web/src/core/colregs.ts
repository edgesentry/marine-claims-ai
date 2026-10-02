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
import { findGroundedQuote } from "../pipeline/spanValidate";
import type { GroundingMode } from "../pipeline/groundingGate";
import type { PdfContent } from "../pipeline/pdfLocate";
import { locateQuoteInPdfSafe } from "../pipeline/pdfLocate";
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
  groundingMode?: GroundingMode;
  /** Source document text for Exact Span verification. */
  sourceText?: string;
  pdfContent?: PdfContent;
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

function groundExcerpt(
  field: string,
  excerpt: string | undefined,
  sourceText: string | undefined,
  pdfContent: PdfContent | undefined,
): { excerpt?: string; grounding?: GroundingRef } {
  const raw = (excerpt || "").trim();
  if (!raw) return {};

  if (!sourceText) {
    return {
      excerpt: raw,
      grounding: { field, source_quote: raw.slice(0, 240) },
    };
  }

  const quote = findGroundedQuote(raw, sourceText);
  if (!quote) return {};

  let page_number: number | null = null;
  let pdf_coordinates = null as GroundingRef["pdf_coordinates"];
  if (pdfContent) {
    const loc = locateQuoteInPdfSafe(quote, pdfContent);
    page_number = loc.page_number;
    pdf_coordinates = loc.pdf_coordinates;
  }

  return {
    excerpt: quote,
    grounding: {
      field,
      source_quote: quote.slice(0, 240),
      page_number,
      pdf_coordinates,
    },
  };
}

export function runColregs(input: ColregsRunInput): ColregsRunResult {
  const mode: GroundingMode =
    input.groundingMode ??
    (input.sourceText ? "require_span" : "paste_bypass");

  let factsExcerpt = input.factsExcerpt;
  let rulingExcerpt = input.rulingExcerpt;
  let grounding = input.grounding;

  if (!grounding) {
    const facts = groundExcerpt(
      "facts_excerpt",
      input.factsExcerpt,
      input.sourceText,
      input.pdfContent,
    );
    const ruling = groundExcerpt(
      "ruling_excerpt",
      input.rulingExcerpt,
      input.sourceText,
      input.pdfContent,
    );
    factsExcerpt = facts.excerpt;
    rulingExcerpt = ruling.excerpt;
    grounding = [facts.grounding, ruling.grounding].filter(
      (g): g is GroundingRef => g != null,
    );

    if (mode === "require_span" && input.sourceText) {
      if (input.factsExcerpt?.trim() && !facts.excerpt) {
        throw new Error("facts_excerpt not grounded in source text");
      }
      if (input.rulingExcerpt?.trim() && !ruling.excerpt) {
        throw new Error("ruling_excerpt not grounded in source text");
      }
    }
  }

  const extraction = buildColregsExtraction({
    geometry: input.geometry,
    factsExcerpt,
    rulingExcerpt,
    faultRatioHint: input.faultRatioHint,
    documentKind: input.documentKind,
    situationCandidates: input.situationCandidates,
    confidence: input.confidence ?? 0.6,
    grounding,
    groundingMode: mode,
    sourceText: input.sourceText,
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
