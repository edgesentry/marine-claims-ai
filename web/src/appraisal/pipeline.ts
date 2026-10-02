/**
 * Appraisal pipeline (port of marine_claims_ai.appraisal.pipeline).
 * Source of truth for browser / Vitest — Python demo path is deprecated.
 */
import {
  apportionRuleD,
  type ApportionmentRule,
  type DockingContext,
  type RepairLineItem,
} from "../engines/ruleD5";
import {
  anyDamageAllowsRepair,
  inferRepairZone,
  type CausalityResult,
} from "../engines/bfs";

export const ACTION_DISALLOWED = "Disallowed";
export const ACTION_APPORTIONED = "Apportioned 50%";
export const ACTION_APPROVED = "Approved";

export interface NplScore {
  red_flag_similarity: number;
  matched_pattern_id: string | null;
  matched_trade_code: string | null;
  matched_pattern_text?: string | null;
  citation: string | null;
  recommended_action: string;
}

export interface NplScorer {
  score_description(description: string, category?: string | null): NplScore;
}

export const noOpNplScorer: NplScorer = {
  score_description() {
    return {
      red_flag_similarity: 0,
      matched_pattern_id: null,
      matched_trade_code: null,
      citation: null,
      recommended_action: ACTION_APPROVED,
    };
  },
};

export interface SpecLineItem {
  id?: number | string;
  num?: string;
  category?: string;
  description: string;
  estimated_cost: number;
}

export interface CasualtyProfile {
  vessel_name?: string;
  incident_type?: string;
  incident_date?: string;
  incident_location?: string;
  damaged_components: string[];
  damage_evidence?: string[];
  source_pdf?: string;
}

export type AnalyzedItem = SpecLineItem & {
  status: string;
  approved_amount: number;
  excluded_amount: number;
  reason: string;
  clause_ref: string;
  red_flag_similarity: number;
  matched_pattern_id: string | null;
  matched_trade_code: string | null;
  recommended_action: string | null;
  citation: string | null;
  apportionment_rule?: ApportionmentRule;
  insurer_share?: number;
  owner_share?: number;
  repair_zone?: string;
  ontology?: Record<string, unknown>;
};

export interface AppraisalSummary {
  casualty_profile: CasualtyProfile;
  total_items: number;
  total_claimed_jpy: number;
  total_approved_jpy: number;
  total_excluded_jpy: number;
  leakage_prevention_rate_pct: number;
  items_covered_count: number;
  items_excluded_count: number;
  items_review_count: number;
  docking_context: DockingContext;
  rule_d5_apportionment_rule: ApportionmentRule;
  rule_d5_reconciliation_error_jpy: number;
  pricing_note: string;
}

const OUTER_HULL_SURFACE_KEYS = ["船体外板", "船側外板", "船底外板"] as const;
const PROPULSION_KEYS = ["プロペラ", "推進器", "プロペラ軸", "舵"] as const;
const MACHINERY_KEYS = [
  "主機関",
  "ピストン",
  "吸排気弁",
  "燃料噴射弁",
  "発電機関",
  "波止弁",
  "ポンプ",
  "シリンダー",
  "亜鉛",
  "カロリーファイヤー",
  "汚物処理",
  "減速機",
  "クラッチ",
] as const;
const STATUTORY_OWNER_KEYS = [
  "法定",
  "検査証書",
  "SOLAS",
  "船級",
  "年次検査",
  "中間検査",
  "定期検査",
  "JG",
] as const;

export function descriptionIsBowThrusterWork(desc: string): boolean {
  if (!desc.includes("バウスラスター")) return false;
  if (
    desc.includes("機関室") ||
    desc.includes("汚物処理") ||
    desc.includes("始動機盤") ||
    desc.includes("主配電盤")
  ) {
    return false;
  }
  return desc.trim().startsWith("バウスラスター") || desc.includes("バウスラスター プロペラ");
}

export function isCommonDockDescription(desc: string): boolean {
  return desc.includes("入出渠") || desc.includes("滞渠") || desc.includes("入渠");
}

function lineId(item: SpecLineItem): string {
  return `line-${item.id ?? item.num ?? "x"}`;
}

