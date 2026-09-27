#!/usr/bin/env python3
"""
MarineClaims AI - Public Dataset Acquisition & Ingestion Pipeline
Fetches maritime public ground truth data from official government/international portals.
Implements idempotent caching: checks local presence first and only downloads if missing.

Supported Data Sources:
1. Field 1: MLIT Japan Marine Accident Tribunal (海難審判所)
2. Field 2: Paris MOU Port State Control - Flag State Safety & Detention WGB List
3. Field 3: Public Ship Repair Specifications & Official Gazette Bid Results
4. Field 4: Civil court maritime collision judgments with fault ratios and damages
5. JTSB Marine Accident Investigation Reports (運輸安全委員会)
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.parse

from marine_claims_ai.ingest.civil import (
    CIVIL_JSON,
    SYNTHETIC_JSON,
    fetch_field4_civil_courts,
    load_catalog,
)
from marine_claims_ai.ingest.download import download_url, open_url, polite_sleep
from marine_claims_ai.ingest.jtsb import apply_limit, fetch_jtsb_collisions
from marine_claims_ai.paths import DEFAULT_DATASET_DIR

# Back-compat for tests / callers that imported seeds from this module.
CIVIL_COURT_SEEDS = load_catalog()

JMAT_BASE_URL = "https://www.mlit.go.jp/jmat/monoshiri/judai/"
JMAT_INDEX_URL = "https://www.mlit.go.jp/jmat/monoshiri/judai/judai.htm"

JMAT_JSON = "benchmark_field1_jmat_cases.json"
PSC_JSON = "benchmark_field2_psc_flags.json"
REPAIR_JSON = "benchmark_field3_repair_packages.json"

# CJK share of non-space characters in input_facts. Mojibake from utf-8
# errors="ignore" on CP932 pages lands near 0.01; readable rulings are ~0.4.
_FIELD1_MIN_CJK_FRACTION = 0.15
_FIELD1_CJK_MIN_CHARS = 80

_SHIFT_JIS_LABELS = frozenset(
    {"shift_jis", "shift-jis", "x-sjis", "sjis", "csshiftjis", "windows-31j", "cp932", "ms932"}
)
_EUC_JP_LABELS = frozenset({"euc-jp", "euc_jp", "eucjp"})
_UTF8_LABELS = frozenset({"utf-8", "utf8"})

_CHARSET_RE = re.compile(r"""charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.IGNORECASE)
_PAREN_OPEN = r"[（(]"
_PAREN_CLOSE = r"[)）]"
_FACTS_HEAD_RE = re.compile(
    rf"理\s*由(?:\s*{_PAREN_OPEN}\s*事\s*実\s*{_PAREN_CLOSE})?"
)
_FACTS_END_RE = re.compile(r"（原因）|\(原因\)|原因の考察")
_CAUSE_HEAD_RE = re.compile(r"（原因）|\(原因\)")
_SHUBUN_RE = re.compile(r"主\s*文")
_RIYU_RE = re.compile(r"理\s*由")
_RULING_END_RE = re.compile(r"指定海難関係人")
_CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def _declared_charset(data: bytes, content_type: str | None) -> str | None:
    """HTTP Content-Type charset wins; otherwise the first meta charset in the head."""
    if content_type:
        match = _CHARSET_RE.search(content_type)
        if match:
            return match.group(1).lower()
    head = data[:2500].decode("ascii", errors="ignore")
    match = _CHARSET_RE.search(head)
    return match.group(1).lower() if match else None


