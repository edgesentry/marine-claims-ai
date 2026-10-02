/**
 * Extract fault ratios and monetary awards from Japanese maritime civil judgments.
 *
 * Faithful port of marine_claims_ai.ingest.civil_judgment_extractor.
 * Handles Arabic, fullwidth, and kanji numeral conventions common in courts.go.jp
 * PDFs/HTML and locates operative comparative-negligence holdings.
 */

// ---------------------------------------------------------------------------
// Kanji / fullwidth numeral helpers
// ---------------------------------------------------------------------------

const DIGIT: Record<string, number> = {
  "〇": 0,
  零: 0,
  "○": 0,
  一: 1,
  二: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
};

const FULLWIDTH_FROM = "０１２３４５６７８９％：．．，";
const FULLWIDTH_TO = "0123456789%:..,";

/** Like Python str.translate(str.maketrans(...)) for the fullwidth digit map. */
function translateFullwidth(text: string): string {
  let out = "";
  for (const ch of text) {
    const idx = FULLWIDTH_FROM.indexOf(ch);
    out += idx >= 0 ? FULLWIDTH_TO[idx]! : ch;
  }
  return out;
}

const UNIT_SMALL: Record<string, number> = { 十: 10, 百: 100, 千: 1000 };

const KANJI_INT_TOKEN = "[〇零○一二三四五六七八九十百千万億\\d０-９]+";
const ARABIC_YEN = /([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})円/g;
const KANJI_YEN = new RegExp(`(${KANJI_INT_TOKEN})円`, "g");

const HOLDING_ANCHORS = [
  "過失相殺",
  "過失割合",
  "責任割合",
  "過失の割合",
  "過失の程度",
  "双方の過失",
  "寄与度",
] as const;

export interface FaultRatioHit {
  ratio: string;
  evidence: string;
  method: string;
  confidence: number;
  side_a_label: string | null;
  side_b_label: string | null;
  side_a_role: string | null;
  side_b_role: string | null;
}

export interface YenHit {
  amount_jpy: number;
  label: string;
  evidence: string;
}

export class JudgmentExtraction {
  fault_ratio: string | null = null;
  fault_ratio_hits: FaultRatioHit[] = [];
  claimed_repair_jpy: number | null = null;
  awarded_damages_jpy: number | null = null;
  disallowed_jpy: number | null = null;
  yen_hits: YenHit[] = [];
  holding_excerpt: string | null = null;
  side_a_label: string | null = null;
  side_b_label: string | null = null;
  side_a_role: string | null = null;
  side_b_role: string | null = null;

  toDict(): Record<string, unknown> {
    return {
      fault_ratio: this.fault_ratio,
      fault_ratio_hits: this.fault_ratio_hits.map((h) => ({ ...h })),
      claimed_repair_jpy: this.claimed_repair_jpy,
      awarded_damages_jpy: this.awarded_damages_jpy,
      disallowed_jpy: this.disallowed_jpy,
      yen_hits: this.yen_hits.map((h) => ({ ...h })),
      holding_excerpt: this.holding_excerpt,
      side_a_label: this.side_a_label,
      side_b_label: this.side_b_label,
      side_a_role: this.side_a_role,
      side_b_role: this.side_b_role,
    };
  }
}

function isAsciiDigit(ch: string): boolean {
  return ch >= "0" && ch <= "9";
}

/** Strip any of the given characters from both ends (Python str.strip chars). */
function stripChars(s: string, chars: string): string {
  const set = new Set([...chars]);
  let start = 0;
  let end = s.length;
  while (start < end && set.has(s[start]!)) start++;
  while (end > start && set.has(s[end - 1]!)) end--;
  return s.slice(start, end);
}

export function normalizeJudgmentText(text: string): string {
  if (!text) return "";
  let t = translateFullwidth(text);
  t = t.replace(/\u3000/g, " ");
  t = t.replace(/[ \t]+/g, " ");
  t = t.replace(/\n{3,}/g, "\n\n");
  return t;
}

