/**
 * Stage A ExtractionResult schema contracts (Issue #87).
 */
import { describe, expect, it } from "vitest";
import {
  assertValidForStageB,
  buildColregsExtraction,
  buildPscExtraction,
  buildRuleD5Extraction,
  ExtractionValidationError,
  extractionJsonSchema,
  geometryFromExtraction,
  guidedDecodeSpec,
  ruleD5LinesFromExtraction,
  safeParseExtraction,
} from "../src/schemas";

const validRuleD5 = {
  schema_id: "rule_d5.v1" as const,
  confidence: 0.8,
  grounding: [{ field: "lines.1", source_quote: "入出渠費" }],
  payload: {
    docking_context: "deferred_to_routine" as const,
    lines: [
      { id: "1", cost: 1_000_000, trade_code: "DOCK-01", title: "入出渠" },
      { id: "2", cost: 500_000, trade_code: "HULL-01", work_party: "casualty" as const },
    ],
  },
};

const validColregs = {
  schema_id: "colregs.v1" as const,
  confidence: 0.6,
  grounding: [{ field: "facts_excerpt", source_quote: "両船は横切の関係" }],
  payload: {
    geometry: {
      heading_a_deg: 30,
      heading_b_deg: 300,
      true_bearing_a_to_b_deg: 70,
    },
    facts_excerpt: "両船は横切の関係にあった。",
    ruling_excerpt: "被告船に過失あり。",
    situation_candidates: [
      { situation: "crossing" as const, confidence: 0.9 },
      { situation: "head_on" as const, confidence: 0.1 },
    ],
    fault_ratio_hint: "70:30",
    document_kind: "judgment" as const,
  },
};

const validPsc = {
  schema_id: "psc.v1" as const,
  confidence: 0.9,
  grounding: [],
  payload: {
    deficiencies: [
      {
        code: "15150",
        action_code: "30",
        description: "ISM major non-conformity",
        inspection_date: "2024-06-01",
      },
    ],
    prior_deficiencies: [
      {
        code: "15150",
        action_code: "17",
        description: "Prior ISM finding",
        inspection_date: "2023-08-01",
      },
    ],
    lookback_months: 24,
    mou_id: "tokyo",
  },
};

describe("ExtractionResult valid envelopes", () => {
  it("accepts rule_d5.v1", () => {
    const parsed = assertValidForStageB(validRuleD5);
    expect(parsed.schema_id).toBe("rule_d5.v1");
    if (parsed.schema_id !== "rule_d5.v1") throw new Error("unreachable");
    expect(parsed.payload.lines).toHaveLength(2);
    const lines = ruleD5LinesFromExtraction(parsed);
    expect(lines[0]!.trade_code).toBe("DOCK-01");
  });

  it("accepts colregs.v1", () => {
    const parsed = assertValidForStageB(validColregs);
    expect(parsed.schema_id).toBe("colregs.v1");
    if (parsed.schema_id !== "colregs.v1") throw new Error("unreachable");
    const geom = geometryFromExtraction(parsed);
    expect(geom.heading_a_deg).toBe(30);
    expect(parsed.payload.situation_candidates?.[0]?.situation).toBe("crossing");
  });

  it("accepts psc.v1", () => {
    const parsed = assertValidForStageB(validPsc);
    expect(parsed.schema_id).toBe("psc.v1");
    if (parsed.schema_id !== "psc.v1") throw new Error("unreachable");
    expect(parsed.payload.deficiencies[0]!.code).toBe("15150");
    expect(parsed.payload.prior_deficiencies).toHaveLength(1);
  });

  it("accepts optional abstain slot without blocking Stage A validity", () => {
    const withAbstain = {
      ...validRuleD5,
      abstain: {
        code: "HUMAN_REVIEW_REQUIRED" as const,
        reason: "Low confidence on work_party labels",
      },
    };
    expect(assertValidForStageB(withAbstain).abstain?.code).toBe(
      "HUMAN_REVIEW_REQUIRED",
    );
  });
});

