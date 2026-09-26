from __future__ import annotations

from pathlib import Path

from marine_claims_ai.analytics.apportion import summarize
from marine_claims_ai.index.build import (
    build_duckdb_analytics,
    normalize_with_polars,
    rows_from_sources,
)


def test_rows_from_sources_maps_domains(sample_dataset_dir: Path):
    rows = rows_from_sources(str(sample_dataset_dir))
    domains = {r["domain"] for r in rows}
    assert domains == {"jmat", "psc", "repair", "civil_court"}
    assert len(rows) == 5

    repair = [r for r in rows if r["domain"] == "repair"]
    by_id = {r["id"]: r for r in repair}
    assert by_id["repair-1"]["casualty_related"] is True
    assert by_id["repair-2"]["casualty_related"] is False  # ENG-* concurrent


def test_normalize_with_polars_types(sample_dataset_dir: Path):
    rows = rows_from_sources(str(sample_dataset_dir))
    df = normalize_with_polars(rows)
    assert df.height == 5
    assert "cost_jpy" in df.columns
    assert df.filter(df["id"] == "repair-2")["casualty_related"][0] is False


def test_duckdb_apportionment_summary(tmp_path: Path, sample_dataset_dir: Path):
    rows = rows_from_sources(str(sample_dataset_dir))
    df = normalize_with_polars(rows)
    duck_path = tmp_path / "test.duckdb"
    build_duckdb_analytics(str(duck_path), df, force=True)

    summary = summarize(str(duck_path))
    assert summary["repair_items"] == 2
    assert summary["claimed_total_jpy"] == 450000 + 1800000
    assert summary["insurer_share_jpy"] == 450000
    assert summary["owner_concurrent_jpy"] == 1800000
    assert summary["claims_leakage_prevented_jpy"] == 1800000
    assert summary["drydock_5050_pool_jpy"] == int((450000 + 1800000) * 0.5)
    assert any(item["id"] == "repair-2" for item in summary["leakage_items"])


def test_summarize_missing_db_raises(tmp_path: Path):
    missing = tmp_path / "nope.duckdb"
    try:
        summarize(str(missing))
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised
