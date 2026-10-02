/**
 * Issue #90 — Multilingual document → language-agnostic schema normalization DoD.
 * Same geometry / deficiency / repair codes → identical Stage B scores across JA/EN.
 */
import { describe, expect, it } from "vitest";
import { apportionRuleD } from "../src/engines/ruleD5";
import {
  criticalSystemId,
  normalizeActionCode,
  parseDeficiencyItem,
  scoreSeaworthiness,
} from "../src/engines/psc";
import {
  detectDocumentLanguage,
  normalizeDockingContext,
  normalizeRepairPhrase,
  normalizeSituationLabel,
  type NormalizeBackend,
} from "../src/pipeline/normalizeLabels";
import { lexiconVersion } from "../src/pipeline/lexicon";
import { repairItemsToRuleDLines } from "../src/pdf/repairLines";
import ruleD5Pairs from "./fixtures/multilingual/rule_d5_ja_en_pairs.json";
import pscPairs from "./fixtures/multilingual/psc_ja_en_pairs.json";
import situationPairs from "./fixtures/multilingual/colregs_situation_labels.json";

describe("Issue #90 lexicon + language detect", () => {
  it("loads shipyard jargon lexicon", () => {
    expect(lexiconVersion()).toBe(1);
    expect(normalizeRepairPhrase("外板ケレン")?.trade_code).toBe("HULL-01");
    expect(normalizeRepairPhrase("scaling and painting")?.trade_code).toBe("HULL-01");
  });

  it("detects JA vs EN without machine translation", () => {
    expect(detectDocumentLanguage("外板ケレン及び塗装工事　850,000円")).toBe("ja");
    expect(
      detectDocumentLanguage("Shell plating scaling and painting work — JPY 850,000"),
    ).toBe("en");
    expect(
      detectDocumentLanguage("外板ケレン scaling and painting 850,000円"),
    ).toBe("mixed");
  });

  it("normalizes docking_context phrases to schema enums", () => {
    expect(normalizeDockingContext("事故入渠のため入渠")).toBe("casualty_immediate");
    expect(normalizeDockingContext("routine docking with owner work")).toBe(
      "deferred_to_routine",
    );
  });

  it("slm backend stub falls back to lexicon (#77 reserved)", () => {
    const backend: NormalizeBackend = "slm";
    expect(normalizeRepairPhrase("piston draw", { backend })?.trade_code).toBe("ENG-02");
  });
});

describe("Issue #90 DoD — Rule D5 JA/EN identical Stage B", () => {
  it("pair lines map to the same trade_code", () => {
    for (const pair of ruleD5Pairs.pairs) {
      const ja = normalizeRepairPhrase(pair.ja.description);
      const en = normalizeRepairPhrase(pair.en.description);
      expect(ja?.trade_code, pair.id).toBe(pair.expect_trade_code);
      expect(en?.trade_code, pair.id).toBe(pair.expect_trade_code);
      expect(ja?.trade_code).toBe(en?.trade_code);
    }
  });

  it("JA and EN repair packages yield identical Rule D5 totals", () => {
    const opts = {
      dailyDockRate: ruleD5Pairs.daily_dock_rate,
      dockDays: ruleD5Pairs.dock_days,
      includeStatutory: ruleD5Pairs.include_statutory,
    };
    const jaItems = ruleD5Pairs.pairs.map((p) => ({
      description: p.ja.description,
      estimated_cost: p.ja.estimated_cost,
    }));
    const enItems = ruleD5Pairs.pairs.map((p) => ({
      description: p.en.description,
      estimated_cost: p.en.estimated_cost,
    }));
    const jaLines = repairItemsToRuleDLines(jaItems, opts);
    const enLines = repairItemsToRuleDLines(enItems, opts);

    const jaCodes = jaLines.map((l) => l.trade_code).sort();
    const enCodes = enLines.map((l) => l.trade_code).sort();
    expect(jaCodes).toEqual(enCodes);

    const ctx = ruleD5Pairs.docking_context as "casualty_immediate";
    const jaResult = apportionRuleD(jaLines, ctx);
    const enResult = apportionRuleD(enLines, ctx);
    expect(jaResult.insurer_total).toBe(enResult.insurer_total);
    expect(jaResult.owner_total).toBe(enResult.owner_total);
    expect(jaResult.apportionment_rule).toBe(enResult.apportionment_rule);
    expect(jaResult.common_dues_total).toBe(enResult.common_dues_total);
  });
});

describe("Issue #90 DoD — PSC JA/EN identical Stage B", () => {
  it("critical_system and Defect Score match across JA/EN descriptions", () => {
    for (const c of pscPairs.cases) {
      if (c.expect_critical_system) {
        expect(criticalSystemId(c.code, c.ja_description)).toBe(c.expect_critical_system);
        expect(criticalSystemId(c.code, c.en_description)).toBe(c.expect_critical_system);
      }
      if (c.expect_action_code) {
        expect(normalizeActionCode(c.ja_action)).toBe(c.expect_action_code);
        expect(normalizeActionCode(c.en_action)).toBe(c.expect_action_code);
      }

      const action = c.action_code ?? c.expect_action_code ?? "17";
      const jaItem = parseDeficiencyItem({
        code: c.code,
        action_code: action,
        description: c.ja_description,
      });
      const enItem = parseDeficiencyItem({
        code: c.code,
        action_code: action,
        description: c.en_description,
      });
      expect(jaItem).toBeTruthy();
      expect(enItem).toBeTruthy();
      expect(jaItem!.critical_system).toBe(enItem!.critical_system);

      const jaReport = scoreSeaworthiness([jaItem!], { mouId: "tokyo" });
      const enReport = scoreSeaworthiness([enItem!], { mouId: "tokyo" });
      expect(jaReport.defect_score).toBe(enReport.defect_score);
      expect(jaReport.risk_band).toBe(enReport.risk_band);
      expect(jaReport.detention_present).toBe(enReport.detention_present);
    }
  });
});

describe("Issue #90 DoD — COLREGS situation labels", () => {
  it("JA and EN labels normalize to the same situation enum", () => {
    for (const pair of situationPairs.pairs) {
      expect(normalizeSituationLabel(pair.ja)).toBe(pair.expect);
      expect(normalizeSituationLabel(pair.en)).toBe(pair.expect);
      expect(normalizeSituationLabel(pair.ja)).toBe(normalizeSituationLabel(pair.en));
    }
  });
});
