/**
 * Gate A Priority 1 harness (port of benchmarks/gate_a_priority1.py).
 * PDF-free lite path is the CI / Vitest default (A4/A8 use in-memory fixtures).
 */
import { apportionRuleD, type RepairLineItem } from "../engines/ruleD5";
import {
  evaluateClaimsDynamically,
  noOpNplScorer,
} from "../appraisal/pipeline";
import { evaluateA4ExactSpanFromText } from "../pipeline/extractSpec";
import {
  evaluateA8Field3Mape,
  type Field3Config,
  type Field3Package,
} from "./verify3Fields";
import {
  evaluateCaseDicts,
  gateReport,
  scorePredictions,
} from "./publicAppraisalEval";

/** Synthetic PDF text + items for A4 zero-dataset lite. */
export const A4_LITE_PDF_TEXT =
  "船体入出渠及び滞渠\n船体外板高圧清水洗浄\nJG定期検査立会";

export const A4_LITE_ITEMS = [
  {
    id: 1,
    category: "【甲板部】",
    num: "1",
    description: "船体入出渠及び滞渠",
    estimated_cost: 4_300_000,
  },
  {
    id: 2,
    category: "【甲板部】",
    num: "2",
    description: "船体外板高圧清水洗浄",
    estimated_cost: 450_000,
  },
  {
    id: 99,
    category: "【機関部】",
    num: "99",
    description: "架空の機関室オーバーホール工事XYZ999アルファ",
    estimated_cost: 9_999_999,
  },
];

export interface GateConfig {
  version?: number;
  scale_targets?: Record<string, number>;
  gates?: Record<string, number>;
  critical_exclude_substrings?: string[];
  public_appraisal_config?: string;
}

export const DEFAULT_GATE_CONFIG: GateConfig = {
  version: 1,
  scale_targets: {
    min_vessels: 10,
    min_line_items: 2500,
    min_bid_notices: 20,
  },
  gates: {
    min_status_agreement: 0.85,
    max_critical_false_accepts: 0,
    max_rule_d5_reconciliation_error_jpy: 0,
    max_fabricated_line_items: 0,
    max_field3_mape_pct: 5.0,
    min_cases_with_pdfs: 1,
  },
  critical_exclude_substrings: [
    "カロリーファイヤー",
    "プロペラ軸",
    "減速機",
    "クラッチ",
    "汚物処理装置",
    "主機関",
    "ピストン",
  ],
};

/** Synthetic dual-necessity docking — insurer+owner must reconcile to 0 JPY. */
export function evaluateA3RuleD5Synthetic(): Record<string, unknown> {
  const items: RepairLineItem[] = [
    {
      id: "hull-1",
      trade_code: "HULL-01",
      cost: 450_000,
      work_party: "casualty",
      title: "外板損傷修繕",
    },
    {
      id: "safe-1",
      trade_code: "SAFE-01",
      cost: 550_000,
      necessity: "statutory_seaworthiness",
      title: "JG定期検査",
    },
    {
      id: "dock-1",
      trade_code: "DOCK-01",
      cost: 4_300_000,
      title: "入出渠・滞渠",
    },
  ];
  const result = apportionRuleD(items, "casualty_immediate");
  let err = 0;
  for (const ln of result.lines) {
    err += Math.abs(ln.insurer_share + ln.owner_share - ln.cost);
  }
  err += Math.abs(result.insurer_total + result.owner_total - result.claimed_total);
  return {
    metric: "A3",
    reconciliation_error_jpy: err,
    apportionment_rule: result.apportionment_rule,
    common_dues_total: result.common_dues_total,
    pass: err === 0,
  };
}

