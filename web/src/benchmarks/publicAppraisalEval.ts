/**
 * Public appraisal eval scoring (port of benchmarks/public_appraisal_eval.py).
 * Canonical Gate A scoring for Vitest / PWA — independent of Python.
 */
import { normalizeStatusBucket, isCriticalFalseAccept } from "../appraisal/boundary";

const GOLD_OUTER_HULL = ["船体外板", "船側外板", "船底外板"] as const;
const GOLD_DRYDOCK = ["入出渠", "滞渠"] as const;
const GOLD_MACHINERY = [
  "主機関",
  "ピストン",
  "吸排気弁",
  "燃料噴射弁",
  "発電機関",
  "カロリーファイヤー",
  "汚物処理",
  "減速機",
  "クラッチ",
  "シリンダー",
] as const;
const GOLD_PROPULSION = ["プロペラ軸", "プロペラ、軸", "推進器"] as const;

export { normalizeStatusBucket };

export function itemKey(item: Record<string, unknown>): string {
  const num = String(item.num ?? item.id ?? "");
  const desc = String(item.description ?? "").trim();
  return `${num}::${desc.slice(0, 80)}`;
}

/** Founder provisional gold v1 — independent of pipeline (regression signal). */
export function assignProvisionalGoldStatus(
  description: string,
  damagedZones: string[],
  category = "",
): string {
  const desc = description || "";
  const zones = new Set(damagedZones || []);
  const hasHull = ["外板", "球状船首", "貨物タンク", "タンク", "甲板"].some((z) =>
    zones.has(z),
  );
  const hasProp = ["推進器", "舵"].some((z) => zones.has(z));
  const hasMach = zones.has("機関室");

  if (GOLD_DRYDOCK.some((k) => desc.includes(k))) return "APPORTIONED";

  if (desc.includes("バウスラスター") && !desc.includes("機関室") && !desc.includes("汚物処理")) {
    if (desc.trim().startsWith("バウスラスター") || desc.includes("バウスラスター プロペラ")) {
      return zones.has("球状船首") ? "REVIEW" : "EXCLUDED";
    }
  }

  if (
    GOLD_MACHINERY.some((k) => desc.includes(k)) ||
    (category.includes("機関") && ["ポンプ", "弁", "開放"].some((k) => desc.includes(k)))
  ) {
    return hasMach ? "COVERED" : "EXCLUDED";
  }

  if (GOLD_PROPULSION.some((k) => desc.includes(k))) {
    return hasProp ? "COVERED" : "EXCLUDED";
  }

  if (GOLD_OUTER_HULL.some((k) => desc.includes(k))) {
    return hasHull ? "COVERED" : "EXCLUDED";
  }

  return "EXCLUDED";
}

export function attachProvisionalGold(
  items: Array<Record<string, unknown>>,
  damagedZones: string[],
): Array<Record<string, unknown>> {
  return items.map((item) => ({
    ...item,
    gold_status: assignProvisionalGoldStatus(
      String(item.description ?? ""),
      damagedZones,
      String(item.category ?? ""),
    ),
  }));
}

export function scorePredictions(
  items: Array<Record<string, unknown>>,
  damagedZones: string[],
  criticalSubstrings: string[],
): Record<string, unknown> {
  const labeled = attachProvisionalGold(items, damagedZones);
  let total = 0;
  let agree = 0;
  let falseAccept = 0;
  let falseReject = 0;
  let criticalFa = 0;
  const disagreements: Array<Record<string, unknown>> = [];

  for (const row of labeled) {
    const gold = normalizeStatusBucket(String(row.gold_status ?? ""));
    const pred = normalizeStatusBucket(String(row.status ?? ""));
    if (gold === "OTHER" || pred === "OTHER") continue;
    total += 1;
    if (gold === pred) {
      agree += 1;
    } else {
      disagreements.push({
        key: itemKey(row),
        gold,
        pred,
        description: String(row.description ?? "").slice(0, 120),
      });
      if (gold === "EXCLUDED" && ["COVERED", "REVIEW", "APPORTIONED"].includes(pred)) {
        falseAccept += 1;
      }
      if (["COVERED", "APPORTIONED", "REVIEW"].includes(gold) && pred === "EXCLUDED") {
        falseReject += 1;
      }
    }
    if (
      isCriticalFalseAccept({
        gold_bucket: gold,
        pred_bucket: pred,
        description: String(row.description ?? ""),
        critical_substrings: criticalSubstrings,
        damaged_zones: damagedZones,
      })
    ) {
      criticalFa += 1;
    }
  }

  const agreement = total ? agree / total : 0;
  return {
    items_scored: total,
    agreement: Math.round(agreement * 10000) / 10000,
    false_accept: falseAccept,
    false_reject: falseReject,
    critical_false_accept: criticalFa,
    disagreements_sample: disagreements.slice(0, 25),
    gold_rows: labeled,
  };
}

export function evaluateCaseDicts(opts: {
  case: Record<string, unknown>;
  predicted_items: Array<Record<string, unknown>>;
  damaged_zones: string[];
  critical_substrings: string[];
}): Record<string, unknown> {
  const metrics = scorePredictions(
    opts.predicted_items,
    opts.damaged_zones,
    opts.critical_substrings,
  );
  const { gold_rows, ...rest } = metrics;
  return {
    case_id: opts.case.case_id,
    title: opts.case.title,
    damaged_zones: opts.damaged_zones,
    items_predicted: opts.predicted_items.length,
    ...rest,
    gold_rows,
  };
}

export function gateReport(
  caseResults: Array<Record<string, unknown>>,
  gates: Record<string, unknown>,
): Record<string, unknown> {
  const runnable = caseResults.filter((c) => !c.skipped);
  const criticalFa = runnable.reduce(
    (s, c) => s + Number(c.critical_false_accept || 0),
    0,
  );
  const agreements = runnable
    .filter((c) => c.items_scored)
    .map((c) => Number(c.agreement));
  const meanAgreement = agreements.length
    ? Math.round((agreements.reduce((a, b) => a + b, 0) / agreements.length) * 10000) /
      10000
    : 0;
  const minCases = Number(gates.min_cases_with_pdfs || 0);
  const maxCfa = Number(gates.max_critical_false_accepts || 0);
  const minAgr = Number(gates.min_status_agreement || 0);
  return {
    cases_configured: caseResults.length,
    cases_run: runnable.length,
    cases_skipped: caseResults.length - runnable.length,
    mean_agreement: meanAgreement,
    critical_false_accept_total: criticalFa,
    pass_min_cases: runnable.length >= minCases,
    pass_critical_fa: criticalFa <= maxCfa,
    pass_agreement: runnable.length ? meanAgreement >= minAgr : false,
    overall_pass:
      runnable.length >= minCases &&
      criticalFa <= maxCfa &&
      (runnable.length ? meanAgreement >= minAgr : false),
    gates,
  };
}
