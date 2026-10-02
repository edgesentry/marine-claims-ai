import "./styles/demo.css";
import { roleLabel, situationLabel, t, displayRule, displayStatus, displayCausalityReason, displayLineTitle, type Lang } from "./i18n";
import {
  classifyEncounter,
  OVERTAKING_RELATIVE_BEARING_MAX_DEG,
  OVERTAKING_RELATIVE_BEARING_MIN_DEG,
  type EncounterGeometry,
} from "./engines/colregs";
import { type DockingContext, type RepairLineItem } from "./engines/ruleD5";
import {
  type CatalogSeed,
  type FaultRules,
} from "./engines/fault";
import { validateCausality } from "./engines/bfs";
import {
  DEFAULT_LOOKBACK_MONTHS,
  scoreSeaworthiness,
  tryParsePscPaste,
  type NormalizedDeficiency,
  type PscFixtureCase,
  type SeaworthinessRiskReport,
} from "./engines/psc";
import { extractPdfText } from "./pdf/parseTender";
import {
  extractPdfTextWithOcr,
  ocrImageFile,
  stageAConfidenceForSource,
  OCR_STAGE_A_CONFIDENCE,
  type PdfExtractionSource,
} from "./pdf/ocrPages";
import { extractRepairItemsFromText, syntheticUc2Lines } from "./pdf/repairLines";
import {
  extractFactsExcerpt,
  extractFromJudgment,
  extractJtsbCauseExcerpt,
  isLikelyJtsbReport,
} from "./ingest/civilJudgmentExtractor";
import {
  extractColregsTelemetry,
  telemetryGrounding,
  telemetryToGeometry,
  telemetryFieldConfidence,
} from "./ingest/colregsTelemetryExtractor";
import {
  geometryForCatalogCase,
  resolveDisplayDegrees,
  type CatalogJmatCase,
} from "./demo/catalogGeometry";
import { looksLikeHtml } from "./ingest/pscDeficiencyExtractor";
import {
  evaluateClaimsDynamically,
  noOpNplScorer,
  type AnalyzedItem,
  type NplScorer,
} from "./appraisal/pipeline";
import { createNplScorer, type NplLibrary } from "./appraisal/negativePatterns";
import {
  apportionmentHtml,
  apportionmentMarkdown,
  colregsHtml,
  colregsMarkdown,
  downloadText,
  pscHtml,
  pscMarkdown,
  type PscView,
  type Uc2View,
  type Uc3View,
} from "./ui/export";
import {
  buildColregsExtraction,
  buildPscExtraction,
  ExtractionValidationError,
  GroundingValidationError,
  ruleD5LinesFromExtraction,
  type ColregsExtraction,
  type ExtractionResult,
  type RuleD5Extraction,
} from "./schemas";
import {
  runColregs,
  runPsc,
  runPscFixture,
  runPscFromDocument,
  runRuleD5,
  runRuleD5FromRepairText,
} from "./core";
import { getDuckDb } from "./db/duckdb";
import {
  classifyDocument,
  resolveDocumentRoute,
  TAB_ALLOWED_TYPES,
  type DemoTab,
  type DocumentClassification,
  type DocumentType,
  type KnownDocumentType,
} from "./pipeline/documentRouter";

type Tab = DemoTab;

interface PendingReview {
  extraction: ExtractionResult;
  reasons: string[];
}

/** Uploaded / pasted text awaiting Analyze after document-type routing (#86). */
interface PendingUpload {
  text: string;
  filename: string;
  classification: DocumentClassification;
  /** null = use detected type */
  override: DocumentType | null;
  /** How Stage A text was obtained (#94). */
  extractionSource: PdfExtractionSource;
}

interface AppState {
  lang: Lang;
  tab: Tab;
  // UC2
  dailyDockRate: number;
  dockDays: number;
  hireRate: number;
  legacyLeadDays: number;
  aiLeadMinutes: number;
  dockingContext: DockingContext;
  includeStatutory: boolean;
  uc2Lines: RepairLineItem[];
  uc2FromPdf: boolean;
  uc2Confirmed: boolean;
  uc2Analyzed: AnalyzedItem[];
  uc2Pending: PendingReview | null;
  uc2Upload: PendingUpload | null;
  /** Non-null while in-browser OCR runs (#94). */
  ocrBusy: string | null;
  // UC3
  caseId: string;
  headingA: number;
  headingB: number;
  bearingAb: number;
  overrideGeom: boolean;
  rules: FaultRules | null;
  seeds: CatalogSeed[];
  jmatCases: Array<Record<string, string>>;
  civil7: CatalogSeed | null;
  uc3Pending: PendingReview | null;
  uc3Confirmed: boolean;
  uc3Upload: PendingUpload | null;
  nplScorer: NplScorer;
  // PSC
  pscFixtures: PscFixtureCase[];
  pscCaseId: string;
  pscLookbackMonths: number;
  pscPasteText: string;
  pscUsePaste: boolean;
  pscPasteCurrent: NormalizedDeficiency[];
  pscPastePrior: NormalizedDeficiency[] | null;
  pscPasteCic: Record<string, number> | null;
  pscPasteMou: string | null;
  pscPasteLabel: string;
  /** Document upload path (#92) vs JSON/CSV paste. */
  pscFromDocument: boolean;
  pscPending: PendingReview | null;
  pscConfirmed: boolean;
  pscUpload: PendingUpload | null;
}

const state: AppState = {
  lang: (localStorage.getItem("lang") as Lang) || "en",
  tab: "uc2",
  dailyDockRate: 860_000,
  dockDays: 5,
  hireRate: 4_000_000,
  legacyLeadDays: 21,
  aiLeadMinutes: 15,
  dockingContext: "casualty_immediate",
  includeStatutory: true,
  uc2Lines: [],
  uc2FromPdf: false,
  uc2Confirmed: false,
  uc2Analyzed: [],
  uc2Pending: null,
  uc2Upload: null,
  ocrBusy: null,
  caseId: "civil_7",
  headingA: 30,
  headingB: 300,
  bearingAb: 70,
  overrideGeom: false,
  rules: null,
  seeds: [],
  jmatCases: [],
  civil7: null,
  uc3Pending: null,
  uc3Confirmed: false,
  uc3Upload: null,
  nplScorer: noOpNplScorer,
  pscFixtures: [],
  pscCaseId: "repeat_ism_major",
  pscLookbackMonths: DEFAULT_LOOKBACK_MONTHS,
  pscPasteText: "",
  pscUsePaste: false,
  pscPasteCurrent: [],
  pscPastePrior: null,
  pscPasteCic: null,
  pscPasteMou: null,
  pscPasteLabel: "",
  pscFromDocument: false,
  pscPending: null,
  pscConfirmed: false,
  pscUpload: null,
};

function fmtYen(n: number): string {
  return `¥${n.toLocaleString()}`;
}

function routerTypeI18nKey(type: DocumentType): string {
  return `router_type_${type}`;
}

function routerPanelHtml(tab: Tab, upload: PendingUpload | null, analyzeId: string): string {
  if (!upload) return "";
  const decision = resolveDocumentRoute(tab, upload.classification, upload.override);
  const detectedLabel = t(routerTypeI18nKey(upload.classification.type), state.lang);
  const confPct = Math.round(upload.classification.confidence * 100);
  const allowed = [...TAB_ALLOWED_TYPES[tab]];
  const statusMsg =
    decision.reason === "unknown"
      ? t("router_blocked_unknown", state.lang)
      : decision.reason === "tab_mismatch"
        ? t("router_blocked_mismatch", state.lang)
        : t("router_ready", state.lang);
  const statusClass = decision.allowed ? "ok" : "warn";
  const ocrHint =
    upload.extractionSource === "ocr"
      ? `<p class="warn">${escapeHtml(t("ocr_source_hint", state.lang))}</p>`
      : "";
  return `
    <div class="router-panel" data-router-tab="${escapeHtml(tab)}">
      <p><strong>${escapeHtml(t("router_detected", state.lang))}:</strong>
        <code>${escapeHtml(detectedLabel)}</code>
        · ${escapeHtml(t("router_confidence", state.lang))}: <code>${escapeHtml(String(confPct))}%</code>
      </p>
      ${ocrHint}
      <label>${escapeHtml(t("router_override", state.lang))}
        <select id="routerOverride_${escapeHtml(tab)}">
          <option value="" ${upload.override == null ? "selected" : ""}>${escapeHtml(t("router_override_none", state.lang))}</option>
          ${allowed
            .map(
              (ty: KnownDocumentType) =>
                `<option value="${escapeHtml(ty)}" ${upload.override === ty ? "selected" : ""}>${escapeHtml(t(routerTypeI18nKey(ty), state.lang))}</option>`,
            )
            .join("")}
        </select>
      </label>
      <p class="${statusClass}">${escapeHtml(statusMsg)}</p>
      <div class="actions">
        <button type="button" class="btn" id="${escapeHtml(analyzeId)}" ${decision.allowed ? "" : "disabled"}>${escapeHtml(t("router_analyze", state.lang))}</button>
      </div>
    </div>
  `;
}