/** Pipeline path: drydock line uses D5 shares with 0 JPY reconciliation. */
export function evaluateA3RuleD5Pipeline(): Record<string, unknown> {
  const casualty = {
    vessel_name: "synthetic",
    incident_type: "衝突",
    incident_date: "2024-01-01",
    incident_location: "test",
    damaged_components: ["球状船首", "外板"],
    damage_evidence: [] as string[],
    source_pdf: "synthetic",
  };
  const items = [
    {
      id: 1,
      category: "【甲板部】",
      num: "1",
      description: "船体入出渠及び滞渠",
      estimated_cost: 4_300_000,
    },
    {
      id: 2,
      category: "【甲板部】",
      num: "2",
      description: "船体外板・船側外板高圧清水洗浄",
      estimated_cost: 450_000,
    },
    {
      id: 3,
      category: "【法定部】",
      num: "3",
      description: "JG定期検査立会",
      estimated_cost: 550_000,
    },
  ];
  const { analyzed, summary } = evaluateClaimsDynamically(
    items,
    casualty,
    noOpNplScorer,
    { dockingContext: "casualty_immediate", assumeStatutoryOwnerWork: true },
  );
  const dock = analyzed.find((x) => x.description.includes("入出渠"))!;
  const err = summary.rule_d5_reconciliation_error_jpy;
  const lineErr = Math.abs(
    (dock.insurer_share ?? 0) + (dock.owner_share ?? 0) - dock.estimated_cost,
  );
  return {
    metric: "A3_pipeline",
    reconciliation_error_jpy: err + lineErr,
    apportionment_rule: dock.apportionment_rule,
    pass: err + lineErr === 0,
  };
}

/** Bow-collision synthetic case for A1/A2 without PDFs. */
export function evaluateA1A2Synthetic(
  criticalSubstrings: string[] = DEFAULT_GATE_CONFIG.critical_exclude_substrings!,
): Record<string, unknown> {
  const zones = ["球状船首", "外板"];
  const items = [
    {
      id: 1,
      category: "【甲板部】",
      num: "1",
      description: "船体入出渠及び滞渠",
      estimated_cost: 4_300_000,
    },
    {
      id: 2,
      category: "【甲板部】",
      num: "2",
      description: "船体外板・船側外板高圧清水洗浄",
      estimated_cost: 450_000,
    },
    {
      id: 59,
      category: "【機関部】",
      num: "59",
      description: "減速機入出力側、クラッチ陸揚げ点検整備受検",
      estimated_cost: 1_200_000,
    },
    {
      id: 81,
      category: "【機関部】",
      num: "81",
      description: "カロリーファイヤー（給湯設備）開放掃除洗浄復旧耐圧",
      estimated_cost: 350_000,
    },
    {
      id: 90,
      category: "【機関部】",
      num: "90",
      description: "主機関ピストン抜出開放点検",
      estimated_cost: 4_800_000,
    },
  ];
  const { analyzed, summary } = evaluateClaimsDynamically(
    items,
    {
      damaged_components: zones,
      vessel_name: "synthetic-bow",
      source_pdf: "synthetic",
    },
    noOpNplScorer,
  );
  const caseResult = evaluateCaseDicts({
    case: { case_id: "synthetic_bow", title: "Synthetic bow collision" },
    predicted_items: analyzed as unknown as Array<Record<string, unknown>>,
    damaged_zones: zones,
    critical_substrings: criticalSubstrings,
  });
  caseResult.skipped = false;
  caseResult.summary = {
    rule_d5_reconciliation_error_jpy: summary.rule_d5_reconciliation_error_jpy,
  };
  const gate = gateReport([caseResult], {
    min_cases_with_pdfs: 1,
    max_critical_false_accepts: 0,
    min_status_agreement: 0.85,
  });
  return {
    metric: "A1_A2",
    mean_agreement: gate.mean_agreement,
    critical_false_accept_total: gate.critical_false_accept_total,
    cases_run: gate.cases_run,
    cases_skipped: 0,
    overall_pass: gate.overall_pass,
    cases: [caseResult],
    pass: Boolean(gate.pass_critical_fa) && Number(gate.critical_false_accept_total) === 0,
  };
}

export function scaleStatus(opts: {
  grounded_items: number;
  cases_run: number;
  bid_count: number;
  targets: Record<string, number>;
}): Record<string, unknown> {
  const minVessels = opts.targets.min_vessels ?? 10;
  const minItems = opts.targets.min_line_items ?? 2500;
  const minBids = opts.targets.min_bid_notices ?? 20;
  const incomplete =
    opts.cases_run < minVessels ||
    opts.grounded_items < minItems ||
    opts.bid_count < minBids;
  return {
    scale_incomplete: incomplete,
    vessels_run: opts.cases_run,
    line_items: opts.grounded_items,
    bid_notices: opts.bid_count,
    targets: {
      min_vessels: minVessels,
      min_line_items: minItems,
      min_bid_notices: minBids,
    },
  };
}

