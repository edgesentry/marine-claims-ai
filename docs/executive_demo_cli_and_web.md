# Executive Demo & Gate A: WASM PWA (Issues #54 / #76)

**Source of truth:** `web/src/` (TypeScript + DuckDB-WASM).

| Area | Path |
| :--- | :--- |
| Engines | `web/src/engines/` (Rule D5, COLREGS, fault, BFS) |
| Appraisal + NPL | `web/src/appraisal/` |
| Exact Span A4 | `web/src/pipeline/` |
| Civil A7 | `web/src/ingest/civilJudgmentExtractor.ts` |
| Field3 A8 | `web/src/benchmarks/verify3Fields.ts` |
| Gate A | `web/src/benchmarks/gateAPriority{1,2}.ts` |
| Tests | `web/tests/` (Vitest) |

```bash
cd web
npm install
npm test
npm run gate-a
npm run build && npm run preview
```

`marine-claims-demo` and Gate A Python scripts print these instructions and exit 2.

**Python kept intentionally (build-time / corpus ops):**

| Package | Why it stays |
| :--- | :--- |
| `ingest/` | Network fetch, polite download, PDF/HTML cache for public corpora |
| `index/` | DuckDB build + vector/keyword retrieval (`marine-claims-index` / search) |
| `analytics/apportion.py` + `drydock_sql.py` | DuckDB SQL plane over built indexes |
| `benchmarks/retrieval_scale.py`, `civil_coverage.py` | Corpus-scale metrics over local DuckDB/catalog |
| `ci/`, `adapters/`, `ontology/psc.py` | Leak checks, jurisdiction adapters, PSC code maps for ingest |
| `demo/cli.py` | Redirect shim only |

LanceDB / fastembed were removed; search uses DuckDB `list_cosine_similarity` + keyword RRF with PWA-aligned hash embeddings.
