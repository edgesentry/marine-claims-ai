/**
 * Shared Rule D5 Stage A → Stage B runner (PWA + CLI via web/src/core).
 */
import {
  apportionRuleD,
  type DockingContext,
  type RepairLineItem,
  type RuleDResult,
} from "../engines/ruleD5";
import {
  extractRepairItemsFromText,
  repairItemsToRuleDLines,
  syntheticUc2Lines,
} from "../pdf/repairLines";
import type { Lang } from "../i18n";
import type { PdfContent } from "../pipeline/pdfLocate";
import { extractSpecWithSpansFromText } from "../pipeline/extractSpec";
import { findGroundedQuote } from "../pipeline/spanValidate";
import type { GroundingMode } from "../pipeline/groundingGate";
import {
  resolveConfidenceMode,
  type ConfidenceMode,
} from "../pipeline/confidenceGate";
import {
  buildRuleD5Extraction,
  ruleD5LinesFromExtraction,
  type GroundingRef,
  type RuleD5Extraction,
} from "../schemas";

export interface RuleD5RunInput {
  dockingContext: DockingContext;
  lines: RepairLineItem[];
  assumeStatutoryOwnerWork?: boolean;
  confidence?: number;
  field_confidence?: Record<string, number>;
  grounding?: GroundingRef[];
  groundingMode?: GroundingMode;
  confidenceMode?: ConfidenceMode;
  sourceText?: string;
  hireRate?: number;
  legacyLeadDays?: number;
  aiLeadMinutes?: number;
}

export type RuleD5RunResult =
  | {
      status: "scored";
      extraction: RuleD5Extraction;
      apportionment: RuleDResult;
      days_saved: number;
      offhire_jpy: number;
      discarded_ungrounded?: number;
    }
  | {
      status: "abstain";
      extraction: RuleD5Extraction;
      reasons: string[];
      discarded_ungrounded?: number;
    };

function syncDockCosts(lines: RepairLineItem[], dockTotal: number): RepairLineItem[] {
  return lines.map((ln) =>
    (ln.trade_code || "").startsWith("DOCK") ? { ...ln, cost: dockTotal } : ln,
  );
}

function leadTimeMetrics(input: RuleD5RunInput): {
  days_saved: number;
  offhire_jpy: number;
} {
  const hireRate = input.hireRate ?? 0;
  const legacyLeadDays = input.legacyLeadDays ?? 0;
  const aiLeadMinutes = input.aiLeadMinutes ?? 0;
  const aiDays = aiLeadMinutes / (60 * 24);
  const daysSaved = Math.max(0, legacyLeadDays - aiDays);
  return {
    days_saved: Math.round(daysSaved * 100) / 100,
    offhire_jpy: Math.round(daysSaved * hireRate),
  };
}

