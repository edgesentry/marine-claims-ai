/**
 * Stage A extraction accuracy harness (Issue #93).
 * Measures schema validity, field exact-match, Exact Span grounding, abstain
 * precision/recall, and Stage A→B agreement — independently of Gate A / Stage B
 * rule-agreement corpora.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runColregs } from "../core/colregs";
import { runPscFromDocument } from "../core/psc";
import { runRuleD5FromRepairText } from "../core/ruleD5";
import { assertGroundingForStageB } from "../pipeline/groundingGate";
import { safeParseExtraction } from "../schemas/validate";
import type { DockingContext } from "../engines/ruleD5";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES_ROOT = resolve(__dirname, "../../tests/fixtures");
const DEFAULT_GOLD_PATH = resolve(FIXTURES_ROOT, "stage_a/gold_cases.json");
const DEFAULT_GATES_PATH = resolve(
  __dirname,
  "../../../config/stage_a_eval.json",
);

export interface StageAGoldLine {
  trade_code: string;
  cost: number;
}

export interface StageAGoldDeficiency {
  code: string;
  action_code?: string | null;
}

export interface StageAGoldCase {
  id: string;
  uc: "colregs" | "psc" | "rule_d5" | "rule_d5_parity";
  tags?: string[];
  source_text?: string;
  source_text_ja?: string;
  source_text_en?: string;
  fixture_file?: string;
  expect_abstain: boolean;
  rule_d5_opts?: {
    docking_context: DockingContext;
    daily_dock_rate: number;
    dock_days: number;
    include_statutory: boolean;
  };
  gold: {
    heading_a_deg?: number;
    heading_b_deg?: number;
    true_bearing_a_to_b_deg?: number;
    speed_a_kn?: number;
    speed_b_kn?: number;
    deficiencies?: StageAGoldDeficiency[];
    lines?: StageAGoldLine[];
  };
  stage_b_gold?: {
    situation?: string;
    role_a?: string | null;
    role_b?: string | null;
    detention_present?: boolean;
    apportionment_rule?: string;
    identical_insurer_total?: boolean;
  };
  notes?: string;
}

export interface StageAGates {
  min_cases?: number;
  min_schema_valid_rate?: number;
  min_field_exact_match_rate?: number;
  min_grounding_pass_rate?: number;
  min_abstain_precision?: number;
  min_abstain_recall?: number;
  min_stage_b_agreement_rate?: number;
  degraded?: StageAGates;
  multilingual?: StageAGates;
}

export interface StageAGateConfig {
  version?: number;
  description?: string;
  gates: StageAGates;
}

export interface StageACaseResult {
  id: string;
  uc: string;
  tags: string[];
  schema_valid: boolean;
  field_total: number;
  field_hits: number;
  field_exact_match_rate: number;
  grounding_pass: boolean | null;
  expect_abstain: boolean;
  did_abstain: boolean;
  abstain_correct: boolean;
  stage_b_scored: boolean;
  stage_b_agree: boolean | null;
  notes?: string[];
}

export interface StageASubsetMetrics {
  cases: number;
  schema_valid_rate: number;
  field_exact_match_rate: number;
  grounding_pass_rate: number;
  abstain_precision: number;
  abstain_recall: number;
  stage_b_agreement_rate: number;
  pass: boolean;
  gate_failures: string[];
}

export interface StageAEvalReport {
  version: number;
  cases_total: number;
  results: StageACaseResult[];
  overall: StageASubsetMetrics;
  degraded: StageASubsetMetrics;
  multilingual: StageASubsetMetrics;
  overall_pass: boolean;
  gates: StageAGates;
}

function loadJson<T>(path: string): T {
  return JSON.parse(readFileSync(path, "utf8")) as T;
}

function resolveSourceText(c: StageAGoldCase): string {
  if (c.source_text?.trim()) return c.source_text;
  if (c.fixture_file) {
    return readFileSync(resolve(FIXTURES_ROOT, c.fixture_file), "utf8");
  }
  throw new Error(`Case ${c.id}: no source_text or fixture_file`);
}

function nearlyEqual(a: number, b: number, eps = 0.51): boolean {
  return Math.abs(a - b) <= eps;
}

function matchLines(
  gold: StageAGoldLine[],
  pred: Array<{ trade_code?: string | null; cost: number }>,
): { hits: number; total: number } {
  const remaining = pred.map((p) => ({
    trade_code: String(p.trade_code || ""),
    cost: Number(p.cost),
    used: false,
  }));
  let hits = 0;
  for (const g of gold) {
    const idx = remaining.findIndex(
      (p) =>
        !p.used &&
        p.trade_code === g.trade_code &&
        nearlyEqual(p.cost, g.cost, 1),
    );
    if (idx >= 0) {
      remaining[idx]!.used = true;
      hits += 1;
    }
  }
  return { hits, total: gold.length };
}

function matchDeficiencies(
  gold: StageAGoldDeficiency[],
  pred: Array<{ code: string; action_code?: string | null }>,
): { hits: number; total: number } {
  const remaining = pred.map((p) => ({
    code: p.code,
    action_code: p.action_code ?? null,
    used: false,
  }));
  let hits = 0;
  let total = 0;
  for (const g of gold) {
    total += 1; // code
    const idx = remaining.findIndex((p) => !p.used && p.code === g.code);
    if (idx < 0) {
      if (g.action_code != null && g.action_code !== "") total += 1;
      continue;
    }
    remaining[idx]!.used = true;
    hits += 1;
    if (g.action_code != null && g.action_code !== "") {
      total += 1;
      if (String(remaining[idx]!.action_code ?? "") === String(g.action_code)) {
        hits += 1;
      }
    }
  }
  return { hits, total };
}

function scoreColregsFields(
  gold: StageAGoldCase["gold"],
  geometry: {
    heading_a_deg: number;
    heading_b_deg: number;
    true_bearing_a_to_b_deg: number;
    speed_a_kn?: number | null;
    speed_b_kn?: number | null;
  },
): { hits: number; total: number } {
  let hits = 0;
  let total = 0;
  const checks: Array<[keyof typeof gold, number | null | undefined]> = [
    ["heading_a_deg", geometry.heading_a_deg],
    ["heading_b_deg", geometry.heading_b_deg],
    ["true_bearing_a_to_b_deg", geometry.true_bearing_a_to_b_deg],
    ["speed_a_kn", geometry.speed_a_kn ?? null],
    ["speed_b_kn", geometry.speed_b_kn ?? null],
  ];
  for (const [key, pred] of checks) {
    const g = gold[key];
    if (typeof g !== "number") continue;
    total += 1;
    if (typeof pred === "number" && nearlyEqual(pred, g)) hits += 1;
  }
  return { hits, total };
}

function rate(num: number, den: number): number {
  return den > 0 ? num / den : 1;
}

function evaluateSubset(
  results: StageACaseResult[],
  gates: StageAGates | undefined,
  label: string,
): StageASubsetMetrics {
  const g = gates ?? {};
  const cases = results.length;
  const schemaOk = results.filter((r) => r.schema_valid).length;
  const fieldHits = results.reduce((s, r) => s + r.field_hits, 0);
  const fieldTotal = results.reduce((s, r) => s + r.field_total, 0);
  const groundingScored = results.filter((r) => r.grounding_pass !== null);
  const groundingOk = groundingScored.filter((r) => r.grounding_pass).length;

  const tp = results.filter((r) => r.expect_abstain && r.did_abstain).length;
  const fp = results.filter((r) => !r.expect_abstain && r.did_abstain).length;
  const fn = results.filter((r) => r.expect_abstain && !r.did_abstain).length;

  const stageBScored = results.filter((r) => r.stage_b_agree !== null);
  const stageBOk = stageBScored.filter((r) => r.stage_b_agree).length;

  const metrics = {
    cases,
    schema_valid_rate: rate(schemaOk, cases),
    field_exact_match_rate: rate(fieldHits, fieldTotal),
    grounding_pass_rate: rate(groundingOk, groundingScored.length),
    abstain_precision: rate(tp, tp + fp),
    abstain_recall: rate(tp, tp + fn),
    stage_b_agreement_rate: rate(stageBOk, stageBScored.length),
    pass: true,
    gate_failures: [] as string[],
  };

  const fail = (msg: string) => {
    metrics.pass = false;
    metrics.gate_failures.push(`${label}: ${msg}`);
  };

  if (g.min_cases != null && cases < g.min_cases) {
    fail(`min_cases ${cases} < ${g.min_cases}`);
  }
  if (
    g.min_schema_valid_rate != null &&
    metrics.schema_valid_rate + 1e-9 < g.min_schema_valid_rate
  ) {
    fail(
      `schema_valid_rate ${metrics.schema_valid_rate.toFixed(3)} < ${g.min_schema_valid_rate}`,
    );
  }
  if (
    g.min_field_exact_match_rate != null &&
    fieldTotal > 0 &&
    metrics.field_exact_match_rate + 1e-9 < g.min_field_exact_match_rate
  ) {
    fail(
      `field_exact_match_rate ${metrics.field_exact_match_rate.toFixed(3)} < ${g.min_field_exact_match_rate}`,
    );
  }
  if (
    g.min_grounding_pass_rate != null &&
    groundingScored.length > 0 &&
    metrics.grounding_pass_rate + 1e-9 < g.min_grounding_pass_rate
  ) {
    fail(
      `grounding_pass_rate ${metrics.grounding_pass_rate.toFixed(3)} < ${g.min_grounding_pass_rate}`,
    );
  }
  if (
    g.min_abstain_precision != null &&
    tp + fp > 0 &&
    metrics.abstain_precision + 1e-9 < g.min_abstain_precision
  ) {
    fail(
      `abstain_precision ${metrics.abstain_precision.toFixed(3)} < ${g.min_abstain_precision}`,
    );
  }
  if (
    g.min_abstain_recall != null &&
    tp + fn > 0 &&
    metrics.abstain_recall + 1e-9 < g.min_abstain_recall
  ) {
    fail(
      `abstain_recall ${metrics.abstain_recall.toFixed(3)} < ${g.min_abstain_recall}`,
    );
  }
  if (
    g.min_stage_b_agreement_rate != null &&
    stageBScored.length > 0 &&
    metrics.stage_b_agreement_rate + 1e-9 < g.min_stage_b_agreement_rate
  ) {
    fail(
      `stage_b_agreement_rate ${metrics.stage_b_agreement_rate.toFixed(3)} < ${g.min_stage_b_agreement_rate}`,
    );
  }

  return metrics;
}

function evalColregs(c: StageAGoldCase): StageACaseResult {
  const source = resolveSourceText(c);
  const notes: string[] = [];
  const run = runColregs({
    narrativeText: source,
    factsExcerpt: source,
    sourceText: source,
    groundingMode: "require_span",
    confidenceMode: "enforce",
    confidence: 0.9,
  });

  const schema_valid = safeParseExtraction(run.extraction).success;
  let grounding_pass: boolean | null = null;
  if (!c.expect_abstain && run.status === "scored") {
    try {
      assertGroundingForStageB(run.extraction, {
        mode: "require_span",
        sourceText: source,
      });
      grounding_pass = true;
    } catch {
      grounding_pass = false;
    }
  } else if (run.status === "abstain") {
    // Abstain path may still carry a schema-valid envelope; grounding N/A for Stage B.
    grounding_pass = null;
  }

  const did_abstain = run.status === "abstain";
  let field_hits = 0;
  let field_total = 0;
  let stage_b_agree: boolean | null = null;

  if (run.status === "scored") {
    const scored = scoreColregsFields(c.gold, run.geometry);
    field_hits = scored.hits;
    field_total = scored.total;
    if (c.stage_b_gold) {
      const g = c.stage_b_gold;
      stage_b_agree =
        (g.situation == null || run.verdict.situation === g.situation) &&
        (g.role_a == null || run.verdict.role_a === g.role_a) &&
        (g.role_b == null || run.verdict.role_b === g.role_b);
    }
  } else if (!c.expect_abstain) {
    notes.push("unexpected_abstain");
    // Still count gold fields as misses when we should have extracted.
    field_total = [
      c.gold.heading_a_deg,
      c.gold.heading_b_deg,
      c.gold.true_bearing_a_to_b_deg,
      c.gold.speed_a_kn,
      c.gold.speed_b_kn,
    ].filter((v) => typeof v === "number").length;
  }

  return {
    id: c.id,
    uc: c.uc,
    tags: c.tags ?? [],
    schema_valid,
    field_total,
    field_hits,
    field_exact_match_rate: rate(field_hits, field_total),
    grounding_pass,
    expect_abstain: c.expect_abstain,
    did_abstain,
    abstain_correct: c.expect_abstain === did_abstain,
    stage_b_scored: run.status === "scored",
    stage_b_agree,
    notes: notes.length ? notes : undefined,
  };
}

function evalPsc(c: StageAGoldCase): StageACaseResult {
  const source = resolveSourceText(c);
  const notes: string[] = [];
  let did_abstain = false;
  let schema_valid = false;
  let grounding_pass: boolean | null = null;
  let field_hits = 0;
  let field_total = 0;
  let stage_b_agree: boolean | null = null;
  let stage_b_scored = false;

  try {
    const run = runPscFromDocument(source, {
      lookbackMonths: 24,
      confidence: 0.75,
      confidenceMode: "enforce",
      filename: c.fixture_file ?? c.id,
    });
    schema_valid = safeParseExtraction(run.extraction).success;
    did_abstain = run.status === "abstain";
    stage_b_scored = run.status === "scored";

    if (run.status === "scored") {
      try {
        // HTML fixtures are stripped before grounding quotes are taken; skip
        // raw-HTML sourceText and rely on field presence + runner require_span.
        assertGroundingForStageB(run.extraction, {
          mode: "require_span",
          sourceText: source.trimStart().startsWith("<") ? undefined : source,
        });
        grounding_pass = true;
      } catch {
        grounding_pass = false;
      }

      const goldDefs = c.gold.deficiencies ?? [];
      const matched = matchDeficiencies(goldDefs, run.deficiencies);
      field_hits = matched.hits;
      field_total = matched.total;

      if (c.stage_b_gold?.detention_present != null) {
        stage_b_agree =
          run.report.detention_present === c.stage_b_gold.detention_present;
      }
    } else {
      notes.push("abstain");
      const goldDefs = c.gold.deficiencies ?? [];
      field_total = goldDefs.reduce(
        (n, d) => n + 1 + (d.action_code != null && d.action_code !== "" ? 1 : 0),
        0,
      );
    }
  } catch (err) {
    notes.push(`error:${err instanceof Error ? err.message : String(err)}`);
    schema_valid = false;
    did_abstain = true;
    const goldDefs = c.gold.deficiencies ?? [];
    field_total = goldDefs.reduce(
      (n, d) => n + 1 + (d.action_code != null && d.action_code !== "" ? 1 : 0),
      0,
    );
  }

  return {
    id: c.id,
    uc: c.uc,
    tags: c.tags ?? [],
    schema_valid,
    field_total,
    field_hits,
    field_exact_match_rate: rate(field_hits, field_total),
    grounding_pass,
    expect_abstain: c.expect_abstain,
    did_abstain,
    abstain_correct: c.expect_abstain === did_abstain,
    stage_b_scored,
    stage_b_agree,
    notes: notes.length ? notes : undefined,
  };
}

function evalRuleD5(c: StageAGoldCase, source: string): StageACaseResult {
  const notes: string[] = [];
  const opts = c.rule_d5_opts!;
  let did_abstain = false;
  let schema_valid = false;
  let grounding_pass: boolean | null = null;
  let field_hits = 0;
  let field_total = 0;
  let stage_b_agree: boolean | null = null;
  let stage_b_scored = false;
  let insurerTotal: number | null = null;

  try {
    const run = runRuleD5FromRepairText(source, {
      dockingContext: opts.docking_context,
      dailyDockRate: opts.daily_dock_rate,
      dockDays: opts.dock_days,
      includeStatutory: opts.include_statutory,
      confidence: 0.7,
      confidenceMode: "enforce",
    });
    schema_valid = safeParseExtraction(run.extraction).success;
    did_abstain = run.status === "abstain";
    stage_b_scored = run.status === "scored";

    if (run.status === "scored") {
      try {
        assertGroundingForStageB(run.extraction, {
          mode: "require_span",
          sourceText: source,
        });
        grounding_pass = true;
      } catch {
        grounding_pass = false;
      }
      const matched = matchLines(
        c.gold.lines ?? [],
        run.extraction.payload.lines,
      );
      field_hits = matched.hits;
      field_total = matched.total;
      insurerTotal = run.apportionment.insurer_total;
      if (c.stage_b_gold?.apportionment_rule) {
        stage_b_agree = String(run.apportionment.apportionment_rule).includes(
          c.stage_b_gold.apportionment_rule,
        );
      }
    } else {
      notes.push("abstain");
      field_total = (c.gold.lines ?? []).length;
    }
  } catch (err) {
    notes.push(`error:${err instanceof Error ? err.message : String(err)}`);
    schema_valid = false;
    did_abstain = true;
    field_total = (c.gold.lines ?? []).length;
  }

  return {
    id: c.id,
    uc: c.uc,
    tags: c.tags ?? [],
    schema_valid,
    field_total,
    field_hits,
    field_exact_match_rate: rate(field_hits, field_total),
    grounding_pass,
    expect_abstain: c.expect_abstain,
    did_abstain,
    abstain_correct: c.expect_abstain === did_abstain,
    stage_b_scored,
    stage_b_agree,
    notes: [
      ...(notes.length ? notes : []),
      ...(insurerTotal != null ? [`insurer_total=${insurerTotal}`] : []),
    ],
  };
}

function evalRuleD5Parity(c: StageAGoldCase): StageACaseResult {
  const ja = c.source_text_ja ?? "";
  const en = c.source_text_en ?? "";
  const jaResult = evalRuleD5({ ...c, id: `${c.id}:ja`, uc: "rule_d5" }, ja);
  const enResult = evalRuleD5({ ...c, id: `${c.id}:en`, uc: "rule_d5" }, en);

  const jaIns = Number(
    (jaResult.notes ?? [])
      .find((n) => n.startsWith("insurer_total="))
      ?.split("=")[1] ?? NaN,
  );
  const enIns = Number(
    (enResult.notes ?? [])
      .find((n) => n.startsWith("insurer_total="))
      ?.split("=")[1] ?? NaN,
  );

  const field_hits = jaResult.field_hits + enResult.field_hits;
  const field_total = jaResult.field_total + enResult.field_total;
  const schema_valid = jaResult.schema_valid && enResult.schema_valid;
  const grounding_pass =
    jaResult.grounding_pass === true && enResult.grounding_pass === true
      ? true
      : jaResult.grounding_pass === false || enResult.grounding_pass === false
        ? false
        : null;

  let stage_b_agree: boolean | null = null;
  if (c.stage_b_gold?.identical_insurer_total) {
    stage_b_agree =
      Number.isFinite(jaIns) && Number.isFinite(enIns) && jaIns === enIns;
  }

  return {
    id: c.id,
    uc: c.uc,
    tags: c.tags ?? [],
    schema_valid,
    field_total,
    field_hits,
    field_exact_match_rate: rate(field_hits, field_total),
    grounding_pass,
    expect_abstain: c.expect_abstain,
    did_abstain: jaResult.did_abstain || enResult.did_abstain,
    abstain_correct:
      c.expect_abstain === (jaResult.did_abstain || enResult.did_abstain),
    stage_b_scored: jaResult.stage_b_scored && enResult.stage_b_scored,
    stage_b_agree,
    notes: [
      `ja_insurer=${jaIns}`,
      `en_insurer=${enIns}`,
      ...(jaResult.notes ?? []).map((n) => `ja:${n}`),
      ...(enResult.notes ?? []).map((n) => `en:${n}`),
    ],
  };
}

function evalCase(c: StageAGoldCase): StageACaseResult {
  switch (c.uc) {
    case "colregs":
      return evalColregs(c);
    case "psc":
      return evalPsc(c);
    case "rule_d5":
      return evalRuleD5(c, resolveSourceText(c));
    case "rule_d5_parity":
      return evalRuleD5Parity(c);
    default:
      throw new Error(`Unknown uc: ${(c as StageAGoldCase).uc}`);
  }
}

export function loadStageAGoldCases(
  goldPath: string = DEFAULT_GOLD_PATH,
): StageAGoldCase[] {
  const raw = loadJson<{ cases: StageAGoldCase[] }>(goldPath);
  return raw.cases;
}

export function loadStageAGates(
  gatesPath: string = DEFAULT_GATES_PATH,
): StageAGateConfig {
  return loadJson<StageAGateConfig>(gatesPath);
}

/**
 * Run Stage A extraction accuracy eval against public gold fixtures.
 */