/** Escape text before interpolating into innerHTML (CodeQL js/xss-through-dom). */
function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function emptyUc2View(): Uc2View {
  return {
    rule: "—",
    dock_total: 0,
    insurer_common: 0,
    owner_common: 0,
    insurer_total: 0,
    owner_total: 0,
    days_saved: 0,
    offhire_jpy: 0,
    line_rows: [],
  };
}

function reviewBannerHtml(pending: PendingReview): string {
  const conf = pending.extraction.confidence;
  const reasons = pending.reasons.length
    ? pending.reasons
    : pending.extraction.abstain?.reason
      ? [pending.extraction.abstain.reason]
      : [];
  return `<div class="review-banner" role="status">
    <h2><span class="pill review">${escapeHtml(t("human_review_title", state.lang))}</span></h2>
    <p>${escapeHtml(t("human_review_body", state.lang))}</p>
    <p class="muted">${escapeHtml(t("human_review_not_legal", state.lang))}</p>
    <p>${escapeHtml(t("confidence_label", state.lang))}: <strong>${escapeHtml(conf.toFixed(2))}</strong></p>
    ${
      reasons.length
        ? `<ul class="reasons">${reasons.map((r) => `<li><code>${escapeHtml(r)}</code></li>`).join("")}</ul>`
        : ""
    }
    <p class="muted">${escapeHtml(t("review_edit_hint", state.lang))}</p>
  </div>`;
}

function buildUc2(): Uc2View {
  if (state.uc2Pending && !state.uc2Confirmed) {
    void validateCausality("船首", "機関室");
    return emptyUc2View();
  }

  const lines =
    state.uc2Lines.length > 0
      ? state.uc2Lines
      : syntheticUc2Lines(state.dailyDockRate, state.dockDays, state.includeStatutory, state.lang);
  const dockTotal = state.dailyDockRate * state.dockDays;
  const synced = lines.map((ln) =>
    (ln.trade_code || "").startsWith("DOCK") ? { ...ln, cost: dockTotal } : ln,
  );
  const fromPdfPendingGate = state.uc2FromPdf && !state.uc2Confirmed;
  const run = runRuleD5({
    dockingContext: state.dockingContext,
    lines: synced,
    assumeStatutoryOwnerWork: state.includeStatutory,
    confidence: state.uc2FromPdf ? (state.uc2Confirmed ? 0.85 : 0.65) : 0.85,
    grounding: synced
      .filter((ln) => ln.title)
      .slice(0, 8)
      .map((ln) => ({
        field: `lines.${ln.id}`,
        source_quote: String(ln.title),
      })),
    groundingMode: state.uc2FromPdf && !state.uc2Confirmed ? "require_span" : "paste_bypass",
    confidenceMode: state.uc2Confirmed
      ? "confirmed"
      : fromPdfPendingGate
        ? "enforce"
        : "bypass",
    hireRate: state.hireRate,
    legacyLeadDays: state.legacyLeadDays,
    aiLeadMinutes: state.aiLeadMinutes,
  });

  void validateCausality("船首", "機関室");

  if (run.status === "abstain") {
    state.uc2Pending = { extraction: run.extraction, reasons: run.reasons };
    return emptyUc2View();
  }

  const result = run.apportionment;
  return {
    rule: result.apportionment_rule,
    dock_total: result.common_dues_total,
    insurer_common: result.insurer_common_share,
    owner_common: result.owner_common_share,
    insurer_total: result.insurer_total,
    owner_total: result.owner_total,
    days_saved: run.days_saved,
    offhire_jpy: run.offhire_jpy,
    line_rows: result.lines.map((ln) => ({
      id: ln.id,
      title: ln.title || ln.id,
      trade_code: ln.trade_code,
      cost: ln.cost,
      insurer: ln.insurer_share,
      owner: ln.owner_share,
      rule: ln.apportionment_rule,
    })),
  };
}

function geometryForCase(): EncounterGeometry {
  return geometryForCatalogCase({
    caseId: state.caseId,
    overrideGeom: state.overrideGeom,
    slider: {
      headingA: state.headingA,
      headingB: state.headingB,
      bearingAb: state.bearingAb,
    },
    jmatCases: state.jmatCases as CatalogJmatCase[],
  });
}

/** Sync disabled heading/bearing inputs to the geometry Stage B already uses (#102). */
function syncDisplayGeometryFromCase(): void {
  if (state.overrideGeom) return;
  const preserve =
    state.caseId === "civil_7" && state.civil7?.case_id === "upload"
      ? {
          headingA: state.headingA,
          headingB: state.headingB,
          bearingAb: state.bearingAb,
        }
      : null;
  const d = resolveDisplayDegrees({
    caseId: state.caseId,
    jmatCases: state.jmatCases as CatalogJmatCase[],
    preserveDegrees: preserve,
  });
  state.headingA = d.headingA;
  state.headingB = d.headingB;
  state.bearingAb = d.bearingAb;
}

function emptyUc3View(title: string, facts: string, ruling: string, documentKind?: "judgment" | "jtsb"): Uc3View {
  return {
    title,
    situation: "—",
    situation_label: "—",
    role_a_label: "—",
    role_b_label: "—",
    fault_ratio: "—",
    relative_bearing: 0,
    rule_citations: [],
    facts,
    ruling,
    document_kind: documentKind,
  };
}

function buildUc3(): Uc3View {
  let title = state.caseId;
  let facts = "";
  let ruling = "";
  let catalogFault: string | null = null;

  if (state.caseId === "civil_7" && state.civil7) {
    title = state.civil7.title;
    facts = state.civil7.input_facts || "";
    ruling = state.civil7.holding || "";
    catalogFault = state.civil7.fault_ratio || null;
  } else {
    const jmat = state.jmatCases.find((c) => c.case_id === state.caseId);
    if (jmat) {
      title = jmat.title || title;
      facts = jmat.facts_text || "";
      ruling = jmat.ruling_text || "";
    }
  }

  const geometry = geometryForCase();
  if (state.overrideGeom) catalogFault = null;

  const docKind =
    state.caseId === "civil_7" && state.civil7?.document_kind
      ? state.civil7.document_kind
      : undefined;

  if (state.uc3Pending && !state.uc3Confirmed) {
    return emptyUc3View(title, facts, ruling, docKind);
  }

  const isUpload = state.civil7?.case_id === "upload";
  const run = runColregs({
    geometry,
    factsExcerpt: facts || undefined,
    rulingExcerpt: ruling || undefined,
    title,
    faultRatioHint: catalogFault || undefined,
    documentKind: docKind,
    confidence: isUpload ? (state.uc3Confirmed ? 0.85 : 0.55) : 0.7,
    groundingMode: isUpload && !state.uc3Confirmed ? "require_span" : "paste_bypass",
    confidenceMode: state.uc3Confirmed
      ? "confirmed"
      : isUpload && !state.uc3Confirmed
        ? "enforce"
        : "bypass",
    sourceText:
      isUpload && !state.uc3Confirmed
        ? [facts, ruling].filter(Boolean).join("\n") || undefined
        : undefined,
    rules: state.rules,
    seeds: state.seeds,
  });

  if (run.status === "abstain") {
    state.uc3Pending = { extraction: run.extraction, reasons: run.reasons };
    return emptyUc3View(title, facts, ruling, docKind);
  }

  const { extraction, verdict, fault_ratio: faultRatio } = run;
  const rel = verdict.relative_bearing_a_to_b_deg;
  const documentKind = extraction.payload.document_kind ?? docKind;

  return {
    title,
    situation: verdict.situation,
    situation_label: situationLabel(verdict.situation, state.lang),
    role_a_label: roleLabel(verdict.role_a, state.lang),
    role_b_label: roleLabel(verdict.role_b, state.lang),
    fault_ratio: faultRatio,
    relative_bearing: Math.round(rel * 10) / 10,
    rule_citations: verdict.rule_citations,
    facts: extraction.payload.facts_excerpt || facts,
    ruling: extraction.payload.ruling_excerpt || ruling,
    document_kind: documentKind,
  };
}

function briefingBox(prefix: "uc2" | "uc3" | "psc"): string {
  return `<aside class="briefing" aria-label="${escapeHtml(t("briefing_label", state.lang))}">
    <h2 class="briefing-title">${escapeHtml(t(`briefing_title_${prefix}`, state.lang))}</h2>
    <div class="briefing-prose">
      <p>${escapeHtml(t(`${prefix}_briefing_p1`, state.lang))}</p>
      <p>${escapeHtml(t(`${prefix}_briefing_p2`, state.lang))}</p>
      <p>${escapeHtml(t(`${prefix}_briefing_p3`, state.lang))}</p>
    </div>
  </aside>`;
}

function explainBox(prefix: "uc2" | "uc3" | "psc"): string {
  return `<aside class="explain">
    <div><strong>${escapeHtml(t("explain_usecase", state.lang))}</strong> ${escapeHtml(t(`${prefix}_explain_usecase`, state.lang))}</div>
    <div><strong>${escapeHtml(t("explain_input", state.lang))}</strong> ${escapeHtml(t(`${prefix}_explain_input`, state.lang))}</div>
    <div><strong>${escapeHtml(t("explain_process", state.lang))}</strong> ${escapeHtml(t(`${prefix}_explain_process`, state.lang))}</div>
    <div><strong>${escapeHtml(t("explain_output", state.lang))}</strong> ${escapeHtml(t(`${prefix}_explain_output`, state.lang))}</div>
  </aside>`;
}

