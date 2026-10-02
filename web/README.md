# MarineClaims AI — Client-Side WASM PWA

Static Progressive Web App for Rule D5 / COLREGS executive demos (Issue #76).

## Stack

- TypeScript + Vite
- `@duckdb/duckdb-wasm` (Rule D5 SQL + `list_cosine_similarity`)
- `pdfjs-dist` (client-side PDF text extraction)
- Service Worker via `vite-plugin-pwa`

## Commands

```bash
npm install
npm run build:data   # requires repo .venv with duckdb (uv sync)
npm test
npm run dev
npm run build
npm run preview
```

Open the preview URL in Edge/Chrome. After the first load, airplane mode should still allow UC2/UC3 recalculation and report download (same-origin assets only).
