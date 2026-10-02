#!/usr/bin/env node
/**
 * Build static Parquet + JSON assets for the WASM PWA.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, copyFileSync, writeFileSync, unlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(__dirname, "..");
const repoRoot = resolve(webRoot, "..");
const outDir = join(webRoot, "public", "data");
mkdirSync(outDir, { recursive: true });

const configFiles = [
  "fault_ratio_rules.json",
  "civil_precedent_catalog.json",
  "jmat_collision_eval.json",
  "collision_geometries.json",
  "psc_inspection_fixtures.json",
];

for (const name of configFiles) {
  const src = join(repoRoot, "config", name);
  if (existsSync(src)) copyFileSync(src, join(outDir, name));
}

// Issue #92 — anonymized MOU-style sample (tracked as .txt; Zero-Dataset bans .html)
const pscSampleSrc = join(
  webRoot,
  "tests",
  "fixtures",
  "psc",
  "tokyo_mou_table_sample.txt",
);
if (existsSync(pscSampleSrc)) {
  copyFileSync(pscSampleSrc, join(outDir, "psc_sample_inspection.txt"));
}

const py = `
import json, math, re
from pathlib import Path

import duckdb

REPO = Path(${JSON.stringify(repoRoot)})
OUT = Path(${JSON.stringify(outDir)})
DIM = 384

def tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[\\w\\u3040-\\u30ff\\u3400-\\u9fff]+", text or "") if len(t) >= 2]

def fnv1a(s: str) -> int:
    h = 0x811C9DC5
    for ch in s:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def hash_embed(text: str) -> list[float]:
    # Must match web/src/engines/fault.ts hashEmbed (FNV-1a).
    vec = [0.0] * DIM
    toks = tokenize(text)
    if not toks:
        return vec
    for tok in toks:
        h = fnv1a(tok)
        idx = h % DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

civil = json.loads((REPO / "config" / "civil_precedent_catalog.json").read_text(encoding="utf-8"))
seeds = civil.get("seeds") or []

con = duckdb.connect()
con.execute("""
CREATE TABLE civil (
  case_id VARCHAR,
  title VARCHAR,
  court VARCHAR,
  input_facts VARCHAR,
  holding VARCHAR,
  fault_ratio VARCHAR,
  blob VARCHAR,
  embedding FLOAT[]
)
""")
for s in seeds:
    blob = " ".join(str(s.get(k) or "") for k in ("title", "input_facts", "holding", "court"))
    emb = hash_embed(blob)
    con.execute(
        "INSERT INTO civil VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            str(s.get("case_id") or ""),
            str(s.get("title") or ""),
            str(s.get("court") or ""),
            str(s.get("input_facts") or ""),
            str(s.get("holding") or ""),
            str(s.get("fault_ratio") or ""),
            blob,
            emb,
        ],
    )
con.execute(f"COPY civil TO '{(OUT / 'civil_precedents.parquet').as_posix()}' (FORMAT PARQUET)")

jmat = json.loads((REPO / "config" / "jmat_collision_eval.json").read_text(encoding="utf-8"))
cases = jmat.get("cases") or []
con.execute("""
CREATE TABLE jmat (
  case_id VARCHAR,
  title VARCHAR,
  facts_text VARCHAR,
  ruling_text VARCHAR,
  expected_situation VARCHAR,
  expected_role_a VARCHAR,
  expected_role_b VARCHAR,
  embedding FLOAT[]
)
""")
for c in cases:
    blob = " ".join(str(c.get(k) or "") for k in ("title", "facts_text", "ruling_text"))
    emb = hash_embed(blob)
    con.execute(
        "INSERT INTO jmat VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            str(c.get("case_id") or ""),
            str(c.get("title") or ""),
            str(c.get("facts_text") or ""),
            str(c.get("ruling_text") or ""),
            str(c.get("expected_situation") or ""),
            str(c.get("expected_role_a") or ""),
            str(c.get("expected_role_b") or ""),
            emb,
        ],
    )
con.execute(f"COPY jmat TO '{(OUT / 'jmat_cases.parquet').as_posix()}' (FORMAT PARQUET)")
print(f"wrote civil={len(seeds)} jmat={len(cases)}")
`;

const pyPath = join(outDir, "_build_parquet.py");
writeFileSync(pyPath, py);

const candidates = [
  join(repoRoot, ".venv", "bin", "python"),
  "python3",
  "python",
];

let ok = false;
let lastErr = "";
for (const bin of candidates) {
  try {
    if (bin.includes("/") && !existsSync(bin)) continue;
    execFileSync(bin, [pyPath], { stdio: "inherit" });
    ok = true;
    break;
  } catch (err) {
    lastErr = String(err);
  }
}

try {
  unlinkSync(pyPath);
} catch {
  /* ignore */
}

if (!ok) {
  console.warn("[build-data] DuckDB Parquet build skipped; JSON fixtures only.");
  if (lastErr) console.warn(lastErr.slice(0, 400));
} else {
  console.log("[build-data] parquet + JSON ready in", outDir);
}