function renderUc2(root: HTMLElement): void {
  const view = buildUc2();
  const causality = validateCausality("船首", "機関室");
  const pending = state.uc2Pending && !state.uc2Confirmed ? state.uc2Pending : null;
  const pendingExt = pending?.extraction as RuleD5Extraction | undefined;
  const editableLines =
    pendingExt?.payload.lines ??
    (state.uc2Lines.length
      ? state.uc2Lines
      : []);

  const resultsPanel = pending
    ? `<section class="panel">
        ${reviewBannerHtml(pending)}
        <div class="review-fields">
          ${editableLines
            .map(
              (ln, i) => `<label>${escapeHtml(t("col_title", state.lang))} / ${escapeHtml(t("col_cost", state.lang))}
              <input type="text" data-rev-title="${i}" value="${escapeHtml(ln.title || ln.id)}">
              <input type="number" data-rev-cost="${i}" value="${escapeHtml(ln.cost)}">
            </label>`,
            )
            .join("")}
        </div>
        <div class="actions">
          <button type="button" class="btn" id="confirmScoreUc2">${escapeHtml(t("confirm_and_score", state.lang))}</button>
        </div>
      </section>`
    : `<section class="panel">
        <h2>${escapeHtml(t("rule_label", state.lang))}</h2>
        <p><code>${escapeHtml(displayRule(view.rule, state.lang))}</code></p>
        <dl class="metrics">
          <div><dt>${escapeHtml(t("common_dues", state.lang))}</dt><dd>${escapeHtml(fmtYen(view.dock_total))}</dd></div>
          <div><dt>${escapeHtml(t("insurer_share", state.lang))}</dt><dd>${escapeHtml(fmtYen(view.insurer_common))}</dd></div>
          <div><dt>${escapeHtml(t("owner_share", state.lang))}</dt><dd>${escapeHtml(fmtYen(view.owner_common))}</dd></div>
        </dl>
        <h3>${escapeHtml(t("offhire_title", state.lang))}</h3>
        <p>${escapeHtml(t("days_saved", state.lang))}: ${view.days_saved} · ${escapeHtml(t("offhire_saved", state.lang))}: ${escapeHtml(fmtYen(view.offhire_jpy))}</p>
        <table class="lines">
          <thead><tr><th>${escapeHtml(t("col_id", state.lang))}</th><th>${escapeHtml(t("col_title", state.lang))}</th><th>${escapeHtml(t("col_cost", state.lang))}</th><th>${escapeHtml(t("col_insurer", state.lang))}</th><th>${escapeHtml(t("col_owner", state.lang))}</th><th>${escapeHtml(t("col_rule", state.lang))}</th></tr></thead>
          <tbody>
            ${view.line_rows
              .map(
                (r) =>
                  `<tr><td>${escapeHtml(r.id)}</td><td>${escapeHtml(displayLineTitle(r.title, state.lang))}</td><td>${escapeHtml(fmtYen(r.cost))}</td><td>${escapeHtml(fmtYen(r.insurer))}</td><td>${escapeHtml(fmtYen(r.owner))}</td><td><code>${escapeHtml(displayRule(r.rule, state.lang))}</code></td></tr>`,
              )
              .join("")}
          </tbody>
        </table>
        <div class="actions">
          <button type="button" class="btn" id="expMd">${escapeHtml(t("export_apportion_md", state.lang))}</button>
          <button type="button" class="btn" id="expHtml">${escapeHtml(t("export_apportion_html", state.lang))}</button>
        </div>
      </section>`;

  root.innerHTML = `
    ${briefingBox("uc2")}
    <p class="lead">${escapeHtml(t("uc2_lead", state.lang))}</p>
    ${explainBox("uc2")}
    <div class="grid-2">
      <section class="panel">
        <label>${escapeHtml(t("daily_dock_rate", state.lang))}
          <input type="range" id="dockRate" min="100000" max="5000000" step="10000" value="${state.dailyDockRate}">
          <span id="dockRateVal">${escapeHtml(fmtYen(state.dailyDockRate))}</span>
        </label>
        <label>${escapeHtml(t("dock_days", state.lang))}
          <input type="range" id="dockDays" min="1" max="30" value="${state.dockDays}">
          <span id="dockDaysVal">${state.dockDays}</span>
        </label>
        <label>${escapeHtml(t("hire_rate", state.lang))}
          <input type="range" id="hireRate" min="100000" max="20000000" step="100000" value="${state.hireRate}">
          <span id="hireRateVal">${escapeHtml(fmtYen(state.hireRate))}</span>
        </label>
        <label>${escapeHtml(t("legacy_lead_days", state.lang))}
          <input type="range" id="legacyLead" min="1" max="60" value="${state.legacyLeadDays}">
          <span id="legacyLeadVal">${state.legacyLeadDays}</span>
        </label>
        <label>${escapeHtml(t("ai_lead_minutes", state.lang))}
          <input type="range" id="aiLead" min="1" max="1440" value="${state.aiLeadMinutes}">
          <span id="aiLeadVal">${state.aiLeadMinutes}</span>
        </label>
        <label>${escapeHtml(t("docking_context", state.lang))}
          <select id="dockCtx">
            <option value="casualty_immediate" ${state.dockingContext === "casualty_immediate" ? "selected" : ""}>${escapeHtml(t("ctx_immediate", state.lang))}</option>
            <option value="deferred_to_routine" ${state.dockingContext === "deferred_to_routine" ? "selected" : ""}>${escapeHtml(t("ctx_deferred", state.lang))}</option>
          </select>
        </label>
        <label class="check"><input type="checkbox" id="inclStat" ${state.includeStatutory ? "checked" : ""}> ${escapeHtml(t("include_statutory", state.lang))}</label>
        <div class="dropzone" id="pdfDrop">${escapeHtml(t("drop_pdf", state.lang))}<input type="file" id="pdfFile" accept="application/pdf" hidden></div>
        ${state.ocrBusy && state.tab === "uc2" ? `<p class="warn" id="ocrBusy">${escapeHtml(state.ocrBusy)}</p>` : ""}
        ${routerPanelHtml("uc2", state.uc2Upload, "analyzeUc2")}
        <div class="actions">
          <button type="button" class="btn" id="useSynthetic">${escapeHtml(t("use_synthetic", state.lang))}</button>
        </div>
        ${
          state.uc2FromPdf
            ? `<p class="ok">${escapeHtml(
                pending
                  ? t("analyzed_pending_review", state.lang)
                  : t("analyzed_ok", state.lang),
              )}</p>`
            : ""
        }
        ${
          state.uc2Analyzed.length
            ? `<p class="muted">${escapeHtml(t("pipeline_statuses", state.lang))}: ${state.uc2Analyzed
                .map(
                  (a) =>
                    `${escapeHtml(displayLineTitle(a.description, state.lang).slice(0, 28))}… → <code>${escapeHtml(displayStatus(a.status, state.lang))}</code>`,
                )
                .join("<br>")}</p>`
            : ""
        }
        <p class="muted">${escapeHtml(t("causality_check", state.lang))}: <code>${escapeHtml(displayCausalityReason(causality.reason, state.lang))}</code> · ${escapeHtml(causality.valid ? t("causality_valid", state.lang) : t("causality_invalid", state.lang))}</p>
      </section>
      ${resultsPanel}
    </div>
  `;

  const bindRange = (id: string, valId: string, key: keyof AppState, fmt?: (n: number) => string) => {
    const el = root.querySelector(`#${id}`) as HTMLInputElement;
    el?.addEventListener("input", () => {
      (state as unknown as Record<string, unknown>)[key] = Number(el.value);
      const span = root.querySelector(`#${valId}`);
      if (span) span.textContent = fmt ? fmt(Number(el.value)) : el.value;
      render();
    });
  };
  bindRange("dockRate", "dockRateVal", "dailyDockRate", fmtYen);
  bindRange("dockDays", "dockDaysVal", "dockDays");
  bindRange("hireRate", "hireRateVal", "hireRate", fmtYen);
  bindRange("legacyLead", "legacyLeadVal", "legacyLeadDays");
  bindRange("aiLead", "aiLeadVal", "aiLeadMinutes");

  root.querySelector("#dockCtx")?.addEventListener("change", (e) => {
    state.dockingContext = (e.target as HTMLSelectElement).value as DockingContext;
    render();
  });
  root.querySelector("#inclStat")?.addEventListener("change", (e) => {
    state.includeStatutory = (e.target as HTMLInputElement).checked;
    if (!state.uc2FromPdf) state.uc2Lines = [];
    render();
  });
  root.querySelector("#useSynthetic")?.addEventListener("click", () => {
    state.uc2Lines = [];
    state.uc2FromPdf = false;
    state.uc2Confirmed = false;
    state.uc2Pending = null;
    state.uc2Analyzed = [];
    state.uc2Upload = null;
    render();
  });
  root.querySelector("#confirmScoreUc2")?.addEventListener("click", () => {
    const base = editableLines.map((ln) => ({ ...ln }));
    for (const input of root.querySelectorAll<HTMLInputElement>("[data-rev-title]")) {
      const i = Number(input.dataset.revTitle);
      if (base[i]) base[i] = { ...base[i]!, title: input.value };
    }
    for (const input of root.querySelectorAll<HTMLInputElement>("[data-rev-cost]")) {
      const i = Number(input.dataset.revCost);
      if (base[i]) base[i] = { ...base[i]!, cost: Number(input.value) || 0 };
    }
    state.uc2Lines = base;
    state.uc2Confirmed = true;
    state.uc2Pending = null;
    render();
  });
  root.querySelector("#routerOverride_uc2")?.addEventListener("change", (e) => {
    if (!state.uc2Upload) return;
    const v = (e.target as HTMLSelectElement).value;
    state.uc2Upload = {
      ...state.uc2Upload,
      override: v ? (v as DocumentType) : null,
    };
    render();
  });
  root.querySelector("#analyzeUc2")?.addEventListener("click", () => {
    void analyzeUc2Upload();
  });
  const drop = root.querySelector("#pdfDrop") as HTMLElement;
  const fileInput = root.querySelector("#pdfFile") as HTMLInputElement;
  drop?.addEventListener("click", () => fileInput?.click());
  drop?.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("drag");
  });
  drop?.addEventListener("dragleave", () => drop.classList.remove("drag"));
  drop?.addEventListener("drop", async (e) => {
    e.preventDefault();
    drop.classList.remove("drag");
    const f = e.dataTransfer?.files?.[0];
    if (f) await handlePdf(f);
  });
  fileInput?.addEventListener("change", async () => {
    const f = fileInput.files?.[0];
    if (f) await handlePdf(f);
  });

  root.querySelector("#expMd")?.addEventListener("click", () => {
    downloadText("rule_d5.md", apportionmentMarkdown(view, state.lang), "text/markdown");
  });
  root.querySelector("#expHtml")?.addEventListener("click", () => {
    downloadText("rule_d5.html", apportionmentHtml(view, state.lang), "text/html");
  });
}

