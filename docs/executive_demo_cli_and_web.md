# Executive Demo & Gate A: WASM PWA (Issues #54 / #76 / #83)

**Source of truth:** `web/src/` (TypeScript + DuckDB-WASM).

| Area | Path |
| :--- | :--- |
| Engines | `web/src/engines/` (Rule D5, COLREGS, fault, BFS, **PSC**) |
| Shared core runners | `web/src/core/` (Stage A → Stage B; used by PWA + CLI) |
| Node CLI | `cli/main.ts` (`cd web && npm run cli -- …`) |
| Stage A schemas | `web/src/schemas/` (Zod `ExtractionResult`; JSON Schema in `docs/schemas/`) |
| Appraisal + NPL | `web/src/appraisal/` |
| Exact Span A4 | `web/src/pipeline/` |
| Multilingual lexicon (#90) | `web/src/pipeline/normalizeLabels.ts`, `detectLanguage.ts`, `lexicon.ts`; SoT `config/lexicons/shipyard_jargon.v1.json` |
| Civil A7 | `web/src/ingest/civilJudgmentExtractor.ts` |
| Field3 A8 | `web/src/benchmarks/verify3Fields.ts` |
| Gate A | `web/src/benchmarks/gateAPriority{1,2}.ts` |
| Tests | `web/tests/` (Vitest) |

Demo tabs: **1. Rule D5** · **2. COLREGS** · **3. PSC** (public MOU fixtures → Defect Score).

**Legal / rule basis (one line each):** London AAA **Rule D5** · **COLREGS 1972** Rules 13–17 / **海上衝突予防法** 第13–17条 · Tokyo/Paris **MOU** deficiency + action codes (IMO A.1155(32) procedures context). Full table: [demo_use_cases.md](demo_use_cases.md#legal--rule-basis-summary).

## Stage A → Stage B contract (Issue #87)

Tier 1 heuristics (and later Tier 2 SLM / Tier 3 LLM) must emit a validated **`ExtractionResult`** envelope before any Stage B scorer runs:

| `schema_id` | Payload (summary) | Stage B consumer |
| :--- | :--- | :--- |
| `rule_d5.v1` | `docking_context` + repair `lines[]` | `apportionRuleD` |
| `colregs.v1` | `geometry` + facts/ruling excerpts + optional situation candidates | `classifyEncounter` / `predictFaultRatio` |
| `psc.v1` | normalized-ready `deficiencies[]` (+ optional priors) | `scoreSeaworthiness` |

Envelope fields: `{ schema_id, payload, confidence, field_confidence?, grounding[], abstain? }`. Invalid JSON is rejected (`ExtractionValidationError`) and does **not** reach Rule D5 / COLREGS / PSC scorers. Low confidence under `enforce` stamps `HUMAN_REVIEW_REQUIRED` and skips Stage B until Confirm & score ([confidence abstention](confidence_abstention.md)). Public JSON Schema exports live under [`docs/schemas/`](schemas/); regenerate with `cd web && npm run build:schemas`. Guided-decode helpers (`guidedDecodeSpec`) prepare SLM/LLM paths (#77 / #5) without invoking models here. **Display i18n ≠ extraction language:** UI locale (`i18n.ts`) does not change schema enums; JA/EN jargon → ontology codes via lexicon (#90). Vector candidates are #104, not the default path.

### Exact Span grounding (Issue #88)

Shape-valid envelopes still need source grounding for critical fields before Stage B, unless the caller sets `groundingMode: "paste_bypass"` (hand-pasted PSC JSON, fixtures, synthetic UI). See [exact_span_grounding.md](exact_span_grounding.md).

```bash
cd web
npm install
npm test
npm run gate-a
npm run build && npm run preview
```

Python demo CLI / Gate A shims were removed; use the WASM PWA and the TypeScript CLI (`cli/`, via `npm run cli`) which share `web/src/core/`.

**Python kept intentionally (build-time / corpus ops):**

| Package | Why it stays |
| :--- | :--- |
| `ingest/` | Network fetch, polite download, PDF/HTML cache for public corpora |
| `index/` | DuckDB build + vector/keyword retrieval (`marine-claims-index` / search) |
| `analytics/apportion.py` + `drydock_sql.py` | DuckDB SQL plane over built indexes |
| `benchmarks/retrieval_scale.py`, `civil_coverage.py` | Corpus-scale metrics over local DuckDB/catalog |
| `ci/`, `adapters/`, `ontology/psc.py` | Leak checks, jurisdiction adapters, PSC code maps for ingest (PWA SoT is `web/src/engines/psc.ts`) |

LanceDB / fastembed were removed; search uses DuckDB `list_cosine_similarity` + keyword RRF with PWA-aligned hash embeddings.
