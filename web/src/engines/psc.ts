/**
 * Paris / Tokyo MOU PSC deficiency taxonomy + seaworthiness Defect Score.
 * Port of marine_claims_ai.ontology.psc + ingest.psc_deficiencies (Issues #31 / #42 / #83).
 */

export const ACTION_RECTIFY_BEFORE_DEPARTURE = "15";
export const ACTION_RECTIFY_WITHIN_14_DAYS = "16";
export const ACTION_RECTIFY = "17";
export const ACTION_DETENTION = "30";

export const DETENTION_ACTION_CODES = new Set([ACTION_DETENTION]);

export const ACTION_CODE_SEVERITY: Record<string, number> = {
  [ACTION_DETENTION]: 1.0,
  [ACTION_RECTIFY]: 0.5,
  [ACTION_RECTIFY_BEFORE_DEPARTURE]: 0.4,
  [ACTION_RECTIFY_WITHIN_14_DAYS]: 0.25,
};
export const DEFAULT_ACTION_SEVERITY = 0.1;

export interface CategoryEntry {
  label: string;
  convention: string;
  chapter: string;
}

export const DEFICIENCY_CATEGORY_MAP: Record<string, CategoryEntry> = {
  "011": {
    label: "Certificate & Documentation - Ship Certificates",
    convention: "SOLAS",
    chapter: "Certificates",
  },
  "012": {
    label: "Certificate & Documentation - Crew Certificates",
    convention: "STCW",
    chapter: "Crew certification",
  },
  "013": {
    label: "Certificate & Documentation - Documents",
    convention: "SOLAS",
    chapter: "Documents",
  },
  "021": {
    label: "Structural Conditions",
    convention: "SOLAS",
    chapter: "II-1",
  },
  "041": {
    label: "Emergency Systems",
    convention: "SOLAS",
    chapter: "II-1/II-2",
  },
  "071": {
    label: "Fire safety",
    convention: "SOLAS",
    chapter: "II-2",
  },
  "081": {
    label: "Alarms",
    convention: "SOLAS",
    chapter: "II-1/II-2",
  },
  "101": {
    label: "Safety of Navigation",
    convention: "SOLAS",
    chapter: "V",
  },
  "131": {
    label: "Propulsion and auxiliary machinery",
    convention: "SOLAS",
    chapter: "II-1",
  },
  "141": {
    label: "Pollution prevention - MARPOL Annex I",
    convention: "MARPOL",
    chapter: "Annex I",
  },
  "142": {
    label: "Pollution prevention - MARPOL Annex II",
    convention: "MARPOL",
    chapter: "Annex II",
  },
  "143": {
    label: "Pollution prevention - MARPOL Annex III",
    convention: "MARPOL",
    chapter: "Annex III",
  },
  "144": {
    label: "Pollution prevention - MARPOL Annex IV",
    convention: "MARPOL",
    chapter: "Annex IV",
  },
  "145": {
    label: "Pollution prevention - MARPOL Annex V",
    convention: "MARPOL",
    chapter: "Annex V",
  },
  "146": {
    label: "Pollution prevention - MARPOL Annex VI",
    convention: "MARPOL",
    chapter: "Annex VI",
  },
  "147": {
    label: "Pollution prevention - Anti Fouling",
    convention: "MARPOL",
    chapter: "AFS",
  },
  "148": {
    label: "Pollution prevention - Ballast Water",
    convention: "MARPOL",
    chapter: "BWM",
  },
  "151": {
    label: "ISM",
    convention: "ISM",
    chapter: "SOLAS IX",
  },
};

export const DEFICIENCY_MAJOR_CATEGORY_MAP: Record<string, CategoryEntry> = {
  "01": {
    label: "Certificate & Documentation",
    convention: "SOLAS",
    chapter: "Certificates",
  },
  "04": {
    label: "Emergency Systems",
    convention: "SOLAS",
    chapter: "II-1/II-2",
  },
  "07": {
    label: "Fire safety",
    convention: "SOLAS",
    chapter: "II-2",
  },
  "10": {
    label: "Safety of Navigation",
    convention: "SOLAS",
    chapter: "V",
  },
  "13": {
    label: "Propulsion and auxiliary machinery",
    convention: "SOLAS",
    chapter: "II-1",
  },
  "14": {
    label: "Pollution prevention",
    convention: "MARPOL",
    chapter: "Annexes",
  },
  "15": {
    label: "ISM",
    convention: "ISM",
    chapter: "SOLAS IX",
  },
};

