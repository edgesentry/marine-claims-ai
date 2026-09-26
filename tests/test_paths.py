from __future__ import annotations

from marine_claims_ai import __version__
from marine_claims_ai.paths import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_DATASET_DIR,
    DEFAULT_DUCK_PATH,
    DEFAULT_LANCE_DIR,
    DEFAULT_NEGATIVE_PATTERN_PATH,
    REPO_ROOT,
)


def test_package_version():
    assert __version__ == "0.1.0"


def test_repo_paths_point_inside_checkout():
    assert REPO_ROOT.name == "marine-claims-AI" or (REPO_ROOT / "pyproject.toml").exists()
    assert DEFAULT_DATASET_DIR.parent.name == "_inputs"
    assert DEFAULT_LANCE_DIR.name == ".lancedb"
    assert DEFAULT_DUCK_PATH.name == "marine_claims.duckdb"
    assert DEFAULT_CONFIG_PATH.name == "benchmark_rules.json"
    assert DEFAULT_NEGATIVE_PATTERN_PATH.name == "negative_pattern_library.json"
    assert DEFAULT_NEGATIVE_PATTERN_PATH.is_file()
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert (REPO_ROOT / "src" / "marine_claims_ai").is_dir()
