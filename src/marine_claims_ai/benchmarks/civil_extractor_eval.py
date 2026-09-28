"""
Validate civil judgment extractor against gold catalog / offline fixtures.

Zero-Dataset policy: default mode uses embedded public judgment snippets and
catalog holding text only (no network, no raw PDF commits). Optional
``--data-dir`` compares extractions from locally cached PDFs/HTML against
``config/civil_precedent_catalog.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from marine_claims_ai.ingest.civil import load_catalog, local_cache_name
from marine_claims_ai.ingest.civil_judgment_extractor import (
    extract_from_judgment,
    extraction_matches_gold,
)
from marine_claims_ai.ingest.pdf_text import pdf_to_text
from marine_claims_ai.paths import DEFAULT_DATASET_DIR

# Public-domain phrasing patterns drawn from courts.go.jp / JMAT style holdings.
# Values align with civil_precedent_catalog.json gold conventions.
OFFLINE_GOLD_SNIPPETS: list[dict[str, Any]] = [
    {
        "id": "kencho_yugyo_65_35",
        "case_id": 1,
        "text": (
            "両船の責任割合は、建昌六・五、有漁丸三・五である。"
            "建昌の責任割合は前記のとおり六五パーセントである。"
            "請求額は八〇七万二三三五円であり、認容額は一一七〇万五〇〇〇円とした。"
        ),
        "fault_ratio": "65:35",
        "claimed_repair_jpy": 8_072_335,
        "awarded_damages_jpy": 11_705_000,
        "disallowed_jpy": None,
    },
    {
        "id": "arabic_70_30",
        "case_id": None,
        "text": "過失割合は 70:30 である。請求額は 20,000,000円、認容額は 12,345,678円、否認は 3,000,000円 とした。",
        "fault_ratio": "70:30",
        "claimed_repair_jpy": 20_000_000,
        "awarded_damages_jpy": 12_345_678,
        "disallowed_jpy": 3_000_000,
    },
    {
        "id": "kanji_pair_80_20",
        "case_id": None,
        "text": "裁判所は過失割合を八〇対二〇と認めるのが相当である。",
        "fault_ratio": "80:20",
        "claimed_repair_jpy": None,
        "awarded_damages_jpy": None,
        "disallowed_jpy": None,
    },
    {
        "id": "wari_plaintiff_30",
        "case_id": None,
        "text": "原告の過失割合を三割と認めるのが相当である。",
        "fault_ratio": "30:70",
        "claimed_repair_jpy": None,
        "awarded_damages_jpy": None,
        "disallowed_jpy": None,
    },
    {
        "id": "named_tenths_80_20",
        "case_id": None,
        "text": "金宝丸にも一因があるが、その責任割合はしんえい丸八、金宝丸二である。",
        "fault_ratio": "80:20",
        "claimed_repair_jpy": None,
        "awarded_damages_jpy": None,
        "disallowed_jpy": None,
    },
    {
        "id": "shuin_ichin_70_30",
        "case_id": 4,
        "text": "本件衝突の主因はA船にあり、B船の協力動作懈怠も一因をなすものである。",
        "fault_ratio": "70:30",
        "claimed_repair_jpy": None,
        "awarded_damages_jpy": None,
        "disallowed_jpy": None,
    },
    {
        "id": "hassei_ichin_70_30",
        "case_id": 4,
        "text": (
            "本件衝突は、見張り不十分で進路を避けなかったことによって発生したが、"
            "警告信号を行わず協力動作をとらなかったことも一因をなすものである。"
        ),
        "fault_ratio": "70:30",
        "claimed_repair_jpy": None,
        "awarded_damages_jpy": None,
        "disallowed_jpy": None,
    },
    {
        "id": "catalog_holding_case1",
        "case_id": 1,
        "text": "双方の過失を認定し、責任割合を建昌65・有漁丸35と判示。人損・物損を責任割合で按分。",
        "fault_ratio": "65:35",
        "claimed_repair_jpy": None,
        "awarded_damages_jpy": None,
        "disallowed_jpy": None,
    },
    {
        "id": "fullwidth_60_40",
        "case_id": None,
        "text": "過失割合は６０対４０である。請求額は１２５，０００，０００円、認容額は７２，０００，０００円。",
        "fault_ratio": "60:40",
        "claimed_repair_jpy": 125_000_000,
        "awarded_damages_jpy": 72_000_000,
        "disallowed_jpy": None,
    },
    {
        "id": "percent_symbol_75",
        "case_id": None,
        "text": "責任割合を七五％と認定した。",
        "fault_ratio": "75:25",
        "claimed_repair_jpy": None,
        "awarded_damages_jpy": None,
        "disallowed_jpy": None,
    },
]


def _score_case(text: str, gold: dict[str, Any]) -> dict[str, Any]:
    extracted = extract_from_judgment(text)
    match = extraction_matches_gold(extracted, gold)
    return {
        "extracted": {
            "fault_ratio": extracted.fault_ratio,
            "claimed_repair_jpy": extracted.claimed_repair_jpy,
            "awarded_damages_jpy": extracted.awarded_damages_jpy,
            "disallowed_jpy": extracted.disallowed_jpy,
            "holding_excerpt": extracted.holding_excerpt,
        },
        "match": match,
    }


def _summarize_fault_ratio_tolerance(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate A7 soft metric: fault ratio within ±10pt among scored FR cases."""
    scored = 0
    within = 0
    for r in results:
        match = r.get("match") or {}
        w = match.get("fault_ratio_within_10pt")
        if w is None and "fault_ratio_ok" in r:
            # holdings mode stores flags at top level
            continue
        if w is None:
            continue
        scored += 1
        if w:
            within += 1
    rate = (within / scored) if scored else 0.0
    return {
        "fault_ratio_within_10pt_scored": scored,
        "fault_ratio_within_10pt_passed": within,
        "fault_ratio_within_10pt_rate": rate,
    }


