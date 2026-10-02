"""Shared filesystem paths for the open-core package.

Canonical 3-tier layout (`_inputs/` / `_data/` / `_logs/`) is defined in
``docs/directory_structure_and_data_governance.md``. Callers must use these
constants instead of hardcoding relative paths.
"""

from __future__ import annotations

from pathlib import Path

# src/marine_claims_ai/paths.py → repo root is parents[1] (src → repo)
PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]

# --- Tier 1: raw external documents (read-only) -------------------------------
DEFAULT_INPUTS_DIR = REPO_ROOT / "_inputs"
DEFAULT_INPUT_REPAIRS_DIR = DEFAULT_INPUTS_DIR / "repairs"
DEFAULT_INPUT_CASUALTIES_DIR = DEFAULT_INPUTS_DIR / "casualties"
DEFAULT_INPUT_JMAT_DIR = DEFAULT_INPUT_CASUALTIES_DIR / "jmat"
DEFAULT_INPUT_JTSB_DIR = DEFAULT_INPUT_CASUALTIES_DIR / "jtsb"
DEFAULT_INPUT_LEGAL_DIR = DEFAULT_INPUTS_DIR / "legal"
DEFAULT_INPUT_CIVIL_COURT_DIR = DEFAULT_INPUT_LEGAL_DIR / "civil_court"
DEFAULT_INPUT_CHARTER_PARTY_DIR = DEFAULT_INPUTS_DIR / "charter_party"
DEFAULT_INPUT_REINSURANCE_DIR = DEFAULT_INPUTS_DIR / "reinsurance"
DEFAULT_INPUT_STANDARDS_DIR = DEFAULT_INPUTS_DIR / "standards"

# --- Tier 2: derived storage (rebuildable) ------------------------------------
DEFAULT_DATA_DIR = REPO_ROOT / "_data"
DEFAULT_DUCK_DIR = DEFAULT_DATA_DIR / "duckdb"
DEFAULT_DUCK_PATH = DEFAULT_DUCK_DIR / "marine_claims.duckdb"
DEFAULT_BENCHMARK_DIR = DEFAULT_DATA_DIR / "benchmarks"
DEFAULT_CACHE_DIR = DEFAULT_DATA_DIR / "cache"
DEFAULT_OCR_CACHE_DIR = DEFAULT_CACHE_DIR / "ocr"

# Compat: flat PoC PDF cache used by current demo / eval scripts.
DEFAULT_DATASET_DIR = DEFAULT_DATA_DIR / "poc_datasets"

# --- Tier 3: operational / audit logs ----------------------------------------
DEFAULT_LOG_DIR = REPO_ROOT / "_logs"

# --- Legacy locations (read fallbacks; prefer constants above) ----------------
LEGACY_DATASET_DIR = DEFAULT_INPUTS_DIR / "poc_datasets"
LEGACY_DUCK_PATH = DEFAULT_DATA_DIR / "marine_claims.duckdb"

# --- Tracked config -----------------------------------------------------------
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "benchmark_rules.json"
DEFAULT_NEGATIVE_PATTERN_PATH = REPO_ROOT / "config" / "negative_pattern_library.json"
DEFAULT_CIVIL_CATALOG_PATH = REPO_ROOT / "config" / "civil_precedent_catalog.json"
DEFAULT_PSC_FIXTURES_PATH = REPO_ROOT / "config" / "psc_inspection_fixtures.json"
DEFAULT_JURISDICTIONS_DIR = REPO_ROOT / "config" / "jurisdictions"
