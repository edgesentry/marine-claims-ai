import { describe, expect, it } from "vitest";
import library from "./fixtures/negative_pattern_library.json";
import {
  ACTION_APPORTIONED,
  ACTION_APPROVED,
  ACTION_DISALLOWED,
  actionForSimilarity,
  cosineSimilarity,
  createNplScorer,
  formatCitation,
  normalizeCategory,
  patternPassesGates,
  scoreLineItems,
  type NplLibrary,
} from "../src/appraisal/negativePatterns";

describe("negativePatterns", () => {
  it("cosine similarity identical and orthogonal", () => {
    expect(cosineSimilarity([1, 0], [1, 0])).toBeCloseTo(1);
    expect(cosineSimilarity([1, 0], [0, 1])).toBeCloseTo(0);
    expect(cosineSimilarity([1, 0], [-1, 0])).toBeCloseTo(0);
    expect(cosineSimilarity([], [])).toBe(0);
    expect(cosineSimilarity([1], [1, 0])).toBe(0);
  });

  it("action thresholds", () => {
    expect(actionForSimilarity(0.8)).toBe(ACTION_DISALLOWED);
    expect(actionForSimilarity(0.79)).toBe(ACTION_APPORTIONED);
    expect(actionForSimilarity(0.5)).toBe(ACTION_APPORTIONED);
    expect(actionForSimilarity(0.49)).toBe(ACTION_APPROVED);
  });

  it("format citation", () => {
    expect(formatCitation(0.894, "ENG-01")).toBe(
      "Matched with 89.4% similarity to public standard periodic maintenance item ENG-01",
    );
  });

  it("loads curated library shape", () => {
    const lib = library as NplLibrary;
    expect(lib.thresholds?.disallow_min).toBe(0.8);
    const codes = new Set(lib.patterns.map((p) => p.trade_code));
    expect(codes.has("ENG-01")).toBe(true);
    expect(codes.has("VALVE-01")).toBe(true);
    expect(codes.has("HULL-01")).toBe(false);
  });

  it("scores with stub embed", () => {
    const lib: NplLibrary = {
      thresholds: { disallow_min: 0.8, apportion_min: 0.5 },
      patterns: [
        {
          id: "npl-eng-01",
          trade_code: "ENG-01",
          text: "ピストン抜出",
          category: "機関部",
          source: "test",
        },
      ],
    };
    const fakeEmbed = (texts: string[]) =>
      texts.map((t) => {
        if (t.includes("ピストン")) return [1, 0, 0];
        if (t.includes("外板塗装")) return [0, 1, 0];
        return [0, 0, 1];
      });
    const scorer = createNplScorer(lib, fakeEmbed);
    const items = scoreLineItems(
      [
        { id: 1, description: "主機関ピストン抜出開放点検" },
        { id: 2, description: "外板塗装復旧" },
      ],
      scorer,
    );
    expect(items[0]!.recommended_action).toBe(ACTION_DISALLOWED);
    expect(items[0]!.matched_trade_code).toBe("ENG-01");
    expect(items[0]!.red_flag_similarity).toBeCloseTo(1);
    expect(items[1]!.recommended_action).toBe(ACTION_APPROVED);
  });

  it("anchor and category gates", () => {
    const pattern = {
      id: "x",
      trade_code: "ENG-01",
      text: "ピストン抜出",
      category: "機関部",
      anchor_tokens: ["ピストン"],
    };
    expect(patternPassesGates(pattern, "主機関ピストン抜出", "機関部")).toBe(true);
    expect(patternPassesGates(pattern, "外板塗装", "機関部")).toBe(false);
    expect(patternPassesGates(pattern, "主機関ピストン抜出", "甲板部")).toBe(false);
    expect(normalizeCategory("【機関部】")).toBe("機関部");
  });

  it("hashEmbed scorer matches library piston pattern with high similarity", () => {
    const scorer = createNplScorer(library as NplLibrary);
    const score = scorer.score_description(
      "主機関シリンダヘッド及びピストン抜出開放点検",
      "機関部",
    );
    expect(score.matched_trade_code).toBe("ENG-01");
    expect(score.red_flag_similarity).toBeGreaterThanOrEqual(0.8);
    expect(score.recommended_action).toBe(ACTION_DISALLOWED);
  });
});
