/**
 * PSC Stage A: MOU-style PDF/HTML/OCR text → deficiency rows + Exact Span grounding (#92).
 * Table / portal layouts only — not live scrape. Feeds existing parseDeficiencyItem / scoreSeaworthiness.
 */
import {
  normalizeActionCode,
  normalizeDeficiencyCode,
  parseDeficiencyItem,
  type NormalizedDeficiency,
} from "../engines/psc";
import { normalizePscActionPhrase } from "../pipeline/normalizeLabels";
import type { GroundingRef } from "../schemas";

export interface PscDocumentExtract {
  deficiencies: NormalizedDeficiency[];
  prior: NormalizedDeficiency[];
  mouId: string | null;
  inspectionDate: string | null;
  grounding: GroundingRef[];
  /** Document-level confidence hint (table rows found vs sparse). */
  confidence: number;
  label: string;
}

const DEF_CODE_RE = /\b((?:0[1-9]|1[0-5])\d{3})\b/g;
const ACTION_NEAR_RE =
  /(?:action(?:\s*(?:taken|code))?|是正(?:措置)?|detention|拘留)\s*[:：#]?\s*(?:code\s*)?(\d{1,3})\b/i;
const ACTION_INLINE_RE = /\b(?:code\s*)?(15|16|17|19|21|30)\b/i;
const DETENTION_WORD_RE = /\bdetain(?:ion|ed)?\b|拘留|留置/i;
const DATE_ISO_RE = /\b(20\d{2})-(\d{2})-(\d{2})\b/;
const DATE_DMY_RE =
  /\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b|\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(20\d{2})\b/i;
const MOU_RE = /\bTokyo\s+MOU\b|\bParis\s+MOU\b|東京MOU|パリMOU/i;
const PRIOR_HEADING_RE =
  /prior\s+(?:inspection|deficien)|previous\s+(?:inspection|deficien)|過去\s*(?:検査|欠陥)|lookback|履歴/i;
const CURRENT_HEADING_RE =
  /current\s+inspection|this\s+inspection|今回(?:の)?検査|deficienc(?:y|ies)\s+list|検査結果/i;

const MONTHS: Record<string, string> = {
  jan: "01",
  feb: "02",
  mar: "03",
  apr: "04",
  may: "05",
  jun: "06",
  jul: "07",
  aug: "08",
  sep: "09",
  oct: "10",
  nov: "11",
  dec: "12",
};

/** Strip HTML markup to line-oriented plain text (no DOM write-back). */
export function htmlToPlainText(html: string): string {
  const trimmed = html.trim();
  if (!trimmed) return "";
  // Tag strip only — never parseInto DOM / never re-inject as HTML (CodeQL).
  // Structural closers become newlines/tabs so MOU table cells stay row-oriented.
  const plain = trimmed
    .replace(/<\s*br\s*\/?\s*>/gi, "\n")
    .replace(/<\s*\/\s*(tr|p|div|li|h[1-6]|table)\s*>/gi, "\n")
    .replace(/<\s*\/\s*(td|th)\s*>/gi, "\t")
    .replace(/<[^>]*>/g, " ")
    // Whitespace entities only; skip &amp;/&lt; unescape to avoid double-unescape chains.
    .replace(/&nbsp;/gi, " ")
    .replace(/&#160;/g, " ");
  return collapseWs(plain);
}

function collapseWs(text: string): string {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

/** True when input looks like markup rather than JSON/CSV paste. */
export function looksLikeHtml(text: string): boolean {
  const t = text.trim();
  return /^<!DOCTYPE\s+html/i.test(t) || /<(?:html|table|tr|td|th|div|body)\b/i.test(t);
}

function parseDateToken(text: string): string | null {
  const iso = DATE_ISO_RE.exec(text);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const dmy = DATE_DMY_RE.exec(text);
  if (!dmy) return null;
  if (dmy[4] && dmy[5] && dmy[6]) {
    const mon = MONTHS[dmy[5].slice(0, 3).toLowerCase()];
    if (!mon) return null;
    return `${dmy[6]}-${mon}-${dmy[4].padStart(2, "0")}`;
  }
  if (dmy[1] && dmy[2] && dmy[3]) {
    // Prefer DD/MM/YYYY for European MOU portals; swap if month > 12.
    let day = Number(dmy[1]);
    let month = Number(dmy[2]);
    const year = dmy[3];
    if (month > 12 && day <= 12) {
      const tmp = day;
      day = month;
      month = tmp;
    }
    if (month < 1 || month > 12 || day < 1 || day > 31) return null;
    return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }
  return null;
}

function detectMou(text: string): string | null {
  const m = MOU_RE.exec(text);
  if (!m) return null;
  const raw = m[0].toLowerCase();
  if (raw.includes("tokyo") || raw.includes("東京")) return "tokyo";
  if (raw.includes("paris") || raw.includes("パリ")) return "paris";
  return null;
}

function extractAction(line: string): string | null {
  const near = ACTION_NEAR_RE.exec(line);
  if (near?.[1]) return normalizeActionCode(near[1]);
  if (DETENTION_WORD_RE.test(line)) return "30";
  const inline = ACTION_INLINE_RE.exec(line);
  if (inline?.[1]) return normalizeActionCode(inline[1]);
  // Phrase lexicon (JA/EN) when numeric action is absent — Issue #90
  const fromLexicon = normalizePscActionPhrase(line);
  return fromLexicon ? normalizeActionCode(fromLexicon) : null;
}

function extractNature(line: string, code: string): string {
  let s = line;
  s = s.replace(new RegExp(`\\b${code}\\b`), " ");
  s = s.replace(ACTION_NEAR_RE, " ");
  s = s.replace(/\b(?:code\s*)?(?:15|16|17|19|21|30)\b/gi, " ");
  s = s.replace(
    /\b(?:deficiency(?:\s*code)?|action(?:\s*taken)?|nature|convention|solas|marpol|ism|stcw)\b/gi,
    " ",
  );
  s = s.replace(/[|:：]/g, " ");
  return collapseWs(s).slice(0, 240);
}

function sourceQuoteForCode(line: string, code: string): string {
  const idx = line.indexOf(code);
  if (idx < 0) return code;
  const start = Math.max(0, idx - 20);
  const end = Math.min(line.length, idx + code.length + 80);
  return collapseWs(line.slice(start, end)).slice(0, 200) || code;
}

interface RawHit {
  code: string;
  action: string | null;
  nature: string;
  date: string | null;
  quote: string;
  section: "current" | "prior";
}

function sectionForLineIndex(
  lines: string[],
  lineIdx: number,
): "current" | "prior" {
  let section: "current" | "prior" = "current";
  for (let i = 0; i <= lineIdx; i++) {
    const L = lines[i]!;
    if (PRIOR_HEADING_RE.test(L)) section = "prior";
    else if (CURRENT_HEADING_RE.test(L)) section = "current";
  }
  return section;
}

function collectHits(plain: string): {
  hits: RawHit[];
  mouId: string | null;
  inspectionDate: string | null;
} {
  const mouId = detectMou(plain);
  const docDate = parseDateToken(plain);
  const lines = plain.split(/\n/).map((l) => l.trim()).filter(Boolean);
  const hits: RawHit[] = [];
  const seen = new Set<string>();

  const tryAdd = (
    codeRaw: string,
    window: string,
    lineIdx: number,
  ): void => {
    const code = normalizeDeficiencyCode(codeRaw);
    if (!code || code.length < 5) return;
    const nature = extractNature(window, code);
    const action = extractAction(window);
    if (!action && nature.length < 8) return;
    const key = `${sectionForLineIndex(lines, lineIdx)}:${code}:${action ?? ""}:${nature.slice(0, 40)}`;
    if (seen.has(key)) return;
    seen.add(key);
    hits.push({
      code,
      action,
      nature,
      date: parseDateToken(window) || docDate,
      quote: sourceQuoteForCode(window, code),
      section: sectionForLineIndex(lines, lineIdx),
    });
  };

  // Pass 1: single-line portal / TSV rows (code + nature + action on one line).
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    DEF_CODE_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = DEF_CODE_RE.exec(line)) !== null) {
      tryAdd(m[1]!, line, i);
    }
  }

  // Pass 2: HTML table cells often become one field per line after strip.
  // When a line is (mostly) a 5-digit code, join the next few lines as a row window.
  if (!hits.some((h) => h.action != null)) {
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]!;
      const alone = /^(?:0[1-9]|1[0-5])\d{3}$/.exec(line);
      if (!alone) continue;
      const window = [line, lines[i + 1], lines[i + 2], lines[i + 3]]
        .filter(Boolean)
        .join(" ");
      tryAdd(alone[0]!, window, i);
    }
  }

  // Pass 3: code line + following nature line (action may still be missing).
  if (!hits.length) {
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]!;
      DEF_CODE_RE.lastIndex = 0;
      const m = DEF_CODE_RE.exec(line);
      if (!m) continue;
      const window = `${line} ${lines[i + 1] || ""} ${lines[i + 2] || ""}`;
      tryAdd(m[1]!, window, i);
    }
  }

  return { hits, mouId, inspectionDate: docDate };
}

