import { describe, expect, it } from "vitest";
import snippets from "./fixtures/civil_offline_snippets.json";
import { evaluateOfflineSnippets } from "../src/benchmarks/civilExtractorEval";
import {
  bestFaultRatio,
  extractFaultRatios,
  extractFromJudgment,
  extractNegligenceHolding,
  extractionMatchesGold,
  faultRatioWithinPts,
  parseFaultRatioParts,
  parseKanjiInt,
  parseYenToken,
} from "../src/ingest/civilJudgmentExtractor";

describe("parseKanjiInt", () => {
  it.each([
    ["六五", 65],
    ["八〇", 80],
    ["三五", 35],
    ["三十五", 35],
    ["六十五", 65],
    ["十", 10],
    ["百二十", 120],
    ["八〇七万二三三五", 8_072_335],
    ["一一七〇万五〇〇〇", 11_705_000],
    ["一億〇三九〇万三〇〇〇", 103_903_000],
    ["65", 65],
    ["６５", 65],
  ] as const)("%s → %i", (token, expected) => {
    expect(parseKanjiInt(token)).toBe(expected);
  });
});

describe("parseYenToken", () => {
  it.each([
    ["8,072,335円", 8_072_335],
    ["八〇七万二三三五円", 8_072_335],
    ["１１７０５０００円", 11_705_000],
    ["一一七〇万五〇〇〇円", 11_705_000],
  ] as const)("%s → %i", (token, expected) => {
    expect(parseYenToken(token)).toBe(expected);
  });
});

describe("fault ratio patterns", () => {
  it("arabic and kanji fault pairs", () => {
    expect(bestFaultRatio("過失割合は 65対35 である。")).toBe("65:35");
    expect(bestFaultRatio("過失割合を八〇対二〇と認めるのが相当である。")).toBe(
      "80:20",
    );
    expect(bestFaultRatio("責任割合を建昌65・有漁丸35と判示。")).toBe("65:35");
  });

  it("middle_dot and named_tenths", () => {
    const text = "両船の責任割合は、建昌六・五、有漁丸三・五である。";
    expect(bestFaultRatio(text)).toBe("65:35");
    const hit = extractFaultRatios(text)[0]!;
    expect(hit.side_a_label).toBe("建昌");
    expect(hit.side_b_label).toBe("有漁丸");
    expect(hit.side_a_role).toBe("vessel");
    expect(hit.side_b_role).toBe("vessel");

    const text2 = "その責任割合はしんえい丸八、金宝丸二である。";
    expect(bestFaultRatio(text2)).toBe("80:20");
    const hit2 = extractFaultRatios(text2)[0]!;
    expect(hit2.side_a_label).toBe("しんえい丸");
    expect(hit2.side_b_label).toBe("金宝丸");
  });

  it("percent and wari", () => {
    expect(
      bestFaultRatio("建昌の責任割合は前記のとおり六五パーセントである。"),
    ).toBe("65:35");
    expect(bestFaultRatio("責任割合を七五％と認定した。")).toBe("75:25");
    expect(bestFaultRatio("原告の過失割合を三割と認めるのが相当である。")).toBe(
      "30:70",
    );
    const wari = extractFromJudgment(
      "原告の過失割合を三割と認めるのが相当である。",
    );
    expect(wari.side_a_label).toBe("原告");
    expect(wari.side_a_role).toBe("plaintiff");
    expect(wari.side_b_role).toBe("counterparty");
  });

  it("shuin_ichin roles", () => {
    const hits = extractFaultRatios(
      "本件衝突の主因はAにあり、Bの過失も一因をなす。",
    );
    expect(hits[0]!.ratio).toBe("70:30");
    expect(hits[0]!.side_a_role).toBe("primary_cause");
    expect(hits[0]!.side_b_role).toBe("secondary_cause");
    const text =
      "本件衝突は、見張り不十分によって発生したが、" +
      "協力動作をとらなかったことも一因をなすものである。";
    expect(bestFaultRatio(text)).toBe("70:30");
  });

  it("monetary labeled extraction", () => {
    const text =
      "請求額は 20,000,000円、認容額は 12,345,678円、否認は 3,000,000円 とした。";
    const out = extractFromJudgment(text);
    expect(out.claimed_repair_jpy).toBe(20_000_000);
    expect(out.awarded_damages_jpy).toBe(12_345_678);
    expect(out.disallowed_jpy).toBe(3_000_000);
  });
});