function parseDigitRun(s: string): number | null {
  if (!s) return null;
  if ([...s].every((ch) => ch in DIGIT || isAsciiDigit(ch))) {
    let out = 0;
    for (const ch of s) {
      out = out * 10 + (isAsciiDigit(ch) ? Number(ch) : DIGIT[ch]!);
    }
    return out;
  }
  return null;
}

function parseUnderMan(s: string): number | null {
  if (!s) return 0;
  const digitRun = parseDigitRun(s);
  if (digitRun !== null && ![...s].some((ch) => ch in UNIT_SMALL)) {
    return digitRun;
  }

  let total = 0;
  let num: number | null = null;
  let i = 0;
  const chars = [...s];
  while (i < chars.length) {
    const ch = chars[i]!;
    if (ch in DIGIT || isAsciiDigit(ch)) {
      let run = 0;
      while (i < chars.length && (chars[i]! in DIGIT || isAsciiDigit(chars[i]!))) {
        const d = isAsciiDigit(chars[i]!) ? Number(chars[i]) : DIGIT[chars[i]!]!;
        run = run * 10 + d;
        i += 1;
      }
      num = run;
      continue;
    }
    if (ch in UNIT_SMALL) {
      const coef = num !== null ? num : 1;
      total += coef * UNIT_SMALL[ch]!;
      num = null;
      i += 1;
      continue;
    }
    return null;
  }
  if (num !== null) total += num;
  return total;
}

export function parseKanjiInt(token: string): number | null {
  if (!token) return null;
  token = translateFullwidth(token).trim();
  if (!token) return null;
  if (/^\d+$/.test(token)) return Number(token);
  if ([...token].every((ch) => ch in DIGIT)) return parseDigitRun(token);

  let total = 0;
  let rest = token;
  if (rest.includes("億")) {
    const idx = rest.indexOf("億");
    const left = rest.slice(0, idx);
    rest = rest.slice(idx + 1);
    const leftV = left ? parseUnderMan(left) : 1;
    if (leftV === null) return null;
    total += leftV * 100_000_000;
  }
  if (rest.includes("万")) {
    const idx = rest.indexOf("万");
    const left = rest.slice(0, idx);
    rest = rest.slice(idx + 1);
    const leftV = left ? parseUnderMan(left) : 1;
    if (leftV === null) return null;
    total += leftV * 10_000;
  }
  const tail = rest ? parseUnderMan(rest) : 0;
  if (tail === null) return null;
  return total + tail;
}

export function parseYenToken(token: string): number | null {
  token = translateFullwidth(token).trim();
  if (token.endsWith("円")) token = token.slice(0, -1);
  token = token.replace(/,/g, "").replace(/，/g, "");
  if (!token) return null;
  if (/^\d+$/.test(token)) return Number(token);
  return parseKanjiInt(token);
}

function ratioStr(a: number, b: number): string | null {
  if (a < 0 || b < 0) return null;
  // Tenths notation: 八、二 → 80:20
  if (a + b === 10 && a >= 1 && a <= 9 && b >= 1 && b <= 9) {
    a *= 10;
    b *= 10;
  }
  if (a + b !== 100) return null;
  if (!(a >= 1 && a <= 99 && b >= 1 && b <= 99)) return null;
  return `${a}:${b}`;
}

function singlePercentRatio(pct: number): string | null {
  if (!(pct >= 1 && pct <= 99)) return null;
  return `${pct}:${100 - pct}`;
}

// ---------------------------------------------------------------------------
// Fault ratio extraction
// ---------------------------------------------------------------------------

const RE_ARABIC_PAIR =
  /(?:過失割合|責任割合|過失の割合|寄与度)?[^\d]{0,24}(\d{1,2})\s*[:：対／/]\s*(\d{1,2})/g;
