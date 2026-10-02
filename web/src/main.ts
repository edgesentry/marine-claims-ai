import "./styles/demo.css";
import { roleLabel, situationLabel, t, displayRule, displayStatus, displayCausalityReason, displayLineTitle, type Lang } from "./i18n";
import {
  classifyEncounter,
  OVERTAKING_RELATIVE_BEARING_MAX_DEG,
  OVERTAKING_RELATIVE_BEARING_MIN_DEG,
  type EncounterGeometry,
} from "./engines/colregs";
import { apportionRuleD, type DockingContext, type RepairLineItem } from "./engines/ruleD5";
import {
  predictFaultRatio,
  type CatalogSeed,
  type FaultRules,
} from "./engines/fault";
import { validateCausality } from "./engines/bfs";
import {
  extractPdfText,
  extractRepairItemsFromText,
  repairItemsToRuleDLines,
  syntheticUc2Lines,
} from "./pdf/parseTender";
import {
  extractFactsExcerpt,
  extractFromJudgment,
  extractJtsbCauseExcerpt,
  isLikelyJtsbReport,
} from "./ingest/civilJudgmentExtractor";
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
  type Uc2View,
  type Uc3View,
} from "./ui/export";
import { getDuckDb } from "./db/duckdb";

type Tab = "uc2" | "uc3";

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
  uc2Analyzed: AnalyzedItem[];
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
  nplScorer: NplScorer;
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
  uc2Analyzed: [],
  caseId: "civil_7",
  headingA: 30,
  headingB: 300,
  bearingAb: 70,
  overrideGeom: false,
  rules: null,
  seeds: [],
  jmatCases: [],
  civil7: null,
  nplScorer: noOpNplScorer,
};

