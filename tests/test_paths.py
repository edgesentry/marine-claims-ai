from __future__ import annotations

from marine_claims_ai import __version__
from marine_claims_ai.paths import (
    DEFAULT_BENCHMARK_DIR,
    DEFAULT_CACHE_DIR,
    DEFAULT_CIVIL_CATALOG_PATH,
    DEFAULT_CONFIG_PATH,
    DEFAULT_DATA_DIR,
    DEFAULT_DATASET_DIR,
    DEFAULT_DUCK_DIR,
    DEFAULT_DUCK_PATH,
    DEFAULT_INPUT_CASUALTIES_DIR,
    DEFAULT_INPUT_LEGAL_DIR,
    DEFAULT_INPUT_REPAIRS_DIR,
    DEFAULT_INPUTS_DIR,
    DEFAULT_JURISDICTIONS_DIR,
    DEFAULT_LOG_DIR,
    DEFAULT_NEGATIVE_PATTERN_PATH,
    LEGACY_DATASET_DIR,
    LEGACY_DUCK_PATH,
    REPO_ROOT,
)


def test_package_version():
    assert __version__ == "0.1.0"


def test_repo_paths_point_inside_checkout():
    assert REPO_ROOT.name == "marine-claims-AI" or (REPO_ROOT / "pyproject.toml").exists()
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert (REPO_ROOT / "src" / "marine_claims_ai").is_dir()


def test_tier_inputs_paths():
    assert DEFAULT_INPUTS_DIR == REPO_ROOT / "_inputs"
    assert DEFAULT_INPUT_REPAIRS_DIR == DEFAULT_INPUTS_DIR / "repairs"
    assert DEFAULT_INPUT_CASUALTIES_DIR == DEFAULT_INPUTS_DIR / "casualties"
    assert DEFAULT_INPUT_LEGAL_DIR == DEFAULT_INPUTS_DIR / "legal"


def test_tier_data_paths():
    assert DEFAULT_DATA_DIR == REPO_ROOT / "_data"
    assert DEFAULT_DUCK_DIR == DEFAULT_DATA_DIR / "duckdb"
    assert DEFAULT_DUCK_PATH == DEFAULT_DUCK_DIR / "marine_claims.duckdb"
    assert DEFAULT_BENCHMARK_DIR == DEFAULT_DATA_DIR / "benchmarks"
    assert DEFAULT_CACHE_DIR == DEFAULT_DATA_DIR / "cache"
    assert DEFAULT_DATASET_DIR == DEFAULT_DATA_DIR / "poc_datasets"


def test_tier_log_path():
    assert DEFAULT_LOG_DIR == REPO_ROOT / "_logs"


def test_legacy_fallback_paths():
    assert LEGACY_DATASET_DIR == DEFAULT_INPUTS_DIR / "poc_datasets"
    assert LEGACY_DUCK_PATH == DEFAULT_DATA_DIR / "marine_claims.duckdb"


def test_tracked_config_paths_exist():
    assert DEFAULT_CONFIG_PATH.name == "benchmark_rules.json"
    assert DEFAULT_NEGATIVE_PATTERN_PATH.is_file()
    assert DEFAULT_CIVIL_CATALOG_PATH.is_file()
    assert DEFAULT_JURISDICTIONS_DIR.name == "jurisdictions"
    assert (DEFAULT_JURISDICTIONS_DIR / "jp.json").is_file()