const RE_ARABIC_PAIR_LOOSE = /(\d{1,2})\s*[:：対／/]\s*(\d{1,2})/g;
const RE_KANJI_PAIR = new RegExp(
  `(?:過失割合|責任割合)[^\\d〇零一二三四五六七八九]{0,24}` +
    `(${KANJI_INT_TOKEN})\\s*[:：対]\\s*(${KANJI_INT_TOKEN})`,
  "g",
);
const RE_NAMED_TENTHS =
  /責任割合は[^。]{0,40}?([^\s、,]{1,16})([〇零一二三四五六七八九十\d]{1,2})[、,]([^\s、,]{1,16})([〇零一二三四五六七八九十\d]{1,2})/g;
const RE_PERCENT = new RegExp(
  `(?:過失割合|責任割合|過失の割合)[^\\d〇零一二三四五六七八九]{0,32}` +
    `(${KANJI_INT_TOKEN}|\\d{1,2})\\s*(?:パーセント|％|%)`,
  "g",
);
const RE_PERCENT_LOOSE = new RegExp(
  `(${KANJI_INT_TOKEN}|\\d{1,2})\\s*(?:パーセント|％|%)`,
  "g",
);
const RE_WARI = new RegExp(
  `(原告|被告|訴外[^の]{0,8}|[^\\s、。]{1,12}?)?(?:の)?` +
    `(?:過失割合|過失|責任)[^。]{0,24}` +
    `(${KANJI_INT_TOKEN}|\\d{1,2})\\s*割` +
    `(?:と認める|と判示|とする|である|が相当)?`,
  "g",
);
const RE_MIDDLE_DOT =
  /(?:責任割合|過失割合)[^。]{0,48}?([^\s、,]{1,16}?)([〇零一二三四五六七八九十\d]{1,2})\s*[・･]\s*([〇零一二三四五六七八九十\d])[、,]([^\s、,]{1,16}?)([〇零一二三四五六七八九十\d]{1,2})\s*[・･]\s*([〇零一二三四五六七八九十\d])/g;
const RE_COMPACT_NAMED =
  /(?:を|、|は)([^\s\d：:対／/・･、,]{1,16}?)(\d{1,2})\s*[・･]\s*([^\s\d：:対／/・･、,]{0,16}?)(\d{1,2})(?!\d)/g;

const PARTY_ROLES: Record<string, string> = {
  原告: "plaintiff",
  被告: "defendant",
  控訴人: "appellant",
  被控訴人: "appellee",
};

function roleForLabel(label: string | null): string | null {
  if (!label) return null;
  for (const [key, role] of Object.entries(PARTY_ROLES)) {
    if (label.includes(key)) return role;
  }
  if (/(丸|船|艦)$/.test(label) || label.length >= 2) return "vessel";
  return null;
}

function cleanSideLabel(raw: string | null): string | null {
  if (!raw) return null;
  let label = stripChars(raw, " 　、。のはをがに");
  label = label.replace(/^(?:両船の|その|前記の|本件の|責任割合を?|過失割合を?)/, "");
  label = stripChars(label, " 　、。のをは");
  if (!label || label.length > 16) return null;
  if (["責任割合", "過失割合", "割合", "は", "を", "が"].includes(label)) return null;
  return label;
}

const CAUSE_CONTEXT = /(過失|責任|航行|航法|衝突|海難|見張り|避航|寄与)/;

function causePairInNegligenceContext(text: string, anchors: readonly string[]): boolean {
  const positions: Array<[number, number]> = [];
  for (const anchor of anchors) {
    const idx = text.indexOf(anchor);
    if (idx < 0) return false;
    positions.push([idx, idx + anchor.length]);
  }
  const start = Math.max(0, Math.min(...positions.map((p) => p[0])) - 40);
  const end = Math.min(text.length, Math.max(...positions.map((p) => p[1])) + 40);
  return CAUSE_CONTEXT.test(text.slice(start, end));
}

function* matchAll(re: RegExp, text: string): Generator<RegExpExecArray> {
  const flags = re.flags.includes("g") ? re.flags : re.flags + "g";
  const local = new RegExp(re.source, flags);
  let m: RegExpExecArray | null;
  while ((m = local.exec(text)) !== null) {
    yield m;
    if (m[0].length === 0) local.lastIndex += 1;
  }
}

