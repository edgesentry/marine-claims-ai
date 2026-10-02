"""Hash-embed and DuckDB retrieval smoke tests."""

from __future__ import annotations

from pathlib import Path

from marine_claims_ai.index.build import (
    build_duckdb,
    normalize_with_polars,
    rows_from_sources,
)
from marine_claims_ai.index.embed import hash_embed
from marine_claims_ai.index.search import search


def test_hash_embed_stable_and_normalized():
    a = hash_embed("船体外板高圧清水洗浄")
    b = hash_embed("船体外板高圧清水洗浄")
    assert a == b
    assert len(a) == 384
    norm = sum(x * x for x in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_duckdb_search_returns_repair_hit(tmp_path: Path, sample_dataset_dir: Path):
    rows = rows_from_sources(str(sample_dataset_dir))
    df = normalize_with_polars(rows)
    duck_path = tmp_path / "search.duckdb"
    build_duckdb(str(duck_path), df, force=True)
    hits = search(str(duck_path), "外板洗浄", "repair", None, 5)
    assert hits
    assert any(str(h.get("id") or "").startswith("repair-") for h in hits)