describe("ExtractionResult invalid envelopes", () => {
  it("rejects unknown schema_id", () => {
    const r = safeParseExtraction({
      ...validRuleD5,
      schema_id: "unknown.v1",
    });
    expect(r.success).toBe(false);
  });

  it("rejects confidence out of range", () => {
    const r = safeParseExtraction({ ...validRuleD5, confidence: 1.5 });
    expect(r.success).toBe(false);
  });

  it("rejects grounding without source_quote", () => {
    const r = safeParseExtraction({
      ...validRuleD5,
      grounding: [{ field: "lines.1" }],
    });
    expect(r.success).toBe(false);
  });

  it("rejects rule_d5 with empty lines", () => {
    const r = safeParseExtraction({
      ...validRuleD5,
      payload: { docking_context: "casualty_immediate", lines: [] },
    });
    expect(r.success).toBe(false);
  });

  it("rejects rule_d5 with invalid docking_context", () => {
    const r = safeParseExtraction({
      ...validRuleD5,
      payload: { ...validRuleD5.payload, docking_context: "routine" },
    });
    expect(r.success).toBe(false);
  });

  it("rejects colregs missing geometry headings", () => {
    const r = safeParseExtraction({
      ...validColregs,
      payload: {
        geometry: { true_bearing_a_to_b_deg: 10 },
        facts_excerpt: "x",
      },
    });
    expect(r.success).toBe(false);
  });

  it("rejects colregs with invalid situation candidate", () => {
    const r = safeParseExtraction({
      ...validColregs,
      payload: {
        ...validColregs.payload,
        situation_candidates: [{ situation: "tss", confidence: 0.5 }],
      },
    });
    expect(r.success).toBe(false);
  });

  it("rejects psc with empty deficiencies", () => {
    const r = safeParseExtraction({
      ...validPsc,
      payload: { deficiencies: [] },
    });
    expect(r.success).toBe(false);
  });

  it("rejects psc deficiency without code", () => {
    const r = safeParseExtraction({
      ...validPsc,
      payload: {
        deficiencies: [{ description: "missing code" }],
      },
    });
    expect(r.success).toBe(false);
  });

  it("assertValidForStageB throws ExtractionValidationError", () => {
    expect(() => assertValidForStageB({ schema_id: "rule_d5.v1" })).toThrow(
      ExtractionValidationError,
    );
  });
});

describe("Tier-1 adapters", () => {
  it("buildRuleD5Extraction gates and returns engine lines", () => {
    const ext = buildRuleD5Extraction({
      dockingContext: "casualty_immediate",
      lines: [{ id: "a", cost: 100, trade_code: "DOCK-01" }],
      groundingMode: "paste_bypass",
    });
    expect(ext.schema_id).toBe("rule_d5.v1");
    expect(ruleD5LinesFromExtraction(ext)[0]!.id).toBe("a");
  });

  it("buildColregsExtraction requires geometry", () => {
    const ext = buildColregsExtraction({
      geometry: {
        heading_a_deg: 0,
        heading_b_deg: 180,
        true_bearing_a_to_b_deg: 0,
      },
      factsExcerpt: "head-on approach",
      grounding: [{ field: "facts_excerpt", source_quote: "head-on approach" }],
      groundingMode: "paste_bypass",
    });
    expect(ext.payload.geometry.heading_b_deg).toBe(180);
  });

  it("buildPscExtraction maps NormalizedDeficiency fields", () => {
    const ext = buildPscExtraction({
      deficiencies: [
        {
          code: "07105",
          action_code: "17",
          description: "Fire pump",
          inspection_date: "2024-01-01",
          mou_id: "paris",
          prefix: "071",
          convention: "SOLAS",
          category_label: "Fire safety",
          citation: null,
          severity_weight: 0.5,
          category_weight: 0.8,
          critical_system: "fire",
          contribution: 0,
          is_repeat_critical: false,
        },
      ],
      groundingMode: "paste_bypass",
    });
    expect(ext.payload.deficiencies[0]!.code).toBe("07105");
    expect(ext.payload.deficiencies[0]).not.toHaveProperty("severity_weight");
  });

  it("buildRuleD5Extraction rejects empty lines", () => {
    expect(() =>
      buildRuleD5Extraction({
        dockingContext: "casualty_immediate",
        lines: [],
      }),
    ).toThrow(ExtractionValidationError);
  });
});

describe("guided JSON hooks", () => {
  it("extractionJsonSchema returns object schema per UC", () => {
    for (const id of ["rule_d5.v1", "colregs.v1", "psc.v1"] as const) {
      const schema = extractionJsonSchema(id);
      expect(schema).toHaveProperty("type", "object");
      expect(schema).toHaveProperty("properties");
    }
  });

  it("guidedDecodeSpec includes system_hint", () => {
    const spec = guidedDecodeSpec("psc.v1");
    expect(spec.schema_id).toBe("psc.v1");
    expect(spec.system_hint.toLowerCase()).toContain("psc");
    expect(spec.json_schema).toHaveProperty("properties");
  });
});
