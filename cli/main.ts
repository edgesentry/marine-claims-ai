#!/usr/bin/env node
/**
 * Node CLI entry (repo-root). Shares Stage A → Stage B core with the WASM PWA.
 *
 * From web/:
 *   npm run cli -- help
 *   npm run cli -- rule-d5
 *   npm run cli -- colregs --heading-a 30 --heading-b 300 --bearing 70
 *   npm run cli -- colregs --text narrative.txt
 *   npm run cli -- psc --fixture repeat_ism_major
 *   npm run cli -- validate path/to/envelope.json
 *   npm run cli -- classify-encounter --heading-a 0 --heading-b 180 --bearing 0
 *   npm run cli -- route --text path.txt [--tab uc2|uc3|psc]
 *   npm run cli -- apportion --lines path.json
 */
import { readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { classifyEncounter } from "../web/src/engines/colregs.ts";
import {
  apportionRuleD,
  type DockingContext,
  type RepairLineItem,
} from "../web/src/engines/ruleD5.ts";
import type { PscFixtureCase, PscFixturesFile } from "../web/src/engines/psc.ts";
import {
  assertValidForStageB,
  ExtractionValidationError,
  allSchemaIds,
  extractionJsonSchema,
  guidedDecodeSpec,
} from "../web/src/schemas/index.ts";
import {
  runColregs,
  runPscFixture,
  runPscFromPaste,
  runPscFromDocument,
  runRuleD5,
  runRuleD5FromRepairText,
  runRuleD5Synthetic,
} from "../web/src/core/index.ts";
import {
  classifyDocument,
  resolveDocumentRoute,
  shouldAbstainFromStageB,
  type DemoTab,
  type DocumentType,
} from "../web/src/pipeline/documentRouter.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");

function print(obj: unknown): void {
  process.stdout.write(JSON.stringify(obj, null, 2) + "\n");
}

/** Print a runner result; exit 3 when Stage A abstains (Issue #89). */
function printRun(result: { status: string }): void {
  print(result);
  if (result.status === "abstain") {
    process.stderr.write(
      "HUMAN_REVIEW_REQUIRED: Stage B not scored. Re-run with --confirm after review, or raise --confidence.\n",
    );
    process.exit(3);
  }
}

function fail(message: string, code = 1): never {
  process.stderr.write(message + "\n");
  process.exit(code);
}

function usage(): string {
  return `Marine Claims AI CLI (repo-root cli/; core in web/src/core)

UC commands (same Stage A → Stage B path as the PWA):
  rule-d5 [--text FILE | --lines FILE.json]
          [--docking casualty_immediate|deferred_to_routine]
          [--dock-rate N] [--dock-days N] [--no-statutory] [--hire N]
          [--confidence N] [--confirm]
  colregs (--heading-a N --heading-b N --bearing N | --text FILE)
          [--facts TEXT] [--ruling TEXT] [--fault-hint R]
          [--confidence N] [--confirm]
  psc [--fixture ID | --json FILE | --csv FILE | --text FILE]
      [--lookback N] [--confidence N] [--confirm]

Component commands (test individual pieces):
  validate FILE.json
  apportion --lines FILE.json [--docking ...]
  classify-encounter --heading-a N --heading-b N --bearing N
  route --text FILE [--tab uc2|uc3|psc] [--override TYPE] [--filename NAME]
  schema-ids | schema-dump SCHEMA_ID | schema-json SCHEMA_ID
  help
`;
}

function parseArgs(argv: string[]): {
  cmd: string;
  flags: Record<string, string | boolean>;
  positionals: string[];
} {
  const [cmd = "help", ...rest] = argv;
  const flags: Record<string, string | boolean> = {};
  const positionals: string[] = [];
  for (let i = 0; i < rest.length; i++) {
    const a = rest[i]!;
    if (a === "--") continue;
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = rest[i + 1];
      if (next == null || next.startsWith("--")) {
        flags[key] = true;
      } else {
        flags[key] = next;
        i += 1;
      }
    } else {
      positionals.push(a);
    }
  }
  return { cmd, flags, positionals };
}

function flagStr(flags: Record<string, string | boolean>, key: string): string | undefined {
  const v = flags[key];
  return typeof v === "string" ? v : undefined;
}

