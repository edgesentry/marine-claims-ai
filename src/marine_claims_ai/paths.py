"""Shared filesystem paths for the open-core package."""

from __future__ import annotations

from pathlib import Path

# src/marine_claims_ai/paths.py → repo root is parents[1] (src → repo)
PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]

DEFAULT_DATASET_DIR = REPO_ROOT / "_inputs" / "poc_datasets"
DEFAULT_LANCE_DIR = REPO_ROOT / ".lancedb"
DEFAULT_DUCK_PATH = REPO_ROOT / "_inputs" / "marine_claims.duckdb"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "benchmark_rules.json"
DEFAULT_NEGATIVE_PATTERN_PATH = REPO_ROOT / "config" / "negative_pattern_library.json"
DEFAULT_CIVIL_CATALOG_PATH = REPO_ROOT / "config" / "civil_precedent_catalog.json"
DEFAULT_PSC_FIXTURES_PATH = REPO_ROOT / "config" / "psc_inspection_fixtures.json"
DEFAULT_JURISDICTIONS_DIR = REPO_ROOT / "config" / "jurisdictions"