export const CATEGORY_BASE_WEIGHT: Record<string, number> = {
  "041": 1.0,
  "071": 1.0,
  "101": 1.0,
  "131": 1.0,
  "151": 1.0,
  "021": 0.85,
  "081": 0.7,
  "011": 0.6,
  "012": 0.6,
  "013": 0.6,
  "141": 0.85,
  "142": 0.85,
  "143": 0.85,
  "144": 0.85,
  "145": 0.85,
  "146": 0.85,
  "147": 0.7,
  "148": 0.85,
};
export const DEFAULT_CATEGORY_BASE_WEIGHT = 0.4;

export const CRITICAL_SYSTEM_CODES = new Set(["02105", "04102", "04106", "08104"]);
export const CRITICAL_SYSTEM_PREFIXES = new Set(["151"]);
const CRITICAL_SYSTEM_KEYWORDS: Array<[string, string]> = [
  ["steering", "steering_gear"],
  ["emergency fire pump", "emergency_fire_pump"],
  ["ism", "ism"],
];

export const REPEAT_MULTIPLIER = 1.5;
export const DEFAULT_LOOKBACK_MONTHS = 24;

const CODE_LONG = /(?<!\d)(\d{4,5})(?!\d)/;
const CODE_SHORT = /(?<!\d)(\d{2,3})(?!\d)/;
const ISM_WORD = /\bism\b/i;

export type RiskBand = "low" | "elevated" | "critical";

export interface NormalizedDeficiency {
  code: string;
  action_code: string | null;
  description: string;
  inspection_date: string | null;
  mou_id: string | null;
  prefix: string | null;
  convention: string | null;
  category_label: string | null;
  citation: string | null;
  severity_weight: number;
  category_weight: number;
  critical_system: string | null;
  contribution: number;
  is_repeat_critical: boolean;
}

export interface SeaworthinessRiskReport {
  defect_score: number;
  detention_present: boolean;
  risk_band: RiskBand;
  deficiencies: NormalizedDeficiency[];
  repeat_critical_flags: string[];
  convention_citations: string[];
  active_statutory_risks: string[];
  mou_id: string | null;
  notes: string;
}

export interface PscFixtureCase {
  id: string;
  kind?: string;
  mou_id?: string;
  notes?: string;
  inspection?: Record<string, unknown>;
  prior_inspection?: Record<string, unknown>;
  cic_weights?: Record<string, number>;
  expect?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface PscFixturesFile {
  version: number;
  description?: string;
  cases: PscFixtureCase[];
}

function firstStr(raw: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    if (!(key in raw)) continue;
    const value = raw[key];
    if (value == null) continue;
    const text = String(value).trim();
    if (text) return text;
  }
  return null;
}

export function normalizeActionCode(actionCode: string | null | undefined): string | null {
  if (actionCode == null) return null;
  const text = String(actionCode).trim();
  if (!text) return null;
  const match = text.match(/(\d{1,3})/);
  return match ? match[1]! : text;
}

export function isDetentionAction(actionCode: string | null | undefined): boolean {
  const code = normalizeActionCode(actionCode);
  return code != null && DETENTION_ACTION_CODES.has(code);
}

export function actionSeverity(actionCode: string | null | undefined): number {
  const code = normalizeActionCode(actionCode);
  if (code == null) return DEFAULT_ACTION_SEVERITY;
  return ACTION_CODE_SEVERITY[code] ?? DEFAULT_ACTION_SEVERITY;
}

export function normalizeDeficiencyCode(code: string | null | undefined): string | null {
  if (code == null) return null;
  const text = String(code).trim();
  if (!text) return null;
  const longMatch = text.match(CODE_LONG);
  if (longMatch) return longMatch[1]!;
  const compact = text.replace(/ /g, "").replace(/-/g, "").replace(/\./g, "");
  const longCompact = compact.match(CODE_LONG);
  if (longCompact) return longCompact[1]!;
  const shortMatch = text.match(CODE_SHORT) || compact.match(CODE_SHORT);
  if (shortMatch) return shortMatch[1]!;
  const digits = compact.replace(/\D/g, "");
  return digits || null;
}

