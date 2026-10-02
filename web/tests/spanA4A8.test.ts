import { describe, expect, it } from "vitest";
import {
  assertQuoteInText,
  findGroundedQuote,
  quoteInText,
  SpanValidationError,
} from "../src/pipeline/spanValidate";
import { extractSpecWithSpansFromText } from "../src/pipeline/extractSpec";
import {
  A4_LITE_ITEMS,
  A4_LITE_PDF_TEXT,
  DEFAULT_GATE_CONFIG,
  runGateAPriority1Lite,
} from "../src/benchmarks/gateAPriority1";
import field3Packages from "./fixtures/field3_repair_packages.json";
import field3Rules from "./fixtures/benchmark_rules_field3.json";
import { evaluateField3Repairs } from "../src/benchmarks/verify3Fields";

describe("spanValidate A4", () => {
  it("accepts exact and whitespace variants", () => {
    const pdf = "船体入出渠及び滞渠\n船体外板高圧清水洗浄";
    expect(quoteInText("船体入出渠及び滞渠", pdf)).toBe(true);
    expect(quoteInText("船体入出渠 及び滞渠", pdf)).toBe(true);
    expect(() => assertQuoteInText("船体外板高圧清水洗浄", pdf)).not.toThrow();
  });

  it("rejects fabricated quotes", () => {
    const pdf = "船体入出渠及び滞渠\n船体外板高圧清水洗浄";
    const fabricated = "架空の機関室オーバーホール工事XYZ999アルファ";
    expect(quoteInText(fabricated, pdf)).toBe(false);
    expect(() => assertQuoteInText(fabricated, pdf)).toThrow(SpanValidationError);
    expect(findGroundedQuote(fabricated, pdf)).toBeNull();
  });

  it("finds longest grounded prefix across join gaps", () => {
    const pdf = "効力検査関係（１）下記機器の検査\n備考番号工事内訳\n（２）海洋汚染防止";
    const description = "効力検査関係（１）下記機器の検査 （２）海洋汚染防止";
    const quote = findGroundedQuote(description, pdf);
    expect(quote).not.toBeNull();
    expect(quoteInText(quote!, pdf)).toBe(true);
    expect(quote).toContain("効力検査関係");
  });

  it("extractSpec rejects ungrounded rows", () => {
    const result = extractSpecWithSpansFromText(A4_LITE_PDF_TEXT, A4_LITE_ITEMS);
    expect(result.fabricated_line_items).toBe(1);
    expect(result.items).toHaveLength(2);
    expect(result.items[0]!.source_quote).toBe("船体入出渠及び滞渠");
  });
});

describe("verify3Fields A8", () => {
  it("MAPE under 5% with yard tolerance 1.03", () => {
    const cfg = field3Rules.field3_repair_cost;
    const result = evaluateField3Repairs(field3Packages, cfg);
    expect(Number(result.mape_pct)).toBeLessThanOrEqual(5);
    expect(Number(result.sample_count)).toBe(field3Packages.length);
  });
});

describe("gateAPriority1 with A4/A8 live", () => {
  it("lite Gate A runs A4 grounding and A8 MAPE", () => {
    const report = runGateAPriority1Lite(DEFAULT_GATE_CONFIG, {
      bid_count: 0,
      field3Packages,
      field3Config: field3Rules.field3_repair_cost,
    });
    const metrics = report.metrics as Record<string, Record<string, unknown>>;
    expect(metrics.A4.skipped).toBeFalsy();
    expect(Number(metrics.A4.grounded_items)).toBe(2);
    expect(Number(metrics.A4.discarded_ungrounded)).toBe(1);
    expect(metrics.A8.skipped).toBe(false);
    expect(Number(metrics.A8.mape_pct)).toBeLessThanOrEqual(5);
    expect((report.gate as Record<string, unknown>).overall_pass).toBe(true);
  });
});
