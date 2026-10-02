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
