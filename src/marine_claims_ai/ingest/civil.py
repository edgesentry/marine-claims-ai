"""Field 4: real civil precedents vs synthetic regression benchmarks (kept separate)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from marine_claims_ai.ingest.civil_judgment_extractor import extract_from_judgment
from marine_claims_ai.ingest.download import download_url, polite_sleep
from marine_claims_ai.ingest.jtsb import apply_limit
from marine_claims_ai.ingest.pdf_text import pdf_to_text
from marine_claims_ai.paths import REPO_ROOT

CIVIL_JSON = "benchmark_court_civil_cases.json"
SYNTHETIC_JSON = "benchmark_court_civil_synthetic.json"
DEFAULT_CATALOG = REPO_ROOT / "config" / "civil_precedent_catalog.json"
DEFAULT_SYNTHETIC_CATALOG = REPO_ROOT / "config" / "civil_synthetic_benchmarks.json"
NON_SYNTHETIC = frozenset({"court_pdf", "published_holding"})

# Honest floors after separating portal stubs / models from real lane.
# REAL_DOD_* = ingest sanity floor; GATE_A_SCALE_* = Issue #59 corpus targets.
REAL_DOD_FAULT_RATIO = 60
REAL_DOD_YEN = 4
GATE_A_SCALE_TARGET_FAULT_RATIO = 60
GATE_A_SCALE_TARGET_CIVIL_CASES = 60


def has_concrete_document_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.netloc == "www.courts.go.jp" and parsed.path in ("", "/"):
        return False
    return True


def load_catalog(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load REAL precedent catalog only."""
    catalog_path = Path(path) if path else DEFAULT_CATALOG
    with open(catalog_path, encoding="utf-8") as f:
        data = json.load(f)
    seeds = data.get("seeds") if isinstance(data, dict) else data
    if not isinstance(seeds, list):
        raise ValueError(f"Invalid civil catalog at {catalog_path}")
    return seeds


def load_synthetic_catalog(path: str | Path | None = None) -> list[dict[str, Any]]:
    catalog_path = Path(path) if path else DEFAULT_SYNTHETIC_CATALOG
    with open(catalog_path, encoding="utf-8") as f:
        data = json.load(f)
    seeds = data.get("seeds") if isinstance(data, dict) else data
    if not isinstance(seeds, list):
        raise ValueError(f"Invalid synthetic catalog at {catalog_path}")
    return seeds


def catalog_stats(seeds: list[dict[str, Any]]) -> dict[str, int]:
    non_syn = [s for s in seeds if s.get("source_type") in NON_SYNTHETIC]
    with_fr = [s for s in non_syn if s.get("fault_ratio")]
    with_yen = [
        s
        for s in non_syn
        if s.get("claimed_repair_jpy") is not None or s.get("awarded_damages_jpy") is not None
    ]
    by_type: dict[str, int] = {}
    for s in seeds:
        key = str(s.get("source_type") or "unknown")
        by_type[key] = by_type.get(key, 0) + 1
    concrete = sum(1 for s in non_syn if has_concrete_document_url(str(s.get("url") or "")))
    return {
        "total": len(seeds),
        "non_synthetic": len(non_syn),
        "non_synthetic_with_fault_ratio": len(with_fr),
        "non_synthetic_with_yen": len(with_yen),
        "non_synthetic_with_concrete_url": concrete,
        "synthetic": by_type.get("synthetic_benchmark", 0),
        **{f"type_{k}": v for k, v in sorted(by_type.items())},
    }


def real_dod_status(
    stats: dict[str, int],
    *,
    fault_ratio_floor: int | None = None,
    yen_floor: int | None = None,
) -> dict[str, bool]:
    """
    Check corpus floors.

    Defaults use ``REAL_DOD_*`` ingest sanity thresholds. Pass
    ``fault_ratio_floor=GATE_A_SCALE_TARGET_FAULT_RATIO`` for Gate A scale.
    """
    fr_floor = REAL_DOD_FAULT_RATIO if fault_ratio_floor is None else int(fault_ratio_floor)
    y_floor = REAL_DOD_YEN if yen_floor is None else int(yen_floor)
    return {
        "fault_ratio": stats["non_synthetic_with_fault_ratio"] >= fr_floor,
        "yen": stats["non_synthetic_with_yen"] >= y_floor,
        "concrete_url": stats.get("non_synthetic_with_concrete_url", 0)
        >= stats.get("non_synthetic", 0),
    }


def enrich_from_text(
    record: dict[str, Any],
    text: str,
    *,
    excerpt_tag: str = "pdf_excerpt",
) -> dict[str, Any]:
    """Pull fault ratios and yen figures from judgment / saiketsu text."""
    if not text:
        return record
    out = dict(record)
    extracted = extract_from_judgment(text)

    if not out.get("fault_ratio") and extracted.fault_ratio:
        out["fault_ratio"] = extracted.fault_ratio

    if out.get("claimed_repair_jpy") is None and extracted.claimed_repair_jpy is not None:
        out["claimed_repair_jpy"] = extracted.claimed_repair_jpy

    if out.get("awarded_damages_jpy") is None and extracted.awarded_damages_jpy is not None:
        out["awarded_damages_jpy"] = extracted.awarded_damages_jpy

    if out.get("disallowed_jpy") is None and extracted.disallowed_jpy is not None:
        out["disallowed_jpy"] = extracted.disallowed_jpy

    compact = re.sub(r"\s+", " ", text)[:3500]
    if compact:
        base_facts = out.get("input_facts") or ""
        marker = f"[{excerpt_tag}]"
        if marker not in base_facts and "[pdf_excerpt]" not in base_facts and "[html_excerpt]" not in base_facts:
            out["input_facts"] = f"{base_facts}\n{marker} {compact}".strip()
    return out