/**
 * Extract normalized deficiencies from MOU portal / table text (or HTML).
 * Critical field grounding: deficiencies.{i}.code with contiguous source_quote.
 */
export function extractPscDeficienciesFromText(
  input: string,
  opts: { filename?: string | null } = {},
): PscDocumentExtract {
  const raw = input.trim();
  if (!raw) {
    return {
      deficiencies: [],
      prior: [],
      mouId: null,
      inspectionDate: null,
      grounding: [],
      confidence: 0,
      label: opts.filename || "empty",
    };
  }

  const plain = looksLikeHtml(raw) ? htmlToPlainText(raw) : collapseWs(raw);
  const { hits, mouId, inspectionDate } = collectHits(plain);

  const currentHits = hits.filter((h) => h.section === "current");
  const priorHits = hits.filter((h) => h.section === "prior");
  // If everything landed in prior by mistake (heading only), treat as current.
  const useCurrent = currentHits.length ? currentHits : hits;
  const usePrior = currentHits.length ? priorHits : [];

  const deficiencies: NormalizedDeficiency[] = [];
  const prior: NormalizedDeficiency[] = [];
  const grounding: GroundingRef[] = [];

  for (const hit of useCurrent) {
    const parsed = parseDeficiencyItem(
      {
        deficiency_code: hit.code,
        action_taken: hit.action,
        nature: hit.nature,
        inspection_date: hit.date,
        mou_id: mouId,
      },
      { defaultDate: inspectionDate, defaultMou: mouId },
    );
    if (!parsed) continue;
    const idx = deficiencies.length;
    deficiencies.push(parsed);
    grounding.push({
      field: `deficiencies.${idx}.code`,
      source_quote: hit.quote,
      page_number: null,
      pdf_coordinates: null,
    });
  }
  for (const hit of usePrior) {
    const parsed = parseDeficiencyItem(
      {
        deficiency_code: hit.code,
        action_taken: hit.action,
        nature: hit.nature,
        inspection_date: hit.date,
        mou_id: mouId,
      },
      { defaultDate: inspectionDate, defaultMou: mouId },
    );
    if (parsed) prior.push(parsed);
  }

  const confidence =
    deficiencies.length === 0
      ? 0.2
      : Math.min(0.92, 0.55 + deficiencies.length * 0.08 + (mouId ? 0.05 : 0));

  const label =
    opts.filename?.replace(/\.[^.]+$/, "") ||
    (mouId ? `${mouId}_inspection` : "psc_document");

  return {
    deficiencies,
    prior,
    mouId,
    inspectionDate,
    grounding,
    confidence,
    label,
  };
}