describe("offline suite DoD", () => {
  it("meets accuracy / within_10pt thresholds with no failures", () => {
    const report = evaluateOfflineSnippets(snippets);
    expect(Number(report.total)).toBeGreaterThanOrEqual(8);
    expect(Number(report.accuracy)).toBeGreaterThanOrEqual(0.9);
    expect(Number(report.fault_ratio_within_10pt_rate)).toBeGreaterThanOrEqual(
      0.8,
    );
    const failed = (report.results as Array<{ ok: boolean }>).filter(
      (r) => !r.ok,
    );
    expect(failed).toEqual([]);
  });
});

describe("parseFaultRatioParts", () => {
  it.each([
    ["70:30", [70, 30] as [number, number]],
    ["65:35", [65, 35] as [number, number]],
    ["８０：２０", [80, 20] as [number, number]],
    ["50:50", [50, 50] as [number, number]],
    ["bad", null],
    ["70:40", null],
    [null, null],
  ] as const)("%j → %j", (ratio, expected) => {
    expect(parseFaultRatioParts(ratio as string | null)).toEqual(expected);
  });
});

describe("faultRatioWithinPts", () => {
  it.each([
    ["70:30", "70:30", true],
    ["70:30", "65:35", true],
    ["70:30", "60:40", true],
    ["70:30", "55:45", false],
    ["80:20", "70:30", true],
    ["80:20", "65:35", false],
    [null, "70:30", false],
    ["70:30", null, false],
  ] as const)("%j vs %j → %s", (extracted, gold, ok) => {
    expect(
      faultRatioWithinPts(extracted as string | null, gold as string | null, {
        max_pts: 10,
      }),
    ).toBe(ok);
  });
});

describe("extractionMatchesGold within_10pt", () => {
  it("reports exact and soft tolerance correctly", () => {
    const text = "過失割合は 70:30 である。";
    const extracted = extractFromJudgment(text);
    const exact = extractionMatchesGold(extracted, { fault_ratio: "70:30" });
    expect(exact.fault_ratio_ok).toBe(true);
    expect(exact.fault_ratio_within_10pt).toBe(true);
    expect(exact.fault_ratio_exact).toBe(true);

    const soft = extractionMatchesGold(
      extracted,
      { fault_ratio: "65:35" },
      { fault_ratio_tolerance_pts: 10 },
    );
    expect(soft.fault_ratio_ok).toBe(true);
    expect(soft.fault_ratio_exact).toBe(false);
    expect(soft.fault_ratio_within_10pt).toBe(true);

    const strict = extractionMatchesGold(extracted, { fault_ratio: "65:35" });
    expect(strict.fault_ratio_ok).toBe(false);
    expect(strict.fault_ratio_within_10pt).toBe(true);
  });

  it("negligence holding excerpt contains anchor", () => {
    const text =
      "事実認定の詳細は別紙のとおりである。" +
      "過失相殺について検討するに、双方に見張り不十分があり、" +
      "過失割合は六五対三五と認めるのが相当である。" +
      "よって主文のとおり判決する。";
    const excerpt = extractNegligenceHolding(text);
    expect(excerpt).not.toBeNull();
    expect(excerpt!.includes("過失相殺") || excerpt!.includes("過失割合")).toBe(
      true,
    );
    expect(bestFaultRatio(excerpt || "")).toBe("65:35");
  });
});
