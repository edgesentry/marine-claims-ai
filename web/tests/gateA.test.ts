import { describe, expect, it } from "vitest";
import {
  assignProvisionalGoldStatus,
  gateReport,
  scorePredictions,
  normalizeStatusBucket,
} from "../src/benchmarks/publicAppraisalEval";
import { isCriticalFalseAccept } from "../src/appraisal/boundary";
import {
  DEFAULT_GATE_CONFIG,
  evaluateA3RuleD5Pipeline,
  evaluateA3RuleD5Synthetic,
  runGateAPriority1Lite,
  scaleStatus,
} from "../src/benchmarks/gateAPriority1";

describe("publicAppraisalEval", () => {
  it("normalizeStatusBucket", () => {
    expect(normalizeStatusBucket("APPORTIONED (50%)")).toBe("APPORTIONED");
    expect(normalizeStatusBucket("EXCLUDED (便乗修理)")).toBe("EXCLUDED");
    expect(normalizeStatusBucket("REVIEW / PARTIAL")).toBe("REVIEW");
    expect(normalizeStatusBucket("COVERED")).toBe("COVERED");
  });

  it("provisional gold bow collision policy", () => {
    const zones = ["球状船首", "外板"];
    expect(assignProvisionalGoldStatus("船体入出渠及び滞渠", zones)).toBe("APPORTIONED");
    expect(assignProvisionalGoldStatus("船体外板、船側外板高圧清水洗浄", zones)).toBe(
      "COVERED",
    );
    expect(assignProvisionalGoldStatus("カロリーファイヤー開放掃除", zones)).toBe("EXCLUDED");
    expect(assignProvisionalGoldStatus("プロペラ軸及び翼取り外し", zones)).toBe("EXCLUDED");
    expect(assignProvisionalGoldStatus("バウスラスター プロペラ研磨", zones)).toBe("REVIEW");
  });

  it("critical false accept detection", () => {
    expect(
      isCriticalFalseAccept({
        gold_bucket: "EXCLUDED",
        pred_bucket: "COVERED",
        description: "カロリーファイヤー開放",
        critical_substrings: ["カロリーファイヤー"],
        damaged_zones: ["球状船首"],
      }),
    ).toBe(true);
    expect(
      isCriticalFalseAccept({
        gold_bucket: "EXCLUDED",
        pred_bucket: "EXCLUDED",
        description: "カロリーファイヤー開放",
        critical_substrings: ["カロリーファイヤー"],
        damaged_zones: ["球状船首"],
      }),
    ).toBe(false);
  });

  it("scorePredictions agreement and gates", () => {
    const zones = ["球状船首", "外板"];
    const items = [
      {
        num: "2",
        description: "船体入出渠及び滞渠",
        category: "【甲板部】",
        status: "APPORTIONED (50%)",
      },
      {
        num: "3",
        description: "船体外板、船側外板高圧清水洗浄",
        category: "【甲板部】",
        status: "COVERED",
      },
      {
        num: "81",
        description: "カロリーファイヤー開放掃除",
        category: "【機関部】",
        status: "EXCLUDED (便乗修理)",
      },
      {
        num: "99",
        description: "プロペラ軸及び翼取り外し",
        category: "【機関部】",
        status: "COVERED",
      },
    ];
    const metrics = scorePredictions(items, zones, ["カロリーファイヤー", "プロペラ軸"]);
    expect(metrics.items_scored).toBe(4);
    expect(metrics.false_accept).toBe(1);
    expect(metrics.critical_false_accept).toBe(1);
    expect(Number(metrics.agreement)).toBeGreaterThan(0);
    expect(Number(metrics.agreement)).toBeLessThan(1);

    const gate = gateReport(
      [
        {
          skipped: false,
          agreement: metrics.agreement,
          critical_false_accept: metrics.critical_false_accept,
          items_scored: metrics.items_scored,
        },
      ],
      {
        min_cases_with_pdfs: 1,
        max_critical_false_accepts: 0,
        min_status_agreement: 0.85,
      },
    );
    expect(gate.pass_critical_fa).toBe(false);
    expect(gate.overall_pass).toBe(false);
  });
});

describe("gateAPriority1", () => {
  it("loads default thresholds", () => {
    expect(DEFAULT_GATE_CONFIG.gates!.max_critical_false_accepts).toBe(0);
    expect(DEFAULT_GATE_CONFIG.gates!.max_rule_d5_reconciliation_error_jpy).toBe(0);
    expect(DEFAULT_GATE_CONFIG.gates!.min_status_agreement).toBe(0.85);
  });

  it("A3 synthetic and pipeline zero error", () => {
    const syn = evaluateA3RuleD5Synthetic();
    const pipe = evaluateA3RuleD5Pipeline();
    expect(syn.pass).toBe(true);
    expect(syn.reconciliation_error_jpy).toBe(0);
    expect(pipe.pass).toBe(true);
    expect(pipe.reconciliation_error_jpy).toBe(0);
  });

  it("scale incomplete when below targets", () => {
    const s = scaleStatus({
      grounded_items: 100,
      cases_run: 3,
      bid_count: 1,
      targets: { min_vessels: 10, min_line_items: 2500, min_bid_notices: 20 },
    });
    expect(s.scale_incomplete).toBe(true);
  });

  it("lite Gate A passes zero-tolerance", () => {
    const report = runGateAPriority1Lite(DEFAULT_GATE_CONFIG, { bid_count: 0 });
    expect(report.gate).toBeDefined();
    const gate = report.gate as Record<string, unknown>;
    expect(gate.zero_tolerance_pass).toBe(true);
    expect(gate.rule_d5_reconciliation_error_jpy).toBe(0);
    expect(gate.critical_false_accept_total).toBe(0);
    expect((report.scale as Record<string, unknown>).scale_incomplete).toBe(true);
    expect(gate.overall_pass).toBe(true);
  });
});