async function handlePdf(file: File): Promise<void> {
  state.ocrBusy = t("ocr_in_progress", state.lang);
  render();
  const extracted = await extractPdfTextWithOcr(file, {
    extractText: extractPdfText,
    onProgress: (p) => {
      const pct = Math.round(p.progress * 100);
      state.ocrBusy = `${t("ocr_in_progress", state.lang)} (${pct}%)`;
      const el = document.querySelector("#ocrBusy");
      if (el) el.textContent = state.ocrBusy;
      else render();
    },
  });
  state.ocrBusy = null;

  if (!extracted.text.trim()) {
    console.error("[ocr] upload failed", extracted.error);
    alert(t(extracted.error ? "ocr_failed" : "err_pdf_empty_text", state.lang));
    render();
    return;
  }

  const classification = classifyDocument(extracted.text, { filename: file.name });
  state.uc2Upload = {
    text: extracted.text,
    filename: file.name,
    classification,
    override: null,
    extractionSource: extracted.source,
  };
  // Reset prior Stage B until Analyze (Issue #86).
  state.uc2Lines = [];
  state.uc2FromPdf = false;
  state.uc2Confirmed = false;
  state.uc2Pending = null;
  state.uc2Analyzed = [];
  render();
}

async function analyzeUc2Upload(): Promise<void> {
  const upload = state.uc2Upload;
  if (!upload) return;
  const decision = resolveDocumentRoute("uc2", upload.classification, upload.override);
  if (!decision.allowed) {
    alert(
      decision.reason === "unknown"
        ? t("router_blocked_unknown", state.lang)
        : t("router_blocked_mismatch", state.lang),
    );
    return;
  }
  const text = upload.text;
  const fileName = upload.filename;
  const items = extractRepairItemsFromText(text);
  if (!items.length) {
    alert(t("err_no_line_items", state.lang));
    return;
  }
  try {
    const run = runRuleD5FromRepairText(text, {
      dockingContext: state.dockingContext,
      dailyDockRate: state.dailyDockRate,
      dockDays: state.dockDays,
      includeStatutory: state.includeStatutory,
      lang: state.lang,
      hireRate: state.hireRate,
      legacyLeadDays: state.legacyLeadDays,
      aiLeadMinutes: state.aiLeadMinutes,
      confidence: stageAConfidenceForSource(upload.extractionSource),
    });
    state.uc2Lines = ruleD5LinesFromExtraction(run.extraction);
    state.uc2FromPdf = true;
    state.uc2Confirmed = false;
    if (run.status === "abstain") {
      state.uc2Pending = { extraction: run.extraction, reasons: run.reasons };
    } else {
      state.uc2Pending = null;
      state.uc2Confirmed = true;
    }
  } catch (err) {
    if (
      err instanceof ExtractionValidationError ||
      err instanceof GroundingValidationError
    ) {
      alert(t("err_schema_invalid", state.lang));
      return;
    }
    if (err instanceof Error && /No repair line items|ungrounded/i.test(err.message)) {
      alert(t("err_no_line_items", state.lang));
      return;
    }
    throw err;
  }
  const dockTotal = state.dailyDockRate * state.dockDays;
  const synced = state.uc2Lines.map((ln) =>
    (ln.trade_code || "").startsWith("DOCK") ? { ...ln, cost: dockTotal } : ln,
  );
  const { analyzed } = evaluateClaimsDynamically(
    synced.map((ln, i) => ({
      id: i + 1,
      num: String(i + 1),
      category: (ln.trade_code || "").startsWith("ENG") ? "【機関部】" : "【甲板部】",
      description: ln.title || ln.id,
      estimated_cost: ln.cost,
    })),
    {
      damaged_components: ["球状船首", "外板"],
      vessel_name: "PWA demo",
      source_pdf: fileName,
    },
    state.nplScorer,
    {
      dockingContext: state.dockingContext,
      assumeStatutoryOwnerWork: state.includeStatutory,
    },
  );
  state.uc2Analyzed = analyzed;
  render();
}

