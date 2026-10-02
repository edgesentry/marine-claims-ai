from __future__ import annotations

import json
from pathlib import Path

from marine_claims_ai.benchmarks.retrieval_scale import (
    aggregate_hit_rates,
    diff_reports,
    hit_at_k,
    run_eval,
)
from marine_claims_ai.index.build import load_json_first, rows_from_sources


def test_hit_at_k_domain_and_prefix():
    hits = [
        {"id": "repair-1", "domain": "repair"},
        {"id": "jmat-2", "domain": "jmat"},
    ]
    assert hit_at_k(hits, ["jmat"], None, 2) is True
    assert hit_at_k(hits, ["jtsb"], None, 1) is False
    assert hit_at_k(hits, None, ["jmat-"], 2) is True
    assert hit_at_k(hits, None, ["jtsb-"], 2) is False


def test_aggregate_and_diff():
    per = [
        {"hits": {"hit@5": True, "hit@10": True}},
        {"hits": {"hit@5": False, "hit@10": True}},
    ]
    agg = aggregate_hit_rates(per, [5, 10])
    assert agg["hit@5"] == 0.5
    assert agg["hit@10"] == 1.0
    delta = diff_reports({"aggregate": {"hit@5": 0.25}}, {"aggregate": agg})
    assert delta["hit@5"]["delta"] == 0.25


def test_run_eval_with_stub_search(tmp_path: Path):
    queries = {
        "k_values": [5],
        "queries": [
            {
                "id": "q1",
                "query": "外板洗浄",
                "expected_domains": ["repair"],
                "expected_id_prefixes": ["repair-"],
            }
        ],
    }
    qpath = tmp_path / "q.json"
    qpath.write_text(json.dumps(queries), encoding="utf-8")

    def stub_search(_lance, _q, _d, _t, top_k):
        return [{"id": "repair-1", "domain": "repair"}][:top_k]

    report = run_eval(str(tmp_path / "marine.duckdb"), qpath, search_fn=stub_search)
    assert report["aggregate"]["hit@5"] == 1.0
    assert report["per_query"][0]["top_ids"] == ["repair-1"]


def test_rows_include_jtsb_and_legacy_fallback(tmp_path: Path, sample_dataset_dir: Path):
    rows = rows_from_sources(str(sample_dataset_dir))
    domains = {r["domain"] for r in rows}
    assert "jtsb" in domains
    assert "jmat" in domains

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "benchmark_field1_jmat_20cases.json").write_text(
        json.dumps(
            [
                {
                    "case_id": 9,
                    "title": "legacy",
                    "url": "",
                    "input_facts": "旧ファイル",
                    "ground_truth_ruling": "裁決",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    data, name = load_json_first(
        str(legacy),
        "benchmark_field1_jmat_cases.json",
        "benchmark_field1_jmat_20cases.json",
    )
    assert name.endswith("20cases.json")
    assert data[0]["case_id"] == 9
