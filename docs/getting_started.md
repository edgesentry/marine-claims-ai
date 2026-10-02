# Getting Started

Install, ingest, index, evaluate, and run the claims pipeline. Local caches default to **`_data/`** (legacy **`_inputs/`** remains a read fallback). Never commit raw PDFs or extracted JSON — see [AGENTS.md](../AGENTS.md).

This guide is the canonical how-to formerly kept in the repository README.

Related: [Executive demo](executive_demo_cli_and_web.md) · [Demo use cases](demo_use_cases.md) · [Public benchmarks](public_benchmarks_and_accuracy_evaluation.md) · [Technical stack](technical_stack.md) · [Database lifecycle](database_architecture_and_lifecycle.md).

---

## 0. Install

```bash
uv sync
uv run pytest -q
```

---

## 0b. Executive demo (Issues #54 / #76 / #83)

Browser UI is the static WASM PWA under `web/` (no Python demo server). Tabs: **Rule D5**, **COLREGS**, **PSC**.

Shared Stage A → Stage B logic lives in `web/src/core/` (UI-independent). The Node CLI at repo-root `cli/` calls the same runners for demos and component checks.

```bash
cd web && npm install && npm test && npm run gate-a
cd web && npm run build && npm run preview

# CLI (same core as PWA)
cd web && npm run cli -- help
cd web && npm run cli -- rule-d5
cd web && npm run cli -- colregs --heading-a 30 --heading-b 300 --bearing 70
cd web && npm run cli -- psc --fixture repeat_ism_major
cd web && npm run cli -- classify-encounter --heading-a 0 --heading-b 180 --bearing 0
```

Full design: [executive_demo_cli_and_web.md](executive_demo_cli_and_web.md). Use-case I/O and **legal / rule basis** (AAA Rule D5 · COLREGS / 海上衝突予防法 · Tokyo/Paris MOU + IMO A.1155(32)): [demo_use_cases.md](demo_use_cases.md).

---

## 1. Ingest public datasets

Fetches JMAT (full major index), PSC, repair packages, civil-court seeds, and JTSB collision reports into the local dataset dir (`_data/poc_datasets` by default):

```bash
# Defaults: JMAT uncapped; JTSB limit 200
uv run python scripts/fetch_public_datasets.py --force

# Selective / capped fetches
uv run python scripts/fetch_public_datasets.py --field 1 --force
uv run python scripts/fetch_public_datasets.py --field jtsb --limit 200 --force
uv run python scripts/fetch_public_datasets.py --field 4 --force
```

Civil precedents are split into two tracked catalogs:

- `config/civil_precedent_catalog.json` — **real** documents only (concrete PDF/HTML URLs)
- `config/civil_synthetic_benchmarks.json` — **synthetic** regression patterns (not evidence of real-world accuracy)

```bash
uv run python scripts/civil_coverage.py --catalog
uv run python scripts/civil_coverage.py --lane real
uv run python scripts/civil_coverage.py --lane synthetic
```

Catalog document links (concrete PDF/HTML only):

```bash
# Reachability (CI default)
uv run python scripts/ci/verify_civil_catalog.py --mode alive

# Soft content consistency (title / fault / yen evidence)
uv run python scripts/ci/verify_civil_catalog.py --mode content
```

Entries that only point at `https://www.courts.go.jp/` are skipped (no document to compare).

Automated fault-ratio / yen extraction from raw judgment text (Issue #43):

```bash
# Offline fixtures vs gold patterns (≥90% gate; Zero-Dataset safe)
uv run python scripts/validate_civil_judgment_extractor.py --mode offline

# Local cached PDFs/HTML vs catalog gold (evidenced fields only)
uv run python scripts/validate_civil_judgment_extractor.py --mode local
```

---

## 2. Rebuild local indexes (Polars → DuckDB)

```bash
uv run python scripts/init_duckdb_vector.py --force
uv run python scripts/hybrid_search.py --query "外板高圧洗浄" --domain repair --top-k 5
uv run python scripts/apportion_analytics.py
```

DuckDB path defaults to `_data/duckdb/marine_claims.duckdb` (`marine_claims_ai.paths.DEFAULT_DUCK_PATH`).
Search uses hashed embeddings (same as the offline PWA) plus keyword RRF.

---

## 3. Multi-field benchmark evaluation

```bash
uv run python scripts/verify_3fields_benchmarks.py --config config/benchmark_rules.json
```

### Retrieval scale (hit@k)

Fixed query set in `config/retrieval_eval_queries.json`. Compare thin vs scaled corpora:

```bash
uv run python scripts/eval_retrieval_scale.py \
  --out _data/poc_datasets/retrieval_scale_report.json

# After rebuilding on a larger cache, diff against a saved baseline:
uv run python scripts/eval_retrieval_scale.py \
  --baseline _data/poc_datasets/retrieval_scale_report_baseline.json \
  --out _data/poc_datasets/retrieval_scale_report.json
```

---

## 4. Claims adjustment pipeline

```bash
uv run python scripts/prototype_experiment.py \
  --spec _data/poc_datasets/sample_drydock_repair_specification.pdf \
  --casualty _data/poc_datasets/jtsb_cargo_collision_report.pdf \
  --export-report

# Negative Pattern Library red-flag scoring (standalone)
uv run python scripts/score_negative_patterns.py \
  --text "主機関シリンダヘッド及びピストン抜出開放点検" \
  --text "船体外板高圧清水洗浄"
```

If PDFs still live under legacy `_inputs/poc_datasets/`, pass those paths explicitly or copy/symlink into `_data/poc_datasets/`.

JPY amounts on public specs without tender prices are **standard unit-price heuristics** (see `summary.pricing_note`). The optional `--export-report` writes a deterministic English Preliminary Survey Report (no LLM).

### Public appraisal accuracy / Gate A

**Canonical (PDF-free):** TypeScript Vitest harness.

```bash
cd web && npm run gate-a
```

Optional: if you need a machine-readable report from the browser Gate A runner, use `npm run gate-a` (writes under `web/` / `_data` as configured there). Legacy Python Gate A entrypoints were removed after the WASM migration.

Gates: Critical FA = 0, Rule D5 recon = 0 JPY, (at scale) mean status agreement ≥ 85%.

---

## Repository layout (reference)

```text
marine-claims-AI/
├── AGENTS.md
├── README.md
├── pyproject.toml / uv.lock
├── src/marine_claims_ai/     # ingest / index / analytics / CI (Python)
├── web/                      # WASM PWA SoT (engines, Gate A, UI)
├── scripts/                  # thin CLI entrypoints
├── config/
└── docs/
```

`_data/`, `_inputs/` (legacy), and `*.duckdb` are gitignored local caches. Core logic lives under `src/marine_claims_ai/`; `scripts/` only wraps `main()` entrypoints.
