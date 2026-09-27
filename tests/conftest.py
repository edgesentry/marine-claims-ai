"""Shared fixtures for marine_claims_ai unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_dataset_dir(tmp_path: Path) -> Path:
    """Minimal public-benchmark JSON fixtures for indexing tests."""
    (tmp_path / "benchmark_field1_jmat_cases.json").write_text(
        json.dumps(
            [
                {
                    "case_id": 1,
                    "title": "衝突事件A",
                    "url": "https://example.com/jmat/1",
                    "input_facts": "見張り不十分により衝突した。",
                    "ground_truth_ruling": "見張り義務違反を認定。",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "benchmark_field2_psc_flags.json").write_text(
        json.dumps(
            [
                {
                    "rank": 1,
                    "flag_state": "Panama",
                    "input_inspections_count": 100,
                    "ground_truth_detentions_count": 5,
                    "ground_truth_detention_rate_pct": 5.0,
                    "ground_truth_risk_tier": "GREY/BLACK (High Risk)",
                }
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "benchmark_field3_repair_packages.json").write_text(
        json.dumps(
            [
                {
                    "pkg_id": 1,
                    "category": "船体部",
                    "name": "外板高圧洗浄",
                    "qty": "1式",
                    "ground_truth_cost_jpy": 450000,
                    "trade_code": "HULL-01",
                },
                {
                    "pkg_id": 2,
                    "category": "機関部",
                    "name": "ピストン抜き出し",
                    "qty": "1式",
                    "ground_truth_cost_jpy": 1800000,
                    "trade_code": "ENG-02",
                },
                {
                    "pkg_id": 3,
                    "category": "共通部",
                    "name": "船体入出渠料及び滞渠基本料",
                    "qty": "1式",
                    "ground_truth_cost_jpy": 4300000,
                    "trade_code": "DOCK-01",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "benchmark_court_civil_cases.json").write_text(
        json.dumps(
            [
                {
                    "case_id": 1,
                    "title": "民事衝突",
                    "court": "東京地方裁判所",
                    "url": "https://example.com/civil/1",
                    "input_facts": "運河内接触。便乗修理含む請求。",
                    "holding": "外板のみ認容。過失50:50。",
                    "fault_ratio": "50:50",
                    "claimed_repair_jpy": 10000000,
                    "disallowed_jpy": 3000000,
                    "awarded_damages_jpy": 3500000,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "benchmark_jtsb_collision_cases.json").write_text(
        json.dumps(
            [
                {
                    "case_id": 1,
                    "title": "旅客船はまなす衝突（岸壁）",
                    "date": "2007年 04月27日",
                    "place": "北海道羅臼港係留地",
                    "accident_type": "事故 衝突（単）",
                    "url": "https://example.com/jtsb/1.pdf",
                    "input_facts": "係留地において旅客船が岸壁に衝突した。",
                    "source_type": "jtsb_pdf",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return tmp_path
