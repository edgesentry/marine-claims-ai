/**
 * Shared PSC Stage A → Stage B runner (PWA + CLI via web/src/core).
 */
import {
  DEFAULT_LOOKBACK_MONTHS,
  scoreFixtureCase,
  scoreSeaworthiness,
  tryParsePscPaste,
  type NormalizedDeficiency,
  type PscFixtureCase,
  type SeaworthinessRiskReport,
} from "../engines/psc";
import type { GroundingMode } from "../pipeline/groundingGate";
import {
  resolveConfidenceMode,
  type ConfidenceMode,
} from "../pipeline/confidenceGate";
import {
  buildPscExtraction,
  type GroundingRef,
  type PscExtraction,
} from "../schemas";

export interface PscRunInput {
  deficiencies: NormalizedDeficiency[];
  prior?: NormalizedDeficiency[] | null;
  mouId?: string | null;
  cicWeights?: Record<string, number> | null;
  lookbackMonths?: number;
  confidence?: number;
  field_confidence?: Record<string, number>;
  grounding?: GroundingRef[];
  groundingMode?: GroundingMode;
  confidenceMode?: ConfidenceMode;
  sourceText?: string;
}

export type PscRunResult =
  | {
      status: "scored";
      extraction: PscExtraction;
      report: SeaworthinessRiskReport;
    }
  | {
      status: "abstain";
      extraction: PscExtraction;
      reasons: string[];
    };

export function runPsc(input: PscRunInput): PscRunResult {
  if (!input.deficiencies.length) {
    throw new Error("PSC run requires at least one deficiency");
  }
  const groundingMode = input.groundingMode ?? "require_span";
  const confidenceMode = resolveConfidenceMode(
    groundingMode,
    input.confidenceMode,
  );
  const extraction = buildPscExtraction({
    deficiencies: input.deficiencies,
    prior: input.prior,
    mouId: input.mouId,
    cicWeights: input.cicWeights,
    lookbackMonths: input.lookbackMonths ?? DEFAULT_LOOKBACK_MONTHS,
    confidence: input.confidence ?? 0.75,
    field_confidence: input.field_confidence,
    grounding: input.grounding,
    groundingMode,
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

  const report = scoreSeaworthiness(input.deficiencies, {
    prior: input.prior,
    mouId: extraction.payload.mou_id ?? input.mouId,
    cicWeights: extraction.payload.cic_weights ?? input.cicWeights,
    lookbackMonths:
      extraction.payload.lookback_months ??
      input.lookbackMonths ??
      DEFAULT_LOOKBACK_MONTHS,
  });
  return { status: "scored", extraction, report };
}

export function runPscFromPaste(
  text: string,
  opts: {
    lookbackMonths?: number;
    confidence?: number;
    confidenceMode?: ConfidenceMode;
  } = {},
): PscRunResult & { label: string } {
  const parsed = tryParsePscPaste(text);
  if (!parsed.current.length) {
    throw new Error("No deficiencies found in pasted input");
  }
  const result = runPsc({
    deficiencies: parsed.current,
    prior: parsed.prior,
    mouId: parsed.mouId,
    cicWeights: parsed.cicWeights,
    lookbackMonths: opts.lookbackMonths,
    confidence: opts.confidence,
    groundingMode: "paste_bypass",
    confidenceMode: opts.confidenceMode,
  });
  return { ...result, label: parsed.label };
}

export function runPscFixture(
  fixture: PscFixtureCase | Record<string, unknown>,
  opts: {
    lookbackMonths?: number;
    confidence?: number;
    confidenceMode?: ConfidenceMode;
  } = {},
): PscRunResult {
  const c = fixture as PscFixtureCase;
  const report = scoreFixtureCase(fixture, {
    lookbackMonths: opts.lookbackMonths,
  });
  const groundingMode = "paste_bypass" as const;
  const confidenceMode = resolveConfidenceMode(
    groundingMode,
    opts.confidenceMode,
  );
  const extraction = buildPscExtraction({
    deficiencies: report.deficiencies,
    mouId: report.mou_id ?? (typeof c.mou_id === "string" ? c.mou_id : null),
    cicWeights:
      c.cic_weights && typeof c.cic_weights === "object"
        ? Object.fromEntries(
            Object.entries(c.cic_weights).map(([k, v]) => [String(k), Number(v)]),
          )
        : null,
    lookbackMonths: opts.lookbackMonths ?? DEFAULT_LOOKBACK_MONTHS,
    confidence: opts.confidence ?? 0.9,
    groundingMode,
    confidenceMode,
  });

  if (confidenceMode === "enforce" && extraction.abstain) {
    return {
      status: "abstain",
      extraction,
      reasons: extraction.abstain.reason.split("; ").slice(1),
    };
  }

  return { status: "scored", extraction, report };
}
