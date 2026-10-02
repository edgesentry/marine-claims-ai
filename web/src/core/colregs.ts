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
import {
  resolveConfidenceMode,
  type ConfidenceMode,
} from "../pipeline/confidenceGate";
import type { PdfContent } from "../pipeline/pdfLocate";
import { locateQuoteInPdfSafe } from "../pipeline/pdfLocate";
import {
  extractColregsTelemetry,
  telemetryFieldConfidence,
  telemetryGrounding as groundingFromTelemetry,
  telemetryToGeometry,
} from "../ingest/colregsTelemetryExtractor";
import {
  buildColregsExtraction,
  geometryFromExtraction,
  type ColregsExtraction,
  type GroundingRef,
} from "../schemas";

export interface ColregsRunInput {
  geometry?: EncounterGeometry;
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
  field_confidence?: Record<string, number>;
  grounding?: GroundingRef[];
  groundingMode?: GroundingMode;
  confidenceMode?: ConfidenceMode;
  /** Source document text for Exact Span verification. */
  sourceText?: string;
  /**
   * When set, extract headings/bearings from this narrative (#91).
   * Falls back to `geometry` when extraction is incomplete (catalog / UI).
   * On document paths (`require_span`), incomplete triad stamps geometry_missing abstain.
   */
  narrativeText?: string;
  /** Prefer narrative telemetry over explicit geometry when both are present. */
  preferNarrativeGeometry?: boolean;
  pdfContent?: PdfContent;
  rules?: FaultRules | null;
  seeds?: CatalogSeed[];
}

export type ColregsRunResult =
  | {
      status: "scored";
      extraction: ColregsExtraction;
      geometry: EncounterGeometry;
      verdict: EncounterVerdict;
      fault_ratio: string;
      prediction: FaultPrediction | null;
    }
  | {
      status: "abstain";
      extraction: ColregsExtraction;
      reasons: string[];
    };

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

function resolveGeometry(input: ColregsRunInput): {
  geometry: EncounterGeometry;
  telemetryGrounding: GroundingRef[];
  field_confidence: Record<string, number>;
  fromNarrative: boolean;
} {
  const narrative =
    input.narrativeText?.trim() ||
    (input.preferNarrativeGeometry
      ? [input.factsExcerpt, input.rulingExcerpt, input.sourceText]
          .filter(Boolean)
          .join("\n")
      : "");
  const tryNarrative =
    Boolean(narrative) &&
    (input.preferNarrativeGeometry === true || input.geometry == null);

  if (tryNarrative) {
    const telemetry = extractColregsTelemetry(narrative);
    const extracted = telemetryToGeometry(telemetry);
    if (extracted) {
      return {
        geometry: extracted,
        telemetryGrounding: groundingFromTelemetry(telemetry).map((g) => {
          if (!input.sourceText) return g;
          const quote = findGroundedQuote(g.source_quote, input.sourceText);
          if (!quote) return g;
          let page_number: number | null = null;
          let pdf_coordinates = null as GroundingRef["pdf_coordinates"];
          if (input.pdfContent) {
            const loc = locateQuoteInPdfSafe(quote, input.pdfContent);
            page_number = loc.page_number;
            pdf_coordinates = loc.pdf_coordinates;
          }
          return {
            ...g,
            source_quote: quote.slice(0, 240),
            page_number,
            pdf_coordinates,
          };
        }),
        field_confidence: telemetryFieldConfidence(telemetry),
        fromNarrative: true,
      };
    }

    // Incomplete triad: abstain on document path; else fall through to UI geometry.
    if (input.geometry == null || input.groundingMode === "require_span") {
      const placeholder: EncounterGeometry = input.geometry ?? {
        heading_a_deg: 0,
        heading_b_deg: 0,
        true_bearing_a_to_b_deg: 0,
      };
      return {
        geometry: placeholder,
        telemetryGrounding: [],
        field_confidence: {
          ...telemetryFieldConfidence(telemetry),
          geometry_missing: 0,
        },
        fromNarrative: false,
      };
    }
  }

  if (!input.geometry) {
    throw new Error(
      "colregs requires geometry or narrative text with extractable headings/bearings",
    );
  }
  return {
    geometry: input.geometry,
    telemetryGrounding: [],
    field_confidence: {},
    fromNarrative: false,
  };
}

export function runColregs(input: ColregsRunInput): ColregsRunResult {
  const mode: GroundingMode =
    input.groundingMode ??
    (input.sourceText ? "require_span" : "paste_bypass");
  const confidenceMode = resolveConfidenceMode(mode, input.confidenceMode);

  const resolved = resolveGeometry({
    ...input,
    groundingMode: mode,
    preferNarrativeGeometry:
      input.preferNarrativeGeometry ??
      (input.geometry == null && Boolean(input.narrativeText || input.sourceText)),
  });

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
    grounding = [
      facts.grounding,
      ruling.grounding,
      ...resolved.telemetryGrounding,
    ].filter((g): g is GroundingRef => g != null);

    if (mode === "require_span" && input.sourceText) {
      if (input.factsExcerpt?.trim() && !facts.excerpt) {
        throw new Error("facts_excerpt not grounded in source text");
      }
      if (input.rulingExcerpt?.trim() && !ruling.excerpt) {
        throw new Error("ruling_excerpt not grounded in source text");
      }
      for (const g of resolved.telemetryGrounding) {
        const quote = findGroundedQuote(g.source_quote, input.sourceText);
        if (!quote) {
          throw new Error(`${g.field} not grounded in source text`);
        }
      }
    }
  } else if (resolved.telemetryGrounding.length) {
    grounding = [...grounding, ...resolved.telemetryGrounding];
  }

  const extraction = buildColregsExtraction({
    geometry: resolved.geometry,
    factsExcerpt,
    rulingExcerpt,
    faultRatioHint: input.faultRatioHint,
    documentKind: input.documentKind,
    situationCandidates: input.situationCandidates,
    confidence: input.confidence ?? 0.6,
    field_confidence: {
      ...resolved.field_confidence,
      ...input.field_confidence,
    },
    grounding,
    groundingMode: mode,
    confidenceMode,
    sourceText: input.sourceText,
  });

  if (confidenceMode === "enforce" && extraction.abstain) {
    return {
      status: "abstain",
      extraction,
      reasons: extraction.abstain.reason.split("; ").slice(1),
    };
  }

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
  return {
    status: "scored",
    extraction,
    geometry,
    verdict,
    fault_ratio,
    prediction,
  };
}