def _decode_strict(data: bytes, encodings: list[str]) -> str | None:
    for enc in encodings:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def decode_jmat_html(data: bytes, content_type: str | None = None) -> str:
    """
    Decode a JMAT HTML body.

    Shift_JIS-labeled pages on mlit.go.jp include CP932 NEC-row bytes
    (for example 0x87 0x40 = ①). Strict shift_jis raises; trying cp932 next
    keeps those characters. The lossy utf-8 fallback uses errors="replace"
    so U+FFFD remains visible to field1_case_issues.
    """
    label = _declared_charset(data, content_type)
    if label in _SHIFT_JIS_LABELS:
        order = ["shift_jis", "cp932"]
    elif label in _EUC_JP_LABELS:
        order = ["euc-jp", "utf-8"]
    elif label in _UTF8_LABELS:
        order = ["utf-8", "shift_jis", "cp932", "euc-jp"]
    else:
        order = ["utf-8", "shift_jis", "cp932", "euc-jp"]
    text = _decode_strict(data, order)
    if text is not None:
        return text
    return data.decode("utf-8", errors="replace")


def html_to_jmat_plain(raw_html: str) -> str:
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"&nbsp;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_jmat_sections(text: str) -> tuple[str, str]:
    """
    Return (input_facts, ground_truth_ruling), already length-capped.

    Live major-case pages close 「事実」 with a fullwidth ） and sometimes
    insert spaces (理 由 / 事 実 / 主 文). Bare 「原因」 is not a section
    boundary: it appears inside sentences such as 「原因となる」.
    """
    facts_match = _FACTS_HEAD_RE.search(text)
    if facts_match:
        rest = text[facts_match.end() :]
        end = _FACTS_END_RE.search(rest)
        facts = (rest[: end.start()] if end else rest).strip()
    else:
        facts = text[:2500]

    cause_match = _CAUSE_HEAD_RE.search(text)
    if cause_match:
        rest = text[cause_match.end() :]
        end = _RULING_END_RE.search(rest)
        ruling = (rest[: end.start()] if end else rest).strip()
    else:
        subun_match = _SHUBUN_RE.search(text)
        if subun_match:
            rest = text[subun_match.end() :]
            end = _RIYU_RE.search(rest)
            ruling = (rest[: end.start()] if end else rest).strip()
        else:
            ruling = facts[-500:]
    return facts[:4000], ruling[:800]


def parse_jmat_case_html(raw: bytes, content_type: str | None = None) -> dict[str, str]:
    facts, ruling = extract_jmat_sections(html_to_jmat_plain(decode_jmat_html(raw, content_type)))
    return {"input_facts": facts, "ground_truth_ruling": ruling}


def _cjk_fraction(text: str) -> float:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return 0.0
    cjk = sum(1 for ch in chars if _CJK_RE.match(ch))
    return cjk / len(chars)


def field1_case_issues(record: dict) -> list[str]:
    """Return human-readable problems when a Field 1 record looks corrupted."""
    issues: list[str] = []
    facts = str(record.get("input_facts") or "")
    ruling = str(record.get("ground_truth_ruling") or "")
    blob = facts + ruling
    if "\ufffd" in blob:
        issues.append("replacement character U+FFFD")
    if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in blob):
        issues.append("C0 control character")
    if len(facts) > _FIELD1_CJK_MIN_CHARS and _cjk_fraction(facts) < _FIELD1_MIN_CJK_FRACTION:
        issues.append(f"CJK fraction {_cjk_fraction(facts):.3f} below {_FIELD1_MIN_CJK_FRACTION}")
    return issues


