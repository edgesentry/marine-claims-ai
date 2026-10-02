/**
 * Issue #86 Definition of Done — document-type auto-router.
 *
 * DoD:
 * 1. 0 misroute on labeled public anonymized text fixtures
 * 2. Ambiguous / empty text → unknown
 * 3. unknown / tab mismatch never allows Stage B without override
 * 4. Override to an allowed type unlocks the route
 *
 * Included in `npm test`; also listed in `npm run gate-a`.
 */
import { describe, expect, it } from "vitest";
import {
  classifyDocument,
  resolveDocumentRoute,
  shouldAbstainFromStageB,
  TAB_ALLOWED_TYPES,
  type DocumentType,
  type KnownDocumentType,
} from "../src/pipeline/documentRouter";
/** Public anonymized snippets only (no binary PDFs). */
export const ROUTER_FIXTURES: Array<{
  id: string;
  type: KnownDocumentType;
  text: string;
  filename?: string;
}> = [
  {
    id: "repair_spec_ja",
    type: "repair_spec",
    filename: "sample_drydock_repair_specification.pdf",
    text: `
修繕仕様書（ドライドック）
【甲板部】
1. 外板ケレン及び塗装工事　数量 1 式　単価 850,000 円　金額 850,000 円
2. 船底清掃　estimated cost ¥420,000
【機関部】
3. ピストン整備　工事番号 ENG-01　摘要 オーバーホール　1,200,000 円
入渠・滞渠料（共通入渠費）　日額 860,000 円 × 5 日
Repair specification / drydock tender for concurrent owner's work.
`,
  },
  {
    id: "civil_judgment_ja",
    type: "civil_judgment",
    filename: "civil_judgment_excerpt.txt",
    text: `
○○地方裁判所 民事第○部
判決
主文
1 被告は原告に対し金一千万円を支払え。
事実及び理由
本件は船舶衝突に基づく損害賠償請求である。
過失割合は原告船 40％、被告船 60％と認める。
判示のとおり原告の請求を一部認容する。
`,
  },
  {
    id: "jmat_ruling_ja",
    type: "jmat_ruling",
    filename: "jmat_adjudication.txt",
    text: `
海難審判所 裁決
受審人 ○○（海技士）
指定海難関係人 △△
本件海難について、裁決書の趣旨により次のとおり裁決する。
Japan Marine Accident Tribunal (JMAT) adjudication abstract.
`,
  },
  {
    id: "jtsb_report_ja",
    type: "jtsb_report",
    filename: "jtsb_cargo_collision_report.pdf",
    text: `
運輸安全委員会 船舶事故調査報告書
Japan Transport Safety Board (JTSB) Marine Accident Investigation Report
＜原因＞
本事故は、両船が見張り不十分のまま接近したことによる。
再発防止に係る安全勧告を発する。
`,
  },
  {
    id: "psc_inspection_en",
    type: "psc_inspection",
    filename: "psc_tokyo_mou_fixture.json",
    text: `
Tokyo MOU Port State Control inspection record
deficiency_code,action_taken,nature
07105,17,Fire pumps — deficiency requiring detention
15150,16,ISM Code related deficiency
SOLAS / MARPOL / ISM deficiencies listed above. Code 30 = detention.
Paris MOU style action codes 15/16/17.
`,
  },
];

describe("Issue #86 DoD — document-type auto-router", () => {
  it("DoD: 0 misroute on labeled public fixtures", () => {
    const misroutes: string[] = [];
    for (const fx of ROUTER_FIXTURES) {
      const result = classifyDocument(fx.text, { filename: fx.filename });
      if (result.type !== fx.type) {
        misroutes.push(`${fx.id}: got ${result.type} expected ${fx.type}`);
      }
    }
    expect(misroutes).toEqual([]);
  });

  it("DoD: empty / garbage → unknown (never silent Stage B type)", () => {
    expect(classifyDocument("").type).toBe("unknown");
    expect(classifyDocument("lorem ipsum dolor sit amet").type).toBe("unknown");
  });

  it("DoD: ambiguous mixed signals → unknown", () => {
    const mixed = `
運輸安全委員会 船舶事故調査
修繕仕様書 ドライドック 外板ケレン 850,000 円
海難審判所 裁決 受審人
Tokyo MOU deficiency 07105 detention
地方裁判所 判決 主文 過失割合
`;
    const result = classifyDocument(mixed);
    expect(result.type).toBe("unknown");
    expect(result.signals.some((s) => s.includes("ambiguous") || s.includes("low_"))).toBe(
      true,
    );
  });

  it("DoD: unknown never allows Stage B on any tab without override", () => {
    const unknown = classifyDocument(" unrelated memo ");
    expect(unknown.type).toBe("unknown");
    for (const tab of ["uc2", "uc3", "psc"] as const) {
      const decision = resolveDocumentRoute(tab, unknown, null);
      expect(decision.allowed).toBe(false);
      expect(decision.reason).toBe("unknown");
      expect(shouldAbstainFromStageB(decision)).toBe(true);
    }
  });

  it("DoD: tab mismatch abstains until override to an allowed type", () => {
    const jtsb = classifyDocument(ROUTER_FIXTURES.find((f) => f.id === "jtsb_report_ja")!.text, {
      filename: "jtsb_cargo_collision_report.pdf",
    });
    expect(jtsb.type).toBe("jtsb_report");

    const onRuleD5 = resolveDocumentRoute("uc2", jtsb, null);
    expect(onRuleD5.allowed).toBe(false);
    expect(onRuleD5.reason).toBe("tab_mismatch");
    expect(shouldAbstainFromStageB(onRuleD5)).toBe(true);

    const overridden = resolveDocumentRoute("uc2", jtsb, "repair_spec");
    expect(overridden.allowed).toBe(true);
    expect(overridden.effective).toBe("repair_spec");
    expect(shouldAbstainFromStageB(overridden)).toBe(false);

    const onColregs = resolveDocumentRoute("uc3", jtsb, null);
    expect(onColregs.allowed).toBe(true);
    expect(onColregs.effective).toBe("jtsb_report");
  });

  it("DoD: each tab allow-list matches Issue #86 labels", () => {
    expect([...TAB_ALLOWED_TYPES.uc2]).toEqual(["repair_spec"]);
    expect(new Set(TAB_ALLOWED_TYPES.uc3)).toEqual(
      new Set<DocumentType>(["civil_judgment", "jmat_ruling", "jtsb_report"]),
    );
    expect([...TAB_ALLOWED_TYPES.psc]).toEqual(["psc_inspection"]);
  });

  it("DoD: matching detected type allows Stage B", () => {
    for (const fx of ROUTER_FIXTURES) {
      const classification = classifyDocument(fx.text, { filename: fx.filename });
      expect(classification.type).toBe(fx.type);
      const tab =
        fx.type === "repair_spec" ? "uc2" : fx.type === "psc_inspection" ? "psc" : "uc3";
      const decision = resolveDocumentRoute(tab, classification, null);
      expect(decision.allowed).toBe(true);
      expect(shouldAbstainFromStageB(decision)).toBe(false);
    }
  });
});
