from __future__ import annotations

import json
from pathlib import Path

from marine_claims_ai.benchmarks.civil_coverage import coverage_from_json
from marine_claims_ai.ingest.civil import catalog_stats


def test_coverage_from_json(tmp_path: Path):
    cases = [
        {
            "case_id": 1,
            "source_type": "court_pdf",
            "fault_ratio": "65:35",
            "claimed_repair_jpy": 1000,
            "awarded_damages_jpy": 500,
        },
        {
            "case_id": 2,
            "source_type": "published_holding",
            "fault_ratio": "70:30",
            "claimed_repair_jpy": None,
            "awarded_damages_jpy": None,
        },
        {
            "case_id": 3,
            "source_type": "synthetic_benchmark",
            "fault_ratio": "50:50",
            "claimed_repair_jpy": 9,
            "awarded_damages_jpy": 1,
        },
    ]
    path = tmp_path / "benchmark_court_civil_cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    stats = coverage_from_json(path)
    assert stats["total"] == 3
    assert stats["non_synthetic"] == 2
    assert stats["non_synthetic_with_fault_ratio"] == 2
    assert stats["non_synthetic_with_yen"] == 1
    assert stats["synthetic"] == 1
    assert catalog_stats(cases)["non_synthetic_with_yen"] == 1
