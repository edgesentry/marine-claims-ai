# PWA in-browser OCR (Issue #94) + offline deskew (#45)

Stage A for Rule D5 / COLREGS can ingest **image-only PDFs** via client-side OCR (Tesseract.js WASM, `jpn+eng`). Cloud OCR APIs are not used — uploads stay in the browser (閉域 / FISC-friendly for executive demos).

Offline / eval path (Issue #45): Python `marine_claims_ai.ingest.ocr_cleanup` deskews, normalizes contrast, suppresses stamp noise, reconstructs table cells, and emits `RepairItem` JSON (`description` + `estimated_cost`) compatible with the PWA `ExtractedItem` contract.

## Flow

```text
PDF drop (PWA #94)
  → pdf.js text layer
    → if empty: render pages → Tesseract.js (same-origin weights)
    → reconstructTableLines (broken OCR rows) → classifyDocument → Analyze
    → runRuleD5FromRepairText / COLREGS extract
    → OCR source uses Stage A confidence 0.52 → HUMAN_REVIEW (#89)

Offline preprocess (Python #45)
  → deskew / contrast / stamp suppress / table grid
  → RepairItem[] → _data/cache/ocr/*.json (Zero-Dataset; never commit)
  → same Stage A schema fields as PWA ExtractedItem
```

Image geometry (deskew / table-grid / optional `pdf_coordinates`) lives in Python (#45). The WASM client feeds OCR **text** (plus light table-line merge) into existing Stage A schemas.

## Offline assets (airplane mode)

| Bundle | Approx. size | Path (after `npm run fetch:tessdata`) |
| :--- | ---: | :--- |
| Tessdata + WASM cores (incl. relaxedsimd) | ~52 MB | `web/public/tessdata/` + `web/public/tesseract/` |
| **Total OCR offline payload** | **~52 MB** | precached by Service Worker (per-file limit 40 MB) |

DuckDB-WASM and other PWA assets are additional (existing demo).

```bash
cd web
npm run fetch:tessdata   # also runs on predev / prebuild
npm run build && npm run preview
```

After the **first** successful load (SW caches tessdata + WASM):

- Airplane mode still allows OCR on new PDF drops (same-origin only).
- Rule D5 / COLREGS / PSC recalculation and report download continue to work as before.

If tessdata was never fetched, OCR fails closed with an explicit message — Stage B does not run.

## FISC / dock trade-offs

| Approach | Pitch fit | Offline | Bundle | Accuracy on skewed scans |
| :--- | :--- | :--- | :--- | :--- |
| **Client OCR (#94)** | Live “drop their PDF” in a closed room | Yes after first cache | ~+52 MB | Adequate for demo; low confidence → HUMAN_REVIEW |
| **Offline preprocess (#45)** | Prep before meeting / CI ≥95% gate | No browser OCR weights | Small (Python `[ocr]` extra) | Higher (deskew / tables) |
| Cloud OCR API | Convenient | No | Small | High | **Avoided** for Gate B / FISC narrative |

## Hand-off: Python #45 → Stage A (CLI / PWA)

The WASM PWA does **not** call Python at runtime. Preprocess offline, then feed the **same yen-line text** (or a PDF that embeds that text) into the shared Stage A → Rule D5 path.

### 1. Preprocess a scan (Python)

```bash
uv sync --extra ocr
# requires system tesseract-ocr + tesseract-ocr-jpn

uv run python - <<'PY'
from pathlib import Path
from marine_claims_ai.ingest.ocr_cleanup import process_invoice_image
from marine_claims_ai.paths import DEFAULT_OCR_CACHE_DIR

# Input: PNG/JPEG of a drydock invoice (keep under _inputs/ or a local path; do not commit).
items = process_invoice_image(Path("_inputs/repairs/specs/my_scan.png"), cache_key="demo_scan")
print(f"{len(items)} lines → {DEFAULT_OCR_CACHE_DIR / 'demo_scan.json'}")
for it in items:
    print(f"{it.description}\t{it.estimated_cost}")
PY
```

Cache JSON shape (Zero-Dataset; gitignored):

```json
{
  "source": "...",
  "items": [
    { "description": "甲板部 外板補修工事（球状船首）", "estimated_cost": 1200000, "row_index": 0, "source_quote": "...", "bbox": null }
  ],
  "ocr_text": "...",
  "cells": []
}
```

`items[].description` + `items[].estimated_cost` match PWA `ExtractedItem` / CLI repair-line heuristics.

### 2. Export yen lines for Stage A

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from marine_claims_ai.paths import DEFAULT_OCR_CACHE_DIR

cache = json.loads((DEFAULT_OCR_CACHE_DIR / "demo_scan.json").read_text(encoding="utf-8"))
out = Path("_data/cache/ocr/demo_scan_lines.txt")
lines = []
for it in cache["items"]:
    cost = f"{int(it['estimated_cost']):,}"
    lines.append(f"{it['description']} {cost}円")
# Prefer full-page OCR text when present (better Exact Span quotes).
text = (cache.get("ocr_text") or "").strip() or "\n".join(lines)
out.write_text(text + "\n", encoding="utf-8")
print(out)
PY
```

### 3a. Score with the shared CLI (recommended hand-off)

Same `web/src/core` runners as the PWA — no browser OCR weights needed:

```bash
cd web
npm run cli -- rule-d5 --text ../_data/cache/ocr/demo_scan_lines.txt
```

Expect schema-valid repair lines; low confidence / missing spans still abstain into `HUMAN_REVIEW_REQUIRED` (#89) when the runner enforces Stage A gates.

### 3b. Show it in the PWA Rule D5 tab

The Rule D5 tab accepts **PDF drop only** (not a free-text paste). Options:

| Goal | What to drop |
| :--- | :--- |
| Live closed-room demo | Original image-only PDF → in-browser OCR (#94) |
| Pre-cleaned meeting deck | A **text-layer PDF** whose pages contain the exported yen lines (so pdf.js skips OCR). Build any way you like (Word → PDF, `enscript`, etc.); keep under `_data/` / `_inputs/`, never commit customer scans |
| Verify core only | Use **3a CLI**; skip the browser |

After drop → router Confirm → **Analyze** → Confirm & score if abstaining.

There is **no** “Load `_data/cache/ocr/*.json`” button in the PWA. The contract is the shared field shape + text/PDF carrying those lines.

### 4. Quick contract check (no image deps)

```bash
uv run python - <<'PY'
from marine_claims_ai.ingest.ocr_cleanup import extract_tabular_lines
text = open("web/tests/fixtures/ocr_scan_synthetic/repair_lines.txt", encoding="utf-8").read()
print([it.model_dump() for it in extract_tabular_lines(text)])
PY
cd web && npm test -- tests/ocrUploadPath.test.ts
```

## Python OCR extra (Issue #45)

```bash
uv sync --group dev --extra ocr
# system: tesseract-ocr + tesseract-ocr-jpn (CI installs these)
uv run pytest tests/test_ocr_cleanup.py -q
```

Tracked gold: [`config/degraded_invoice_fixtures/manifest.json`](../config/degraded_invoice_fixtures/manifest.json). Synthetic PNGs are generated at test time (not committed).

## Cache policy (`_data/cache/ocr/`)

Browser OCR results stay in memory / session only — **never written** into the repo.

Developer / Python intermediate OCR JSON belongs under `_data/cache/ocr/` (gitignored Zero-Dataset; `DEFAULT_OCR_CACHE_DIR` in `marine_claims_ai.paths`). Do not commit OCR artifacts or customer scans.

## Manual check (DoD)

1. `cd web && npm run fetch:tessdata && npm run build && npm run preview`
2. Upload a text-layer repair PDF → text path (confidence 0.65) → HUMAN_REVIEW as today.
3. Upload an image-only / blank-text PDF with readable yen lines → OCR progress → router → Analyze → schema-valid lines with `HUMAN_REVIEW_REQUIRED` (confidence 0.52).
4. Toggle airplane mode after first load → repeat step 3.
5. (Optional) `uv run pytest tests/test_ocr_cleanup.py` — broken-line + synthetic scan gates ≥95%.

### Synthetic image-only fixture (local)

```bash
cd web
./scripts/make-ocr-scan-fixture.sh
# → tests/fixtures/ocr_scan_synthetic/repair_scan_image_only.pdf
# (gitignored *.pdf — regenerate locally; pdftotext is empty)
```

Synthetic OCR text used in Vitest: [`web/tests/fixtures/ocr_scan_synthetic/repair_lines.txt`](../web/tests/fixtures/ocr_scan_synthetic/repair_lines.txt). Broken-line gold is shared with the Python #45 manifest (`ocr-broken-lines`).
