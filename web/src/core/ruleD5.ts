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
  grounding?: GroundingRef[];
  hireRate?: number;
  legacyLeadDays?: number;
  aiLeadMinutes?: number;
}

export interface RuleD5RunResult {
  extraction: RuleD5Extraction;
  apportionment: RuleDResult;
  days_saved: number;
  offhire_jpy: number;
}

function syncDockCosts(lines: RepairLineItem[], dockTotal: number): RepairLineItem[] {
  return lines.map((ln) =>
    (ln.trade_code || "").startsWith("DOCK") ? { ...ln, cost: dockTotal } : ln,
  );
}

export function runRuleD5(input: RuleD5RunInput): RuleD5RunResult {
  const extraction = buildRuleD5Extraction({
    dockingContext: input.dockingContext,
    lines: input.lines,
    assumeStatutoryOwnerWork: input.assumeStatutoryOwnerWork,
    confidence: input.confidence,
    grounding: input.grounding,
  });
  const gated = ruleD5LinesFromExtraction(extraction);
  const apportionment = apportionRuleD(
    gated,
    extraction.payload.docking_context,
  );
  const hireRate = input.hireRate ?? 0;
  const legacyLeadDays = input.legacyLeadDays ?? 0;
  const aiLeadMinutes = input.aiLeadMinutes ?? 0;
  const aiDays = aiLeadMinutes / (60 * 24);
  const daysSaved = Math.max(0, legacyLeadDays - aiDays);
  return {
    extraction,
    apportionment,
    days_saved: Math.round(daysSaved * 100) / 100,
    offhire_jpy: Math.round(daysSaved * hireRate),
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
  },
): RuleD5RunResult {
  const items = extractRepairItemsFromText(text);
  if (!items.length) {
    throw new Error("No repair line items found in text");
  }
  const rawLines = repairItemsToRuleDLines(items, {
    dailyDockRate: opts.dailyDockRate,
    dockDays: opts.dockDays,
    includeStatutory: opts.includeStatutory,
    lang: opts.lang ?? "en",
  });
  const dockTotal = opts.dailyDockRate * opts.dockDays;
  const lines = syncDockCosts(rawLines, dockTotal);
  return runRuleD5({
    dockingContext: opts.dockingContext,
    lines,
    assumeStatutoryOwnerWork: opts.includeStatutory,
    confidence: opts.confidence ?? 0.65,
    grounding: items.slice(0, 12).map((it, i) => ({
      field: `lines.pdf-${i + 1}`,
      source_quote: it.description.slice(0, 200),
    })),
    hireRate: opts.hireRate,
    legacyLeadDays: opts.legacyLeadDays,
    aiLeadMinutes: opts.aiLeadMinutes,
  });
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
    hireRate: opts.hireRate,
    legacyLeadDays: opts.legacyLeadDays,
    aiLeadMinutes: opts.aiLeadMinutes,
  });
}