export function buildRuleDLineItems(
  items: SpecLineItem[],
  assumeStatutoryOwnerWork = true,
): RepairLineItem[] {
  const lines: RepairLineItem[] = [];
  let sawStatutory = false;
  let sawDock = false;

  for (const item of items) {
    const desc = item.description || "";
    const cost = Math.trunc(item.estimated_cost || 0);
    const lid = lineId(item);

    if (isCommonDockDescription(desc)) {
      sawDock = true;
      lines.push({ id: lid, trade_code: "DOCK-01", cost, title: desc.slice(0, 80) });
      continue;
    }
    if (STATUTORY_OWNER_KEYS.some((k) => desc.includes(k))) {
      sawStatutory = true;
      lines.push({
        id: lid,
        trade_code: "SAFE-01",
        cost,
        necessity: "statutory_seaworthiness",
        title: desc.slice(0, 80),
      });
      continue;
    }
    if (
      ["主機関", "ピストン", "プロペラ軸", "減速機", "発電機関", "カロリー"].some((k) =>
        desc.includes(k),
      )
    ) {
      lines.push({
        id: lid,
        trade_code: "ENG-02",
        cost,
        necessity: "deferred",
        title: desc.slice(0, 80),
      });
      continue;
    }
    if (["外板", "球状船首", "船首", "バウスラスター"].some((k) => desc.includes(k))) {
      lines.push({
        id: lid,
        trade_code: "HULL-01",
        cost,
        work_party: "casualty",
        title: desc.slice(0, 80),
      });
      continue;
    }
    lines.push({
      id: lid,
      trade_code: "OWN-01",
      cost,
      necessity: "deferred",
      title: desc.slice(0, 80),
    });
  }

  if (assumeStatutoryOwnerWork && sawDock && !sawStatutory) {
    lines.push({
      id: "safe-synthetic",
      trade_code: "SAFE-01",
      cost: 550_000,
      necessity: "statutory_seaworthiness",
      title: "Statutory survey (assumed concurrent)",
    });
  }
  return lines;
}

function ontologyExcludeReason(
  causality: CausalityResult,
  damagedZones: string[],
): string {
  const reasonCode = causality.reason || "unknown";
  const repair = causality.repair_node;
  if (reasonCode === "watertight_barrier_violation") {
    return (
      `事故損傷部位（${damagedZones.join(", ")}）から修理区画（${repair}）へは` +
      "水密隔壁を越える因果が成立せず、便乗修理として除外。"
    );
  }
  if (reasonCode === "beyond_casualty_propagation_limit") {
    return (
      `事故損傷部位（${damagedZones.join(", ")}）から修理区画（${repair}）までは` +
      `伝播ホップ数 ${causality.hops} が上限 ${causality.max_hops} を超え、` +
      "直接因果が認められないため除外。"
    );
  }
  return (
    `事故損傷部位（${damagedZones.join(", ")}）と修理区画の空間因果が検証できないため除外` +
    `（ontology_reason=${reasonCode}）。`
  );
}