function renderUc3(root: HTMLElement): void {
  const view = buildUc3();
  const geom = geometryForCase();
  const verdict = classifyEncounter(geom);
  const rad = (verdict.relative_bearing_a_to_b_deg * Math.PI) / 180;
  const tx = Math.sin(rad);
  const ty = Math.cos(rad);
  const options = [
    { id: "civil_7", title: state.civil7?.title || "Civil #7" },
    ...state.jmatCases.slice(0, 20).map((c) => ({ id: c.case_id!, title: c.title || c.case_id! })),
  ];
  const pending = state.uc3Pending && !state.uc3Confirmed ? state.uc3Pending : null;
  const pendingExt = pending?.extraction as ColregsExtraction | undefined;

  const resultsPanel = pending
    ? `<section class="panel">
        ${reviewBannerHtml(pending)}
        <div class="review-fields">
          <label>${escapeHtml(t("heading_a", state.lang))}
            <input type="number" id="revHdgA" value="${escapeHtml(pendingExt?.payload.geometry.heading_a_deg ?? state.headingA)}">
          </label>
          <label>${escapeHtml(t("heading_b", state.lang))}
            <input type="number" id="revHdgB" value="${escapeHtml(pendingExt?.payload.geometry.heading_b_deg ?? state.headingB)}">
          </label>
          <label>${escapeHtml(t("bearing_ab", state.lang))}
            <input type="number" id="revBrg" value="${escapeHtml(pendingExt?.payload.geometry.true_bearing_a_to_b_deg ?? state.bearingAb)}">
          </label>
          <label>${escapeHtml(t("facts", state.lang))}
            <textarea id="revFacts" rows="4">${escapeHtml(pendingExt?.payload.facts_excerpt || view.facts)}</textarea>
          </label>
          <label>${escapeHtml(view.document_kind === "jtsb" ? t("ruling_jtsb", state.lang) : t("ruling", state.lang))}
            <textarea id="revRuling" rows="4">${escapeHtml(pendingExt?.payload.ruling_excerpt || view.ruling)}</textarea>
          </label>
        </div>
        <div class="actions">
          <button type="button" class="btn" id="confirmScoreUc3">${escapeHtml(t("confirm_and_score", state.lang))}</button>
        </div>
      </section>`
    : `<section class="panel">
        <h2>${escapeHtml(view.title)}</h2>
        <dl class="metrics">
          <div><dt>${escapeHtml(t("situation", state.lang))}</dt><dd>${escapeHtml(view.situation_label)}</dd></div>
          <div><dt>${escapeHtml(t("role_a", state.lang))}</dt><dd>${escapeHtml(view.role_a_label)}</dd></div>
          <div><dt>${escapeHtml(t("role_b", state.lang))}</dt><dd>${escapeHtml(view.role_b_label)}</dd></div>
          <div><dt>${escapeHtml(t("fault_ratio", state.lang))}</dt><dd><strong>${escapeHtml(view.fault_ratio)}</strong></dd></div>
        </dl>
        <h3>${escapeHtml(t("radar_title", state.lang))}</h3>
        <svg class="radar" viewBox="-1.2 -1.2 2.4 2.4">
          <circle cx="0" cy="0" r="1" fill="none" stroke="currentColor" opacity="0.3"/>
          <circle cx="0" cy="0" r="0.5" fill="none" stroke="currentColor" opacity="0.2"/>
          <line x1="0" y1="-1.1" x2="0" y2="1.1" stroke="currentColor" opacity="0.2"/>
          <line x1="-1.1" y1="0" x2="1.1" y2="0" stroke="currentColor" opacity="0.2"/>
          <path d="M ${Math.sin((OVERTAKING_RELATIVE_BEARING_MIN_DEG * Math.PI) / 180)} ${-Math.cos((OVERTAKING_RELATIVE_BEARING_MIN_DEG * Math.PI) / 180)}
                   A 1 1 0 0 1 ${Math.sin((OVERTAKING_RELATIVE_BEARING_MAX_DEG * Math.PI) / 180)} ${-Math.cos((OVERTAKING_RELATIVE_BEARING_MAX_DEG * Math.PI) / 180)}"
                fill="rgba(201,162,39,0.15)" stroke="none"/>
          <circle cx="0" cy="0" r="0.06" fill="var(--accent)"/>
          <circle cx="${tx}" cy="${-ty}" r="0.08" fill="var(--warn)"/>
        </svg>
        <p class="muted">${escapeHtml(t("article", state.lang))}: ${escapeHtml((view.rule_citations || []).join(" · ") || "—")}</p>
        <h3>${escapeHtml(t("facts", state.lang))}</h3>
        ${state.civil7?.case_id === "upload" ? `<p class="muted facts-note">${escapeHtml(t("facts_pdf_notice", state.lang))}</p>` : ""}
        <pre class="facts">${escapeHtml(view.facts || t("facts_empty", state.lang))}</pre>
        <h3>${escapeHtml(view.document_kind === "jtsb" ? t("ruling_jtsb", state.lang) : t("ruling", state.lang))}</h3>
        <pre class="facts">${escapeHtml(view.ruling?.trim() ? view.ruling : t("ruling_empty", state.lang))}</pre>
        <div class="actions">
          <button type="button" class="btn" id="exp3Md">${escapeHtml(t("export_colregs_md", state.lang))}</button>
          <button type="button" class="btn" id="exp3Html">${escapeHtml(t("export_colregs_html", state.lang))}</button>
        </div>
      </section>`;

  root.innerHTML = `
    ${briefingBox("uc3")}
    <p class="lead">${escapeHtml(t("uc3_lead", state.lang))}</p>
    ${explainBox("uc3")}
    <div class="grid-2">
      <section class="panel">
        <label>${escapeHtml(t("select_case", state.lang))}
          <select id="caseSel">
            ${options
              .map(
                (o) =>
                  `<option value="${escapeHtml(o.id)}" ${o.id === state.caseId ? "selected" : ""}>${escapeHtml(o.title)}</option>`,
              )
              .join("")}
          </select>
        </label>
        <label class="check"><input type="checkbox" id="ovrGeom" ${state.overrideGeom ? "checked" : ""}> ${escapeHtml(t("geometry_override", state.lang))}</label>
        <label>${escapeHtml(t("heading_a", state.lang))}
          <input type="number" id="hdgA" value="${state.headingA}" ${state.overrideGeom ? "" : "disabled"}>
        </label>
        <label>${escapeHtml(t("heading_b", state.lang))}
          <input type="number" id="hdgB" value="${state.headingB}" ${state.overrideGeom ? "" : "disabled"}>
        </label>
        <label>${escapeHtml(t("bearing_ab", state.lang))}
          <input type="number" id="brg" value="${state.bearingAb}" ${state.overrideGeom ? "" : "disabled"}>
        </label>
        ${
          !state.overrideGeom
            ? `<p class="muted">${escapeHtml(t("geometry_narrative_derived", state.lang))}</p>`
            : ""
        }
        <div class="dropzone" id="pdfDrop3">${escapeHtml(t("drop_pdf", state.lang))}<input type="file" id="pdfFile3" accept="application/pdf" hidden></div>
        ${state.ocrBusy && state.tab === "uc3" ? `<p class="warn" id="ocrBusy">${escapeHtml(state.ocrBusy)}</p>` : ""}
        ${routerPanelHtml("uc3", state.uc3Upload, "analyzeUc3")}
      </section>
      ${resultsPanel}
    </div>
  `;

  root.querySelector("#caseSel")?.addEventListener("change", (e) => {
    state.caseId = (e.target as HTMLSelectElement).value;
    state.uc3Pending = null;
    state.uc3Confirmed = false;
    state.uc3Upload = null;
    state.overrideGeom = false;
    if (state.caseId === "civil_7") {
      const seed = state.seeds.find((s) => s.case_id === "7" || s.case_id === "civil_7");
      if (seed) state.civil7 = { ...seed, case_id: "civil_7" };
    }
    syncDisplayGeometryFromCase();
    render();
  });
  root.querySelector("#ovrGeom")?.addEventListener("change", (e) => {
    state.overrideGeom = (e.target as HTMLInputElement).checked;
    if (!state.overrideGeom) syncDisplayGeometryFromCase();
    render();
  });
  for (const [id, key] of [
    ["hdgA", "headingA"],
    ["hdgB", "headingB"],
    ["brg", "bearingAb"],
  ] as const) {
    root.querySelector(`#${id}`)?.addEventListener("change", (e) => {
      (state as unknown as Record<string, number>)[key] = Number((e.target as HTMLInputElement).value);
      state.overrideGeom = true;
      render();
    });
  }

  root.querySelector("#confirmScoreUc3")?.addEventListener("click", () => {
    const hdgA = Number((root.querySelector("#revHdgA") as HTMLInputElement)?.value);
    const hdgB = Number((root.querySelector("#revHdgB") as HTMLInputElement)?.value);
    const brg = Number((root.querySelector("#revBrg") as HTMLInputElement)?.value);
    const facts = (root.querySelector("#revFacts") as HTMLTextAreaElement)?.value ?? "";
    const ruling = (root.querySelector("#revRuling") as HTMLTextAreaElement)?.value ?? "";
    state.headingA = hdgA;
    state.headingB = hdgB;
    state.bearingAb = brg;
    state.overrideGeom = true;
    if (state.civil7) {
      state.civil7 = {
        ...state.civil7,
        input_facts: facts,
        holding: ruling,
      };
    }
    state.uc3Confirmed = true;
    state.uc3Pending = null;
    render();
  });

  root.querySelector("#routerOverride_uc3")?.addEventListener("change", (e) => {
    if (!state.uc3Upload) return;
    const v = (e.target as HTMLSelectElement).value;
    state.uc3Upload = {
      ...state.uc3Upload,
      override: v ? (v as DocumentType) : null,
    };
    render();
  });
  root.querySelector("#analyzeUc3")?.addEventListener("click", () => {
    void analyzeUc3Upload();
  });

  const drop = root.querySelector("#pdfDrop3") as HTMLElement;
  const fileInput = root.querySelector("#pdfFile3") as HTMLInputElement;
  drop?.addEventListener("click", () => fileInput?.click());
  fileInput?.addEventListener("change", async () => {
    const f = fileInput.files?.[0];
    if (!f) return;
    state.ocrBusy = null;
    const extracted = await extractPdfTextWithOcr(f, {
      extractText: extractPdfText,
      onProgress: (p) => {
        const pct = Math.round(p.progress * 100);
        state.ocrBusy = `${t("ocr_in_progress", state.lang)} (${pct}%)`;
        const el = document.querySelector("#ocrBusy");
        if (el) el.textContent = state.ocrBusy;
        else render();
      },
    });
    state.ocrBusy = null;
    if (!extracted.text.trim()) {
      alert(t(extracted.error ? "ocr_failed" : "err_pdf_empty_text", state.lang));
      render();
      return;
    }
    const classification = classifyDocument(extracted.text, { filename: f.name });
    state.uc3Upload = {
      text: extracted.text,
      filename: f.name,
      classification,
      override: null,
      extractionSource: extracted.source,
    };
    state.uc3Pending = null;
    state.uc3Confirmed = false;
    render();
  });

  root.querySelector("#exp3Md")?.addEventListener("click", () => {
    downloadText("colregs.md", colregsMarkdown(view, state.lang), "text/markdown");
  });
  root.querySelector("#exp3Html")?.addEventListener("click", () => {
    downloadText("colregs.html", colregsHtml(view, state.lang), "text/html");
  });
}

