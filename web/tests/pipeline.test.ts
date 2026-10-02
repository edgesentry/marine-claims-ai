import { describe, expect, it } from "vitest";
import {
  evaluateClaimsDynamically,
  noOpNplScorer,
  type SpecLineItem,
} from "../src/appraisal/pipeline";
import {
  checkRepairBoundary,
  countCriticalFalseAccepts,
  DEFAULT_CRITICAL_SUBSTRINGS,
  isBowMachineryFalseAccept,
} from "../src/appraisal/boundary";

const BOW = {
  vessel_name: "テスト船",
  incident_type: "衝突",
  incident_date: "2024-01-01",
  incident_location: "試験海域",
  damaged_components: ["球状船首", "外板"],
  damage_evidence: ["球状船首擦過"],
  source_pdf: "fixture.pdf",
};

function item(
  id: number,
  desc: string,
  cost: number,
  category = "【甲板部】",
): SpecLineItem {
  return { id, category, num: String(id), description: desc, estimated_cost: cost };
}

describe("pipeline Rule D5", () => {
  it("50/50 reconciliation zero JPY with statutory", () => {
    const { analyzed, summary } = evaluateClaimsDynamically(
      [
        item(1, "船体入出渠及び滞渠", 4_300_000),
        item(2, "船体外板・船側外板高圧清水洗浄", 450_000),
        item(3, "JG定期検査立会", 550_000),
      ],
      BOW,
      noOpNplScorer,
      { dockingContext: "casualty_immediate", assumeStatutoryOwnerWork: true },
    );
    const dock = analyzed.find((x) => x.description.includes("入出渠"))!;
    expect(dock.apportionment_rule).toBe("RULE_D5_50_50");
    expect(dock.status).toBe("APPORTIONED (50%)");
    expect(dock.insurer_share! + dock.owner_share!).toBe(dock.estimated_cost);
    expect(dock.approved_amount).toBe(dock.insurer_share);
    expect(summary.rule_d5_reconciliation_error_jpy).toBe(0);
  });

  it("100% UW when no statutory", () => {
    const { analyzed, summary } = evaluateClaimsDynamically(
      [
        item(1, "船体入出渠及び滞渠", 4_300_000),
        item(2, "船体外板・船側外板高圧清水洗浄", 450_000),
      ],
      BOW,
      noOpNplScorer,
      { dockingContext: "casualty_immediate", assumeStatutoryOwnerWork: false },
    );
    const dock = analyzed.find((x) => x.description.includes("入出渠"))!;
    expect(dock.apportionment_rule).toBe("RULE_D5_100_UNDERWRITER");
    expect(dock.status).toBe("COVERED");
    expect(dock.insurer_share).toBe(4_300_000);
    expect(dock.owner_share).toBe(0);
    expect(summary.rule_d5_reconciliation_error_jpy).toBe(0);
  });
});

describe("pipeline boundary / Critical FA", () => {
  it("blocks bow → machinery", () => {
    const result = checkRepairBoundary(
      ["球状船首", "外板"],
      "主機関ピストン抜出開放点検",
      "【機関部】",
    );
    expect(result.repair_zone).toBe("machinery");
    expect(result.valid).toBe(false);
  });

  it("allows outer hull on bow casualty", () => {
    const result = checkRepairBoundary(
      ["球状船首", "外板"],
      "船体外板・船側外板高圧清水洗浄",
      "【甲板部】",
    );
    expect(result.repair_zone).toBe("hull_mid");
    expect(result.valid).toBe(true);
  });

  it("detects bow machinery false accept", () => {
    expect(
      isBowMachineryFalseAccept({
        damaged_components: ["球状船首"],
        description: "カロリーファイヤー開放掃除",
        predicted_status: "COVERED",
        gold_status: "EXCLUDED",
      }),
    ).toBe(true);
    expect(
      isBowMachineryFalseAccept({
        damaged_components: ["球状船首"],
        description: "カロリーファイヤー開放掃除",
        predicted_status: "EXCLUDED (便乗修理)",
        gold_status: "EXCLUDED",
      }),
    ).toBe(false);
  });

  it("Critical FA = 0 for bow collision pipeline", () => {
    const items = [
      item(1, "船体入出渠及び滞渠", 4_300_000, "【甲板部】"),
      item(2, "船体外板・船側外板高圧清水洗浄", 450_000, "【甲板部】"),
      item(59, "減速機入出力側、クラッチ陸揚げ点検整備受検", 1_200_000, "【機関部】"),
      item(76, "プロペラ軸及び翼取り外し開放、研磨、掃除、各部点検", 1_200_000, "【機関部】"),
      item(81, "カロリーファイヤー（給湯設備）開放掃除洗浄復旧耐圧", 350_000, "【機関部】"),
      item(90, "主機関ピストン抜出開放点検", 4_800_000, "【機関部】"),
    ];
    const { analyzed } = evaluateClaimsDynamically(items, BOW, noOpNplScorer);
    const golded = analyzed.map((row) => ({
      ...row,
      gold_status: DEFAULT_CRITICAL_SUBSTRINGS.some((s) => row.description.includes(s))
        ? "EXCLUDED"
        : row.status,
    }));
    expect(countCriticalFalseAccepts(golded, BOW.damaged_components)).toBe(0);
    for (const row of analyzed) {
      if (DEFAULT_CRITICAL_SUBSTRINGS.some((s) => row.description.includes(s))) {
        expect(row.status).toContain("EXCLUDED");
      }
    }
  });
});