export function extractFaultRatios(text: string): FaultRatioHit[] {
  text = normalizeJudgmentText(text);
  const hits: FaultRatioHit[] = [];

  function add(
    a: number,
    b: number,
    evidence: string,
    method: string,
    confidence: number,
    opts: {
      side_a_label?: string | null;
      side_b_label?: string | null;
      side_a_role?: string | null;
      side_b_role?: string | null;
    } = {},
  ): void {
    const ratio = ratioStr(a, b);
    if (!ratio) return;
    const la = cleanSideLabel(opts.side_a_label ?? null);
    const lb = cleanSideLabel(opts.side_b_label ?? null);
    hits.push({
      ratio,
      evidence: evidence.trim().slice(0, 160),
      method,
      confidence,
      side_a_label: la,
      side_b_label: lb,
      side_a_role: opts.side_a_role ?? roleForLabel(la),
      side_b_role: opts.side_b_role ?? roleForLabel(lb),
    });
  }

  for (const m of matchAll(RE_ARABIC_PAIR, text)) {
    add(Number(m[1]), Number(m[2]), m[0], "arabic_pair", 0.95);
  }

  for (const m of matchAll(RE_KANJI_PAIR, text)) {
    const a = parseKanjiInt(m[1]!);
    const b = parseKanjiInt(m[2]!);
    if (a !== null && b !== null) add(a, b, m[0], "kanji_pair", 0.95);
  }

  for (const m of matchAll(RE_MIDDLE_DOT, text)) {
    const aWhole = parseKanjiInt(m[2]!);
    const aFrac = parseKanjiInt(m[3]!);
    const bWhole = parseKanjiInt(m[5]!);
    const bFrac = parseKanjiInt(m[6]!);
    if (aWhole !== null && aFrac !== null && bWhole !== null && bFrac !== null) {
      add(
        aWhole * 10 + aFrac,
        bWhole * 10 + bFrac,
        m[0],
        "middle_dot_tenths",
        0.92,
        { side_a_label: m[1], side_b_label: m[4] },
      );
    }
  }

  for (const m of matchAll(RE_NAMED_TENTHS, text)) {
    const a = parseKanjiInt(m[2]!);
    const b = parseKanjiInt(m[4]!);
    if (a !== null && b !== null) {
      add(a, b, m[0], "named_tenths", 0.88, {
        side_a_label: m[1],
        side_b_label: m[3],
      });
    }
  }

  for (const m of matchAll(RE_PERCENT, text)) {
    const pct = parseKanjiInt(m[1]!);
    if (pct !== null) {
      const ratio = singlePercentRatio(pct);
      if (ratio) {
        const [aS, bS] = ratio.split(":");
        const prefix = text.slice(Math.max(0, m.index! - 24), m.index!);
        const nameM = /([^\s、。]{2,12})(?:の)?責任割合\s*$/.exec(prefix);
        const sideA = nameM ? nameM[1]! : null;
        add(Number(aS), Number(bS), m[0], "labeled_percent", 0.9, {
          side_a_label: sideA,
          side_a_role: sideA ? roleForLabel(sideA) : "primary_share",
          side_b_role: "residual_share",
        });
      }
    }
  }

  for (const m of matchAll(RE_PERCENT_LOOSE, text)) {
    const window = text.slice(Math.max(0, m.index! - 40), m.index! + m[0].length + 10);
    if (!/(責任割合|過失割合|過失)/.test(window)) continue;
    const pct = parseKanjiInt(m[1]!);
    if (pct !== null && pct >= 5 && pct <= 95) {
      const ratio = singlePercentRatio(pct);
      if (ratio) {
        const [aS, bS] = ratio.split(":");
        const nameM = /([^\s、。]{2,12})(?:の)?責任割合/.exec(window);
        const sideA = nameM ? nameM[1]! : null;
        add(Number(aS), Number(bS), window.trim(), "context_percent", 0.85, {
          side_a_label: sideA,
          side_a_role: sideA ? roleForLabel(sideA) : "primary_share",
          side_b_role: "residual_share",
        });
      }
    }
  }

  for (const m of matchAll(RE_WARI, text)) {
    const wari = parseKanjiInt(m[2]!);
    if (wari !== null && wari >= 1 && wari <= 9) {
      const ratio = singlePercentRatio(wari * 10);
      if (ratio) {
        const [aS, bS] = ratio.split(":");
        const party = m[1] ?? null;
        add(Number(aS), Number(bS), m[0], "wari", 0.8, {
          side_a_label: party || "原告",
          side_b_label: "相手方",
          side_a_role: roleForLabel(party) || "plaintiff",
          side_b_role: "counterparty",
        });
      }
    }
  }

  for (const m of matchAll(RE_COMPACT_NAMED, text)) {
    const window = text.slice(Math.max(0, m.index! - 24), m.index! + m[0].length + 8);
    if (!/(責任|過失|割合|按分|判示)/.test(window)) continue;
    const la = m[1]!;
    const lb = m[3]!;
    if (!(la || lb)) continue;
    add(Number(m[2]), Number(m[4]), window, "compact_dot", 0.87, {
      side_a_label: la || null,
      side_b_label: lb || null,
    });
  }

  if (!hits.some((h) => h.method === "compact_dot")) {
    for (const m of matchAll(/(\d{1,2})\s*[・･]\s*(\d{1,2})(?!\d)/g, text)) {
      const window = text.slice(Math.max(0, m.index! - 24), m.index! + m[0].length + 8);
      if (/(責任|過失|割合|按分|判示)/.test(window)) {
        add(Number(m[1]), Number(m[2]), window, "compact_dot", 0.87);
      }
    }
  }

  if (!hits.some((h) => h.confidence >= 0.85)) {
    for (const m of matchAll(RE_ARABIC_PAIR_LOOSE, text)) {
      const window = text.slice(Math.max(0, m.index! - 30), m.index! + m[0].length + 10);
      if (/(過失|責任|割合)/.test(window)) {
        add(Number(m[1]), Number(m[2]), window, "loose_arabic", 0.7);
      }
    }
  }

  if (causePairInNegligenceContext(text, ["主因", "一因"])) {
    hits.push({
      ratio: "70:30",
      evidence: "主因/一因",
      method: "shuin_ichin",
      confidence: 0.65,
      side_a_label: null,
      side_b_label: null,
      side_a_role: "primary_cause",
      side_b_role: "secondary_cause",
    });
  } else if (causePairInNegligenceContext(text, ["によって発生", "一因"])) {
    hits.push({
      ratio: "70:30",
      evidence: "によって発生+一因",
      method: "hassei_ichin",
      confidence: 0.6,
      side_a_label: null,
      side_b_label: null,
      side_a_role: "primary_cause",
      side_b_role: "secondary_cause",
    });
  }

  hits.sort((h1, h2) => {
    if (h2.confidence !== h1.confidence) return h2.confidence - h1.confidence;
    const lab1 = h1.side_a_label ? 0 : 1;
    const lab2 = h2.side_a_label ? 0 : 1;
    if (lab1 !== lab2) return lab1 - lab2;
    return h1.ratio < h2.ratio ? -1 : h1.ratio > h2.ratio ? 1 : 0;
  });

  const seen = new Set<string>();
  let unique: FaultRatioHit[] = [];
  for (const h of hits) {
    const key = h.ratio;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(h);
    } else if (
      h.side_a_label &&
      !unique.some((u) => u.ratio === key && u.side_a_label)
    ) {
      unique = unique.map((u) => (u.ratio === key ? h : u));
    }
  }
  return unique;
}