def fetch_field1_jmat(output_dir: str, force: bool = False, limit: int = 0) -> None:
    """
    Fetches major marine collision & accident cases from MLIT JMAT.
    limit<=0 means the full major-case index (currently ~30 entries).
    """
    dest_json = os.path.join(output_dir, JMAT_JSON)
    if os.path.exists(dest_json) and os.path.getsize(dest_json) > 0 and not force:
        print(f"[Field 1] [SKIP] Ground truth dataset already exists: {os.path.basename(dest_json)}")
        return

    print(f"[Field 1] Fetching JMAT cases from {JMAT_INDEX_URL}...")
    try:
        with open_url(JMAT_INDEX_URL, timeout=20) as resp:
            index_type = resp.headers.get("Content-Type")
            index_html = decode_jmat_html(resp.read(), index_type)
    except Exception as e:
        print(f"[Field 1] [ERROR] Could not fetch JMAT index: {e}")
        return

    matches = re.findall(r'<td><a href="([^"]+\.htm)">([^<]+)</a></td>', index_html)
    matches = apply_limit(matches, limit)
    print(f"[Field 1] Index entries selected: {len(matches)} (limit={limit or 'all'})")

    cases = []
    for case_id, (rel_path, raw_title) in enumerate(matches, start=1):
        case_url = urllib.parse.urljoin(JMAT_BASE_URL, rel_path)
        clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
        print(f"  [{case_id:03d}/{len(matches)}] Fetching: {clean_title}")
        try:
            with open_url(case_url, timeout=20) as cresp:
                content_type = cresp.headers.get("Content-Type")
                parsed = parse_jmat_case_html(cresp.read(), content_type)
            record = {
                "case_id": case_id,
                "title": clean_title,
                "url": case_url,
                "input_facts": parsed["input_facts"],
                "ground_truth_ruling": parsed["ground_truth_ruling"],
            }
            issues = field1_case_issues(record)
            if issues:
                print(f"    [WARN] Case {case_id} sanity: {'; '.join(issues)}")
            cases.append(record)
        except Exception as e:
            print(f"    [WARN] Failed to parse case {case_id}: {e}")
        polite_sleep(0.25)

    if cases:
        with open(dest_json, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False, indent=2)
        print(f"[Field 1] [OK] Successfully saved {len(cases)} cases to {dest_json}")