export function categoryPrefix(code: string | null | undefined): string | null {
  const digits = normalizeDeficiencyCode(code);
  if (!digits) return null;
  if (digits.length >= 3) return digits.slice(0, 3);
  if (digits.length >= 2) return digits.slice(0, 2);
  return digits;
}

export function lookupCategory(code: string | null | undefined): CategoryEntry | null {
  const digits = normalizeDeficiencyCode(code);
  if (!digits) return null;
  if (digits.length >= 3) {
    const entry = DEFICIENCY_CATEGORY_MAP[digits.slice(0, 3)];
    if (entry) return { ...entry };
  }
  if (digits.length >= 2) {
    const entry = DEFICIENCY_MAJOR_CATEGORY_MAP[digits.slice(0, 2)];
    if (entry) return { ...entry };
  }
  return null;
}

export function conventionForCode(code: string | null | undefined): string | null {
  const entry = lookupCategory(code);
  if (!entry) return null;
  const chapter = entry.chapter || "";
  const convention = entry.convention || "";
  if (chapter && convention) return `${convention} ${chapter}`.trim();
  return convention || null;
}

export function categoryBaseWeight(code: string | null | undefined): number {
  const prefix = categoryPrefix(code);
  if (prefix == null) return DEFAULT_CATEGORY_BASE_WEIGHT;
  if (prefix in CATEGORY_BASE_WEIGHT) return CATEGORY_BASE_WEIGHT[prefix]!;
  if (prefix.length >= 2 && ["04", "07", "10", "13", "15"].includes(prefix.slice(0, 2))) {
    return 1.0;
  }
  return DEFAULT_CATEGORY_BASE_WEIGHT;
}

export function criticalSystemId(
  code: string | null | undefined,
  description = "",
): string | null {
  const digits = normalizeDeficiencyCode(code);
  const desc = (description || "").toLowerCase();
  if (digits && CRITICAL_SYSTEM_CODES.has(digits)) {
    if (digits === "04102") return "emergency_fire_pump";
    return "steering_gear";
  }
  const prefix = categoryPrefix(digits);
  if (prefix && CRITICAL_SYSTEM_PREFIXES.has(prefix)) return "ism";
  for (const [needle, systemId] of CRITICAL_SYSTEM_KEYWORDS) {
    if (needle === "ism") {
      if (ISM_WORD.test(desc)) return systemId;
    } else if (desc.includes(needle)) {
      return systemId;
    }
  }
  return null;
}

export function citationForCode(code: string | null | undefined): string | null {
  const entry = lookupCategory(code);
  if (!entry) return null;
  const label = entry.label || "";
  const convention = conventionForCode(code) || "";
  const prefix = categoryPrefix(code) || "";
  const parts = [prefix ? `${prefix}xx` : "", label, convention].filter(Boolean);
  return parts.length ? parts.join(" — ") : null;
}

function deficiencyRows(raw: Record<string, unknown>): Record<string, unknown>[] {
  for (const key of ["deficiencies", "deficiency_list", "items", "findings"]) {
    const rows = raw[key];
    if (Array.isArray(rows)) {
      return rows.filter((r): r is Record<string, unknown> => !!r && typeof r === "object");
    }
  }
  if (
    ["deficiency_code", "code", "def_code", "nature_of_deficiency"].some((k) => k in raw)
  ) {
    return [raw];
  }
  return [];
}

export function parseDeficiencyItem(
  item: Record<string, unknown>,
  opts: { defaultDate?: string | null; defaultMou?: string | null } = {},
): NormalizedDeficiency | null {
  const code = normalizeDeficiencyCode(
    firstStr(item, "deficiency_code", "code", "def_code", "defective_item_code"),
  );
  if (!code) return null;
  const action = normalizeActionCode(
    firstStr(item, "action_taken", "action_code", "action", "action_taken_code"),
  );
  const description =
    firstStr(item, "nature", "nature_of_deficiency", "description", "defective_item", "text") ||
    "";
  const date =
    firstStr(item, "inspection_date", "date", "survey_date") || opts.defaultDate || null;
  const mou = firstStr(item, "mou_id", "mou", "region") || opts.defaultMou || null;
  const cat = lookupCategory(code);
  return {
    code,
    action_code: action,
    description,
    inspection_date: date,
    mou_id: mou,
    prefix: categoryPrefix(code),
    convention: conventionForCode(code),
    category_label: cat?.label ?? null,
    citation: citationForCode(code),
    severity_weight: actionSeverity(action),
    category_weight: categoryBaseWeight(code),
    critical_system: criticalSystemId(code, description),
    contribution: 0,
    is_repeat_critical: false,
  };
}

