# Marine Claims AI — Node CLI

Thin CLI at repo root. Calls the same Stage A → Stage B **core** as the WASM PWA (`web/src/core/`).

```bash
cd web
npm install
npm run cli -- help
npm run cli -- rule-d5
npm run cli -- colregs --heading-a 30 --heading-b 300 --bearing 70 --facts "横切"
npm run cli -- psc --fixture repeat_ism_major
npm run cli -- classify-encounter --heading-a 0 --heading-b 180 --bearing 0
npm run cli -- schema-ids
```

Layout:

| Path | Role |
| :--- | :--- |
| `cli/main.ts` | CLI entry only |
| `web/src/core/` | Shared runners (not CLI) |
| `web/src/schemas/` | ExtractionResult contracts |
| `web/src/engines/` | Stage B scorers |
| `web/src/main.ts` | PWA UI |