export function evaluateClaimsDynamically(
  items: SpecLineItem[],
  casualtyProfile: CasualtyProfile,
  scorer: NplScorer = noOpNplScorer,
  opts: {
    dockingContext?: DockingContext;
    assumeStatutoryOwnerWork?: boolean;
  } = {},
): { analyzed: AnalyzedItem[]; summary: AppraisalSummary } {
  const damagedZones = [...casualtyProfile.damaged_components];
  const analyzed: AnalyzedItem[] = [];
  let totalClaimed = 0;
  let totalCovered = 0;
  let totalExcluded = 0;
  const ctx: DockingContext = opts.dockingContext ?? "casualty_immediate";
  const assumeStatutory = opts.assumeStatutoryOwnerWork ?? true;

  const ruleDItems = buildRuleDLineItems(items, assumeStatutory);
  const ruleDResult = apportionRuleD(ruleDItems, ctx);
  const ruleDById = new Map(ruleDResult.lines.map((ln) => [ln.id, ln]));

  const hasHullDamage = damagedZones.some((z) =>
    ["外板", "球状船首", "貨物タンク", "タンク"].includes(z),
  );
  const hasPropulsionDamage = damagedZones.some((z) => ["推進器", "舵"].includes(z));
  const hasMachineryDamage = damagedZones.some((z) => z === "機関室");

  for (const item of items) {
    const desc = item.description;
    const cat = item.category || "";
    const cost = item.estimated_cost;
    totalClaimed += cost;

    let status = "";
    let reason = "";
    let clauseRef = "";
    let approvedAmount = 0;
    let repairZone: string | null = null;
    let causality: CausalityResult | null = null;
    let apportionmentRule: ApportionmentRule | undefined;
    let insurerShare: number | undefined;
    let ownerShare: number | undefined;
    const redFlag = scorer.score_description(desc, cat);

    if (isCommonDockDescription(desc)) {
      const ln = ruleDById.get(lineId(item));
      if (!ln) {
        approvedAmount = Math.floor(cost / 2);
        status = "APPORTIONED (50%)";
        apportionmentRule = "RULE_D5_50_50";
        insurerShare = approvedAmount;
        ownerShare = cost - approvedAmount;
      } else {
        insurerShare = ln.insurer_share;
        ownerShare = ln.owner_share;
        approvedAmount = insurerShare;
        apportionmentRule = ln.apportionment_rule;
        if (ln.apportionment_rule === "RULE_D5_50_50") {
          status = "APPORTIONED (50%)";
          reason =
            "入出渠・滞渠共通費は AAA Rule D5 に基づき、事故復旧と船主法定工事の" +
            "双方がドックを要するため折半認定（WASM 確定計算）。";
        } else {
          status = "COVERED";
          reason =
            "入出渠・滞渠共通費は AAA Rule D5 ¶1 に基づき、船主の法定・堪航性工事が" +
            "併存しないため保険者 100% 負担（WASM 確定計算）。";
        }
        clauseRef = `AAA Rules of Practice Rule D5 / ${apportionmentRule}`;
        if (insurerShare + ownerShare !== cost) {
          throw new Error(
            `Rule D5 reconciliation error: ${insurerShare}+${ownerShare}!=${cost}`,
          );
        }
      }
    } else {
      repairZone = inferRepairZone(desc, cat);
      if (repairZone && damagedZones.length) {
        causality = anyDamageAllowsRepair(damagedZones, repairZone);
        if (!causality.valid) {
          status = "EXCLUDED (便乗修理)";
          approvedAmount = 0;
          reason = ontologyExcludeReason(causality, damagedZones);
          clauseRef = "普通保険条項 第3条 / 水密隔壁・区画因果制約";
        }
      }

      if (!status) {
        const action = redFlag.recommended_action;
        const citation = redFlag.citation || "";
        const ontologyOk = causality != null && causality.valid;
        if (action === ACTION_DISALLOWED && !ontologyOk) {
          status = "EXCLUDED (便乗修理)";
          approvedAmount = 0;
          reason = `${citation}。公開定期検査仕様との意味的一致により便乗修理として全額排斥。`;
          clauseRef = "普通保険条項 第3条 / Negative Pattern Library";
        } else if (action === ACTION_APPORTIONED && !ontologyOk) {
          status = "APPORTIONED (50%)";
          approvedAmount = cost * 0.5;
          reason = `${citation}。定期整備との境界領域のため50%按分。`;
          clauseRef = "ITC-Hulls Apportionment / Negative Pattern Library";
        }
      }

      if (!status) {
        if (OUTER_HULL_SURFACE_KEYS.some((k) => desc.includes(k))) {
          if (hasHullDamage && (causality == null || causality.valid)) {
            status = "COVERED";
            approvedAmount = cost;
            const hullBits = damagedZones.filter((z) =>
              ["外板", "球状船首", "貨物タンク", "タンク"].includes(z),
            );
            reason = `事故による船体受傷部位（${hullBits.join(", ")}）の外板表面処理・塗装復旧工事として直接因果関係を認定。`;
            clauseRef = "船舶保険普通保険条項 第1条";
          } else {
            status = "EXCLUDED (便乗修理)";
            approvedAmount = 0;
            reason = "事故報告書に船体外板の損傷記録がなく、通常の経年防汚塗装と判定。";
            clauseRef = "普通保険条項 第3条";
          }
        } else if (descriptionIsBowThrusterWork(desc)) {
          if (damagedZones.includes("球状船首")) {
            status = "REVIEW / PARTIAL";
            approvedAmount = cost * 0.5;
            reason = "船首部への衝撃による外傷点検は一部認定するが、定期検査分は按分。";
            clauseRef = "船舶保険普通保険条項 第3条";
          } else {
            status = "EXCLUDED (便乗修理)";
            approvedAmount = 0;
            reason = "船首部損傷がなく、定期検査に伴うルーチン開放点検と判定。";
            clauseRef = "普通保険条項 第3条";
          }
        } else if (PROPULSION_KEYS.some((k) => desc.includes(k))) {
          if (hasPropulsionDamage && (causality == null || causality.valid)) {
            status = "COVERED";
            approvedAmount = cost;
            reason = "推進器・軸系の損傷記録があるため復旧工事として認容。";
            clauseRef = "船舶保険普通保険条項 第1条";
          } else {
            status = "EXCLUDED (便乗修理)";
            approvedAmount = 0;
            reason = `事故損傷部位（${damagedZones.join(", ")}）と無関係な推進器定期検査工事として除外。`;
            clauseRef = "普通保険条項 第3条";
          }
        } else if (cat.includes("機関") || MACHINERY_KEYS.some((k) => desc.includes(k))) {
          if (hasMachineryDamage && (causality == null || causality.valid)) {
            status = "COVERED";
            approvedAmount = cost;
            reason = "機関室直接損傷の復旧工事として認定。";
            clauseRef = "普通保険条項 第1条";
          } else {
            status = "EXCLUDED (便乗修理)";
            approvedAmount = 0;
            reason = `事故損傷部位（${damagedZones.join(", ")}）と無関係な機関定期検査工事。便乗修理として全額排斥。`;
            clauseRef = "普通保険条項 第3条";
          }
        } else {
          status = "EXCLUDED (定期点検)";
          approvedAmount = 0;
          reason = "法定属具・定期検査準備作業であり、海難事故による直接損傷の復旧とは因果関係が認められないため除外。";
          clauseRef = "普通保険条項 第1条・第3条";
        }
      }
    }

    const itemResult: AnalyzedItem = {
      ...item,
      status,
      approved_amount: Math.trunc(approvedAmount),
      excluded_amount: Math.trunc(cost - approvedAmount),
      reason,
      clause_ref: clauseRef,
      red_flag_similarity: redFlag.red_flag_similarity ?? 0,
      matched_pattern_id: redFlag.matched_pattern_id,
      matched_trade_code: redFlag.matched_trade_code,
      recommended_action: redFlag.recommended_action,
      citation: redFlag.citation,
    };
    if (apportionmentRule != null) {
      itemResult.apportionment_rule = apportionmentRule;
      itemResult.insurer_share = insurerShare;
      itemResult.owner_share = ownerShare;
    }
    if (repairZone) itemResult.repair_zone = repairZone;
    if (causality) {
      itemResult.ontology = {
        valid: causality.valid,
        reason: causality.reason,
        damage_node: causality.damage_node,
        repair_node: causality.repair_node,
        hops: causality.hops,
      };
    }

    totalCovered += itemResult.approved_amount;
    totalExcluded += itemResult.excluded_amount;
    analyzed.push(itemResult);
  }

  let d5ReconError = 0;
  for (const ln of ruleDResult.lines) {
    if (ln.is_common_dock_charge) {
      d5ReconError += Math.abs(ln.insurer_share + ln.owner_share - ln.cost);
    }
  }

  const summary: AppraisalSummary = {
    casualty_profile: casualtyProfile,
    total_items: analyzed.length,
    total_claimed_jpy: totalClaimed,
    total_approved_jpy: Math.trunc(totalCovered),
    total_excluded_jpy: Math.trunc(totalExcluded),
    leakage_prevention_rate_pct: totalClaimed
      ? Math.round((totalExcluded / totalClaimed) * 1000) / 10
      : 0,
    items_covered_count: analyzed.filter(
      (x) => x.status.includes("COVERED") || x.status.includes("50%"),
    ).length,
    items_excluded_count: analyzed.filter((x) => x.status.includes("EXCLUDED")).length,
    items_review_count: analyzed.filter((x) => x.status.includes("REVIEW")).length,
    docking_context: ctx,
    rule_d5_apportionment_rule: ruleDResult.apportionment_rule,
    rule_d5_reconciliation_error_jpy: d5ReconError,
    pricing_note:
      "Line-item JPY amounts are model estimates. Common drydock dues use AAA Rule D5 WASM apportionment.",
  };

  return { analyzed, summary };
}
