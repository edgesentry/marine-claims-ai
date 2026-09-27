from __future__ import annotations

from pathlib import Path

from marine_claims_ai.ingest.civil import (
    REAL_DOD_FAULT_RATIO,
    REAL_DOD_YEN,
    _materialize_seeds,
    catalog_stats,
    enrich_from_text,
    has_concrete_document_url,
    html_to_plain,
    load_catalog,
    load_synthetic_catalog,
    local_cache_name,
    real_dod_status,
)
from marine_claims_ai.ingest.public_datasets import CIVIL_COURT_SEEDS


def test_real_and_synthetic_catalogs_are_separated():
    real = load_catalog()
    syn = load_synthetic_catalog()
    assert len(CIVIL_COURT_SEEDS) == len(real)
    assert all(s.get("source_type") != "synthetic_benchmark" for s in real)
    assert all(s.get("source_type") == "synthetic_benchmark" for s in syn)
    assert all(has_concrete_document_url(str(s.get("url") or "")) for s in real)
    stats = catalog_stats(real)
    dod = real_dod_status(stats)
    assert stats["non_synthetic_with_fault_ratio"] >= REAL_DOD_FAULT_RATIO
    assert stats["non_synthetic_with_yen"] >= REAL_DOD_YEN
    assert dod["fault_ratio"] and dod["yen"] and dod["concrete_url"]
    assert catalog_stats(syn)["synthetic"] == len(syn)


def test_enrich_from_pdf_text_extracts_ratio_and_amounts():
    seed = {
        "case_id": 99,
        "input_facts": "基礎事実",
        "fault_ratio": None,
        "awarded_damages_jpy": None,
        "claimed_repair_jpy": None,
        "disallowed_jpy": None,
    }
    text = (
        "責任割合は 70:30 である。"
        "請求額は 20,000,000円、認容額は 12,345,678円、否認は 3,000,000円 とした。"
    )
    out = enrich_from_text(seed, text)
    assert out["fault_ratio"] == "70:30"
    assert out["claimed_repair_jpy"] == 20000000
    assert out["awarded_damages_jpy"] == 12345678
    assert out["disallowed_jpy"] == 3000000
    assert "[pdf_excerpt]" in out["input_facts"]


def test_enrich_does_not_overwrite_seed_values():
    seed = {
        "case_id": 1,
        "input_facts": "seed",
        "fault_ratio": "65:35",
        "awarded_damages_jpy": 100,
        "claimed_repair_jpy": 200,
    }
    text = "過失割合 10:90。認容額は 9,999,999円。請求額は 8,888,888円。"
    out = enrich_from_text(seed, text)
    assert out["fault_ratio"] == "65:35"
    assert out["awarded_damages_jpy"] == 100
    assert out["claimed_repair_jpy"] == 200


def test_enrich_main_cause_fallback():
    seed = {"fault_ratio": None, "input_facts": "x"}
    out = enrich_from_text(seed, "本件衝突の主因はAにあり、Bの過失も一因をなす。")
    assert out["fault_ratio"] == "70:30"


def test_local_cache_name_routes_pdf_and_html():
    assert local_cache_name(1, "https://example.com/a.pdf", "civil_1.pdf") == (
        "civil_pdfs",
        "civil_1.pdf",
    )
    assert local_cache_name(
        5, "https://www.courts.go.jp/app/files/hanrei_jp/123/012345_hanrei.htm"
    ) == ("civil_html", "05_012345_hanrei.htm")
    assert local_cache_name(9, "https://www.yuhikaku.co.jp/article/detail/12345") == (
        "civil_html",
        "09_case_9.html",
    )


def test_html_to_plain_keeps_text():
    assert "過失割合" in html_to_plain("<p>過失割合 60:40</p>")


def test_materialize_saves_raw_html(tmp_path, monkeypatch):
    html_bytes = b"<html><body>\x89\xdb\xae\x84\x8a\x84\x8d\x87 60:40</body></html>"  # mojibake ok; raw preserved

    def fake_download(url, dest_path, force=False, timeout=30):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(html_bytes)
        return True

    monkeypatch.setattr("marine_claims_ai.ingest.civil.download_url", fake_download)
    monkeypatch.setattr("marine_claims_ai.ingest.civil.polite_sleep", lambda _s: None)

    seeds = [
        {
            "case_id": 7,
            "source_type": "published_holding",
            "url": "https://www.courts.go.jp/app/files/hanrei_jp/001/000001_hanrei.htm",
            "input_facts": "seed",
            "fault_ratio": "60:40",
        }
    ]
    out = _materialize_seeds(seeds, str(tmp_path), force=True, download_documents=True)
    cached = tmp_path / "civil_html" / "07_000001_hanrei.htm"
    assert cached.is_file()
    assert cached.read_bytes() == html_bytes
    assert out[0]["local_path"] == "civil_html/07_000001_hanrei.htm"
    assert "[html_excerpt]" in out[0]["input_facts"]