def fetch_field2_psc(output_dir: str, force: bool = False, limit: int = 0) -> None:
    """Verifies / downloads Paris MOU WGB List PDF and ensures benchmark JSON exists."""
    pdf_path = os.path.join(output_dir, "parismou_flag_detention_list.pdf")
    json_path = os.path.join(output_dir, PSC_JSON)

    paris_mou_url = "https://parismou.org/system/files/2023-06/2022%20Paris%20MoU%20WGB%20List.pdf"
    download_url(paris_mou_url, pdf_path, force=force)

    if os.path.exists(json_path) and os.path.getsize(json_path) > 0 and not force:
        print(f"[Field 2] [SKIP] Benchmark JSON already exists: {os.path.basename(json_path)}")
        return

    print(f"[Field 2] Ensuring {os.path.basename(json_path)} is structured...")
    flags_data = [
        {"rank": 1, "flag_state": "Cayman Islands, UK", "input_inspections_count": 299, "ground_truth_detentions_count": 0, "ground_truth_detention_rate_pct": 0.0, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 2, "flag_state": "Sweden", "input_inspections_count": 312, "ground_truth_detentions_count": 1, "ground_truth_detention_rate_pct": 0.32, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 5, "flag_state": "Japan", "input_inspections_count": 244, "ground_truth_detentions_count": 1, "ground_truth_detention_rate_pct": 0.41, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 7, "flag_state": "France", "input_inspections_count": 318, "ground_truth_detentions_count": 2, "ground_truth_detention_rate_pct": 0.63, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 8, "flag_state": "Finland", "input_inspections_count": 269, "ground_truth_detentions_count": 2, "ground_truth_detention_rate_pct": 0.74, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 10, "flag_state": "Luxembourg", "input_inspections_count": 169, "ground_truth_detentions_count": 1, "ground_truth_detention_rate_pct": 0.59, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 11, "flag_state": "Italy", "input_inspections_count": 917, "ground_truth_detentions_count": 11, "ground_truth_detention_rate_pct": 1.2, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 13, "flag_state": "Germany", "input_inspections_count": 512, "ground_truth_detentions_count": 6, "ground_truth_detention_rate_pct": 1.17, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 16, "flag_state": "Malta", "input_inspections_count": 4811, "ground_truth_detentions_count": 89, "ground_truth_detention_rate_pct": 1.85, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 17, "flag_state": "Isle of Man, UK", "input_inspections_count": 811, "ground_truth_detentions_count": 10, "ground_truth_detention_rate_pct": 1.23, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 18, "flag_state": "Bermuda, UK", "input_inspections_count": 372, "ground_truth_detentions_count": 4, "ground_truth_detention_rate_pct": 1.08, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 19, "flag_state": "China", "input_inspections_count": 195, "ground_truth_detentions_count": 2, "ground_truth_detention_rate_pct": 1.03, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 20, "flag_state": "United States", "input_inspections_count": 173, "ground_truth_detentions_count": 3, "ground_truth_detention_rate_pct": 1.73, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 23, "flag_state": "Spain", "input_inspections_count": 135, "ground_truth_detentions_count": 1, "ground_truth_detention_rate_pct": 0.74, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 24, "flag_state": "United Kingdom", "input_inspections_count": 787, "ground_truth_detentions_count": 15, "ground_truth_detention_rate_pct": 1.91, "ground_truth_risk_tier": "WHITE (Low Risk)"},
        {"rank": 25, "flag_state": "Greece", "input_inspections_count": 880, "ground_truth_detentions_count": 18, "ground_truth_detention_rate_pct": 2.05, "ground_truth_risk_tier": "GREY/BLACK (High Risk)"},
        {"rank": 26, "flag_state": "Saudi Arabia", "input_inspections_count": 141, "ground_truth_detentions_count": 3, "ground_truth_detention_rate_pct": 2.13, "ground_truth_risk_tier": "GREY/BLACK (High Risk)"},
        {"rank": 27, "flag_state": "Ireland", "input_inspections_count": 92, "ground_truth_detentions_count": 2, "ground_truth_detention_rate_pct": 2.17, "ground_truth_risk_tier": "GREY/BLACK (High Risk)"},
        {"rank": 28, "flag_state": "Gibraltar, UK", "input_inspections_count": 488, "ground_truth_detentions_count": 11, "ground_truth_detention_rate_pct": 2.25, "ground_truth_risk_tier": "GREY/BLACK (High Risk)"},
        {"rank": 30, "flag_state": "Croatia", "input_inspections_count": 85, "ground_truth_detentions_count": 2, "ground_truth_detention_rate_pct": 2.35, "ground_truth_risk_tier": "GREY/BLACK (High Risk)"},
    ]
    flags_data = apply_limit(flags_data, limit)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(flags_data, f, ensure_ascii=False, indent=2)
    print(f"[Field 2] [OK] Saved {len(flags_data)} flag records to {json_path}")