export function runStageAEval(opts?: {
  goldPath?: string;
  gatesPath?: string;
  cases?: StageAGoldCase[];
  gates?: StageAGates;
}): StageAEvalReport {
  const config = opts?.gates
    ? { version: 1, gates: opts.gates }
    : loadStageAGates(opts?.gatesPath);
  const cases = opts?.cases ?? loadStageAGoldCases(opts?.goldPath);
  const results = cases.map(evalCase);

  const overall = evaluateSubset(results, config.gates, "overall");
  const degraded = evaluateSubset(
    results.filter((r) => r.tags.includes("degraded")),
    config.gates.degraded,
    "degraded",
  );
  const multilingual = evaluateSubset(
    results.filter((r) => r.tags.includes("multilingual")),
    config.gates.multilingual,
    "multilingual",
  );

  return {
    version: config.version ?? 1,
    cases_total: results.length,
    results,
    overall,
    degraded,
    multilingual,
    overall_pass: overall.pass && degraded.pass && multilingual.pass,
    gates: config.gates,
  };
}

/** Compact console summary for CI logs. */
export function formatStageAReport(report: StageAEvalReport): string {
  const line = (label: string, m: StageASubsetMetrics) =>
    `${label}: cases=${m.cases} schema=${m.schema_valid_rate.toFixed(3)} ` +
    `fieldEM=${m.field_exact_match_rate.toFixed(3)} ground=${m.grounding_pass_rate.toFixed(3)} ` +
    `abstainP=${m.abstain_precision.toFixed(3)} abstainR=${m.abstain_recall.toFixed(3)} ` +
    `stageB=${m.stage_b_agreement_rate.toFixed(3)} pass=${m.pass}`;

  const failures = [
    ...report.overall.gate_failures,
    ...report.degraded.gate_failures,
    ...report.multilingual.gate_failures,
  ];
  return [
    `Stage A eval (Issue #93): overall_pass=${report.overall_pass}`,
    line("overall", report.overall),
    line("degraded", report.degraded),
    line("multilingual", report.multilingual),
    ...(failures.length ? ["failures:", ...failures.map((f) => `  - ${f}`)] : []),
  ].join("\n");
}
