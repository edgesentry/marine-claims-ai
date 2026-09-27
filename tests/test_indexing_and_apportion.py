from __future__ import annotations

import json
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
    assert domains == {"jmat", "psc", "repair", "civil_court", "jtsb"}
    assert len(rows) == 7

    repair = [r for r in rows if r["domain"] == "repair"]
    by_id = {r["id"]: r for r in repair}
    assert by_id["repair-1"]["casualty_related"] is True
    assert by_id["repair-2"]["casualty_related"] is False  # ENG-* concurrent
    assert by_id["repair-3"]["casualty_related"] is True  # DOCK common dues
    assert by_id["repair-3"]["trade_code"] == "DOCK-01"


def test_normalize_with_polars_types(sample_dataset_dir: Path):
    rows = rows_from_sources(str(sample_dataset_dir))
    df = normalize_with_polars(rows)
    assert df.height == 7
    assert "cost_jpy" in df.columns
    assert df.filter(df["id"] == "repair-2")["casualty_related"][0] is False


def test_duckdb_apportionment_summary(tmp_path: Path, sample_dataset_dir: Path):
    rows = rows_from_sources(str(sample_dataset_dir))
    df = normalize_with_polars(rows)
    duck_path = tmp_path / "test.duckdb"
    build_duckdb_analytics(str(duck_path), df, force=True)

    summary = summarize(str(duck_path))
    # HULL casualty + ENG owner + DOCK (no SAFE/PROP → D5 ¶1 → dock 100% UW)
    assert summary["repair_items"] == 3
    assert summary["claimed_total_jpy"] == 450000 + 1800000 + 4300000
    assert summary["insurer_share_jpy"] == 450000 + 4300000
    assert summary["owner_concurrent_jpy"] == 1800000
    assert summary["claims_leakage_prevented_jpy"] == 1800000
    # drydock_fee_5050 only non-zero when statutory owner work triggers 50/50
    assert summary["drydock_5050_pool_jpy"] == 0
    assert any(item["id"] == "repair-2" for item in summary["leakage_items"])


def test_summarize_missing_db_raises(tmp_path: Path):
    missing = tmp_path / "nope.duckdb"
    try:
        summarize(str(missing))
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised


def test_duckdb_apportionment_5050_with_statutory(tmp_path: Path, sample_dataset_dir: Path):
    """SAFE-* in the same docking triggers D5 ¶2(a) 50/50 on DOCK lines."""
    repair_path = sample_dataset_dir / "benchmark_field3_repair_packages.json"
    packages = json.loads(repair_path.read_text(encoding="utf-8"))
    packages.append(
        {
            "pkg_id": 4,
            "category": "法定部",
            "name": "JG 定期検査",
            "qty": "1式",
            "ground_truth_cost_jpy": 550000,
            "trade_code": "SAFE-01",
        }
    )
    repair_path.write_text(json.dumps(packages, ensure_ascii=False), encoding="utf-8")

    rows = rows_from_sources(str(sample_dataset_dir))
    df = normalize_with_polars(rows)
    duck_path = tmp_path / "test_5050.duckdb"
    build_duckdb_analytics(str(duck_path), df, force=True)
    summary = summarize(str(duck_path))

    assert summary["repair_items"] == 4
    assert summary["insurer_share_jpy"] == 450000 + (4300000 // 2)
    assert summary["owner_concurrent_jpy"] == 1800000 + 550000 + (4300000 // 2)
    assert summary["drydock_5050_pool_jpy"] == 4300000 * 0.5