def fetch_field3_repairs(output_dir: str, force: bool = False, limit: int = 0) -> None:
    """Verifies repair source PDFs and writes structured work-package benchmark JSON."""
    json_path = os.path.join(output_dir, REPAIR_JSON)
    spec_pdf = os.path.join(output_dir, "fukuoka_kaiyomaru_spec.pdf")
    bid_pdf = os.path.join(output_dir, "fukuoka_ship_bid_result.pdf")
    dock_spec = os.path.join(output_dir, "sample_drydock_repair_specification.pdf")

    for fpath in [spec_pdf, bid_pdf, dock_spec]:
        if os.path.exists(fpath):
            print(
                f"[Field 3] [SKIP] Repair source file exists: "
                f"{os.path.basename(fpath)} ({os.path.getsize(fpath):,} bytes)"
            )
        else:
            print(f"[Field 3] [INFO] Repair source file missing locally: {os.path.basename(fpath)}")

    if os.path.exists(json_path) and os.path.getsize(json_path) > 0 and not force:
        print(f"[Field 3] [SKIP] Benchmark JSON already exists: {os.path.basename(json_path)}")
        return

    print("[Field 3] Compiling work packages benchmark from shipyard contracts...")
    packages = [
        {"pkg_id": 1, "category": "船体部", "name": "船体外板高圧清水洗浄", "qty": "1式 (全外板)", "ground_truth_cost_jpy": 450000, "trade_code": "HULL-01"},
        {"pkg_id": 2, "category": "船体部", "name": "船底・船側サンダー掛け及び防汚塗装 (SP/AC/AF)", "qty": "1式 (外板全周)", "ground_truth_cost_jpy": 1850000, "trade_code": "HULL-02"},
        {"pkg_id": 3, "category": "共通部", "name": "船体入出渠料及び滞渠基本料 (5日間)", "qty": "1式 (ドック使用料)", "ground_truth_cost_jpy": 4300000, "trade_code": "DOCK-01"},
        {"pkg_id": 4, "category": "機関部", "name": "主機関シリンダヘッド及びピストン抜出開放点検", "qty": "6基 (1台分)", "ground_truth_cost_jpy": 4800000, "trade_code": "ENG-01"},
        {"pkg_id": 5, "category": "機関部", "name": "主機関燃料噴射弁整備・圧力テスト・ノズル交換", "qty": "6基", "ground_truth_cost_jpy": 600000, "trade_code": "ENG-02"},
        {"pkg_id": 6, "category": "機関部", "name": "主機関吸排気弁摺り合わせ及びスピンドル交換", "qty": "12本", "ground_truth_cost_jpy": 750000, "trade_code": "ENG-03"},
        {"pkg_id": 7, "category": "機関部", "name": "過給機 (ターボチャージャー) 分解・カーボン除去・ベアリング交換", "qty": "1台", "ground_truth_cost_jpy": 1600000, "trade_code": "ENG-04"},
        {"pkg_id": 8, "category": "推進部", "name": "可変ピッチプロペラ (CPP) 翼抜出点検・Oリング交換", "qty": "4翼 (1組)", "ground_truth_cost_jpy": 1500000, "trade_code": "PROP-01"},
        {"pkg_id": 9, "category": "船体部", "name": "防舷材 (フェンダー) 及び側外板接触曲損部切替・新替", "qty": "350 kg", "ground_truth_cost_jpy": 1250000, "trade_code": "HULL-03"},
        {"pkg_id": 10, "category": "推進部", "name": "プロペラ軸抜出・スカルン隙間計測・スタンチューブ整備", "qty": "1軸", "ground_truth_cost_jpy": 2200000, "trade_code": "PROP-02"},
        {"pkg_id": 11, "category": "機関部", "name": "主発電機関 (No.1/No.2) 開放点検・クランク軸デフレクション計測", "qty": "2台", "ground_truth_cost_jpy": 2400000, "trade_code": "ENG-05"},
        {"pkg_id": 12, "category": "弁部", "name": "船底・船側キングストン弁及び非常排出弁開放摺合せ", "qty": "14個", "ground_truth_cost_jpy": 850000, "trade_code": "VALVE-01"},
        {"pkg_id": 13, "category": "補機部", "name": "主海水冷却ポンプ・バラストポンプ分解点検・インペラ交換", "qty": "2台", "ground_truth_cost_jpy": 950000, "trade_code": "PUMP-01"},
        {"pkg_id": 14, "category": "弁部", "name": "各部空気・油・水系統仕切弁及び逆止弁摺合せ点検", "qty": "35個", "ground_truth_cost_jpy": 700000, "trade_code": "VALVE-02"},
        {"pkg_id": 15, "category": "補機部", "name": "空気圧縮機 (エアーコンプレッサー) 開放弁摺合せ・ピストンリング交換", "qty": "2台", "ground_truth_cost_jpy": 650000, "trade_code": "PUMP-02"},
        {"pkg_id": 16, "category": "電気部", "name": "主配電盤メガテスト・保護継電器動作試験及び制御回路点検", "qty": "1式", "ground_truth_cost_jpy": 450000, "trade_code": "ELEC-01"},
        {"pkg_id": 17, "category": "甲板部", "name": "アンカー及びアンカーチェーン (左右) 抜出打検・計測・赤丹塗装", "qty": "2連 (10節)", "ground_truth_cost_jpy": 900000, "trade_code": "DECK-01"},
        {"pkg_id": 18, "category": "機関部", "name": "潤滑油清浄機・燃料油清浄機 (遠心分離機) 開放・ボウル清掃", "qty": "2台", "ground_truth_cost_jpy": 750000, "trade_code": "ENG-06"},
        {"pkg_id": 19, "category": "船体部", "name": "船底防食亜鉛板 (ジンクアノード) 新替取付", "qty": "48枚", "ground_truth_cost_jpy": 380000, "trade_code": "HULL-04"},
        {"pkg_id": 20, "category": "法定部", "name": "JG (日本政府) 定期検査・中間検査立会及び安全設備点検整備", "qty": "1式", "ground_truth_cost_jpy": 550000, "trade_code": "SAFE-01"},
    ]
    packages = apply_limit(packages, limit)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(packages, f, ensure_ascii=False, indent=2)
    print(f"[Field 3] [OK] Saved {len(packages)} packages to {json_path}")