async function analyzeUc3Upload(): Promise<void> {
  const upload = state.uc3Upload;
  if (!upload) return;
  const decision = resolveDocumentRoute("uc3", upload.classification, upload.override);
  if (!decision.allowed) {
    alert(
      decision.reason === "unknown"
        ? t("router_blocked_unknown", state.lang)
        : t("router_blocked_mismatch", state.lang),
    );
    return;
  }
  const text = upload.text;
  const fName = upload.filename;
  const extracted = extractFromJudgment(text);
  const jtsbReport =
    decision.effective === "jtsb_report" || isLikelyJtsbReport(text);
  let holding = extracted.holding_excerpt || "";
  if (!holding) {
    holding = extractJtsbCauseExcerpt(text) || "";
  }
  const facts = extractFactsExcerpt(text);
  const documentKind = jtsbReport ? "jtsb" : "judgment";
  const telemetry = extractColregsTelemetry(text);
  const extractedGeom = telemetryToGeometry(telemetry, {
    speed_a_kn: 12,
    speed_b_kn: 10,
    range_nm: 0.8,
  });
  const geometryComplete = extractedGeom != null;
  if (extractedGeom) {
    state.headingA = extractedGeom.heading_a_deg;
    state.headingB = extractedGeom.heading_b_deg;
    state.bearingAb = extractedGeom.true_bearing_a_to_b_deg;
  }
  const geometry: EncounterGeometry = extractedGeom ?? {
    heading_a_deg: state.headingA,
    heading_b_deg: state.headingB,
    true_bearing_a_to_b_deg: state.bearingAb,
    speed_a_kn: 12,
    speed_b_kn: 10,
    range_nm: 0.8,
  };
  try {
    const extraction = buildColregsExtraction({
      geometry,
      factsExcerpt: facts || undefined,
      rulingExcerpt: holding || undefined,
      faultRatioHint: extracted.fault_ratio || undefined,
      documentKind,
      confidence:
        upload.extractionSource === "ocr" ? OCR_STAGE_A_CONFIDENCE : 0.55,
      field_confidence: {
        ...telemetryFieldConfidence(telemetry),
        ...(geometryComplete ? {} : { geometry_missing: 0 }),
      },
      grounding: [
        facts ? { field: "facts_excerpt", source_quote: facts.slice(0, 240) } : null,
        holding ? { field: "ruling_excerpt", source_quote: holding.slice(0, 240) } : null,
        ...(geometryComplete ? telemetryGrounding(telemetry) : []),
      ].filter((g): g is { field: string; source_quote: string } => g != null),
      groundingMode: "require_span",
      confidenceMode: "enforce",
      sourceText: text,
    });
    state.caseId = "civil_7";
    state.civil7 = {
      case_id: "upload",
      title: fName,
      input_facts: facts,
      holding,
      fault_ratio: extracted.fault_ratio || "",
      document_kind: documentKind,
    };
    // Complete triad: keep override off so fields stay disabled and match Stage B (#102).
    // Incomplete triad: enable override so the operator can edit via review / inputs.
    state.overrideGeom = !geometryComplete;
    state.uc3Confirmed = false;
    if (extraction.abstain) {
      state.uc3Pending = {
        extraction,
        reasons: extraction.abstain.reason.split("; ").slice(1),
      };
    } else {
      state.uc3Pending = null;
      state.uc3Confirmed = true;
    }
    render();
  } catch (err) {
    if (
      err instanceof ExtractionValidationError ||
      err instanceof GroundingValidationError
    ) {
      alert(t("err_schema_invalid", state.lang));
      return;
    }
    throw err;
  }
}

function buildPscReport(): { report: SeaworthinessRiskReport; title: string } {
  if (state.pscPending && !state.pscConfirmed) {
    return {
      report: scoreSeaworthiness([]),
      title: state.pscPasteLabel || state.pscCaseId || "—",
    };
  }

  if (state.pscUsePaste && state.pscPasteCurrent.length) {
    const run = runPsc({
      deficiencies: state.pscPasteCurrent,
      prior: state.pscPastePrior,
      mouId: state.pscPasteMou,
      cicWeights: state.pscPasteCic,
      lookbackMonths: state.pscLookbackMonths,
      confidence: state.pscConfirmed ? 0.85 : 0.75,
      groundingMode: "paste_bypass",
      confidenceMode: state.pscConfirmed ? "confirmed" : "bypass",
    });
    if (run.status === "abstain") {
      state.pscPending = { extraction: run.extraction, reasons: run.reasons };
      return {
        report: scoreSeaworthiness([]),
        title: state.pscPasteLabel || "pasted",
      };
    }
    return { report: run.report, title: state.pscPasteLabel || "pasted" };
  }
  const fixture =
    state.pscFixtures.find((c) => c.id === state.pscCaseId) ||
    state.pscFixtures[0] ||
    null;
  if (!fixture) {
    return {
      report: scoreSeaworthiness([]),
      title: state.pscCaseId || "—",
    };
  }
  const run = runPscFixture(fixture, {
    lookbackMonths: state.pscLookbackMonths,
  });
  if (run.status === "abstain") {
    state.pscPending = { extraction: run.extraction, reasons: run.reasons };
    return {
      report: scoreSeaworthiness([]),
      title: fixture.id,
    };
  }
  return { report: run.report, title: fixture.id };
}

/** JSON / CSV paste vs MOU document text (#92). */
function looksLikeStructuredPscPaste(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  if (looksLikeHtml(t)) return false;
  if (t.startsWith("{") || t.startsWith("[")) return true;
  const header = (t.split(/\n/)[0] || "").toLowerCase();
  return /deficiency_code|def_code|action_taken|nature_of_deficiency/.test(header);
}

function buildPscView(): PscView {
  const { report, title } = buildPscReport();
  return {
    title,
    mou_id: report.mou_id,
    lookback_months: state.pscLookbackMonths,
    defect_score: report.defect_score,
    risk_band: report.risk_band,
    detention_present: report.detention_present,
    repeat_critical_flags: report.repeat_critical_flags,
    notes: report.notes,
    convention_citations: report.convention_citations,
    deficiencies: report.deficiencies.map((d) => ({
      code: d.code,
      action_code: d.action_code,
      description: d.description,
      category_label: d.category_label,
      convention: d.convention,
      critical_system: d.critical_system,
      is_repeat_critical: d.is_repeat_critical,
      contribution: d.contribution,
    })),
  };
}