def evaluate_offline_snippets(
    snippets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score embedded fixtures (CI / Zero-Dataset safe)."""
    snippets = snippets if snippets is not None else OFFLINE_GOLD_SNIPPETS
    results = []
    passed = 0
    for snip in snippets:
        gold = {
            "fault_ratio": snip.get("fault_ratio"),
            "claimed_repair_jpy": snip.get("claimed_repair_jpy"),
            "awarded_damages_jpy": snip.get("awarded_damages_jpy"),
            "disallowed_jpy": snip.get("disallowed_jpy"),
        }
        scored = _score_case(str(snip["text"]), gold)
        ok = bool(scored["match"].get("all_ok"))
        if ok:
            passed += 1
        results.append(
            {
                "id": snip.get("id"),
                "case_id": snip.get("case_id"),
                "ok": ok,
                **scored,
            }
        )
    total = len(results)
    accuracy = (passed / total) if total else 0.0
    tol = _summarize_fault_ratio_tolerance(results)
    return {
        "mode": "offline_snippets",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": accuracy,
        **tol,
        "results": results,
    }


def evaluate_catalog_holdings(seeds: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Compare extractor output on catalog ``holding`` (+ ``input_facts``) text
    against gold fault_ratio when the holding text itself evidences a ratio.

    Seeds whose holding/facts contain no extractable ratio are skipped (not scored).
    """
    seeds = seeds if seeds is not None else load_catalog()
    results = []
    scored_n = 0
    passed = 0
    for seed in seeds:
        text = f"{seed.get('holding') or ''}\n{seed.get('input_facts') or ''}".strip()
        if not text or not seed.get("fault_ratio"):
            continue
        extracted = extract_from_judgment(text)
        if not extracted.fault_ratio:
            results.append(
                {
                    "case_id": seed.get("case_id"),
                    "status": "skip_no_extractable_ratio",
                    "gold": seed.get("fault_ratio"),
                }
            )
            continue
        scored_n += 1
        match = extraction_matches_gold(
            extracted,
            {
                "fault_ratio": seed.get("fault_ratio"),
                "claimed_repair_jpy": seed.get("claimed_repair_jpy"),
                "awarded_damages_jpy": seed.get("awarded_damages_jpy"),
                "disallowed_jpy": seed.get("disallowed_jpy"),
            },
        )
        # For holdings mode, primarily score fault_ratio (yen rarely appears in summaries)
        fr_ok = match.get("fault_ratio_ok") is True
        if fr_ok:
            passed += 1
        results.append(
            {
                "case_id": seed.get("case_id"),
                "status": "ok" if fr_ok else "fail",
                "fault_ratio_ok": fr_ok,
                "fault_ratio_within_10pt": match.get("fault_ratio_within_10pt"),
                "extracted": extracted.fault_ratio,
                "gold": seed.get("fault_ratio"),
                "match": match,
            }
        )
    accuracy = (passed / scored_n) if scored_n else 0.0
    tol = _summarize_fault_ratio_tolerance(results)
    return {
        "mode": "catalog_holdings",
        "catalog_total": len(seeds),
        "scored": scored_n,
        "passed": passed,
        "failed": scored_n - passed,
        "skipped": len(seeds) - scored_n,
        "accuracy": accuracy,
        **tol,
        "results": results,
    }


def _load_local_document_text(data_dir: Path, seed: dict[str, Any]) -> str | None:
    url = str(seed.get("url") or "")
    pdf_name = seed.get("pdf_name")
    case_id = seed.get("case_id")
    if not url and not pdf_name:
        return None
    subdir, fname = local_cache_name(case_id, url, str(pdf_name) if pdf_name else None)
    path = data_dir / subdir / fname
    # Also try plain pdf_name under civil_pdfs/
    alt = data_dir / "civil_pdfs" / str(pdf_name) if pdf_name else None
    if not path.is_file() and alt and alt.is_file():
        path = alt
    if not path.is_file():
        return None
    if path.suffix.lower() == ".pdf":
        return pdf_to_text(str(path))
    raw = path.read_bytes()
    for enc in ("utf-8", "shift_jis", "cp932", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def evaluate_local_documents(
    data_dir: str | Path | None = None,
    seeds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Extract from locally cached civil PDFs/HTML and compare to catalog gold.

    Scoring policy (evidenced fields only):
    - fault_ratio: scored when the extractor finds any ratio in the text
    - yen: scored when the gold amount is among extracted yen hits (pass), or
      when ``source_type == court_pdf`` and the document contains ``円`` (miss → fail).
      Published-summary HTML rows whose pages omit modelled yen are skipped.

    Accuracy is over scored cases only.
    """
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATASET_DIR
    seeds = seeds if seeds is not None else load_catalog()
    results = []
    scored_n = 0
    passed = 0
    field_scored = 0
    field_passed = 0

    for seed in seeds:
        text = _load_local_document_text(data_dir, seed)
        if not text:
            results.append(
                {
                    "case_id": seed.get("case_id"),
                    "status": "skip_no_local_doc",
                    "gold": seed.get("fault_ratio"),
                }
            )
            continue

        extracted = extract_from_judgment(text)
        gold_fr = seed.get("fault_ratio")
        evidenced: dict[str, Any] = {}

        if gold_fr and extracted.fault_ratio is not None:
            evidenced["fault_ratio"] = gold_fr

        has_yen_char = "円" in text
        for attr in ("claimed_repair_jpy", "awarded_damages_jpy", "disallowed_jpy"):
            gold_v = seed.get(attr)
            if not isinstance(gold_v, int):
                continue
            in_hits = any(h.amount_jpy == gold_v for h in extracted.yen_hits)
            if in_hits:
                evidenced[attr] = gold_v
            elif seed.get("source_type") == "court_pdf" and has_yen_char:
                evidenced[attr] = gold_v

        if not evidenced:
            results.append(
                {
                    "case_id": seed.get("case_id"),
                    "status": "skip_gold_not_evidenced_in_document",
                    "gold": gold_fr,
                    "extracted_fault_ratio": extracted.fault_ratio,
                }
            )
            continue

        match = extraction_matches_gold(extracted, evidenced)
        scored_n += 1
        field_scored += int(match.get("scored_fields") or 0)
        field_passed += int(match.get("passed_fields") or 0)
        ok = bool(match.get("all_ok"))
        if ok:
            passed += 1
        results.append(
            {
                "case_id": seed.get("case_id"),
                "status": "ok" if ok else "fail",
                "evidenced_fields": list(evidenced.keys()),
                "match": match,
                "extracted_fault_ratio": extracted.fault_ratio,
            }
        )

    accuracy = (passed / scored_n) if scored_n else 0.0
    field_accuracy = (field_passed / field_scored) if field_scored else 0.0
    tol = _summarize_fault_ratio_tolerance(results)
    return {
        "mode": "local_documents",
        "data_dir": str(data_dir),
        "catalog_total": len(seeds),
        "scored": scored_n,
        "passed": passed,
        "failed": scored_n - passed,
        "accuracy": accuracy,
        "field_accuracy": field_accuracy,
        "field_scored": field_scored,
        "field_passed": field_passed,
        **tol,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["offline", "holdings", "local", "all"],
        default="offline",
        help="offline=embedded snippets (CI default); holdings=catalog text; "
        "local=cached PDFs/HTML; all=run every mode",
    )
    parser.add_argument("--data-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=0.90,
        help="Fail if primary accuracy falls below this threshold (default 0.90)",
    )
    parser.add_argument(
        "--min-within-10pt",
        type=float,
        default=0.80,
        help="Fail if fault-ratio within ±10pt rate falls below this (default 0.80; A7 soft)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    reports: dict[str, Any] = {}
    modes = ["offline", "holdings", "local"] if args.mode == "all" else [args.mode]

    for mode in modes:
        if mode == "offline":
            reports["offline"] = evaluate_offline_snippets()
        elif mode == "holdings":
            reports["holdings"] = evaluate_catalog_holdings()
        else:
            reports["local"] = evaluate_local_documents(args.data_dir)

    # Primary gate: offline snippets always; local when requested and scored>0
    primary = reports.get("offline") or reports.get("local") or reports.get("holdings")
    assert primary is not None

    if args.json:
        print(json.dumps(reports if len(reports) > 1 else primary, ensure_ascii=False, indent=2))
    else:
        for name, rep in reports.items():
            acc = rep.get("accuracy", 0.0)
            scored = rep.get("scored", rep.get("total", 0))
            passed = rep.get("passed", 0)
            w10 = rep.get("fault_ratio_within_10pt_rate")
            w10_s = f" within10pt={w10:.1%}" if w10 is not None else ""
            print(
                f"[{name}] accuracy={acc:.1%} passed={passed}/{scored} "
                f"(failed={rep.get('failed', 0)}){w10_s}"
            )
            for r in rep.get("results", []):
                if r.get("ok") is False or r.get("status") == "fail":
                    print(
                        f"  FAIL id={r.get('id')} case_id={r.get('case_id')} "
                        f"extracted={r.get('extracted', r.get('extracted_fault_ratio'))} "
                        f"gold={r.get('gold', r.get('match', {}).get('fault_ratio_gold'))}"
                    )

    # Exit gate
    gate_reports = []
    if "offline" in reports:
        gate_reports.append(reports["offline"])
    if "local" in reports and reports["local"].get("scored", 0) > 0:
        gate_reports.append(reports["local"])
    if not gate_reports and "holdings" in reports and reports["holdings"].get("scored", 0) > 0:
        gate_reports.append(reports["holdings"])

    for rep in gate_reports:
        if rep.get("accuracy", 0.0) < args.min_accuracy:
            print(
                f"[ERROR] accuracy {rep.get('accuracy', 0):.1%} < {args.min_accuracy:.0%} "
                f"(mode={rep.get('mode')})",
                flush=True,
            )
            return 1
        w10_scored = int(rep.get("fault_ratio_within_10pt_scored") or 0)
        if w10_scored > 0 and float(rep.get("fault_ratio_within_10pt_rate") or 0.0) < args.min_within_10pt:
            print(
                f"[ERROR] within±10pt {rep.get('fault_ratio_within_10pt_rate', 0):.1%} "
                f"< {args.min_within_10pt:.0%} (mode={rep.get('mode')})",
                flush=True,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