export function parseInspectionRecord(raw: Record<string, unknown>): NormalizedDeficiency[] {
  const defaultDate = firstStr(raw, "inspection_date", "date", "survey_date");
  const defaultMou = firstStr(raw, "mou_id", "mou", "region");
  const out: NormalizedDeficiency[] = [];
  for (const row of deficiencyRows(raw)) {
    const parsed = parseDeficiencyItem(row, { defaultDate, defaultMou });
    if (parsed) out.push(parsed);
  }
  return out;
}

function parseIsoDate(text: string | null | undefined): Date | null {
  if (!text) return null;
  const raw = String(text).trim();
  if (!raw) return null;
  const day = raw.slice(0, 10);
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const dt = new Date(Date.UTC(y, mo - 1, d));
  if (
    dt.getUTCFullYear() !== y ||
    dt.getUTCMonth() !== mo - 1 ||
    dt.getUTCDate() !== d
  ) {
    return null;
  }
  return dt;
}

function subtractMonths(d: Date, months: number): Date {
  if (months < 0) throw new Error("months must be non-negative");
  let year = d.getUTCFullYear();
  let month = d.getUTCMonth() + 1 - months;
  while (month <= 0) {
    month += 12;
    year -= 1;
  }
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const day = Math.min(d.getUTCDate(), lastDay);
  return new Date(Date.UTC(year, month - 1, day));
}

function anchorInspectionDate(deficiencies: NormalizedDeficiency[]): Date | null {
  const dates = deficiencies
    .map((d) => parseIsoDate(d.inspection_date))
    .filter((x): x is Date => x != null);
  if (!dates.length) return null;
  return dates.reduce((a, b) => (a.getTime() >= b.getTime() ? a : b));
}

function priorCriticalSystems(
  prior: NormalizedDeficiency[] | null | undefined,
  opts: { anchor?: Date | null; lookbackMonths?: number } = {},
): Set<string> {
  if (!prior?.length) return new Set();
  const anchor = opts.anchor ?? null;
  const lookbackMonths = opts.lookbackMonths ?? DEFAULT_LOOKBACK_MONTHS;
  if (anchor == null) {
    return new Set(prior.map((d) => d.critical_system).filter((x): x is string => !!x));
  }
  const windowStart = subtractMonths(anchor, lookbackMonths);
  const out = new Set<string>();
  for (const d of prior) {
    if (!d.critical_system) continue;
    const priorDate = parseIsoDate(d.inspection_date);
    if (priorDate == null) {
      out.add(d.critical_system);
      continue;
    }
    if (priorDate.getTime() >= windowStart.getTime() && priorDate.getTime() <= anchor.getTime()) {
      out.add(d.critical_system);
    }
  }
  return out;
}

function cicMultiplier(
  prefix: string | null,
  cicWeights: Record<string, number> | null | undefined,
): number {
  if (!cicWeights || !prefix) return 1.0;
  if (prefix in cicWeights) return Number(cicWeights[prefix]);
  const major = prefix.slice(0, 2);
  if (prefix.length >= 2 && major in cicWeights) return Number(cicWeights[major]);
  return 1.0;
}

/** Demo-only engineering bands (not statutory warranty thresholds). */
export function riskBandForReport(opts: {
  defectScore: number;
  detentionPresent: boolean;
  hasCriticalSystem: boolean;
}): RiskBand {
  if (opts.detentionPresent || opts.defectScore >= 1.0) return "critical";
  if (opts.hasCriticalSystem || opts.defectScore >= 0.4) return "elevated";
  return "low";
}