function renderPsc(root: HTMLElement): void {
  const view = buildPscView();
  const options =
    state.pscFixtures.length > 0
      ? state.pscFixtures
      : [{ id: state.pscCaseId || "repeat_ism_major" } as PscFixtureCase];
  const bandClass =
    view.risk_band === "critical"
      ? "band-critical"
      : view.risk_band === "elevated"
        ? "band-elevated"
        : "band-low";
  const pending = state.pscPending && !state.pscConfirmed ? state.pscPending : null;

  const resultsPanel = pending
    ? `<section class="panel">
        ${reviewBannerHtml(pending)}
        <p class="muted">${escapeHtml(t("psc_disclaimer", state.lang))}</p>
        <div class="actions">
          <button type="button" class="btn" id="confirmScorePsc">${escapeHtml(t("confirm_and_score", state.lang))}</button>
        </div>
      </section>`
    : `<section class="panel">
        <h2>${escapeHtml(view.title)}</h2>
        <dl class="metrics">
          <div><dt>${escapeHtml(t("psc_defect_score", state.lang))}</dt><dd><strong>${escapeHtml(view.defect_score)}</strong></dd></div>
          <div><dt>${escapeHtml(t("psc_risk_band", state.lang))}</dt><dd><span class="risk-band ${bandClass}">${escapeHtml(t(`psc_band_${view.risk_band}`, state.lang))}</span></dd></div>
          <div><dt>${escapeHtml(t("psc_detention", state.lang))}</dt><dd>${escapeHtml(
            view.detention_present ? t("psc_present", state.lang) : t("psc_absent", state.lang),
          )}</dd></div>
          <div><dt>${escapeHtml(t("psc_repeat_flags", state.lang))}</dt><dd>${escapeHtml(
            view.repeat_critical_flags.join(", ") || "—",
          )}</dd></div>
        </dl>
        ${view.notes ? `<p class="muted">${escapeHtml(view.notes)}</p>` : ""}
        <table class="lines">
          <thead><tr>
            <th>${escapeHtml(t("psc_col_code", state.lang))}</th>
            <th>${escapeHtml(t("psc_col_action", state.lang))}</th>
            <th>${escapeHtml(t("psc_col_nature", state.lang))}</th>
            <th>${escapeHtml(t("psc_col_repeat", state.lang))}</th>
            <th>${escapeHtml(t("psc_col_contrib", state.lang))}</th>
          </tr></thead>
          <tbody>
            ${
              view.deficiencies.length
                ? view.deficiencies
                    .map(
                      (d) => `<tr>
              <td><code>${escapeHtml(d.code)}</code></td>
              <td>${escapeHtml(d.action_code || "—")}</td>
              <td>${escapeHtml(d.description || d.category_label || "—")}</td>
              <td>${escapeHtml(
                d.is_repeat_critical ? t("psc_yes", state.lang) : t("psc_no", state.lang),
              )}</td>
              <td class="num">${escapeHtml(d.contribution)}</td>
            </tr>`,
                    )
                    .join("")
                : `<tr><td colspan="5">—</td></tr>`
            }
          </tbody>
        </table>
        <div class="actions">
          <button type="button" class="btn" id="expPscMd">${escapeHtml(t("export_psc_md", state.lang))}</button>
          <button type="button" class="btn" id="expPscHtml">${escapeHtml(t("export_psc_html", state.lang))}</button>
        </div>
      </section>`;

  root.innerHTML = `
    ${briefingBox("psc")}
    <p class="lead">${escapeHtml(t("psc_lead", state.lang))}</p>
    ${explainBox("psc")}
    <div class="grid-2">
      <section class="panel">
        <label>${escapeHtml(t("select_psc_fixture", state.lang))}
          <select id="pscCaseSel" ${state.pscUsePaste ? "disabled" : ""}>
            ${options
              .map(
                (o) =>
                  `<option value="${escapeHtml(o.id)}" ${o.id === state.pscCaseId ? "selected" : ""}>${escapeHtml(o.id)}${
                    o.mou_id ? ` (${escapeHtml(String(o.mou_id))})` : ""
                  }</option>`,
              )
              .join("")}
          </select>
        </label>
        <label>${escapeHtml(t("psc_lookback", state.lang))}
          <input type="range" id="pscLookback" min="3" max="60" step="1" value="${state.pscLookbackMonths}">
          <span id="pscLookbackVal">${state.pscLookbackMonths}</span>
        </label>
        <div class="dropzone" id="pdfDropPsc">${escapeHtml(t("drop_psc", state.lang))}<input type="file" id="pdfFilePsc" accept="application/pdf,.html,.htm,text/html,image/png,image/jpeg,image/webp,text/plain" hidden></div>
        ${state.ocrBusy && state.tab === "psc" ? `<p class="warn" id="ocrBusy">${escapeHtml(state.ocrBusy)}</p>` : ""}
        <label>${escapeHtml(t("psc_paste", state.lang))}
          <textarea id="pscPaste" rows="6" placeholder="${escapeHtml(t("psc_paste_hint", state.lang))}">${escapeHtml(state.pscPasteText)}</textarea>
        </label>
        ${routerPanelHtml("psc", state.pscUpload, "analyzePsc")}
        <div class="actions">
          <button type="button" class="btn" id="pscLoadSample">${escapeHtml(t("psc_load_sample", state.lang))}</button>
          <button type="button" class="btn" id="pscApplyPaste">${escapeHtml(t("psc_apply_paste", state.lang))}</button>
          <button type="button" class="btn" id="pscClearPaste">${escapeHtml(t("psc_clear_paste", state.lang))}</button>
        </div>
        <p class="muted">${escapeHtml(t("psc_disclaimer", state.lang))}</p>
      </section>
      ${resultsPanel}
    </div>
  `;

  root.querySelector("#pscCaseSel")?.addEventListener("change", (e) => {
    state.pscCaseId = (e.target as HTMLSelectElement).value;
    state.pscUsePaste = false;
    state.pscFromDocument = false;
    state.pscUpload = null;
    state.pscPending = null;
    state.pscConfirmed = false;
    render();
  });
  root.querySelector("#pscLookback")?.addEventListener("input", (e) => {
    state.pscLookbackMonths = Number((e.target as HTMLInputElement).value);
    const val = root.querySelector("#pscLookbackVal");
    if (val) val.textContent = String(state.pscLookbackMonths);
  });
  root.querySelector("#pscLookback")?.addEventListener("change", (e) => {
    state.pscLookbackMonths = Number((e.target as HTMLInputElement).value);
    render();
  });
  root.querySelector("#pscPaste")?.addEventListener("change", (e) => {
    state.pscPasteText = (e.target as HTMLTextAreaElement).value;
  });
  root.querySelector("#routerOverride_psc")?.addEventListener("change", (e) => {
    if (!state.pscUpload) return;
    const v = (e.target as HTMLSelectElement).value;
    state.pscUpload = {
      ...state.pscUpload,
      override: v ? (v as DocumentType) : null,
    };
    render();
  });
  root.querySelector("#analyzePsc")?.addEventListener("click", () => {
    void analyzePscUpload();
  });
  root.querySelector("#confirmScorePsc")?.addEventListener("click", () => {
    state.pscConfirmed = true;
    state.pscPending = null;
    render();
  });
  root.querySelector("#pscLoadSample")?.addEventListener("click", () => {
    void loadPscSampleHtml();
  });
  root.querySelector("#pscApplyPaste")?.addEventListener("click", () => {
    const ta = root.querySelector("#pscPaste") as HTMLTextAreaElement | null;
    const text = ta?.value ?? state.pscPasteText;
    state.pscPasteText = text;
    if (!text.trim()) {
      alert(t("psc_err_empty", state.lang));
      return;
    }
    const classification = classifyDocument(text, { filename: "paste.txt" });
    state.pscUpload = {
      text,
      filename: "paste.txt",
      classification,
      override: null,
      extractionSource: "text_layer",
    };
    state.pscFromDocument = !looksLikeStructuredPscPaste(text);
    const decision = resolveDocumentRoute("psc", classification, null);
    if (!decision.allowed) {
      state.pscUsePaste = false;
      state.pscPasteCurrent = [];
      render();
      return;
    }
    void analyzePscUpload();
  });
  root.querySelector("#pscClearPaste")?.addEventListener("click", () => {
    state.pscUsePaste = false;
    state.pscFromDocument = false;
    state.pscPasteCurrent = [];
    state.pscPastePrior = null;
    state.pscPasteCic = null;
    state.pscPasteMou = null;
    state.pscPasteLabel = "";
    state.pscPasteText = "";
    state.pscPending = null;
    state.pscConfirmed = false;
    state.pscUpload = null;
    render();
  });

  const drop = root.querySelector("#pdfDropPsc") as HTMLElement;
  const fileInput = root.querySelector("#pdfFilePsc") as HTMLInputElement;
  drop?.addEventListener("click", () => fileInput?.click());
  drop?.addEventListener("dragover", (e) => {
    e.preventDefault();
  });
  drop?.addEventListener("drop", (e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f) void handlePscFile(f);
  });
  fileInput?.addEventListener("change", async () => {
    const f = fileInput.files?.[0];
    if (f) await handlePscFile(f);
  });

  root.querySelector("#expPscMd")?.addEventListener("click", () => {
    downloadText("psc_memo.md", pscMarkdown(view, state.lang), "text/markdown");
  });
  root.querySelector("#expPscHtml")?.addEventListener("click", () => {
    downloadText("psc_memo.html", pscHtml(view, state.lang), "text/html");
  });
}

