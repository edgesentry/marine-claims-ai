/**
 * AAA Rule D5 drydock common-dues apportionment.
 * Mirrors marine_claims_ai.analytics.rule_d_solver (DuckDB SQL CASE logic).
 */

export type DockingContext = "casualty_immediate" | "deferred_to_routine";
export type WorkParty = "casualty" | "owner" | "common";
export type OwnerNecessity = "statutory_seaworthiness" | "deferred" | "unspecified";
export type ApportionmentRule =
  | "RULE_D5_100_UNDERWRITER"
  | "RULE_D5_50_50"
  | "DISCRETE";

export interface RepairLineItem {
  id: string;
  trade_code?: string;
  cost: number;
  work_party?: WorkParty | null;
  necessity?: OwnerNecessity;
  title?: string;
}

export interface ApportionedLine {
  id: string;
  trade_code: string;
  cost: number;
  is_common_dock_charge: boolean;
  insurer_share: number;
  owner_share: number;
  apportionment_rule: ApportionmentRule;
  title: string;
}

export interface RuleDResult {
  docking_context: DockingContext;
  has_statutory_owner_repair: boolean;
  common_dues_total: number;
  insurer_common_share: number;
  owner_common_share: number;
  apportionment_rule: ApportionmentRule;
  lines: ApportionedLine[];
  claimed_total: number;
  insurer_total: number;
  owner_total: number;
}

const STATUTORY_OWNER_PREFIXES = new Set(["SAFE", "PROP"]);
const COMMON_DOCK_PREFIX = "DOCK";

function tradePrefix(tradeCode: string): string {
  const code = (tradeCode || "").trim().toUpperCase();
  if (code.includes("-")) return code.split("-", 1)[0]!;
  return code;
}

export function isCommonDockCharge(tradeCode: string): boolean {
  return tradePrefix(tradeCode) === COMMON_DOCK_PREFIX;
}

export function isStatutoryOwnerTrade(
  tradeCode: string,
  necessity: OwnerNecessity = "unspecified",
): boolean {
  if (necessity === "statutory_seaworthiness") return true;
  return STATUTORY_OWNER_PREFIXES.has(tradePrefix(tradeCode));
}

export function inferWorkParty(item: RepairLineItem): WorkParty {
  if (item.work_party) return item.work_party;
  if (isCommonDockCharge(item.trade_code || "")) return "common";
  const prefix = tradePrefix(item.trade_code || "");
  if (STATUTORY_OWNER_PREFIXES.has(prefix) || prefix === "ENG" || prefix === "VALVE") {
    return "owner";
  }
  if (item.necessity === "statutory_seaworthiness" || item.necessity === "deferred") {
    return "owner";
  }
  return "casualty";
}

/** Yen-safe integer rounding (half-up for .5). */
export function yen(n: number): number {
  return Math.round(n);
}

/**
 * Pure-TS port of the DuckDB CASE in apportion_rule_d.
 * Guarantees insurer_share + owner_share == cost per line (0 JPY recon error).
 */
export function apportionRuleD(
  items: RepairLineItem[],
  dockingContext: DockingContext,
): RuleDResult {
  if (!items.length) {
    return {
      docking_context: dockingContext,
      has_statutory_owner_repair: false,
      common_dues_total: 0,
      insurer_common_share: 0,
      owner_common_share: 0,
      apportionment_rule: "RULE_D5_100_UNDERWRITER",
      lines: [],
      claimed_total: 0,
      insurer_total: 0,
      owner_total: 0,
    };
  }

  const prepared = items.map((item) => {
    const party = inferWorkParty(item);
    const statutory =
      party === "owner"
        ? isStatutoryOwnerTrade(item.trade_code || "", item.necessity || "unspecified")
        : false;
    return {
      id: item.id,
      trade_code: item.trade_code || "",
      title: item.title || "",
      cost: item.cost,
      work_party: party,
      is_common_dock: isCommonDockCharge(item.trade_code || ""),
      is_statutory_owner: statutory,
    };
  });

  const hasStatutory = prepared.some((r) => r.is_statutory_owner && r.work_party === "owner");
  const apply5050 =
    dockingContext === "deferred_to_routine" ||
    (dockingContext === "casualty_immediate" && hasStatutory);
  const rule: ApportionmentRule = apply5050 ? "RULE_D5_50_50" : "RULE_D5_100_UNDERWRITER";

  const lines: ApportionedLine[] = prepared.map((r) => {
    let insurer = 0;
    let owner = 0;
    if (r.is_common_dock) {
      if (apply5050) {
        // Exact half for even yen; for odd yen keep insurer+owner=cost (floor/ceil).
        insurer = Math.floor(r.cost / 2);
        owner = r.cost - insurer;
      } else {
        insurer = r.cost;
        owner = 0;
      }
    } else if (r.work_party === "casualty") {
      insurer = r.cost;
      owner = 0;
    } else if (r.work_party === "owner") {
      insurer = 0;
      owner = r.cost;
    }
    return {
      id: r.id,
      trade_code: r.trade_code,
      title: r.title,
      cost: r.cost,
      is_common_dock_charge: r.is_common_dock,
      insurer_share: insurer,
      owner_share: owner,
      apportionment_rule: r.is_common_dock ? rule : "DISCRETE",
    };
  });

  const common = lines.filter((l) => l.is_common_dock_charge);
  const commonTotal = common.reduce((s, l) => s + l.cost, 0);
  const insurerCommon = common.reduce((s, l) => s + l.insurer_share, 0);
  const ownerCommon = common.reduce((s, l) => s + l.owner_share, 0);

  return {
    docking_context: dockingContext,
    has_statutory_owner_repair: hasStatutory,
    common_dues_total: commonTotal,
    insurer_common_share: insurerCommon,
    owner_common_share: ownerCommon,
    apportionment_rule: rule,
    lines,
    claimed_total: lines.reduce((s, l) => s + l.cost, 0),
    insurer_total: lines.reduce((s, l) => s + l.insurer_share, 0),
    owner_total: lines.reduce((s, l) => s + l.owner_share, 0),
  };
}