export function bestFaultRatio(text: string): string | null {
  const hits = extractFaultRatios(text);
  return hits.length ? hits[0]!.ratio : null;
}

// ---------------------------------------------------------------------------
// Monetary award extraction
// ---------------------------------------------------------------------------

const YEN_LABELS: Array<[string, RegExp]> = [
  ["claimed", /(?:請求額|請求金額|損害額合計|請求の趣旨|損失補償請求額|本訴請求)/g],
  ["awarded", /(?:認容額|認容|支払を命じ|損害賠償金|支払え|賠償を命)/g],
  ["disallowed", /(?:棄却|否認|排除|認めない|減額)/g],
];

export function extractYenAmounts(text: string): YenHit[] {
  text = normalizeJudgmentText(text);
  const hits: YenHit[] = [];

  for (const [label, pat] of YEN_LABELS) {
    for (const m of matchAll(pat, text)) {
      const window = text.slice(m.index!, m.index! + 80);
      let amount: number | null = null;
      let evidence = window;
      const am = new RegExp(ARABIC_YEN.source).exec(window);
      if (am) {
        amount = parseYenToken(am[1]!);
        evidence = am[0];
      } else {
        const km = new RegExp(KANJI_YEN.source).exec(window);
        if (km) {
          amount = parseYenToken(km[1]!);
          evidence = km[0];
        }
      }
      if (amount !== null && amount > 0) {
        hits.push({ amount_jpy: amount, label, evidence: evidence.slice(0, 80) });
      }
    }
  }

  for (const m of matchAll(ARABIC_YEN, text)) {
    const amount = parseYenToken(m[1]!);
    if (amount !== null && amount >= 100_000) {
      hits.push({ amount_jpy: amount, label: "unlabeled", evidence: m[0] });
    }
  }
  for (const m of matchAll(KANJI_YEN, text)) {
    const amount = parseYenToken(m[1]!);
    if (amount !== null && amount >= 100_000) {
      hits.push({ amount_jpy: amount, label: "unlabeled_kanji", evidence: m[0] });
    }
  }

  return hits;
}