async function loadPscSampleHtml(): Promise<void> {
  const base = import.meta.env.BASE_URL || "./";
  try {
    const res = await fetch(`${base}data/psc_sample_inspection.txt`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const classification = classifyDocument(text, {
      filename: "psc_sample_inspection.txt",
    });
    state.pscUpload = {
      text,
      filename: "psc_sample_inspection.txt",
      classification,
      override: null,
      extractionSource: "text_layer",
    };
    state.pscFromDocument = true;
    state.pscPending = null;
    state.pscConfirmed = false;
    render();
  } catch (err) {
    console.error("[psc] sample load failed", err);
    alert(t("psc_err_document", state.lang));
  }
}

async function handlePscFile(file: File): Promise<void> {
  state.ocrBusy = null;
  const name = file.name.toLowerCase();
  const isHtml = /\.html?$/.test(name) || file.type.includes("html");
  const isImage = /^image\//.test(file.type) || /\.(png|jpe?g|webp)$/.test(name);
  const isPdf = file.type === "application/pdf" || name.endsWith(".pdf");

  let text = "";
  let extractionSource: PdfExtractionSource = "text_layer";

  if (isHtml || (!isPdf && !isImage && name.endsWith(".txt"))) {
    text = await file.text();
  } else if (isImage) {
    state.ocrBusy = t("ocr_in_progress", state.lang);
    render();
    try {
      const ocr = await ocrImageFile(file, {
        onProgress: (p) => {
          const pct = Math.round(p.progress * 100);
          state.ocrBusy = `${t("ocr_in_progress", state.lang)} (${pct}%)`;
          const el = document.querySelector("#ocrBusy");
          if (el) el.textContent = state.ocrBusy;
          else render();
        },
      });
      text = ocr.text;
      extractionSource = "ocr";
    } catch (err) {
      console.error("[ocr] PSC image failed", err);
      state.ocrBusy = null;
      alert(t("ocr_failed", state.lang));
      render();
      return;
    }
    state.ocrBusy = null;
  } else {
    // PDF (default)
    state.ocrBusy = t("ocr_in_progress", state.lang);
    render();
    const extracted = await extractPdfTextWithOcr(file, {
      extractText: extractPdfText,
      onProgress: (p) => {
        const pct = Math.round(p.progress * 100);
        state.ocrBusy = `${t("ocr_in_progress", state.lang)} (${pct}%)`;
        const el = document.querySelector("#ocrBusy");
        if (el) el.textContent = state.ocrBusy;
        else render();
      },
    });
    state.ocrBusy = null;
    if (!extracted.text.trim()) {
      alert(t(extracted.error ? "ocr_failed" : "err_pdf_empty_text", state.lang));
      render();
      return;
    }
    text = extracted.text;
    extractionSource = extracted.source;
  }

  if (!text.trim()) {
    alert(t("psc_err_document", state.lang));
    render();
    return;
  }

  const classification = classifyDocument(text, { filename: file.name });
  state.pscUpload = {
    text,
    filename: file.name,
    classification,
    override: null,
    extractionSource,
  };
  state.pscFromDocument = true;
  state.pscPending = null;
  state.pscConfirmed = false;
  state.pscUsePaste = false;
  render();
}

async function analyzePscUpload(): Promise<void> {
  const upload = state.pscUpload;
  if (!upload) return;
  const decision = resolveDocumentRoute("psc", upload.classification, upload.override);
  if (!decision.allowed) {
    alert(
      decision.reason === "unknown"
        ? t("router_blocked_unknown", state.lang)
        : t("router_blocked_mismatch", state.lang),
    );
    return;
  }
  const text = upload.text;
  const asPaste = looksLikeStructuredPscPaste(text) && !state.pscFromDocument;

  try {
    if (asPaste) {
      const parsed = tryParsePscPaste(text);
      if (!parsed.current.length) {
        alert(t("psc_err_empty", state.lang));
        return;
      }
      buildPscExtraction({
        deficiencies: parsed.current,
        prior: parsed.prior,
        mouId: parsed.mouId,
        cicWeights: parsed.cicWeights,
        lookbackMonths: state.pscLookbackMonths,
        confidence: 0.75,
        groundingMode: "paste_bypass",
      });
      state.pscPasteCurrent = parsed.current;
      state.pscPastePrior = parsed.prior;
      state.pscPasteCic = parsed.cicWeights;
      state.pscPasteMou = parsed.mouId;
      state.pscPasteLabel = parsed.label;
      state.pscUsePaste = true;
      state.pscFromDocument = false;
      state.pscPending = null;
      state.pscConfirmed = true;
      render();
      return;
    }

    const confidence = stageAConfidenceForSource(upload.extractionSource);
    const run = runPscFromDocument(text, {
      lookbackMonths: state.pscLookbackMonths,
      confidence,
      filename: upload.filename,
    });
    state.pscPasteCurrent = run.deficiencies;
    state.pscPastePrior = run.prior;
    state.pscPasteCic = null;
    state.pscPasteMou = run.mouId;
    state.pscPasteLabel = run.label;
    state.pscUsePaste = true;
    state.pscFromDocument = true;

    if (run.status === "abstain") {
      state.pscPending = { extraction: run.extraction, reasons: run.reasons };
      state.pscConfirmed = false;
    } else {
      state.pscPending = null;
      state.pscConfirmed = true;
    }
    render();
  } catch (err) {
    if (
      err instanceof ExtractionValidationError ||
      err instanceof GroundingValidationError
    ) {
      alert(t("err_schema_invalid", state.lang));
      return;
    }
    if (err instanceof Error && /No deficiencies/i.test(err.message)) {
      alert(t("psc_err_document", state.lang));
      return;
    }
    // Fall back: try paste parser for mixed inputs
    try {
      const parsed = tryParsePscPaste(text);
      if (parsed.current.length) {
        state.pscPasteCurrent = parsed.current;
        state.pscPastePrior = parsed.prior;
        state.pscPasteCic = parsed.cicWeights;
        state.pscPasteMou = parsed.mouId;
        state.pscPasteLabel = parsed.label;
        state.pscUsePaste = true;
        state.pscFromDocument = false;
        state.pscPending = null;
        state.pscConfirmed = true;
        render();
        return;
      }
    } catch {
      /* ignore */
    }
    alert(asPaste ? t("psc_err_paste", state.lang) : t("psc_err_document", state.lang));
  }
}

function render(): void {
  const app = document.querySelector("#app")!;
  app.innerHTML = `
    <header class="topbar">
      <div class="brand-group">
        <div class="brand"><img class="brand-logo" src="./icons/icon.svg" width="28" height="28" alt=""/> ${escapeHtml(t("app_title", state.lang))}</div>
      </div>
      <nav class="nav">
        <button type="button" class="btn ${state.tab === "uc2" ? "active" : ""}" data-tab="uc2">${escapeHtml(t("nav_uc2", state.lang))}</button>
        <button type="button" class="btn ${state.tab === "uc3" ? "active" : ""}" data-tab="uc3">${escapeHtml(t("nav_uc3", state.lang))}</button>
        <button type="button" class="btn ${state.tab === "psc" ? "active" : ""}" data-tab="psc">${escapeHtml(t("nav_psc", state.lang))}</button>
        <label class="lang-select">
          <span class="sr-only">${escapeHtml(t("lang_label", state.lang))}</span>
          <select id="langSel" aria-label="${escapeHtml(t("lang_label", state.lang))}">
            <option value="en" ${state.lang === "en" ? "selected" : ""}>${escapeHtml(t("lang_en", state.lang))}</option>
            <option value="ja" ${state.lang === "ja" ? "selected" : ""}>${escapeHtml(t("lang_ja", state.lang))}</option>
          </select>
        </label>
        <button type="button" class="btn pwa-install" id="pwaInstall" hidden>${escapeHtml(t("pwa_install_btn", state.lang))}</button>
      </nav>
    </header>
    <main id="main" class="main"></main>
  `;
  const main = app.querySelector("#main") as HTMLElement;
  if (state.tab === "uc2") renderUc2(main);
  else if (state.tab === "uc3") renderUc3(main);
  else renderPsc(main);

  app.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.tab = (btn as HTMLElement).dataset.tab as Tab;
      render();
    });
  });
  app.querySelector("#langSel")?.addEventListener("change", (e) => {
    state.lang = (e.target as HTMLSelectElement).value as Lang;
    localStorage.setItem("lang", state.lang);
    render();
  });
}

async function loadData(): Promise<void> {
  const base = import.meta.env.BASE_URL || "./";
  const [rules, civil, jmat, npl, psc] = await Promise.all([
    fetch(`${base}data/fault_ratio_rules.json`).then((r) => r.json()),
    fetch(`${base}data/civil_precedent_catalog.json`).then((r) => r.json()),
    fetch(`${base}data/jmat_collision_eval.json`).then((r) => r.json()),
    fetch(`${base}data/negative_pattern_library.json`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),
    fetch(`${base}data/psc_inspection_fixtures.json`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),
  ]);
  state.rules = rules as FaultRules;
  if (npl?.patterns) {
    state.nplScorer = createNplScorer(npl as NplLibrary);
  }
  if (psc?.cases && Array.isArray(psc.cases)) {
    state.pscFixtures = psc.cases as PscFixtureCase[];
    if (!state.pscFixtures.some((c) => c.id === state.pscCaseId) && state.pscFixtures[0]) {
      state.pscCaseId = state.pscFixtures[0].id;
    }
  }
  const seeds = (civil.seeds || []) as Array<Record<string, unknown>>;
  state.seeds = seeds.map((s) => ({
    case_id: String(s.case_id ?? ""),
    title: String(s.title ?? ""),
    court: String(s.court ?? ""),
    input_facts: String(s.input_facts ?? ""),
    holding: String(s.holding ?? ""),
    fault_ratio: String(s.fault_ratio ?? ""),
  }));
  state.civil7 = state.seeds.find((s) => s.case_id === "7") || null;
  if (state.civil7) state.civil7 = { ...state.civil7, case_id: "civil_7" };
  state.jmatCases = ((jmat.cases || []) as Array<Record<string, unknown>>).map((c) => ({
    case_id: String(c.case_id ?? ""),
    title: String(c.title ?? ""),
    facts_text: String(c.facts_text ?? ""),
    ruling_text: String(c.ruling_text ?? ""),
    expected_situation: String(c.expected_situation ?? ""),
    expected_role_a: String(c.expected_role_a ?? ""),
    expected_role_b: String(c.expected_role_b ?? ""),
  }));
}

function registerPwa(): void {
  let deferred: BeforeInstallPromptEvent | null = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e as BeforeInstallPromptEvent;
    const btn = document.querySelector("#pwaInstall") as HTMLButtonElement | null;
    if (btn) {
      btn.hidden = false;
      btn.onclick = async () => {
        await deferred?.prompt();
        deferred = null;
        btn.hidden = true;
      };
    }
  });
}

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
}

async function main(): Promise<void> {
  render();
  registerPwa();
  try {
    await loadData();
  } catch (err) {
    console.error("fixture load failed", err);
  }
  render();
  try {
    const db = await getDuckDb();
    // Warm Parquet if present
    try {
      const conn = await db.connect();
      const base = import.meta.env.BASE_URL || "./";
      try {
        await conn.query(
          `SELECT COUNT(*) AS n FROM read_parquet('${base}data/civil_precedents.parquet')`,
        );
      } catch {
        /* parquet optional until build:data */
      }
      await conn.close();
    } catch {
      /* ignore */
    }
  } catch (err) {
    console.warn("DuckDB-WASM init failed; using pure-TS engines", err);
  }
}

main();
