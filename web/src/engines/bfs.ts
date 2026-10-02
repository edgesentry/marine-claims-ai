/**
 * Watertight compartment graph + BFS (port of ontology/compartments.py).
 */

export const COMPARTMENT_EDGES: [string, string][] = [
  ["hull_forward", "hull_mid"],
  ["hull_mid", "hull_aft"],
  ["hull_forward", "deck_forward"],
  ["hull_mid", "deck_mid"],
  ["hull_aft", "deck_aft"],
  ["hull_aft", "propulsion"],
  ["deck_forward", "deck_mid"],
  ["deck_mid", "deck_aft"],
  ["deck_mid", "superstructure"],
];

export const ISOLATED_NODES = ["machinery"] as const;

export const ZONE_ALIASES: Record<string, string> = {
  球状船首: "hull_forward",
  船首: "hull_forward",
  外板: "hull_mid",
  船体: "hull_mid",
  船尾: "hull_aft",
  機関室: "machinery",
  機関: "machinery",
  推進器: "propulsion",
  舵: "propulsion",
  甲板: "deck_mid",
  居住区: "superstructure",
  ブリッジ: "superstructure",
};

export type Graph = Map<string, Set<string>>;

export function buildCompartmentGraph(): Graph {
  const g: Graph = new Map();
  const nodes = new Set<string>([...ISOLATED_NODES]);
  for (const [a, b] of COMPARTMENT_EDGES) {
    nodes.add(a);
    nodes.add(b);
  }
  for (const n of nodes) g.set(n, new Set());
  for (const [a, b] of COMPARTMENT_EDGES) {
    g.get(a)!.add(b);
    g.get(b)!.add(a);
  }
  return g;
}

export function normalizeZone(label: string): string | null {
  const trimmed = (label || "").trim();
  const values = new Set(Object.values(ZONE_ALIASES));
  if (values.has(trimmed)) return trimmed;
  for (const [key, node] of Object.entries(ZONE_ALIASES)) {
    if (trimmed.includes(key)) return node;
  }
  return null;
}

/** BFS shortest path; returns null if unreachable. */
export function shortestPath(graph: Graph, src: string, dst: string): string[] | null {
  if (src === dst) return [src];
  if (!graph.has(src) || !graph.has(dst)) return null;
  const q: string[] = [src];
  const prev = new Map<string, string | null>([[src, null]]);
  while (q.length) {
    const cur = q.shift()!;
    for (const nxt of graph.get(cur) || []) {
      if (prev.has(nxt)) continue;
      prev.set(nxt, cur);
      if (nxt === dst) {
        const path: string[] = [dst];
        let p: string | null | undefined = cur;
        while (p != null) {
          path.push(p);
          p = prev.get(p);
        }
        path.reverse();
        return path;
      }
      q.push(nxt);
    }
  }
  return null;
}

export function hasPath(graph: Graph, src: string, dst: string): boolean {
  return shortestPath(graph, src, dst) != null;
}

export interface CausalityResult {
  valid: boolean;
  reason: string;
  damage_node: string | null;
  repair_node: string | null;
  path: string[] | null;
  hops?: number;
  max_hops?: number;
}

export function validateCausality(
  damageZone: string,
  repairZone: string,
  graph: Graph = buildCompartmentGraph(),
): CausalityResult {
  const src = normalizeZone(damageZone);
  const dst = normalizeZone(repairZone);
  if (src == null || dst == null) {
    return {
      valid: false,
      reason: "unknown_zone",
      damage_node: src,
      repair_node: dst,
      path: null,
    };
  }
  if (src === dst) {
    return {
      valid: true,
      reason: "same_compartment",
      damage_node: src,
      repair_node: dst,
      path: [src],
    };
  }
  const path = shortestPath(graph, src, dst);
  return {
    valid: path != null,
    reason: path ? "path_exists" : "watertight_barrier_violation",
    damage_node: src,
    repair_node: dst,
    path,
  };
}

export function validateClaimsCausality(
  damageZone: string,
  repairZone: string,
  maxHops = 1,
  graph: Graph = buildCompartmentGraph(),
): CausalityResult {
  const base = validateCausality(damageZone, repairZone, graph);
  if (!base.valid) return base;
  if (base.reason === "same_compartment") return { ...base, hops: 0 };
  const path = base.path || [];
  const hops = Math.max(0, path.length - 1);
  if (hops <= maxHops) return { ...base, reason: "adjacent_compartment", hops };
  return {
    valid: false,
    reason: "beyond_casualty_propagation_limit",
    damage_node: base.damage_node,
    repair_node: base.repair_node,
    path,
    hops,
    max_hops: maxHops,
  };
}

const REPAIR_ZONE_PATTERNS: Array<{ keys: string[]; zone: string }> = [
  {
    keys: [
      "主機関",
      "ピストン",
      "吸排気弁",
      "燃料噴射弁",
      "発電機関",
      "機関室",
      "カロリーファイヤー",
      "汚物処理",
      "減速機",
      "クラッチ",
      "ポンプ",
      "シリンダー",
      "波止弁",
      "亜鉛",
      "電磁弁",
    ],
    zone: "machinery",
  },
  {
    keys: ["プロペラ軸", "プロペラ", "推進器", "舵頭", "舵板", "ラダー"],
    zone: "propulsion",
  },
  { keys: ["バウスラスター", "球状船首", "錨鎖", "船首"], zone: "hull_forward" },
  { keys: ["船体外板", "船側外板", "船底外板"], zone: "hull_mid" },
  { keys: ["居住区", "船橋", "ブリッジ"], zone: "superstructure" },
  { keys: ["甲板"], zone: "deck_mid" },
];

export function inferRepairZone(description: string, category = ""): string | null {
  const blob = `${category} ${description}`;
  if (description.includes("バウスラスター") && !description.includes("機関室")) {
    if (
      description.trim().startsWith("バウスラスター") ||
      description.includes("プロペラ研磨")
    ) {
      return "hull_forward";
    }
  }
  if (category.includes("機関") && !description.includes("甲板")) {
    for (const { keys, zone } of REPAIR_ZONE_PATTERNS) {
      if (keys.some((k) => blob.includes(k))) return zone;
    }
    return "machinery";
  }
  for (const { keys, zone } of REPAIR_ZONE_PATTERNS) {
    if (keys.some((k) => blob.includes(k))) return zone;
  }
  return null;
}

export function anyDamageAllowsRepair(
  damagedComponents: string[],
  repairZone: string,
  maxHops = 1,
  graph: Graph = buildCompartmentGraph(),
): CausalityResult {
  let bestInvalid: CausalityResult | null = null;
  for (const label of damagedComponents) {
    const result = validateClaimsCausality(label, repairZone, maxHops, graph);
    if (result.valid) return result;
    bestInvalid = result;
  }
  if (bestInvalid) return bestInvalid;
  return {
    valid: false,
    reason: "no_damage_zones",
    damage_node: null,
    repair_node: normalizeZone(repairZone),
    path: null,
  };
}