/** DuckDB-WASM SQL path (browser). Same CASE as Python rule_d_solver. */
export async function apportionRuleDSql(
  items: RepairLineItem[],
  dockingContext: DockingContext,
): Promise<RuleDResult> {
  const { withConnection } = await import("../db/duckdb");
  if (!items.length) return apportionRuleD(items, dockingContext);

  return withConnection(async (conn) => {
    await conn.query(`
      CREATE TABLE repair_lines (
        id VARCHAR,
        trade_code VARCHAR,
        title VARCHAR,
        cost DECIMAL(38, 10),
        work_party VARCHAR,
        is_common_dock BOOLEAN,
        is_statutory_owner BOOLEAN
      )
    `);

    const prepared = items.map((item) => {
      const party = inferWorkParty(item);
      const statutory =
        party === "owner"
          ? isStatutoryOwnerTrade(item.trade_code || "", item.necessity || "unspecified")
          : false;
      return {
        id: item.id,
        trade_code: item.trade_code || "",
        title: item.title || "",
        cost: String(item.cost),
        work_party: party,
        is_common_dock: isCommonDockCharge(item.trade_code || ""),
        is_statutory_owner: statutory,
      };
    });

    for (const r of prepared) {
      await conn.query(`
        INSERT INTO repair_lines VALUES (
          '${r.id.replace(/'/g, "''")}',
          '${r.trade_code.replace(/'/g, "''")}',
          '${r.title.replace(/'/g, "''")}',
          CAST(${r.cost} AS DECIMAL(38, 10)),
          '${r.work_party}',
          ${r.is_common_dock},
          ${r.is_statutory_owner}
        )
      `);
    }

    const flags = await conn.query(`
      SELECT
        COALESCE(BOOL_OR(is_statutory_owner AND work_party = 'owner'), FALSE)
          AS has_statutory_owner_repair,
        COALESCE(SUM(cost) FILTER (WHERE is_common_dock), 0) AS common_dues_total
      FROM repair_lines
    `);
    const flagRow = flags.get(0)?.toJSON() as {
      has_statutory_owner_repair: boolean;
      common_dues_total: number;
    };
    const hasStatutory = !!flagRow.has_statutory_owner_repair;
    const apply5050 =
      dockingContext === "deferred_to_routine" ||
      (dockingContext === "casualty_immediate" && hasStatutory);
    const rule: ApportionmentRule = apply5050 ? "RULE_D5_50_50" : "RULE_D5_100_UNDERWRITER";

    const result = await conn.query(`
      WITH params AS (
        SELECT ${apply5050}::BOOLEAN AS apply_5050, '${rule}'::VARCHAR AS dock_rule
      )
      SELECT
        r.id, r.trade_code, r.title, r.cost, r.is_common_dock,
        CASE
          WHEN r.is_common_dock AND p.apply_5050 THEN r.cost * 0.5
          WHEN r.is_common_dock AND NOT p.apply_5050 THEN r.cost
          WHEN r.work_party = 'casualty' THEN r.cost
          ELSE CAST(0 AS DECIMAL(38, 10))
        END AS insurer_share,
        CASE
          WHEN r.is_common_dock AND p.apply_5050 THEN r.cost * 0.5
          WHEN r.is_common_dock AND NOT p.apply_5050 THEN CAST(0 AS DECIMAL(38, 10))
          WHEN r.work_party = 'owner' THEN r.cost
          ELSE CAST(0 AS DECIMAL(38, 10))
        END AS owner_share,
        CASE WHEN r.is_common_dock THEN p.dock_rule ELSE 'DISCRETE' END AS apportionment_rule
      FROM repair_lines r CROSS JOIN params p
      ORDER BY r.id
    `);

    const lines: ApportionedLine[] = [];
    for (let i = 0; i < result.numRows; i++) {
      const row = result.get(i)!.toJSON() as Record<string, unknown>;
      const cost = Number(row.cost);
      let insurer = Number(row.insurer_share);
      let owner = Number(row.owner_share);
      // Force exact yen reconciliation when DuckDB yields .0 halves
      if (row.is_common_dock && apply5050) {
        insurer = Math.floor(cost / 2);
        owner = cost - insurer;
      } else {
        insurer = yen(insurer);
        owner = yen(owner);
      }
      lines.push({
        id: String(row.id),
        trade_code: String(row.trade_code),
        title: String(row.title || ""),
        cost: yen(cost),
        is_common_dock_charge: !!row.is_common_dock,
        insurer_share: insurer,
        owner_share: owner,
        apportionment_rule: String(row.apportionment_rule) as ApportionmentRule,
      });
    }

    const common = lines.filter((l) => l.is_common_dock_charge);
    return {
      docking_context: dockingContext,
      has_statutory_owner_repair: hasStatutory,
      common_dues_total: common.reduce((s, l) => s + l.cost, 0),
      insurer_common_share: common.reduce((s, l) => s + l.insurer_share, 0),
      owner_common_share: common.reduce((s, l) => s + l.owner_share, 0),
      apportionment_rule: rule,
      lines,
      claimed_total: lines.reduce((s, l) => s + l.cost, 0),
      insurer_total: lines.reduce((s, l) => s + l.insurer_share, 0),
      owner_total: lines.reduce((s, l) => s + l.owner_share, 0),
    };
  });
}
