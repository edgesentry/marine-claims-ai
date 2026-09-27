"""Local cache loaders for the demo (defaults under ``_data/``)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from marine_claims_ai.paths import (
    DEFAULT_CIVIL_CATALOG_PATH,
    DEFAULT_DATASET_DIR,
    LEGACY_DATASET_DIR,
    REPO_ROOT,
)

KAIYOMARU_ANALYSIS = "claims_analysis_kaiyomaru.json"
JMAT_EVAL = REPO_ROOT / "config" / "jmat_collision_eval.json"
GEOMETRIES = REPO_ROOT / "config" / "collision_geometries.json"


def resolve_dataset_dir() -> Path:
    """Prefer ``_data/poc_datasets``, fall back to legacy ``_inputs/poc_datasets``."""
    if DEFAULT_DATASET_DIR.is_dir():
        return DEFAULT_DATASET_DIR
    if LEGACY_DATASET_DIR.is_dir():
        return LEGACY_DATASET_DIR
    return DEFAULT_DATASET_DIR


def resolve_kaiyomaru_path() -> Path | None:
    for base in (DEFAULT_DATASET_DIR, LEGACY_DATASET_DIR):
        path = base / KAIYOMARU_ANALYSIS
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def load_kaiyomaru_analysis() -> dict[str, Any] | None:
    path = resolve_kaiyomaru_path()
    if path is None:
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_jmat_cases() -> list[dict[str, Any]]:
    with JMAT_EVAL.open(encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("cases") or [])


@lru_cache(maxsize=1)
def load_civil_catalog() -> list[dict[str, Any]]:
    with DEFAULT_CIVIL_CATALOG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return list(data)
    for key in ("seeds", "cases", "entries"):
        if key in data:
            return list(data.get(key) or [])
    return []


@lru_cache(maxsize=1)
def load_geometries() -> list[dict[str, Any]]:
    with GEOMETRIES.open(encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("cases") or [])


def clear_loader_caches() -> None:
    load_kaiyomaru_analysis.cache_clear()
    load_jmat_cases.cache_clear()
    load_civil_catalog.cache_clear()
    load_geometries.cache_clear()


def clear_demo_caches() -> dict[str, int]:
    """Clear demo analysis JSON, PDF page previews, uploads, and in-memory loaders.

    Does not delete public source PDFs under ``poc_datasets`` / ``_inputs``.
    """
    import shutil

    from marine_claims_ai.demo.documents import UPLOAD_DIR
    from marine_claims_ai.demo.pdf_preview import PREVIEW_DIR
    from marine_claims_ai.paths import DEFAULT_DATA_DIR, DEFAULT_DATASET_DIR

    removed_json = 0
    for base in (DEFAULT_DATASET_DIR, LEGACY_DATASET_DIR):
        if not base.is_dir():
            continue
        for path in base.glob("claims_analysis_*.json"):
            try:
                path.unlink()
                removed_json += 1
            except OSError:
                pass

    removed_pages = 0
    if PREVIEW_DIR.is_dir():
        for child in PREVIEW_DIR.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                    removed_pages += 1
                elif child.is_file():
                    child.unlink()
                    removed_pages += 1
            except OSError:
                pass

    removed_uploads = 0
    if UPLOAD_DIR.is_dir():
        for path in UPLOAD_DIR.iterdir():
            try:
                if path.is_file():
                    path.unlink()
                    removed_uploads += 1
            except OSError:
                pass

    clear_loader_caches()
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "analysis_json": removed_json,
        "pdf_pages": removed_pages,
        "uploads": removed_uploads,
    }
