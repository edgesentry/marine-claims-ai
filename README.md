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
├── AGENTS.md                               # AI agent guidelines & zero-data security rules
├── README.md                               # Project overview and public capabilities
├── pyproject.toml / uv.lock                # uv-managed dependencies (duckdb, fastembed, …)
├── .github/workflows/security-lint.yml     # Zero-Dataset leak check, ruff, markdown CI
├── config/
│   └── benchmark_rules.json                # Decoupled rules, keywords, and triage thresholds
├── docs/
│   └── iterative_knowledge_loop_specification.md  # 5-phase continuous improvement loop spec
└── scripts/
    ├── ci/check_zero_dataset_leak.py       # Tracked-data / path / secret leak scanner
    ├── fetch_public_datasets.py            # Idempotent public data ingestion (Fields 1–4)
    ├── init_duckdb_vector.py               # Build local DuckDB + embeddings (gitignored DB)
    ├── hybrid_search.py                    # SQL filter + cosine similarity search CLI
    ├── verify_3fields_benchmarks.py        # Multi-field benchmark evaluation runner
    └── prototype_experiment.py             # End-to-end PDF parsing and claims adjustment pipeline
```

*(Note: Downloaded PDFs, scraped HTMLs, extracted benchmark JSONs, and `_inputs/marine_claims.duckdb` are local caches only — never committed. CI enforces this Zero-Dataset policy on every PR and push to `main`.)*

---

## Quick Start

### 0. Install dependencies (uv)

```bash
uv sync
```

### 1. Ingest Public Datasets

Fetches missing ground truth datasets (JMAT, PSC, repair packages, civil-court seeds):

```bash
uv run python scripts/fetch_public_datasets.py
```

### 2. Build Local Hybrid Search DB

Embeds cached JSON into a local DuckDB file (written under `_inputs/`, not committed):

```bash
uv run python scripts/init_duckdb_vector.py --force
uv run python scripts/hybrid_search.py --query "外板高圧洗浄" --domain repair --top-k 5
```

### 3. Run Multi-Field Benchmark Evaluation

Executes scientific accuracy verification across public ground truth cases:

```bash
uv run python scripts/verify_3fields_benchmarks.py --config config/benchmark_rules.json
```

### 4. Run Claims Adjustment Pipeline

Analyzes a drydock specification PDF against a casualty report PDF:

```bash
uv run python scripts/prototype_experiment.py \
  --spec _inputs/poc_datasets/sample_drydock_repair_specification.pdf \
  --casualty _inputs/poc_datasets/jtsb_cargo_collision_report.pdf
```

---

## Documentation

- [Iterative Knowledge Loop Specification](docs/iterative_knowledge_loop_specification.md)
- [Benchmark Methodology and Architecture](_inputs/poc_datasets/benchmark_methodology_and_architecture.md)
- [Benchmark Validation Report](_inputs/poc_datasets/3fields_benchmark_validation_report.md)