function flagNum(flags: Record<string, string | boolean>, key: string, fallback: number): number {
  const v = flagStr(flags, key);
  if (v == null) return fallback;
  const n = Number(v);
  if (!Number.isFinite(n)) fail(`Invalid number for --${key}: ${v}`);
  return n;
}

function flagBool(flags: Record<string, string | boolean>, key: string): boolean {
  return flags[key] === true || flags[key] === "true" || flags[key] === "1";
}

function readJson(path: string): unknown {
  const abs = resolve(path);
  if (!existsSync(abs)) fail(`File not found: ${abs}`);
  return JSON.parse(readFileSync(abs, "utf-8"));
}

function readText(path: string): string {
  const abs = resolve(path);
  if (!existsSync(abs)) fail(`File not found: ${abs}`);
  return readFileSync(abs, "utf-8");
}

function dockingFromFlags(flags: Record<string, string | boolean>): DockingContext {
  const raw = flagStr(flags, "docking") ?? "deferred_to_routine";
  if (raw !== "casualty_immediate" && raw !== "deferred_to_routine") {
    fail(`Invalid --docking: ${raw}`);
  }
  return raw;
}

function loadPscFixtures(): PscFixturesFile {
  const path = resolve(repoRoot, "config/psc_inspection_fixtures.json");
  if (!existsSync(path)) fail(`Missing fixtures: ${path}`);
  return JSON.parse(readFileSync(path, "utf-8")) as PscFixturesFile;
}

function cmdRuleD5(flags: Record<string, string | boolean>): void {
  const docking = dockingFromFlags(flags);
  const dailyDockRate = flagNum(flags, "dock-rate", 450_000);
  const dockDays = flagNum(flags, "dock-days", 7);
  const includeStatutory = !flagBool(flags, "no-statutory");
  const hireRate = flagNum(flags, "hire", 800_000);
  const legacyLeadDays = flagNum(flags, "legacy-days", 14);
  const aiLeadMinutes = flagNum(flags, "ai-minutes", 30);
  const confidenceRaw = flagStr(flags, "confidence");
  const confidence = confidenceRaw != null ? Number(confidenceRaw) : undefined;
  if (confidenceRaw != null && !Number.isFinite(confidence)) {
    fail(`Invalid --confidence: ${confidenceRaw}`);
  }
  const confidenceMode = flagBool(flags, "confirm") ? ("confirmed" as const) : undefined;

  const linesPath = flagStr(flags, "lines");
  if (linesPath) {
    const raw = readJson(linesPath);
    const lines = (Array.isArray(raw) ? raw : (raw as { lines?: unknown }).lines) as
      | RepairLineItem[]
      | undefined;
    if (!Array.isArray(lines) || !lines.length) {
      fail("--lines must be a RepairLineItem[] or { lines: [...] }");
    }
    printRun(
      runRuleD5({
        dockingContext: docking,
        lines,
        assumeStatutoryOwnerWork: includeStatutory,
        hireRate,
        legacyLeadDays,
        aiLeadMinutes,
        confidence,
        confidenceMode,
        groundingMode: "paste_bypass",
      }),
    );
    return;
  }

  const textPath = flagStr(flags, "text");
  if (textPath) {
    printRun(
      runRuleD5FromRepairText(readText(textPath), {
        dockingContext: docking,
        dailyDockRate,
        dockDays,
        includeStatutory,
        hireRate,
        legacyLeadDays,
        aiLeadMinutes,
        confidence,
        confidenceMode,
      }),
    );
    return;
  }

  printRun(
    runRuleD5Synthetic({
      dockingContext: docking,
      dailyDockRate,
      dockDays,
      includeStatutory,
      hireRate,
      legacyLeadDays,
      aiLeadMinutes,
    }),
  );
}