export function scoreSeaworthiness(
  deficiencies: NormalizedDeficiency[],
  opts: {
    prior?: NormalizedDeficiency[] | null;
    mouId?: string | null;
    cicWeights?: Record<string, number> | null;
    lookbackMonths?: number;
  } = {},
): SeaworthinessRiskReport {
  const lookbackMonths = opts.lookbackMonths ?? DEFAULT_LOOKBACK_MONTHS;
  const anchor = anchorInspectionDate(deficiencies);
  const priorSystems = priorCriticalSystems(opts.prior, { anchor, lookbackMonths });
  const scored: NormalizedDeficiency[] = [];
  let total = 0;
  const repeatFlags: string[] = [];
  const citations: string[] = [];
  const risks: string[] = [];
  let detention = false;
  let resolvedMou = opts.mouId ?? null;

  for (const d of deficiencies) {
    resolvedMou = resolvedMou || d.mou_id;
    const isRepeat = !!(d.critical_system && priorSystems.has(d.critical_system));
    const repeatMult = isRepeat ? REPEAT_MULTIPLIER : 1.0;
    const cicMult = cicMultiplier(d.prefix, opts.cicWeights);
    const contrib = d.category_weight * d.severity_weight * repeatMult * cicMult;
    total += contrib;
    scored.push({
      ...d,
      contribution: Math.round(contrib * 1e6) / 1e6,
      is_repeat_critical: isRepeat,
      mou_id: d.mou_id || opts.mouId || null,
    });
    if (isDetentionAction(d.action_code)) detention = true;
    if (isRepeat && d.critical_system && !repeatFlags.includes(d.critical_system)) {
      repeatFlags.push(d.critical_system);
    }
    if (d.citation && !citations.includes(d.citation)) citations.push(d.citation);
    if (d.convention) {
      let risk = `${d.convention}: ${d.code}`;
      if (d.action_code) risk += ` (action ${d.action_code})`;
      if (!risks.includes(risk)) risks.push(risk);
    }
  }

  const notesParts: string[] = [];
  if (detention) notesParts.push("IMO/MOU detention action (Code 30) present.");
  if (repeatFlags.length) {
    notesParts.push(
      `Repeat critical-system deficiencies: ${[...repeatFlags].sort().join(", ")}.`,
    );
  }
  if (opts.cicWeights && Object.keys(opts.cicWeights).length) {
    notesParts.push("Regional CIC weights applied.");
  }

  const defectScore = Math.round(total * 1e6) / 1e6;
  const hasCritical = scored.some((d) => !!d.critical_system);
  return {
    defect_score: defectScore,
    detention_present: detention,
    risk_band: riskBandForReport({
      defectScore,
      detentionPresent: detention,
      hasCriticalSystem: hasCritical,
    }),
    deficiencies: scored,
    repeat_critical_flags: [...repeatFlags].sort(),
    convention_citations: citations,
    active_statutory_risks: risks,
    mou_id: resolvedMou,
    notes: notesParts.join(" "),
  };
}

export function scoreFixtureCase(
  fixtureCase: PscFixtureCase | Record<string, unknown>,
  opts: {
    cicWeights?: Record<string, number> | null;
    lookbackMonths?: number;
  } = {},
): SeaworthinessRiskReport {
  const c = fixtureCase as PscFixtureCase;
  const inspection =
    (c.inspection as Record<string, unknown> | undefined) ||
    (fixtureCase as Record<string, unknown>);
  const current = parseInspectionRecord(inspection);
  const priorRaw = c.prior_inspection;
  const prior =
    priorRaw && typeof priorRaw === "object"
      ? parseInspectionRecord(priorRaw as Record<string, unknown>)
      : null;
  let weights = opts.cicWeights;
  if (weights == null && c.cic_weights && typeof c.cic_weights === "object") {
    weights = Object.fromEntries(
      Object.entries(c.cic_weights).map(([k, v]) => [String(k), Number(v)]),
    );
  }
  const mouId =
    firstStr(fixtureCase as Record<string, unknown>, "mou_id") ||
    (typeof c.mou_id === "string" ? c.mou_id : null);
  return scoreSeaworthiness(current, {
    prior,
    mouId,
    cicWeights: weights,
    lookbackMonths: opts.lookbackMonths,
  });
}

