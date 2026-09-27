# MarineClaims AI

AI-powered marine insurance claims appraisal, fault attribution, and concurrent repair screening engine.

---

## Overview

MarineClaims AI provides non-life insurers, average adjusters, and marine surveyors with an automated decision-support pipeline for hull and machinery (H&M) claims.

By combining deterministic domain engines (COLREGS rules, naval architecture structural ontologies, and insurance policy clauses) with large language model normalization, the platform eliminates claims leakage (unwarranted payouts for routine shipyard maintenance) and objectively attributes casualty fault without hallucinations.

---

## Key Capabilities

1. **Concurrent Repair Screening**:
   - Evaluates multi-page drydock repair specifications against incident damage zones.
   - Detects routine periodic maintenance (e.g., piston extraction, sea chest valve overhauls) disguised as casualty repairs.
   - Scores each line item against a curated **Negative Pattern Library** (`config/negative_pattern_library.json`) via FastEmbed cosine similarity: `>= 0.80` Disallowed, `0.50–0.80` Apportioned 50%, `< 0.50` Approved (then keyword/ontology gates apply).
   - Automatically applies standard 50/50 drydocking fee apportionment rules.

2. **Collision Fault Attribution**:
   - Evaluates navigational parameters (heading, speed, visibility) against the International Regulations for Preventing Collisions at Sea (COLREGS) and Japan Marine Accident Tribunal (JMAT) rulings.

3. **Port State Control (PSC) Risk Scoring**:
   - Analyzes Paris MOU and Tokyo MOU flag inspection records to predict vessel detention and unseaworthiness risks.

---

## Scope of Open Assets

MarineClaims AI provides a fully open and reproducible foundation for marine claims appraisal:

1. **On-Demand Public Data Ingestion & Benchmarking**:
   - Zero raw datasets or extracted JSON files are bundled directly in this repository to prevent third-party copyright or redistribution issues.
   - Ground truth datasets (JMAT rulings, Paris/Tokyo MOU PSC records, public vessel drydock tenders) are fetched or constructed on demand directly into local workspace caches via reproducible scripts.

2. **Standard Naval Architecture & Regulatory Ontologies**:
   - Ship structural hierarchy and physical compartment ontologies (Hull, Machinery, Superstructure, Watertight Bulkheads).
   - Formal International Regulations for Preventing Collisions at Sea (COLREGS) rule taxonomy.
   - Classification society statutory periodic survey intervals and standardized scope items.

3. **Open Core Verification Engine & Code**:
   - Deterministic naval architecture constraint validation engine (ensures zero physically impossible causal links).
   - Multi-field scientific benchmark runner (`verify_3fields_benchmarks.py`).
   - Idempotent public data ingestion pipeline (`fetch_public_datasets.py`).
   - End-to-end claims appraisal prototype pipeline (`prototype_experiment.py`).

4. **Specifications & Scientific Methodologies**:
   - Continuous 5-phase iterative knowledge loop specification.
   - Scientific benchmark evaluation methodologies and architectural documentation.

---

## Repository Structure

```text
marine-claims-AI/
├── AGENTS.md
├── README.md
├── pyproject.toml / uv.lock          # installable package + uv deps
├── src/marine_claims_ai/             # publishable core library
│   ├── ingest/                       # public dataset fetchers
│   ├── index/                        # LanceDB build + hybrid search
│   ├── analytics/                    # DuckDB apportionment
│   ├── ontology/                     # NetworkX compartment graph
│   ├── appraisal/                    # claims pipeline
│   ├── benchmarks/                   # scientific evaluators
│   └── ci/                           # Zero-Dataset leak scanner
├── scripts/                          # thin CLI entrypoints only
│   ├── ci/check_zero_dataset_leak.py
│   ├── fetch_public_datasets.py
│   ├── eval_retrieval_scale.py
│   ├── init_duckdb_vector.py
│   ├── hybrid_search.py
│   ├── apportion_analytics.py
│   ├── validate_compartment_path.py
│   ├── verify_3fields_benchmarks.py
│   └── prototype_experiment.py
├── config/
└── docs/
```

*(Note: `_inputs/`, `.lancedb/`, and `*.duckdb` are local caches only — never committed. CI enforces Zero-Dataset policy on every PR and push to `main`.)*

Core logic lives under `src/marine_claims_ai/` so the project can be installed and later published as a Python package (`uv sync` / `pip install -e .`). `scripts/` only wraps `main()` entrypoints.

---

## Quick Start

### 0. Install dependencies (uv)

```bash
uv sync
uv run pytest -q
```

### 1. Ingest Public Datasets

Fetches JMAT (full major index), PSC, repair packages, civil-court seeds, and JTSB collision reports:

```bash
# Defaults: JMAT uncapped; JTSB limit 200
uv run python scripts/fetch_public_datasets.py --force

# Selective / capped fetches
uv run python scripts/fetch_public_datasets.py --field 1 --force
uv run python scripts/fetch_public_datasets.py --field jtsb --limit 200 --force
uv run python scripts/fetch_public_datasets.py --field 4 --force
```

Civil precedents are split into two tracked catalogs:

- `config/civil_precedent_catalog.json` — **real** documents only (concrete PDF/HTML URLs) for apportionment / leakage eval
- `config/civil_synthetic_benchmarks.json` — **synthetic** regression patterns (not evidence of real-world accuracy)

```bash
uv run python scripts/civil_coverage.py --catalog
uv run python scripts/civil_coverage.py --lane real
uv run python scripts/civil_coverage.py --lane synthetic
```

Catalog document links (concrete PDF/HTML only) can be checked in CI / locally:

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

### 2. Rebuild Local Indexes (Polars → LanceDB + DuckDB)

```bash
uv run python scripts/init_duckdb_vector.py --force
uv run python scripts/hybrid_search.py --query "外板高圧洗浄" --domain repair --top-k 5
uv run python scripts/apportion_analytics.py
uv run python scripts/validate_compartment_path.py --damage-zone 球状船首 --repair-zone 機関室
```

### 3. Run Multi-Field Benchmark Evaluation

```bash
uv run python scripts/verify_3fields_benchmarks.py --config config/benchmark_rules.json
```

### 3b. Retrieval scale evaluation (hit@k)

Fixed query set in `config/retrieval_eval_queries.json`. Compare thin vs scaled corpora:

```bash
uv run python scripts/eval_retrieval_scale.py \
  --out _inputs/poc_datasets/retrieval_scale_report.json

# After rebuilding on a larger cache, diff against a saved baseline:
uv run python scripts/eval_retrieval_scale.py \
  --baseline _inputs/poc_datasets/retrieval_scale_report_baseline.json \
  --out _inputs/poc_datasets/retrieval_scale_report.json
```

### 4. Run Claims Adjustment Pipeline

```bash
uv run python scripts/prototype_experiment.py \
  --spec _inputs/poc_datasets/sample_drydock_repair_specification.pdf \
  --casualty _inputs/poc_datasets/jtsb_cargo_collision_report.pdf \
  --export-report

# Negative Pattern Library red-flag scoring (standalone)
uv run python scripts/score_negative_patterns.py \
  --text "主機関シリンダヘッド及びピストン抜出開放点検" \
  --text "船体外板高圧清水洗浄"
```

JPY amounts on public specs without tender prices are **standard unit-price heuristics** (see `summary.pricing_note`). The optional `--export-report` writes a deterministic English Preliminary Survey Report (no LLM).

### 4b. Public appraisal accuracy (Week 1)

Measure item-status agreement against **provisional founder gold v1** on tracked public casualty×spec pairs (`config/public_appraisal_eval.json`). PDFs remain local under `_inputs/`.

```bash
uv run python scripts/eval_public_appraisal.py \
  --json-out _inputs/poc_datasets/public_appraisal_eval_report.json \
  --write-gold-dir _inputs/poc_datasets/public_appraisal_gold \
  --fail-on-gate
```

Gates (config): ≥3 runnable cases, critical False Accept = 0, mean status agreement ≥ 85%.

**Interpretation:** provisional gold v1 is an independent *code path* (not a call into `pipeline.py`), but it encodes the same naval-architecture checklist. High agreement today is mainly a **regression signal** (parser/ontology breaks show up as FA/FR). It is **not** a substitute for surveyor-labeled gold or Gate B (#6). Dump `_inputs/.../public_appraisal_gold/` and hand-edit statuses to create a true held-out gold set.

---

## Documentation

- [Technical Stack Architecture](docs/technical_stack.md)
- [Iterative Knowledge Loop Specification](docs/iterative_knowledge_loop_specification.md)
- [Open-Core Research & Development Roadmap](docs/research_and_development_roadmap.md)
- [Symbolic AI Implementation Framework](docs/symbolic_ai_implementation_framework.md)
- [AAA Rule D5 Drydock Apportionment (Issue #29)](docs/aaa_rule_d5_drydock_apportionment.md)
- [Public Datasets & Accuracy Evaluation Methodology](docs/public_benchmarks_and_accuracy_evaluation.md)
- [Prior Research Synthesis](docs/prior_research_synthesis.md)
- [Benchmark Methodology and Architecture](_inputs/poc_datasets/benchmark_methodology_and_architecture.md)
- [Benchmark Validation Report](_inputs/poc_datasets/3fields_benchmark_validation_report.md)

---

## License

This project is licensed under the [Apache License, Version 2.0](LICENSE).

Dependency license policy is enforced in CI via `pip-licenses` (installed environment) and GitHub Dependency Review (PR dependency diffs). Strong copyleft and common source-available traps (GPL/AGPL/LGPL/SSPL/BUSL, etc.) fail the build.