/**
 * PDF-free Gate A Priority 1 (CI / Vitest).
 * A3 synthetic+pipeline, synthetic A1/A2, in-memory A4 span, fixture A8 MAPE.
 */
export function runGateAPriority1Lite(
  gateCfg: GateConfig = DEFAULT_GATE_CONFIG,
  opts: {
    bid_count?: number;
    useSyntheticA1A2?: boolean;
    field3Packages?: Field3Package[];
    field3Config?: Field3Config;
  } = {},
): Record<string, unknown> {
  const gates = gateCfg.gates || {};
  const critical = gateCfg.critical_exclude_substrings || [];
  const a3Syn = evaluateA3RuleD5Synthetic();
  const a3Pipe = evaluateA3RuleD5Pipeline();
  const useSyn = opts.useSyntheticA1A2 !== false;
  const a1a2 = useSyn
    ? evaluateA1A2Synthetic(critical)
    : {
        metric: "A1_A2",
        mean_agreement: 0,
        critical_false_accept_total: 0,
        cases_run: 0,
        cases_skipped: 0,
        overall_pass: true,
        cases: [],
        pass: true,
      };
  const a4 = evaluateA4ExactSpanFromText(A4_LITE_PDF_TEXT, A4_LITE_ITEMS);
  const maxMape = Number(gates.max_field3_mape_pct ?? 5.0);
  const packages = opts.field3Packages;
  const a8 =
    packages && packages.length
      ? evaluateA8Field3Mape(packages, opts.field3Config || {}, maxMape)
      : evaluateA8Field3Mape([], {}, maxMape);

  const maxCfa = Number(gates.max_critical_false_accepts ?? 0);
  const maxD5 = Number(gates.max_rule_d5_reconciliation_error_jpy ?? 0);
  const maxFab = Number(gates.max_fabricated_line_items ?? 0);
  const minAgr = Number(gates.min_status_agreement ?? 0.85);

  const cfa = Number(a1a2.critical_false_accept_total ?? 0);
  const agr = Number(a1a2.mean_agreement ?? 0);
  let d5Err =
    Number(a3Syn.reconciliation_error_jpy) + Number(a3Pipe.reconciliation_error_jpy);
  for (const case_ of (a1a2.cases as Array<Record<string, unknown>>) || []) {
    if (case_.skipped) continue;
    d5Err += Number(
      ((case_.summary as Record<string, unknown>) || {}).rule_d5_reconciliation_error_jpy ||
        0,
    );
  }
  const fab = Number(a4.fabricated_line_items || 0);

  const zeroTolPass =
    cfa <= maxCfa &&
    d5Err <= maxD5 &&
    fab <= maxFab &&
    Boolean(a3Syn.pass) &&
    Boolean(a3Pipe.pass) &&
    Boolean(a4.pass);

  const agreementPass = Number(a1a2.cases_run || 0) === 0 || agr >= minAgr;
  const a8Pass = Boolean(a8.pass);

  const scale = scaleStatus({
    grounded_items: Number(a4.grounded_items || 0),
    cases_run: Number(a1a2.cases_run || 0),
    bid_count: opts.bid_count ?? 0,
    targets: gateCfg.scale_targets || {},
  });

  const overall = scale.scale_incomplete
    ? zeroTolPass && a8Pass
    : zeroTolPass && agreementPass && a8Pass;

  return {
    config_version: gateCfg.version,
    mode: "lite_pdf_free",
    metrics: {
      A1_A2: a1a2,
      A3: {
        synthetic: a3Syn,
        pipeline: a3Pipe,
        reconciliation_error_jpy: d5Err,
      },
      A4: a4,
      A8: a8,
    },
    scale,
    gate: {
      zero_tolerance_pass: zeroTolPass,
      agreement_pass: agreementPass,
      a8_pass: a8Pass,
      overall_pass: overall,
      critical_false_accept_total: cfa,
      mean_agreement: agr,
      rule_d5_reconciliation_error_jpy: d5Err,
      fabricated_line_items: fab,
      thresholds: gates,
    },
  };
}

export { scorePredictions, gateReport };
