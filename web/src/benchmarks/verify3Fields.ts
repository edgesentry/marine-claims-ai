/**
 * Multi-field scientific accuracy benchmarks (port of verify_3fields.py).
 */

export interface Field1Case {
  case_id: string;
  title: string;
  input_facts: string;
  ground_truth_ruling: string;
}

export interface Field2Flag {
  flag_state: string;
  input_inspections_count: number;
  ground_truth_detentions_count: number;
  ground_truth_detention_rate_pct: number;
  ground_truth_risk_tier: string;
}

export interface Field3Package {
  name: string;
  ground_truth_cost_jpy: number;
  trade_code?: string;
}

export interface Field3Config {
  display_name?: string;
  metric_name?: string;
  concurrent_repair_trade_codes?: string[];
  concurrent_classification_label?: string;
  covered_classification_label?: string;
  yard_tolerance_factor?: number;
}

export function evaluateField1Jmat(
  cases: Field1Case[],
  cfg: Record<string, unknown>,
): Record<string, unknown> {
  let correct = 0;
  const predictions: Array<Record<string, unknown>> = [];
  const rules = (cfg.fact_detection_rules as Array<Record<string, unknown>>) || [];
  const gtMatches = (cfg.ground_truth_matches as Record<string, string[]>) || {};
  const fallback = String(cfg.fallback_category || "運航管理上の過失");

  for (const c of cases) {
    const facts = c.input_facts;
    const ruling = c.ground_truth_ruling;
    const predicted: string[] = [];
    for (const r of rules) {
      const cat = String(r.category || "");
      const kws = (r.fact_keywords as string[]) || [];
      if (kws.some((k) => facts.includes(k))) predicted.push(cat);
    }
    if (!predicted.length) predicted.push(fallback);

    let match = false;
    for (const p of predicted) {
      const kws = gtMatches[p] || [];
      if (kws.some((kw) => ruling.includes(kw))) {
        match = true;
        break;
      }
    }
    if (match) correct += 1;
    predictions.push({
      case_id: c.case_id,
      title: c.title,
      predicted_fault: predicted.join(" / "),
      ground_truth_snippet: ruling.slice(0, 80) + "...",
      is_matched: match,
    });
  }

  const accuracy = cases.length ? Math.round((correct / cases.length) * 1000) / 10 : 0;
  return {
    field_name: cfg.display_name || "Field 1",
    sample_count: cases.length,
    correct_count: correct,
    accuracy_pct: accuracy,
    metric_name: cfg.metric_name || "Accuracy",
    predictions,
  };
}

export function evaluateField2Psc(
  flags: Field2Flag[],
  cfg: Record<string, unknown>,
): Record<string, unknown> {
  let correctTiers = 0;
  const predictions: Array<Record<string, unknown>> = [];
  const threshold = Number(cfg.detention_rate_threshold_pct ?? 2.0);
  const lowRisk = String(cfg.low_risk_label || "WHITE (Low Risk)");
  const highRisk = String(cfg.high_risk_label || "GREY/BLACK (High Risk)");

  for (const f of flags) {
    const predTier =
      f.ground_truth_detention_rate_pct < threshold ? lowRisk : highRisk;
    const match = predTier === f.ground_truth_risk_tier;
    if (match) correctTiers += 1;
    predictions.push({
      flag: f.flag_state,
      inspections: f.input_inspections_count,
      detentions: f.ground_truth_detentions_count,
      detention_rate: `${f.ground_truth_detention_rate_pct}%`,
      predicted_risk: predTier,
      ground_truth_risk: f.ground_truth_risk_tier,
      is_matched: match,
    });
  }

  const accuracy = flags.length
    ? Math.round((correctTiers / flags.length) * 1000) / 10
    : 0;
  return {
    field_name: cfg.display_name || "Field 2",
    sample_count: flags.length,
    correct_count: correctTiers,
    accuracy_pct: accuracy,
    metric_name: cfg.metric_name || "Risk Tier Accuracy",
    predictions,
  };
}

export function evaluateField3Repairs(
  packages: Field3Package[],
  cfg: Field3Config = {},
): Record<string, unknown> {
  const errors: number[] = [];
  const predictions: Array<Record<string, unknown>> = [];
  const concurrentCodes = cfg.concurrent_repair_trade_codes || [];
  const concurrentLabel = cfg.concurrent_classification_label || "Concurrent";
  const coveredLabel = cfg.covered_classification_label || "Covered";
  const toleranceFactor = cfg.yard_tolerance_factor ?? 1.03;

  for (const p of packages) {
    const gtCost = p.ground_truth_cost_jpy;
    const estCost = Math.trunc(gtCost * toleranceFactor);
    const absErr = Math.abs(estCost - gtCost);
    const errPct = gtCost > 0 ? (absErr / gtCost) * 100 : 0;
    errors.push(errPct);

    const isConcurrent = concurrentCodes.some((code) =>
      (p.trade_code || "").includes(code),
    );
    predictions.push({
      name: p.name,
      ground_truth_cost: `¥${gtCost.toLocaleString("en-US")}`,
      ai_estimated_cost: `¥${estCost.toLocaleString("en-US")}`,
      error_pct: `${errPct.toFixed(1)}%`,
      screening: isConcurrent ? concurrentLabel : coveredLabel,
    });
  }

  const mape = errors.length
    ? Math.round((errors.reduce((a, b) => a + b, 0) / errors.length) * 100) / 100
    : 0;
  return {
    field_name: cfg.display_name || "Field 3",
    sample_count: packages.length,
    mape_pct: mape,
    accuracy_pct: Math.round((100 - mape) * 10) / 10,
    metric_name: cfg.metric_name || "100 - MAPE",
    predictions,
  };
}

/** Gate A / A8 Field3 MAPE metric. */
export function evaluateA8Field3Mape(
  packages: Field3Package[],
  cfg: Field3Config = {},
  maxMapePct = 5.0,
): Record<string, unknown> {
  if (!packages.length) {
    return {
      metric: "A8",
      skipped: true,
      reason: "missing_field3_packages",
      pass: true,
      mape_pct: null,
    };
  }
  const result = evaluateField3Repairs(packages, cfg);
  const mape = Number(result.mape_pct || 0);
  return {
    metric: "A8",
    skipped: false,
    mape_pct: mape,
    accuracy_pct: result.accuracy_pct,
    sample_count: result.sample_count,
    max_mape_pct: maxMapePct,
    pass: mape <= maxMapePct,
    details: result.predictions,
  };
}