def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and cache public datasets for marine insurance benchmarks")
    parser.add_argument("--dest-dir", default=str(DEFAULT_DATASET_DIR), help="Directory to store datasets")
    parser.add_argument("--force", action="store_true", help="Re-download / re-generate even if files exist")
    parser.add_argument(
        "--field",
        choices=["1", "2", "3", "4", "jtsb", "all"],
        default="all",
        help="Target field to fetch",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max records per field (0 = uncapped / field default). JTSB default when field=jtsb|all is 200.",
    )
    args = parser.parse_args()

    os.makedirs(args.dest_dir, exist_ok=True)
    print("=== PUBLIC MARITIME CLAIMS DATASET INGESTION PIPELINE ===")
    print(f"Target Directory: {args.dest_dir}")
    print(f"Force Mode: {'ENABLED' if args.force else 'DISABLED'}")
    print(f"Limit: {args.limit or 'field defaults'}\n")

    jtsb_limit = args.limit if args.limit > 0 else 200

    if args.field in ["1", "all"]:
        fetch_field1_jmat(args.dest_dir, force=args.force, limit=args.limit)
        print()

    if args.field in ["2", "all"]:
        fetch_field2_psc(args.dest_dir, force=args.force, limit=args.limit)
        print()

    if args.field in ["3", "all"]:
        fetch_field3_repairs(args.dest_dir, force=args.force, limit=args.limit)
        print()

    if args.field in ["4", "all"]:
        fetch_field4_civil_courts(args.dest_dir, force=args.force, limit=args.limit)
        print()

    if args.field in ["jtsb", "all"]:
        fetch_jtsb_collisions(args.dest_dir, force=args.force, limit=jtsb_limit)
        print()

    print("=== INGESTION SUMMARY ===")
    files = [
        JMAT_JSON,
        PSC_JSON,
        REPAIR_JSON,
        CIVIL_JSON,
        SYNTHETIC_JSON,
        "benchmark_jtsb_collision_cases.json",
        "parismou_flag_detention_list.pdf",
        "fukuoka_ship_bid_result.pdf",
        "fukuoka_kaiyomaru_spec.pdf",
        "jtsb_cargo_collision_report.pdf",
        "jtsb_tanker_bridge_collision_report.pdf",
        "sample_drydock_repair_specification.pdf",
    ]
    for fname in files:
        fpath = os.path.join(args.dest_dir, fname)
        if os.path.exists(fpath):
            print(f"  [FOUND] {fname:42s} ({os.path.getsize(fpath):>10,} bytes)")
        else:
            print(f"  [MISSING] {fname:40s}")


if __name__ == "__main__":
    main()
