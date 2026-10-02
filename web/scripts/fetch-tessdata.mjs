/**
 * Fetch Tesseract traineddata + copy WASM/worker into public/ for same-origin
 * airplane-mode PWA caching (Issue #94).
 *
 * Sources: tessdata_fast (eng + jpn) from projectnaptha; core/worker from node_modules.
 */
import { createWriteStream, existsSync, mkdirSync, copyFileSync, statSync } from "node:fs";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");
const tessdataDir = path.join(webRoot, "public", "tessdata");
const tesseractPublic = path.join(webRoot, "public", "tesseract");

const LANGS = ["eng", "jpn"];
const TESSDATA_BASE =
  "https://tessdata.projectnaptha.com/4.0.0_fast";

const CORE_FILES = [
  "tesseract-core.wasm.js",
  "tesseract-core.wasm",
  "tesseract-core-simd.wasm.js",
  "tesseract-core-simd.wasm",
  "tesseract-core-lstm.wasm.js",
  "tesseract-core-lstm.wasm",
  "tesseract-core-simd-lstm.wasm.js",
  "tesseract-core-simd-lstm.wasm",
  "tesseract-core-relaxedsimd.wasm.js",
  "tesseract-core-relaxedsimd.wasm",
  "tesseract-core-relaxedsimd-lstm.wasm.js",
  "tesseract-core-relaxedsimd-lstm.wasm",
];

function mb(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function download(url, dest) {
  if (existsSync(dest) && statSync(dest).size > 1000) {
    console.log(`  skip (exists): ${path.relative(webRoot, dest)} (${mb(statSync(dest).size)})`);
    return;
  }
  console.log(`  fetch ${url}`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  await pipeline(Readable.fromWeb(res.body), createWriteStream(dest));
  console.log(`  wrote ${path.relative(webRoot, dest)} (${mb(statSync(dest).size)})`);
}

mkdirSync(tessdataDir, { recursive: true });
mkdirSync(tesseractPublic, { recursive: true });

console.log("Tessdata (fast eng + jpn)…");
for (const lang of LANGS) {
  await download(
    `${TESSDATA_BASE}/${lang}.traineddata.gz`,
    path.join(tessdataDir, `${lang}.traineddata.gz`),
  );
}

console.log("Copy tesseract.js worker + core…");
const workerSrc = path.join(webRoot, "node_modules", "tesseract.js", "dist", "worker.min.js");
const workerDest = path.join(tesseractPublic, "worker.min.js");
copyFileSync(workerSrc, workerDest);
console.log(`  ${path.relative(webRoot, workerDest)} (${mb(statSync(workerDest).size)})`);

const coreDir = path.join(webRoot, "node_modules", "tesseract.js-core");
for (const name of CORE_FILES) {
  const src = path.join(coreDir, name);
  if (!existsSync(src)) {
    console.warn(`  missing core file: ${name}`);
    continue;
  }
  const dest = path.join(tesseractPublic, name);
  copyFileSync(src, dest);
  console.log(`  ${path.relative(webRoot, dest)} (${mb(statSync(dest).size)})`);
}

let total = 0;
for (const dir of [tessdataDir, tesseractPublic]) {
  for (const f of await import("node:fs").then((m) => m.readdirSync(dir))) {
    total += statSync(path.join(dir, f)).size;
  }
}
console.log(`OCR offline assets total ≈ ${mb(total)}`);
