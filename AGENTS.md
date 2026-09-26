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
- All evaluation data must be generated or fetched on-demand into gitignored local cache directories (`_inputs/`, `datasets/`).
- Only source code (`scripts/`), configuration schemas (`config/benchmark_rules.json`), and architectural documentation (`docs/`) are tracked in version control.

### C. Architectural Boundaries
- Keep all domain logic generalized and standard-compliant (e.g., standard COLREGS rules, classification society survey intervals, physical compartment ontologies).
- Do not introduce proprietary insurer-specific policy riders, custom warranty interpretation heuristics, or private legacy system API connectors into this repository.

## 3. Pre-Commit Self-Audit Protocol
Before completing any file creation, editing, or commit generation:
1. Scan for hardcoded credentials, private endpoints, or local file paths pointing to external private or local directories.
2. Confirm that all test fixtures use synthetic or public domain data.
3. Ensure no mentions of confidential commercial strategies appear in docstrings or comments.
