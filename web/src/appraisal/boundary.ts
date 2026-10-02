/**
 * Physical-boundary API (port of marine_claims_ai.pipeline.boundary).
 */
import {
  anyDamageAllowsRepair,
  inferRepairZone,
  validateClaimsCausality,
} from "../engines/bfs";

export const DEFAULT_CRITICAL_SUBSTRINGS = [
  "カロリーファイヤー",
  "プロペラ軸",
  "減速機",
  "クラッチ",
  "汚物処理装置",
  "主機関",
  "ピストン",
] as const;

export function normalizeStatusBucket(status: string | null | undefined): string {
  const s = String(status || "");
  if (s.includes("APPORTIONED")) return "APPORTIONED";
  if (s.includes("COVERED")) return "COVERED";
  if (s.includes("REVIEW")) return "REVIEW";
  if (s.includes("EXCLUDED")) return "EXCLUDED";
  return "OTHER";
}

export function isCriticalFalseAccept(opts: {
  gold_bucket: string;
  pred_bucket: string;
  description: string;
  critical_substrings: readonly string[];
  damaged_zones: string[];
}): boolean {
  if (opts.gold_bucket !== "EXCLUDED") return false;
  if (opts.pred_bucket !== "COVERED" && opts.pred_bucket !== "REVIEW") return false;
  if (opts.damaged_zones.includes("機関室")) return false;
  return opts.critical_substrings.some((s) => opts.description.includes(s));
}

export function checkRepairBoundary(
  damagedComponents: string[],
  repairDescription: string,
  category = "",
  maxHops = 1,
): Record<string, unknown> {
  const zones = [...damagedComponents];
  const repairZone = inferRepairZone(repairDescription, category);
  if (!repairZone || !zones.length) {
    return {
      repair_zone: repairZone,
      valid: true,
      reason: "unmapped_or_no_damage",
      damage_node: null,
      repair_node: repairZone,
      path: null,
    };
  }
  const causality = anyDamageAllowsRepair(zones, repairZone, maxHops);
  return { repair_zone: repairZone, ...causality };
}

export function isBowMachineryFalseAccept(opts: {
  damaged_components: string[];
  description: string;
  predicted_status: string;
  gold_status?: string;
  critical_substrings?: readonly string[];
}): boolean {
  const crit = opts.critical_substrings ?? DEFAULT_CRITICAL_SUBSTRINGS;
  return isCriticalFalseAccept({
    gold_bucket: normalizeStatusBucket(opts.gold_status ?? "EXCLUDED"),
    pred_bucket: normalizeStatusBucket(opts.predicted_status),
    description: opts.description,
    critical_substrings: crit,
    damaged_zones: opts.damaged_components,
  });
}

export function countCriticalFalseAccepts(
  items: Array<Record<string, unknown>>,
  damagedComponents: string[],
  criticalSubstrings: readonly string[] = DEFAULT_CRITICAL_SUBSTRINGS,
): number {
  let total = 0;
  for (const row of items) {
    if (
      isCriticalFalseAccept({
        gold_bucket: normalizeStatusBucket(String(row.gold_status ?? "")),
        pred_bucket: normalizeStatusBucket(String(row.status ?? "")),
        description: String(row.description ?? ""),
        critical_substrings: criticalSubstrings,
        damaged_zones: damagedComponents,
      })
    ) {
      total += 1;
    }
  }
  return total;
}

export { inferRepairZone, validateClaimsCausality, anyDamageAllowsRepair };
