# Getting Started

Install, ingest, index, evaluate, and run the claims pipeline. Local caches default to **`_data/`** (legacy **`_inputs/`** remains a read fallback). Never commit raw PDFs or extracted JSON — see [AGENTS.md](../AGENTS.md).

This guide is the canonical how-to formerly kept in the repository README.

Related: [Executive demo](executive_demo_cli_and_web.md) · [Public benchmarks](public_benchmarks_and_accuracy_evaluation.md) · [Technical stack](technical_stack.md) · [Database lifecycle](database_architecture_and_lifecycle.md).

---

## 0. Install

```bash
uv sync
uv run pytest -q
```

Optional Web demo dependencies:

```bash
uv sync --group demo
```

---

## 0b. Executive demo (Issue #54)

CLI and Web share `marine_claims_ai.demo.ops`. Full design: [executive_demo_cli_and_web.md](executive_demo_cli_and_web.md).

```bash
uv run marine-claims-demo uc1 --lang ja
uv run marine-claims-demo uc2 --dock-days 5 --export-md _data/rule_d5.md
uv run marine-claims-demo list-cases
uv run marine-claims-demo uc3 --case civil_7 --export-md _data/colregs.md

uv sync --group demo
uv run marine-claims-demo serve
# → http://127.0.0.1:8765/
```

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

## 2. Rebuild local indexes (Polars → LanceDB + DuckDB)

```bash
uv run python scripts/init_duckdb_vector.py --force
uv run python scripts/hybrid_search.py --query "外板高圧洗浄" --domain repair --top-k 5
uv run python scripts/apportion_analytics.py
uv run python scripts/validate_compartment_path.py --damage-zone 球状船首 --repair-zone 機関室
```

DuckDB path defaults to `_data/marine_claims.duckdb` (`marine_claims_ai.paths.DEFAULT_DUCK_PATH`).

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

### Public appraisal accuracy

Measure item-status agreement against **provisional founder gold v1** on tracked public casualty×spec pairs (`config/public_appraisal_eval.json`). PDFs remain local under `_data/` / `_inputs/`.

```bash
uv run python scripts/eval_public_appraisal.py \
  --json-out _data/poc_datasets/public_appraisal_eval_report.json \
  --write-gold-dir _data/poc_datasets/public_appraisal_gold \
  --fail-on-gate
```

Gates (config): ≥3 runnable cases, critical False Accept = 0, mean status agreement ≥ 85%.

**Interpretation:** provisional gold v1 is an independent *code path* (not a call into `pipeline.py`), but it encodes the same naval-architecture checklist. High agreement today is mainly a **regression signal** (parser/ontology breaks show up as FA/FR). It is **not** a substitute for surveyor-labeled gold or Gate B. Dump `public_appraisal_gold/` and hand-edit statuses to create a true held-out gold set.

---

## Repository layout (reference)

```text
marine-claims-AI/
├── AGENTS.md
├── README.md
├── pyproject.toml / uv.lock
├── src/marine_claims_ai/     # publishable core (+ demo/)
├── scripts/                  # thin CLI entrypoints
├── config/
└── docs/
```

`_data/`, `_inputs/` (legacy), `.lancedb/`, and `*.duckdb` are gitignored local caches. Core logic lives under `src/marine_claims_ai/`; `scripts/` only wraps `main()` entrypoints.