/** Parse pasted JSON (fixture case, inspection, or deficiency array). */
export function parsePscJsonInput(text: string): {
  current: NormalizedDeficiency[];
  prior: NormalizedDeficiency[] | null;
  cicWeights: Record<string, number> | null;
  mouId: string | null;
  label: string;
} {
  const raw = JSON.parse(text) as unknown;
  if (Array.isArray(raw)) {
    const current: NormalizedDeficiency[] = [];
    for (const row of raw) {
      if (row && typeof row === "object") {
        const parsed = parseDeficiencyItem(row as Record<string, unknown>);
        if (parsed) current.push(parsed);
      }
    }
    return { current, prior: null, cicWeights: null, mouId: null, label: "pasted-array" };
  }
  if (!raw || typeof raw !== "object") {
    throw new Error("PSC JSON must be an object or array");
  }
  const obj = raw as Record<string, unknown>;
  if (obj.inspection || obj.prior_inspection || obj.cases) {
    if (Array.isArray(obj.cases) && obj.cases.length) {
      const first = obj.cases[0] as PscFixtureCase;
      return {
        current: parseInspectionRecord(
          (first.inspection as Record<string, unknown>) || first,
        ),
        prior: first.prior_inspection
          ? parseInspectionRecord(first.prior_inspection as Record<string, unknown>)
          : null,
        cicWeights: (first.cic_weights as Record<string, number>) || null,
        mouId: typeof first.mou_id === "string" ? first.mou_id : null,
        label: first.id || "fixture",
      };
    }
    const current = parseInspectionRecord(
      (obj.inspection as Record<string, unknown>) || obj,
    );
    const prior = obj.prior_inspection
      ? parseInspectionRecord(obj.prior_inspection as Record<string, unknown>)
      : null;
    const cic =
      obj.cic_weights && typeof obj.cic_weights === "object"
        ? (obj.cic_weights as Record<string, number>)
        : null;
    return {
      current,
      prior,
      cicWeights: cic,
      mouId: firstStr(obj, "mou_id"),
      label: firstStr(obj, "id") || "pasted-json",
    };
  }
  const current = parseInspectionRecord(obj);
  return {
    current,
    prior: null,
    cicWeights: null,
    mouId: firstStr(obj, "mou_id"),
    label: "pasted-json",
  };
}

/**
 * Simple CSV: header row with deficiency_code/action_taken/nature/inspection_date
 * (aliases accepted). One deficiency per line.
 */
export function parsePscCsvInput(text: string): NormalizedDeficiency[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length < 2) return [];
  const headers = splitCsvLine(lines[0]!).map((h) => h.trim().toLowerCase());
  const out: NormalizedDeficiency[] = [];
  for (const line of lines.slice(1)) {
    const cells = splitCsvLine(line);
    const row: Record<string, unknown> = {};
    headers.forEach((h, i) => {
      row[h] = cells[i] ?? "";
    });
    // Normalize common header aliases into parseDeficiencyItem keys
    const mapped: Record<string, unknown> = {
      deficiency_code:
        row.deficiency_code ?? row.code ?? row.def_code ?? row.defective_item_code,
      action_taken:
        row.action_taken ?? row.action_code ?? row.action ?? row.action_taken_code,
      nature: row.nature ?? row.nature_of_deficiency ?? row.description ?? row.text,
      inspection_date: row.inspection_date ?? row.date ?? row.survey_date,
      mou_id: row.mou_id ?? row.mou ?? row.region,
    };
    const parsed = parseDeficiencyItem(mapped);
    if (parsed) out.push(parsed);
  }
  return out;
}

function splitCsvLine(line: string): string[] {
  const result: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]!;
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      result.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  result.push(cur);
  return result;
}

export function tryParsePscPaste(text: string): {
  current: NormalizedDeficiency[];
  prior: NormalizedDeficiency[] | null;
  cicWeights: Record<string, number> | null;
  mouId: string | null;
  label: string;
} {
  const trimmed = text.trim();
  if (!trimmed) {
    return { current: [], prior: null, cicWeights: null, mouId: null, label: "empty" };
  }
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    return parsePscJsonInput(trimmed);
  }
  const current = parsePscCsvInput(trimmed);
  return { current, prior: null, cicWeights: null, mouId: null, label: "pasted-csv" };
}