function firstLabeled(hits: YenHit[], label: string): number | null {
  for (const h of hits) {
    if (h.label === label) return h.amount_jpy;
  }
  return null;
}

export function extractNegligenceHolding(
  text: string,
  opts: { window?: number } = {},
): string | null {
  const window = opts.window ?? 280;
  text = normalizeJudgmentText(text);
  if (!text) return null;
  let bestIdx: number | null = null;
  for (const anchor of HOLDING_ANCHORS) {
    const idx = text.indexOf(anchor);
    if (idx >= 0 && (bestIdx === null || idx < bestIdx)) bestIdx = idx;
  }
  if (bestIdx === null) {
    const hits = extractFaultRatios(text);
    if (hits.length && hits[0]!.evidence) return hits[0]!.evidence;
    return null;
  }
  const start = Math.max(0, bestIdx - 40);
  const end = Math.min(text.length, bestIdx + window);
  let excerpt = text.slice(start, end).trim();
  if (excerpt.slice(40).includes("。")) {
    const cut = excerpt.indexOf("。", 40);
    if (cut > 0) excerpt = excerpt.slice(0, cut + 1);
  }
  return excerpt;
}

export function extractFromJudgment(text: string): JudgmentExtraction {
  text = normalizeJudgmentText(text);
  const result = new JudgmentExtraction();
  if (!text) return result;

  const hits = extractFaultRatios(text);
  result.fault_ratio_hits = hits;
  if (hits.length) {
    const best = hits[0]!;
    result.fault_ratio = best.ratio;
    result.side_a_label = best.side_a_label;
    result.side_b_label = best.side_b_label;
    result.side_a_role = best.side_a_role;
    result.side_b_role = best.side_b_role;
  }

  const yenHits = extractYenAmounts(text);
  result.yen_hits = yenHits;
  result.claimed_repair_jpy = firstLabeled(yenHits, "claimed");
  result.awarded_damages_jpy = firstLabeled(yenHits, "awarded");
  result.disallowed_jpy = firstLabeled(yenHits, "disallowed");

  if (result.awarded_damages_jpy === null && result.claimed_repair_jpy === null) {
    const unlabeled = yenHits.filter((h) => h.label.startsWith("unlabeled"));
    if (unlabeled.length && /(損害|賠償|請求|認容)/.test(text)) {
      result.awarded_damages_jpy = Math.max(...unlabeled.map((h) => h.amount_jpy));
    }
  }

  result.holding_excerpt = extractNegligenceHolding(text);
  return result;
}