_enrich_from_pdf_text = enrich_from_text


def decode_document_bytes(raw: bytes) -> str:
    for enc in ("utf-8", "shift_jis", "cp932", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def html_to_plain(raw_html: str) -> str:
    """Tag strip for enrichment only; on-disk HTML stays untouched raw bytes."""
    plain = re.sub(r"<[^>]+>", " ", raw_html)
    return re.sub(r"\s+", " ", plain)


def local_cache_name(case_id: Any, url: str, pdf_name: str | None = None) -> tuple[str, str]:
    """
    Return (subdir, filename) under the dataset dir for a concrete document URL.
    PDFs → civil_pdfs/; HTML and other pages → civil_html/ (raw response body).
    """
    if pdf_name:
        return "civil_pdfs", str(pdf_name)
    parsed = urlparse(str(url))
    base = os.path.basename(parsed.path) or f"case_{case_id}.html"
    lower = base.lower()
    if lower.endswith(".pdf"):
        subdir = "civil_pdfs"
    else:
        subdir = "civil_html"
        if not lower.endswith((".htm", ".html")):
            base = f"case_{case_id}.html"
    # Prefix case_id to avoid basename collisions across decades.
    cid = int(case_id) if str(case_id).isdigit() else case_id
    prefix = f"{int(cid):02d}_"
    if not str(base).startswith(prefix) and not str(base).startswith(f"{cid}_"):
        base = f"{prefix}{base}"
    return subdir, base


def _materialize_seeds(
    seeds: list[dict[str, Any]],
    output_dir: str,
    force: bool,
    *,
    download_documents: bool = True,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for seed in seeds:
        record = {k: v for k, v in seed.items() if k != "pdf_name"}
        pdf_name = seed.get("pdf_name")
        url = str(seed.get("url") or "")
        case_id = seed.get("case_id")

        if download_documents and url and has_concrete_document_url(url):
            subdir, fname = local_cache_name(
                case_id, url, str(pdf_name) if pdf_name else None
            )
            dest_dir = os.path.join(output_dir, subdir)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, fname)
            ok = download_url(url, dest_path, force=force, timeout=45)
            polite_sleep(0.25)
            record["local_path"] = f"{subdir}/{fname}"
            if ok:
                if fname.lower().endswith(".pdf"):
                    text = pdf_to_text(dest_path)
                    record = enrich_from_text(record, text, excerpt_tag="pdf_excerpt")
                    print(f"  [{case_id:02d}] PDF cached+enriched {fname} ({len(text):,} chars)")
                else:
                    # Keep raw bytes on disk; enrich from a decoded plain-text view only.
                    raw = Path(dest_path).read_bytes()
                    plain = html_to_plain(decode_document_bytes(raw))
                    record = enrich_from_text(record, plain, excerpt_tag="html_excerpt")
                    print(f"  [{case_id:02d}] HTML cached raw {fname} ({len(raw):,} bytes)")
            else:
                print(f"  [{case_id:02d}] download failed; seed metadata only")
        else:
            print(f"  [{case_id:02d}] {seed.get('source_type')} / no concrete document URL")
        cases.append(record)
    return cases


def fetch_field4_civil_courts(
    output_dir: str,
    force: bool = False,
    limit: int = 0,
    catalog_path: str | Path | None = None,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    """
    Materialize REAL civil precedents (and optionally write synthetic regression file separately).
    Real → benchmark_court_civil_cases.json + civil_pdfs/ + civil_html/ (raw)
    Synthetic → benchmark_court_civil_synthetic.json (metadata only; no portal downloads)
    """
    dest_json = os.path.join(output_dir, CIVIL_JSON)
    syn_json = os.path.join(output_dir, SYNTHETIC_JSON)
    os.makedirs(output_dir, exist_ok=True)

    if os.path.exists(dest_json) and os.path.getsize(dest_json) > 0 and not force:
        print(f"[Field 4] [SKIP] Real civil dataset already exists: {os.path.basename(dest_json)}")
        with open(dest_json, encoding="utf-8") as f:
            cases = json.load(f)
    else:
        seeds = apply_limit(load_catalog(catalog_path), limit)
        print(f"[Field 4/real] Building from civil_precedent_catalog.json ({len(seeds)} seeds)...")
        cases = _materialize_seeds(seeds, output_dir, force, download_documents=True)
        with open(dest_json, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False, indent=2)
        stats = catalog_stats(cases)
        print(f"[Field 4/real] [OK] Saved {len(cases)} cases -> {dest_json}")
        print(
            f"[Field 4/real] fault_ratio={stats['non_synthetic_with_fault_ratio']} "
            f"yen={stats['non_synthetic_with_yen']} concrete_url={stats['non_synthetic_with_concrete_url']}"
        )

    if include_synthetic:
        if os.path.exists(syn_json) and os.path.getsize(syn_json) > 0 and not force:
            print(f"[Field 4/synthetic] [SKIP] {os.path.basename(syn_json)}")
        else:
            syn_seeds = apply_limit(load_synthetic_catalog(), limit)
            print(f"[Field 4/synthetic] Writing regression benchmarks ({len(syn_seeds)} seeds)...")
            # Do not download portal stubs; metadata only.
            syn_cases = _materialize_seeds(syn_seeds, output_dir, force, download_documents=False)
            with open(syn_json, "w", encoding="utf-8") as f:
                json.dump(syn_cases, f, ensure_ascii=False, indent=2)
            print(f"[Field 4/synthetic] [OK] Saved {len(syn_cases)} cases -> {syn_json}")

    return cases


def get_civil_court_seeds() -> list[dict[str, Any]]:
    return load_catalog()
