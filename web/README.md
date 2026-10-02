# MarineClaims AI — Client-Side WASM PWA

Static Progressive Web App for Rule D5 / COLREGS / PSC executive demos (Issues #76 / #83).

## Stack

- TypeScript + Vite
- `@duckdb/duckdb-wasm` (Rule D5 SQL + `list_cosine_similarity`)
- `pdfjs-dist` (client-side PDF text extraction)
- `tesseract.js` (in-browser OCR for image-only PDFs — Issue #94)
- Service Worker via `vite-plugin-pwa`

## Commands

```bash
npm install
npm run fetch:tessdata   # ~52 MB OCR weights into public/ (also on predev/prebuild)
npm run build:data       # requires repo .venv with duckdb (uv sync)
npm test
npm run dev
npm run build
npm run preview
```

Open the preview URL in Edge/Chrome. After the first load, airplane mode should still allow Rule D5 / COLREGS / PSC recalculation, **in-browser OCR** (once tessdata/WASM are cached), and report download (same-origin assets only).

OCR offline sizes, FISC trade-offs, and `_data/cache/ocr/` policy: [docs/pwa_ocr_offline.md](../docs/pwa_ocr_offline.md).
