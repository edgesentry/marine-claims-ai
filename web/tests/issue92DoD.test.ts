/**
 * Issue #92 — PSC Stage A MOU PDF/HTML/text → NormalizedDeficiency + Exact Span.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { runPscFromDocument } from "../src/core";
import {
  extractPscDeficienciesFromText,
  htmlToPlainText,
  looksLikeHtml,
} from "../src/ingest/pscDeficiencyExtractor";
import { DEFICIENCY_CATEGORY_MAP, scoreSeaworthiness } from "../src/engines/psc";
import { assertGroundingForStageB } from "../src/pipeline/groundingGate";
import { pscMarkdown } from "../src/ui/export";

const __dirname = dirname(fileURLToPath(import.meta.url));

function loadFixture(name: string): string {
  return readFileSync(resolve(__dirname, "fixtures/psc", name), "utf8");
}

describe("pscDeficiencyExtractor", () => {
  it("strips HTML tables into line-oriented text", () => {
    const html = loadFixture("tokyo_mou_table_sample.txt");
    expect(looksLikeHtml(html)).toBe(true);
    const plain = htmlToPlainText(html);
    expect(plain).toMatch(/07106/);
    expect(plain).toMatch(/04102/);
    expect(plain).toMatch(/Tokyo MOU/i);
  });

  it("extracts Tokyo HTML sample with Code 30 and 071 ≠ navigation", () => {
    const html = loadFixture("tokyo_mou_table_sample.txt");
    const extracted = extractPscDeficienciesFromText(html, {
      filename: "tokyo_mou_table_sample.txt",
    });
    expect(extracted.deficiencies.length).toBeGreaterThanOrEqual(2);
    expect(extracted.mouId).toBe("tokyo");

    const fire = extracted.deficiencies.find((d) => d.code.startsWith("071"));
    expect(fire).toBeTruthy();
    expect(fire!.category_label).toBe("Fire safety");
    expect(DEFICIENCY_CATEGORY_MAP["071"]!.label).toBe("Fire safety");
    expect(fire!.category_label).not.toMatch(/navigation/i);

    const detention = extracted.deficiencies.find((d) => d.action_code === "30");
    expect(detention).toBeTruthy();
    expect(detention!.code).toBe("04102");

    expect(extracted.prior.length).toBeGreaterThanOrEqual(1);
    expect(
      extracted.grounding.every(
        (g) => typeof g.field === "string" && g.field.startsWith("deficiencies."),
      ),
    ).toBe(true);
    expect(extracted.grounding[0]!.source_quote).toContain(
      extracted.deficiencies[0]!.code,
    );
  });

  it("extracts Paris plain-text portal layout", () => {
    const text = loadFixture("paris_mou_text_sample.txt");
    const extracted = extractPscDeficienciesFromText(text);
    expect(extracted.mouId).toBe("paris");
    const codes = extracted.deficiencies.map((d) => d.code);
    expect(codes).toContain("04102");
    expect(codes).toContain("10104");
    const nav = extracted.deficiencies.find((d) => d.code === "10104");
    expect(nav!.category_label).toBe("Safety of Navigation");
  });
});

describe("Issue #92 DoD — MOU document → score without hand JSON", () => {
  it("DoD: public-style HTML fixture scores offline under require_span", () => {
    const html = loadFixture("tokyo_mou_table_sample.txt");
    const run = runPscFromDocument(html, {
      lookbackMonths: 24,
      confidence: 0.75,
      filename: "tokyo_mou_table_sample.txt",
    });
    expect(run.status).toBe("scored");
    if (run.status !== "scored") return;

    expect(run.report.detention_present).toBe(true);
    expect(run.report.risk_band).toBe("critical");
    expect(run.report.defect_score).toBeGreaterThanOrEqual(1.0);

    const fire = run.report.deficiencies.find((d) => d.code.startsWith("071"));
    expect(fire?.category_label).toBe("Fire safety");

    expect(
      run.extraction.grounding.some((g) => g.field === "deficiencies.0.code"),
    ).toBe(true);

    // Exact Span gate accepts document path
    assertGroundingForStageB(run.extraction, {
      mode: "require_span",
      sourceText: htmlToPlainText(html),
    });
  });

  it("DoD: Code 30 / 071≠navigation regressions still pass via document path", () => {
    const text = loadFixture("paris_mou_text_sample.txt");
    const extracted = extractPscDeficienciesFromText(text);
    const report = scoreSeaworthiness(extracted.deficiencies, {
      mouId: extracted.mouId,
    });
    expect(report.detention_present).toBe(true);
    expect(report.risk_band).toBe("critical");
    expect(DEFICIENCY_CATEGORY_MAP["071"]!.label).toBe("Fire safety");
    expect(DEFICIENCY_CATEGORY_MAP["101"]!.label).toBe("Safety of Navigation");
  });

  it("DoD: memo export keeps warranty disclaimer", () => {
    const html = loadFixture("tokyo_mou_table_sample.txt");
    const run = runPscFromDocument(html, { confidence: 0.8 });
    expect(run.status).toBe("scored");
    if (run.status !== "scored") return;
    const md = pscMarkdown(
      {
        title: run.label,
        mou_id: run.report.mou_id,
        lookback_months: 24,
        defect_score: run.report.defect_score,
        risk_band: run.report.risk_band,
        detention_present: run.report.detention_present,
        repeat_critical_flags: run.report.repeat_critical_flags,
        notes: run.report.notes,
        convention_citations: run.report.convention_citations,
        deficiencies: run.report.deficiencies.map((d) => ({
          code: d.code,
          action_code: d.action_code,
          description: d.description,
          category_label: d.category_label,
          convention: d.convention,
          critical_system: d.critical_system,
          is_repeat_critical: d.is_repeat_critical,
          contribution: d.contribution,
        })),
      },
      "en",
    );
    expect(md.toLowerCase()).toMatch(/not a legal warranty/);
  });
});
