/**
 * Shipyard / inspection jargon lexicon loader + longest-token match (Issue #90).
 */
import lexiconJson from "./lexicons/shipyard_jargon.v1.json";

export type LexiconDomain =
  | "repair"
  | "docking"
  | "situation"
  | "psc_action"
  | "psc_critical";

export interface RepairLexiconHit {
  id: string;
  trade_code: string;
  necessity?: "statutory_seaworthiness" | "deferred" | "unspecified";
  work_party?: "casualty" | "owner" | "common";
  matchedToken: string;
}

export interface DockingLexiconHit {
  id: string;
  docking_context: "casualty_immediate" | "deferred_to_routine";
  matchedToken: string;
}

export interface SituationLexiconHit {
  id: string;
  situation: "head_on" | "overtaking" | "crossing" | "safe_passing";
  matchedToken: string;
}

export interface PscActionLexiconHit {
  id: string;
  action_code: string;
  matchedToken: string;
}

export interface PscCriticalLexiconHit {
  id: string;
  critical_system: string;
  matchedToken: string;
}

interface TokenEntry {
  token: string;
  tokenNorm: string;
  id: string;
  payload: Record<string, unknown>;
}

interface LexiconFile {
  version: number;
  description?: string;
  domains: Record<string, Array<Record<string, unknown>>>;
}

const FILE = lexiconJson as LexiconFile;

function normalizeForMatch(s: string): string {
  return (s || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function buildIndex(domain: LexiconDomain): TokenEntry[] {
  const rows = FILE.domains[domain] || [];
  const out: TokenEntry[] = [];
  for (const row of rows) {
    const id = String(row.id || "");
    const tokens = Array.isArray(row.tokens) ? row.tokens : [];
    for (const t of tokens) {
      const token = String(t);
      if (!token.trim()) continue;
      out.push({
        token,
        tokenNorm: normalizeForMatch(token),
        id,
        payload: row,
      });
    }
  }
  // Longest token first so "ピストン抜出" wins over "ピストン".
  out.sort((a, b) => b.tokenNorm.length - a.tokenNorm.length);
  return out;
}

const INDEX: Record<LexiconDomain, TokenEntry[]> = {
  repair: buildIndex("repair"),
  docking: buildIndex("docking"),
  situation: buildIndex("situation"),
  psc_action: buildIndex("psc_action"),
  psc_critical: buildIndex("psc_critical"),
};

function isAsciiToken(tokenNorm: string): boolean {
  return /^[a-z0-9][a-z0-9 _/-]*$/i.test(tokenNorm);
}

function tokenInHaystack(hay: string, tokenNorm: string): boolean {
  if (!tokenNorm) return false;
  // Short Latin tokens (e.g. "ism") must not substring-match inside "mechanism".
  if (isAsciiToken(tokenNorm) && /^[a-z0-9]/i.test(tokenNorm)) {
    const escaped = tokenNorm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`(?:^|[^a-z0-9])${escaped}(?:[^a-z0-9]|$)`, "i");
    return re.test(hay);
  }
  return hay.includes(tokenNorm);
}

function matchDomain(domain: LexiconDomain, text: string): TokenEntry | null {
  const hay = normalizeForMatch(text);
  if (!hay) return null;
  for (const entry of INDEX[domain]) {
    if (tokenInHaystack(hay, entry.tokenNorm)) return entry;
  }
  return null;
}

export function matchRepairPhrase(text: string): RepairLexiconHit | null {
  const hit = matchDomain("repair", text);
  if (!hit) return null;
  const trade = hit.payload.trade_code;
  if (typeof trade !== "string" || !trade) return null;
  const out: RepairLexiconHit = {
    id: hit.id,
    trade_code: trade,
    matchedToken: hit.token,
  };
  const nec = hit.payload.necessity;
  if (
    nec === "statutory_seaworthiness" ||
    nec === "deferred" ||
    nec === "unspecified"
  ) {
    out.necessity = nec;
  }
  const wp = hit.payload.work_party;
  if (wp === "casualty" || wp === "owner" || wp === "common") {
    out.work_party = wp;
  }
  return out;
}

export function matchDockingContext(text: string): DockingLexiconHit | null {
  const hit = matchDomain("docking", text);
  if (!hit) return null;
  const ctx = hit.payload.docking_context;
  if (ctx !== "casualty_immediate" && ctx !== "deferred_to_routine") return null;
  return { id: hit.id, docking_context: ctx, matchedToken: hit.token };
}

export function matchSituationLabel(text: string): SituationLexiconHit | null {
  const hit = matchDomain("situation", text);
  if (!hit) return null;
  const sit = hit.payload.situation;
  if (
    sit !== "head_on" &&
    sit !== "overtaking" &&
    sit !== "crossing" &&
    sit !== "safe_passing"
  ) {
    return null;
  }
  return { id: hit.id, situation: sit, matchedToken: hit.token };
}

export function matchPscActionPhrase(text: string): PscActionLexiconHit | null {
  const hit = matchDomain("psc_action", text);
  if (!hit) return null;
  const code = hit.payload.action_code;
  if (typeof code !== "string" || !code) return null;
  return { id: hit.id, action_code: code, matchedToken: hit.token };
}

export function matchCriticalSystemPhrase(text: string): PscCriticalLexiconHit | null {
  const hit = matchDomain("psc_critical", text);
  if (!hit) return null;
  const sys = hit.payload.critical_system;
  if (typeof sys !== "string" || !sys) return null;
  return { id: hit.id, critical_system: sys, matchedToken: hit.token };
}

/** Exposed for tests / docs — lexicon version stamp. */
export function lexiconVersion(): number {
  return FILE.version;
}