function cmdColregs(flags: Record<string, string | boolean>): void {
  const textPath = flagStr(flags, "text");
  const headingA = flagNum(flags, "heading-a", Number.NaN);
  const headingB = flagNum(flags, "heading-b", Number.NaN);
  const bearing = flagNum(flags, "bearing", Number.NaN);
  const hasGeom = [headingA, headingB, bearing].every(Number.isFinite);
  if (!textPath && !hasGeom) {
    fail("colregs requires --heading-a --heading-b --bearing, or --text FILE");
  }
  const confidenceRaw = flagStr(flags, "confidence");
  const confidence = confidenceRaw != null ? Number(confidenceRaw) : undefined;
  if (confidenceRaw != null && !Number.isFinite(confidence)) {
    fail(`Invalid --confidence: ${confidenceRaw}`);
  }
  const confidenceMode = flagBool(flags, "confirm") ? ("confirmed" as const) : undefined;
  const narrativeText = textPath ? readText(textPath) : undefined;
  const facts = flagStr(flags, "facts") ?? (narrativeText ? narrativeText.slice(0, 4500) : undefined);
  printRun(
    runColregs({
      geometry: hasGeom
        ? {
            heading_a_deg: headingA,
            heading_b_deg: headingB,
            true_bearing_a_to_b_deg: bearing,
            speed_a_kn: flagNum(flags, "speed-a", 12),
            speed_b_kn: flagNum(flags, "speed-b", 10),
            range_nm: flagNum(flags, "range", 0.8),
          }
        : undefined,
      narrativeText,
      preferNarrativeGeometry: Boolean(narrativeText) && !hasGeom,
      factsExcerpt: facts,
      rulingExcerpt: flagStr(flags, "ruling"),
      faultRatioHint: flagStr(flags, "fault-hint"),
      documentKind:
        (flagStr(flags, "document-kind") as "judgment" | "jtsb" | undefined) || undefined,
      confidence: confidence ?? (narrativeText && !hasGeom ? 0.85 : undefined),
      confidenceMode: confidenceMode ?? (narrativeText && !hasGeom ? "bypass" : undefined),
      groundingMode: narrativeText && !hasGeom ? "paste_bypass" : undefined,
      sourceText: narrativeText,
    }),
  );
}

function cmdPsc(flags: Record<string, string | boolean>): void {
  const lookback = flagNum(flags, "lookback", 24);
  const confidenceRaw = flagStr(flags, "confidence");
  const confidence =
    confidenceRaw != null ? flagNum(flags, "confidence", 0.75) : undefined;
  const confidenceMode = flags.confirm ? ("confirmed" as const) : undefined;
  const fixtureId = flagStr(flags, "fixture");
  if (fixtureId) {
    const fixtures = loadPscFixtures();
    const fixture = fixtures.cases.find((c) => c.id === fixtureId) as
      | PscFixtureCase
      | undefined;
    if (!fixture) {
      fail(
        `Unknown fixture "${fixtureId}". Available: ${fixtures.cases.map((c) => c.id).join(", ")}`,
      );
    }
    printRun(runPscFixture(fixture, { lookbackMonths: lookback }));
    return;
  }
  const jsonPath = flagStr(flags, "json");
  if (jsonPath) {
    printRun(runPscFromPaste(readText(jsonPath), { lookbackMonths: lookback }));
    return;
  }
  const csvPath = flagStr(flags, "csv");
  if (csvPath) {
    printRun(runPscFromPaste(readText(csvPath), { lookbackMonths: lookback }));
    return;
  }
  const textPath = flagStr(flags, "text") || flagStr(flags, "html");
  if (textPath) {
    printRun(
      runPscFromDocument(readText(textPath), {
        lookbackMonths: lookback,
        confidence: confidence ?? 0.75,
        confidenceMode,
        filename: textPath,
      }),
    );
    return;
  }
  fail("psc requires --fixture, --json, --csv, or --text/--html");
}

function cmdValidate(positionals: string[]): void {
  const path = positionals[0];
  if (!path) fail("validate requires a FILE.json path");
  try {
    const parsed = assertValidForStageB(readJson(path));
    print({ ok: true, schema_id: parsed.schema_id, confidence: parsed.confidence });
  } catch (err) {
    if (err instanceof ExtractionValidationError) {
      print({ ok: false, error: err.message, issues: err.issues });
      process.exit(2);
    }
    throw err;
  }
}

function cmdApportion(flags: Record<string, string | boolean>): void {
  const linesPath = flagStr(flags, "lines");
  if (!linesPath) fail("apportion requires --lines FILE.json");
  const raw = readJson(linesPath);
  const lines = (Array.isArray(raw) ? raw : (raw as { lines?: unknown }).lines) as
    | RepairLineItem[]
    | undefined;
  if (!Array.isArray(lines) || !lines.length) fail("--lines must contain RepairLineItem[]");
  const docking = dockingFromFlags(flags);
  if (flagStr(flags, "envelope")) {
    assertValidForStageB(readJson(flagStr(flags, "envelope")!));
  }
  print(apportionRuleD(lines, docking));
}

