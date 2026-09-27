# Agent Directives: Public Open-Core Repository

## 1. Classification & Scope
- **Repository**: `marine-claims-AI`
- **Visibility**: **PUBLIC / OPEN SOURCE**
- **Purpose**: Open scientific benchmark suite, baseline appraisal pipelines, public data ingestion tools, and generalized naval architecture ontologies.

## 2. Hard Security Constraints for Agents
Any autonomous or semi-autonomous AI agent operating in this codebase MUST strictly adhere to the following rules:

### A. Zero Confidential Data Ingestion
- **NEVER** import, copy, reference, or commit any files, code, or data from external private repositories, local confidential workspaces, or proprietary databases.
- **NEVER** include identifiable real-world claim information, including:
  - Real vessel names or IMO numbers (use fictional or officially anonymized public records only).
  - Specific shipowner, underwriter, or surveyor identities.
  - Proprietary shipyard labor tariffs, man-hour rates, or unredacted financial invoices.
  - Insurer bilateral settlement percentages, non-public circulars, or dispute agreements.

### B. Zero-Dataset Git Policy (Do Not Commit Raw or Extracted Data)
- **NEVER** commit raw external documents (PDFs, HTML files), private spreadsheets (CSV, TSV), or extracted benchmark JSON files to this Git repository.
- All evaluation data must be generated or fetched on-demand into gitignored local cache directories (`_inputs/`, `_data/`, `_logs/`).
- The canonical directory layout and subfolder rules are defined in **[docs/directory_structure_and_data_governance.md](docs/directory_structure_and_data_governance.md)**:
  - `_inputs/`: Raw external documents only (PDF, HTML). Read-only; no databases or generated files.
  - `_data/`: Derived databases (DuckDB, LanceDB), benchmark evaluation JSONs, and rendering/OCR caches.
  - `_logs/`: Runtime operational logs, benchmark evaluation logs, and audit trails.
- Resolve filesystem locations via `marine_claims_ai.paths` (do not hardcode `_inputs/` / `_data/` / `_logs/` relative paths).
- Only source code (`src/marine_claims_ai/`, thin `scripts/` entrypoints), configuration schemas (`config/benchmark_rules.json`), and architectural documentation (`docs/`) are tracked in version control.

### C. Architectural Boundaries
- Keep all domain logic generalized and standard-compliant (e.g., standard COLREGS rules, classification society survey intervals, physical compartment ontologies).
- Do not introduce proprietary insurer-specific policy riders, custom warranty interpretation heuristics, or private legacy system API connectors into this repository.

## 3. Executive demo (CLI + Web)
When changing or extending the Issue #54 executive demo, follow **[docs/executive_demo_cli_and_web.md](docs/executive_demo_cli_and_web.md)** and the per-tab I/O write-up **[docs/demo_use_cases.md](docs/demo_use_cases.md)**:
- Keep CLI and Web on the shared `marine_claims_ai.demo.ops` layer (no duplicated UC logic).
- Prefer local caches under `_data/`; never commit demo datasets.
- Keep EN/JA strings in `demo/i18n.py`; do not embed confidential pitch narratives or hard-coded commercial metrics.
- Vendor offline front-end assets; do not introduce CDN runtime dependencies for the demo.
- Each Web tab should surface use case / inputs / processing / outputs (see `partials/explain_box.html`) and keep interactive conditions wired through ops params.

Install / ingest / eval how-tos for humans and agents: **[docs/getting_started.md](docs/getting_started.md)**.

## 4. Pre-Commit Self-Audit Protocol
Before completing any file creation, editing, or commit generation:
1. Scan for hardcoded credentials, private endpoints, or local file paths pointing to external private or local directories.
2. Confirm that all test fixtures use synthetic or public domain data.
3. Ensure no mentions of confidential commercial strategies appear in docstrings or comments.
