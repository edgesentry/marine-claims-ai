/**
 * Issue #91 Definition of Done — CI-facing assertions.
 *
 * DoD:
 * 1. At least one public fixture path scores COLREGS without manual slider overrides
 * 2. Role inversion gate remains 0 on extracted telemetry
 * 3. Extracted geometry carries Exact Span grounding (#88)
 * 4. Narrative with no numeric geometry abstains (#89)
 *
 * Included in `npm test` and `npm run gate-a`.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { runColregs } from "../src/core";
import {
  extractColregsTelemetry,
  isCompleteTelemetry,
  telemetryGrounding,
  telemetryToGeometry,
} from "../src/ingest/colregsTelemetryExtractor";
import { buildColregsExtraction } from "../src/schemas";
import { assertGroundingForStageB } from "../src/pipeline/groundingGate";

interface JmatCase {
  case_id: string;
  facts_text: string;
  ruling_text?: string;
  expected_situation: string;
  expected_role_a: string | null;
  expected_role_b: string | null;
}

function loadJmatCases(): JmatCase[] {
  const path = resolve(
    import.meta.dirname,
    "../../config/jmat_collision_eval.json",
  );
  const raw = JSON.parse(readFileSync(path, "utf8")) as { cases: JmatCase[] };
  return raw.cases;
}

describe("Issue #91 DoD — narrative telemetry → COLREGS", () => {
  it("DoD: public JMAT fixture scores without slider overrides", () => {
    const cases = loadJmatCases();
    const kii = cases.find((c) => c.case_id === "crossing_kii_starboard_giveway");
    expect(kii).toBeTruthy();

    const run = runColregs({
      narrativeText: kii!.facts_text,
      factsExcerpt: kii!.facts_text,
      rulingExcerpt: kii!.ruling_text,
      groundingMode: "paste_bypass",
      confidenceMode: "bypass",
      confidence: 0.9,
    });

    expect(run.status).toBe("scored");
    if (run.status !== "scored") return;
    expect(run.geometry.heading_a_deg).toBe(30);
    expect(run.geometry.heading_b_deg).toBe(300);
    expect(run.geometry.true_bearing_a_to_b_deg).toBe(70);
    expect(run.verdict.situation).toBe(kii!.expected_situation);
    expect(run.verdict.role_a).toBe(kii!.expected_role_a);
    expect(run.verdict.role_b).toBe(kii!.expected_role_b);
    expect(
      run.extraction.grounding.some((g) => g.field === "geometry.heading_a_deg"),
    ).toBe(true);
  });

  it("DoD: role inversion remains 0 on extractable public narratives", () => {
    const cases = loadJmatCases().filter(
      (c) =>
        isCompleteTelemetry(extractColregsTelemetry(c.facts_text)) &&
        c.expected_role_a != null,
    );
    expect(cases.length).toBeGreaterThan(0);

    let inversions = 0;
    for (const c of cases) {
      const run = runColregs({
        narrativeText: c.facts_text,
        factsExcerpt: c.facts_text,
        groundingMode: "paste_bypass",
        confidenceMode: "bypass",
        confidence: 0.9,
      });
      if (run.status !== "scored") {
        inversions += 1;
        continue;
      }
      if (
        run.verdict.role_a !== c.expected_role_a ||
        run.verdict.role_b !== c.expected_role_b
      ) {
        // Count only true role swaps (A/B inverted), not situation mismatches alone.
        if (
          run.verdict.role_a === c.expected_role_b &&
          run.verdict.role_b === c.expected_role_a
        ) {
          inversions += 1;
        }
      }
    }
    expect(inversions).toBe(0);
  });

  it("DoD: extracted telemetry requires Exact Span grounding under require_span", () => {
    const text =
      "本船Ａは針路０３０度、速力約１２ノットで進行中、右舷前約４０度に相手船Ｂを視認した。相手船Ｂは針路３００度、速力約１０ノットで航行していた。";
    const telemetry = extractColregsTelemetry(text);
    const geometry = telemetryToGeometry(telemetry)!;
    const grounded = buildColregsExtraction({
      geometry,
      factsExcerpt: text.slice(0, 80),
      grounding: [
        { field: "facts_excerpt", source_quote: text.slice(0, 80) },
        ...telemetryGrounding(telemetry),
      ],
      groundingMode: "require_span",
      sourceText: text,
      confidence: 0.9,
      confidenceMode: "bypass",
    });
    expect(() =>
      assertGroundingForStageB(grounded, { mode: "require_span" }),
    ).not.toThrow();

    const ungrounded = buildColregsExtraction({
      geometry,
      factsExcerpt: text.slice(0, 80),
      grounding: [
        { field: "facts_excerpt", source_quote: text.slice(0, 80) },
        {
          field: "geometry.heading_a_deg",
          source_quote: "fabricated heading quote not in source",
        },
      ],
      groundingMode: "paste_bypass",
      confidence: 0.9,
      confidenceMode: "bypass",
    });
    expect(() =>
      assertGroundingForStageB(ungrounded, {
        mode: "require_span",
        sourceText: text,
      }),
    ).toThrow();
  });

  it("DoD: narrative with no numeric geometry abstains", () => {
    const source = "両船は横切の関係にあった。詳細な針路の記載はない。";
    const run = runColregs({
      narrativeText: source,
      factsExcerpt: source,
      sourceText: source,
      groundingMode: "require_span",
      confidenceMode: "enforce",
      confidence: 0.85,
    });
    expect(run.status).toBe("abstain");
    if (run.status !== "abstain") return;
    expect(run.extraction.abstain?.code).toBe("HUMAN_REVIEW_REQUIRED");
    expect(run.extraction.abstain?.reason).toContain("geometry_missing");
    expect("verdict" in run).toBe(false);
  });
});