function cmdClassify(flags: Record<string, string | boolean>): void {
  const headingA = flagNum(flags, "heading-a", Number.NaN);
  const headingB = flagNum(flags, "heading-b", Number.NaN);
  const bearing = flagNum(flags, "bearing", Number.NaN);
  if (![headingA, headingB, bearing].every(Number.isFinite)) {
    fail("classify-encounter requires --heading-a --heading-b --bearing");
  }
  print(
    classifyEncounter({
      heading_a_deg: headingA,
      heading_b_deg: headingB,
      true_bearing_a_to_b_deg: bearing,
    }),
  );
}

function cmdRoute(flags: Record<string, string | boolean>): void {
  const textPath = flagStr(flags, "text");
  if (!textPath) fail("route requires --text FILE");
  const text = readText(textPath);
  const filename = flagStr(flags, "filename") ?? textPath.split(/[/\\]/).pop();
  const classification = classifyDocument(text, { filename });
  const tabRaw = flagStr(flags, "tab");
  const overrideRaw = flagStr(flags, "override") as DocumentType | undefined;
  const result: Record<string, unknown> = {
    classification: {
      type: classification.type,
      confidence: classification.confidence,
      signals: classification.signals,
      scores: classification.scores,
      backend: classification.backend,
    },
  };
  if (tabRaw) {
    if (tabRaw !== "uc2" && tabRaw !== "uc3" && tabRaw !== "psc") {
      fail(`Invalid --tab: ${tabRaw} (use uc2|uc3|psc)`);
    }
    const decision = resolveDocumentRoute(
      tabRaw as DemoTab,
      classification,
      overrideRaw ?? null,
    );
    result.route = {
      tab: tabRaw,
      override: overrideRaw ?? null,
      allowed: decision.allowed,
      reason: decision.reason,
      detected: decision.detected,
      effective: decision.effective,
      abstain: shouldAbstainFromStageB(decision),
    };
    if (!decision.allowed) {
      print(result);
      process.stderr.write(
        `ROUTE_ABSTAIN: ${decision.reason} — Stage B would not run without a valid --override.\n`,
      );
      process.exit(3);
    }
  }
  print(result);
}

function main(): void {
  const { cmd, flags, positionals } = parseArgs(process.argv.slice(2));
  try {
    switch (cmd) {
      case "help":
      case "-h":
      case "--help":
        process.stdout.write(usage());
        break;
      case "rule-d5":
        cmdRuleD5(flags);
        break;
      case "colregs":
        cmdColregs(flags);
        break;
      case "psc":
        cmdPsc(flags);
        break;
      case "validate":
        cmdValidate(positionals);
        break;
      case "apportion":
        cmdApportion(flags);
        break;
      case "classify-encounter":
        cmdClassify(flags);
        break;
      case "route":
        cmdRoute(flags);
        break;
      case "schema-ids":
        print([...allSchemaIds()]);
        break;
      case "schema-dump": {
        const id = positionals[0] || flagStr(flags, "id");
        if (!id || !allSchemaIds().includes(id as never)) {
          fail(`schema-dump requires one of: ${allSchemaIds().join(", ")}`);
        }
        print(guidedDecodeSpec(id as "rule_d5.v1" | "colregs.v1" | "psc.v1"));
        break;
      }
      case "schema-json": {
        const id = positionals[0];
        if (!id || !allSchemaIds().includes(id as never)) {
          fail(`schema-json requires one of: ${allSchemaIds().join(", ")}`);
        }
        print(extractionJsonSchema(id as "rule_d5.v1" | "colregs.v1" | "psc.v1"));
        break;
      }
      default:
        fail(`Unknown command: ${cmd}\n\n${usage()}`);
    }
  } catch (err) {
    if (err instanceof ExtractionValidationError) {
      fail(`Schema validation failed: ${err.message}`, 2);
    }
    fail(err instanceof Error ? err.message : String(err));
  }
}

main();