function fmtYen(n: number): string {
  return `¥${n.toLocaleString()}`;
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

function buildUc2(): Uc2View {
  const lines =
    state.uc2Lines.length > 0
      ? state.uc2Lines
      : syntheticUc2Lines(state.dailyDockRate, state.dockDays, state.includeStatutory, state.lang);
  const dockTotal = state.dailyDockRate * state.dockDays;
  const synced = lines.map((ln) =>
    (ln.trade_code || "").startsWith("DOCK") ? { ...ln, cost: dockTotal } : ln,
  );
  const result = apportionRuleD(synced, state.dockingContext);
  const aiDays = state.aiLeadMinutes / (60 * 24);
  const daysSaved = Math.max(0, state.legacyLeadDays - aiDays);
  const offhire = Math.round(daysSaved * state.hireRate);

  void validateCausality("船首", "機関室");

  return {
    rule: result.apportionment_rule,
    dock_total: result.common_dues_total,
    insurer_common: result.insurer_common_share,
    owner_common: result.owner_common_share,
    insurer_total: result.insurer_total,
    owner_total: result.owner_total,
    days_saved: Math.round(daysSaved * 100) / 100,
    offhire_jpy: offhire,
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
  if (state.overrideGeom || state.caseId === "civil_7") {
    return {
      heading_a_deg: state.headingA,
      heading_b_deg: state.headingB,
      true_bearing_a_to_b_deg: state.bearingAb,
      speed_a_kn: 12,
      speed_b_kn: 10,
      range_nm: 0.8,
    };
  }
  const jmat = state.jmatCases.find((c) => c.case_id === state.caseId);
  const sit = jmat?.expected_situation || "crossing";
  const defaults: Record<string, [number, number, number]> = {
    head_on: [0, 180, 0],
    overtaking: [0, 0, 180],
    crossing: [0, 270, 45],
  };
  const [a, b, brg] = defaults[sit] || defaults.crossing!;
  return {
    heading_a_deg: a,
    heading_b_deg: b,
    true_bearing_a_to_b_deg: brg,
    speed_a_kn: 12,
    speed_b_kn: 10,
    range_nm: 1,
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
  const verdict = classifyEncounter(geometry);
  const prediction =
    state.rules != null
      ? predictFaultRatio(facts || ruling || title, state.rules, state.seeds, geometry)
      : null;
  const faultRatio = catalogFault || prediction?.fault_ratio || "70:30";
  const rel = verdict.relative_bearing_a_to_b_deg;

  const documentKind =
    state.caseId === "civil_7" && state.civil7?.document_kind
      ? state.civil7.document_kind
      : undefined;

  return {
    title,
    situation: verdict.situation,
    situation_label: situationLabel(verdict.situation, state.lang),
    role_a_label: roleLabel(verdict.role_a, state.lang),
    role_b_label: roleLabel(verdict.role_b, state.lang),
    fault_ratio: faultRatio,
    relative_bearing: Math.round(rel * 10) / 10,
    rule_citations: verdict.rule_citations,
    facts,
    ruling,
    document_kind: documentKind,
  };
}

function briefingBox(prefix: "uc2" | "uc3"): string {
  return `<aside class="briefing" aria-label="${escapeHtml(t("briefing_label", state.lang))}">
    <h2 class="briefing-title">${escapeHtml(t(`briefing_title_${prefix}`, state.lang))}</h2>
    <div class="briefing-prose">
      <p>${escapeHtml(t(`${prefix}_briefing_p1`, state.lang))}</p>
      <p>${escapeHtml(t(`${prefix}_briefing_p2`, state.lang))}</p>
      <p>${escapeHtml(t(`${prefix}_briefing_p3`, state.lang))}</p>
    </div>
  </aside>`;
}

function explainBox(prefix: "uc2" | "uc3"): string {
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
        <div class="actions">
          <button type="button" class="btn" id="useSynthetic">${escapeHtml(t("use_synthetic", state.lang))}</button>
        </div>
        ${state.uc2FromPdf ? `<p class="ok">${escapeHtml(t("analyzed_ok", state.lang))}</p>` : ""}
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
      <section class="panel">
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
      </section>
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
    state.uc2Analyzed = [];
    render();
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
  const text = await extractPdfText(file);
  if (!text.trim()) {
    alert(t("err_pdf_empty_text", state.lang));
    return;
  }
  const items = extractRepairItemsFromText(text);
  if (!items.length) {
    alert(t("err_no_line_items", state.lang));
    return;
  }
  state.uc2Lines = repairItemsToRuleDLines(items, {
    dailyDockRate: state.dailyDockRate,
    dockDays: state.dockDays,
    includeStatutory: state.includeStatutory,
    lang: state.lang,
  });
  state.uc2FromPdf = true;
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
      source_pdf: file.name,
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
          <input type="number" id="hdgA" value="${state.headingA}" ${state.overrideGeom || state.caseId === "civil_7" ? "" : "disabled"}>
        </label>
        <label>${escapeHtml(t("heading_b", state.lang))}
          <input type="number" id="hdgB" value="${state.headingB}" ${state.overrideGeom || state.caseId === "civil_7" ? "" : "disabled"}>
        </label>
        <label>${escapeHtml(t("bearing_ab", state.lang))}
          <input type="number" id="brg" value="${state.bearingAb}" ${state.overrideGeom || state.caseId === "civil_7" ? "" : "disabled"}>
        </label>
        <div class="dropzone" id="pdfDrop3">${escapeHtml(t("drop_pdf", state.lang))}<input type="file" id="pdfFile3" accept="application/pdf" hidden></div>
      </section>
      <section class="panel">
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
      </section>
    </div>
  `;

  root.querySelector("#caseSel")?.addEventListener("change", (e) => {
    state.caseId = (e.target as HTMLSelectElement).value;
    if (state.caseId === "civil_7") {
      state.headingA = 30;
      state.headingB = 300;
      state.bearingAb = 70;
    }
    render();
  });
  root.querySelector("#ovrGeom")?.addEventListener("change", (e) => {
    state.overrideGeom = (e.target as HTMLInputElement).checked;
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

  const drop = root.querySelector("#pdfDrop3") as HTMLElement;
  const fileInput = root.querySelector("#pdfFile3") as HTMLInputElement;
  drop?.addEventListener("click", () => fileInput?.click());
  fileInput?.addEventListener("change", async () => {
    const f = fileInput.files?.[0];
    if (!f) return;
    const text = await extractPdfText(f);
    if (!text.trim()) {
      alert(t("err_pdf_empty_text", state.lang));
      return;
    }
    const extracted = extractFromJudgment(text);
    const jtsbReport = isLikelyJtsbReport(text);
    let holding = extracted.holding_excerpt || "";
    if (!holding) {
      holding = extractJtsbCauseExcerpt(text) || "";
    }
    state.caseId = "civil_7";
    state.civil7 = {
      case_id: "upload",
      title: f.name,
      input_facts: extractFactsExcerpt(text),
      holding,
      fault_ratio: extracted.fault_ratio || "",
      document_kind: jtsbReport ? "jtsb" : "judgment",
    };
    state.overrideGeom = true;
    render();
  });

  root.querySelector("#exp3Md")?.addEventListener("click", () => {
    downloadText("colregs.md", colregsMarkdown(view, state.lang), "text/markdown");
  });
  root.querySelector("#exp3Html")?.addEventListener("click", () => {
    downloadText("colregs.html", colregsHtml(view, state.lang), "text/html");
  });
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
  else renderUc3(main);

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
  const [rules, civil, jmat, npl] = await Promise.all([
    fetch(`${base}data/fault_ratio_rules.json`).then((r) => r.json()),
    fetch(`${base}data/civil_precedent_catalog.json`).then((r) => r.json()),
    fetch(`${base}data/jmat_collision_eval.json`).then((r) => r.json()),
    fetch(`${base}data/negative_pattern_library.json`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),
  ]);
  state.rules = rules as FaultRules;
  if (npl?.patterns) {
    state.nplScorer = createNplScorer(npl as NplLibrary);
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