export function runRuleD5(input: RuleD5RunInput): RuleD5RunResult {
  const groundingMode = input.groundingMode ?? "require_span";
  const confidenceMode = resolveConfidenceMode(
    groundingMode,
    input.confidenceMode,
  );
  const extraction = buildRuleD5Extraction({
    dockingContext: input.dockingContext,
    lines: input.lines,
    assumeStatutoryOwnerWork: input.assumeStatutoryOwnerWork,
    confidence: input.confidence,
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

  const gated = ruleD5LinesFromExtraction(extraction);
  const apportionment = apportionRuleD(
    gated,
    extraction.payload.docking_context,
  );
  const metrics = leadTimeMetrics(input);
  return {
    status: "scored",
    extraction,
    apportionment,
    ...metrics,
  };
}

export function runRuleD5FromRepairText(
  text: string,
  opts: {
    dockingContext: DockingContext;
    dailyDockRate: number;
    dockDays: number;
    includeStatutory: boolean;
    lang?: Lang;
    hireRate?: number;
    legacyLeadDays?: number;
    aiLeadMinutes?: number;
    confidence?: number;
    confidenceMode?: ConfidenceMode;
    pdfContent?: PdfContent;
    /**
     * Optional Tier-2/3 or eval candidates. When set, Exact Span filters these
     * against `text` instead of heuristic extractRepairItemsFromText output.
     */
    candidateItems?: Array<{
      description: string;
      estimated_cost?: number;
      id?: number | string;
      category?: string;
      num?: string;
    }>;
  },
): RuleD5RunResult {
  const items =
    opts.candidateItems?.map((it) => ({
      description: it.description,
      estimated_cost: Number(it.estimated_cost || 0),
    })) ?? extractRepairItemsFromText(text);
  if (!items.length) {
    throw new Error("No repair line items found in text");
  }

  const span = extractSpecWithSpansFromText(text, opts.candidateItems ?? items, {
    pdfPath: "repair-text",
    pdfContent: opts.pdfContent,
  });
  const acceptedDescriptions = new Set(span.items.map((g) => g.description));
  const groundedItems = items.filter((it) => acceptedDescriptions.has(it.description));
  if (!groundedItems.length) {
    throw new Error(
      `All repair line items ungrounded (rejected ${span.fabricated_line_items})`,
    );
  }

  const rawLines = repairItemsToRuleDLines(groundedItems, {
    dailyDockRate: opts.dailyDockRate,
    dockDays: opts.dockDays,
    includeStatutory: opts.includeStatutory,
    lang: opts.lang ?? "en",
  });
  const dockTotal = opts.dailyDockRate * opts.dockDays;
  const lines = syncDockCosts(rawLines, dockTotal);

  const spanByDescription = new Map(
    span.items.map((g) => [g.description, g] as const),
  );
  const grounding: GroundingRef[] = [];
  for (const ln of lines) {
    const fromTitle = ln.title ? spanByDescription.get(ln.title) : undefined;
    if (fromTitle) {
      grounding.push({
        field: `lines.${ln.id}`,
        source_quote: fromTitle.source_quote,
        page_number: fromTitle.page_number,
        pdf_coordinates: fromTitle.pdf_coordinates,
      });
      continue;
    }
    if (String(ln.id).startsWith("pdf-") && ln.title) {
      const quote = findGroundedQuote(ln.title, text);
      if (quote) {
        grounding.push({
          field: `lines.${ln.id}`,
          source_quote: quote,
          page_number: null,
          pdf_coordinates: null,
        });
      }
    }
  }

  const result = runRuleD5({
    dockingContext: opts.dockingContext,
    lines,
    assumeStatutoryOwnerWork: opts.includeStatutory,
    confidence: opts.confidence ?? 0.65,
    grounding,
    groundingMode: "require_span",
    confidenceMode: opts.confidenceMode,
    sourceText: text,
    hireRate: opts.hireRate,
    legacyLeadDays: opts.legacyLeadDays,
    aiLeadMinutes: opts.aiLeadMinutes,
  });
  return {
    ...result,
    discarded_ungrounded: span.fabricated_line_items,
  };
}

export function runRuleD5Synthetic(opts: {
  dockingContext: DockingContext;
  dailyDockRate: number;
  dockDays: number;
  includeStatutory: boolean;
  lang?: Lang;
  hireRate?: number;
  legacyLeadDays?: number;
  aiLeadMinutes?: number;
}): RuleD5RunResult {
  const dockTotal = opts.dailyDockRate * opts.dockDays;
  const lines = syncDockCosts(
    syntheticUc2Lines(
      opts.dailyDockRate,
      opts.dockDays,
      opts.includeStatutory,
      opts.lang ?? "en",
    ),
    dockTotal,
  );
  return runRuleD5({
    dockingContext: opts.dockingContext,
    lines,
    assumeStatutoryOwnerWork: opts.includeStatutory,
    confidence: 0.85,
    grounding: lines
      .filter((ln) => ln.title)
      .slice(0, 8)
      .map((ln) => ({
        field: `lines.${ln.id}`,
        source_quote: String(ln.title),
      })),
    groundingMode: "paste_bypass",
    hireRate: opts.hireRate,
    legacyLeadDays: opts.legacyLeadDays,
    aiLeadMinutes: opts.aiLeadMinutes,
  });
}
