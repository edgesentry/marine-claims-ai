# PWA in-browser OCR (Issue #94)

Stage A for Rule D5 / COLREGS can ingest **image-only PDFs** via client-side OCR (Tesseract.js WASM, `jpn+eng`). Cloud OCR APIs are not used — uploads stay in the browser (閉域 / FISC-friendly for executive demos).

## Flow

```text
PDF drop
  → pdf.js text layer
  → if empty: render pages → Tesseract.js (same-origin weights)
  → classifyDocument → Analyze
  → runRuleD5FromRepairText / COLREGS extract
  → OCR source uses Stage A confidence 0.52 → HUMAN_REVIEW (#89)
```

Full deskew / table-grid reconstruction remains [#45](https://github.com/edgesentry/marine-claims-ai/issues/45) (Python ingest). This wire-up feeds OCR **text** into the existing Stage A schemas only.

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
| **Client OCR (this issue)** | Live “drop their PDF” in a closed room | Yes after first cache | ~+32 MB | Adequate for demo; low confidence → HUMAN_REVIEW |
| Offline preprocess (#45 path later) | Prep before meeting | No OCR weights needed | Small | Higher (deskew / tables) |
| Cloud OCR API | Convenient | No | Small | High | **Avoided** for Gate B / FISC narrative |

## Cache policy (`_data/cache/ocr/`)

Browser OCR results stay in memory / session only — **never written** into the repo.

Developer / Python intermediate OCR JSON (when #45 lands) belongs under `_data/cache/ocr/` (gitignored Zero-Dataset). Do not commit OCR artifacts or customer scans.

## Manual check (DoD)

1. `cd web && npm run fetch:tessdata && npm run build && npm run preview`
2. Upload a text-layer repair PDF → text path (confidence 0.65) → HUMAN_REVIEW as today.
3. Upload an image-only / blank-text PDF with readable yen lines → OCR progress → router → Analyze → schema-valid lines with `HUMAN_REVIEW_REQUIRED` (confidence 0.52).
4. Toggle airplane mode after first load → repeat step 3.

### Synthetic image-only fixture (local)

```bash
cd web
./scripts/make-ocr-scan-fixture.sh
# → tests/fixtures/ocr_scan_synthetic/repair_scan_image_only.pdf
# (gitignored *.pdf — regenerate locally; pdftotext is empty)
```

Synthetic OCR text used in Vitest: [`web/tests/fixtures/ocr_scan_synthetic/repair_lines.txt`](../web/tests/fixtures/ocr_scan_synthetic/repair_lines.txt).