export function parseFaultRatioParts(
  ratio: string | null | undefined,
): [number, number] | null {
  if (!ratio || typeof ratio !== "string") return null;
  const text = translateFullwidth(ratio.trim());
  const m = /^(\d{1,3})\s*[:：]\s*(\d{1,3})$/.exec(text);
  if (!m) return null;
  const a = Number(m[1]);
  const b = Number(m[2]);
  if (a < 0 || b < 0 || a + b !== 100) return null;
  return [a, b];
}

export function faultRatioWithinPts(
  extracted: string | null | undefined,
  gold: string | null | undefined,
  opts: { max_pts?: number } = {},
): boolean {
  const maxPts = opts.max_pts ?? 10;
  const left = parseFaultRatioParts(extracted ?? null);
  const right = parseFaultRatioParts(gold ?? null);
  if (left === null || right === null) return false;
  return Math.abs(left[0] - right[0]) <= Math.trunc(maxPts);
}

export function extractionMatchesGold(
  extracted: JudgmentExtraction,
  gold: Record<string, unknown>,
  opts: { require_yen?: boolean; fault_ratio_tolerance_pts?: number | null } = {},
): Record<string, unknown> {
  const requireYen = opts.require_yen ?? false;
  const faultRatioTolerancePts = opts.fault_ratio_tolerance_pts ?? null;

  const report: Record<string, unknown> = {
    fault_ratio_ok: null,
    fault_ratio_within_10pt: null,
    claimed_ok: null,
    awarded_ok: null,
    disallowed_ok: null,
  };

  const goldFr = gold.fault_ratio;
  if (goldFr) {
    const exact = extracted.fault_ratio === goldFr;
    const within10 = faultRatioWithinPts(
      extracted.fault_ratio,
      String(goldFr),
      { max_pts: 10 },
    );
    report.fault_ratio_within_10pt = within10;
    if (faultRatioTolerancePts !== null) {
      report.fault_ratio_ok = faultRatioWithinPts(
        extracted.fault_ratio,
        String(goldFr),
        { max_pts: Math.trunc(faultRatioTolerancePts) },
      );
    } else {
      report.fault_ratio_ok = exact;
    }
    report.fault_ratio_exact = exact;
    report.fault_ratio_extracted = extracted.fault_ratio;
    report.fault_ratio_gold = goldFr;
  }

  const fieldPairs: Array<[string, keyof JudgmentExtraction]> = [
    ["claimed_ok", "claimed_repair_jpy"],
    ["awarded_ok", "awarded_damages_jpy"],
    ["disallowed_ok", "disallowed_jpy"],
  ];
  for (const [fieldName, attr] of fieldPairs) {
    const goldV = gold[attr];
    if (typeof goldV === "number" && Number.isInteger(goldV)) {
      const got = extracted[attr] as number | null;
      const ok =
        got === goldV || extracted.yen_hits.some((h) => h.amount_jpy === goldV);
      report[fieldName] = ok;
      report[`${attr}_extracted`] = got;
      report[`${attr}_gold`] = goldV;
    } else if (requireYen) {
      report[fieldName] = false;
    }
  }

  const checks = Object.entries(report)
    .filter(([k, v]) => k.endsWith("_ok") && v !== null)
    .map(([, v]) => v);
  report.all_ok = checks.length > 0 && checks.every(Boolean);
  report.scored_fields = checks.length;
  report.passed_fields = checks.filter(Boolean).length;
  return report;
}
