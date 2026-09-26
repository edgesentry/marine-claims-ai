#!/usr/bin/env python3
"""
MarineClaims AI - Generalizable Dynamic Claims Analysis Pipeline
Accepts arbitrary vessel repair specification PDFs and maritime casualty report PDFs,
dynamically extracts casualty parameters, performs semantic causality mapping and
concurrent repair (便乗修理) screening, and outputs structured analytics and survey reports.
"""

import argparse
import json
import os
import re
import subprocess

from marine_claims_ai.appraisal.negative_patterns import (
    ACTION_APPORTIONED,
    ACTION_DISALLOWED,
    NegativePatternScorer,
)
from marine_claims_ai.appraisal.report import render_preliminary_survey_report
from marine_claims_ai.ontology.compartments import (
    any_damage_allows_repair,
    infer_repair_zone,
)
from marine_claims_ai.paths import DEFAULT_DATASET_DIR

DEFAULT_SPEC_PDF = str(DEFAULT_DATASET_DIR / "sample_drydock_repair_specification.pdf")
DEFAULT_CASUALTY_PDF = str(DEFAULT_DATASET_DIR / "jtsb_cargo_collision_report.pdf")
DEFAULT_OUTPUT_DIR = str(DEFAULT_DATASET_DIR)

# Outer-hull restoration only — bare 「塗装」「洗浄」 must not match machinery/calorifier work.
_OUTER_HULL_SURFACE_KEYS = ("船体外板", "船側外板", "船底外板")
_PROPULSION_KEYS = ("プロペラ", "推進器", "プロペラ軸", "舵")
_MACHINERY_KEYS = (
    "主機関",
    "ピストン",
    "吸排気弁",
    "燃料噴射弁",
    "発電機関",
    "波止弁",
    "ポンプ",
    "シリンダー",
    "亜鉛",
    "カロリーファイヤー",
    "汚物処理",
    "減速機",
    "クラッチ",
)


def description_is_bow_thruster_work(desc: str) -> bool:
    """True when the line item is primarily bow-thruster work, not a passing mention."""
    if "バウスラスター" not in desc:
        return False
    if "機関室" in desc or "汚物処理" in desc or "始動機盤" in desc or "主配電盤" in desc:
        return False
    return desc.strip().startswith("バウスラスター") or "バウスラスター プロペラ" in desc


def _ontology_exclude_reason(causality: dict, damaged_zones: list[str]) -> str:
    reason_code = causality.get("reason") or "unknown"
    repair = causality.get("repair_node")
    if reason_code == "watertight_barrier_violation":
        return (
            f"事故損傷部位（{', '.join(damaged_zones)}）から修理区画（{repair}）へは"
            "水密隔壁を越える因果が成立せず、便乗修理として除外。"
        )
    if reason_code == "beyond_casualty_propagation_limit":
        return (
            f"事故損傷部位（{', '.join(damaged_zones)}）から修理区画（{repair}）までは"
            f"伝播ホップ数 {causality.get('hops')} が上限 {causality.get('max_hops')} を超え、"
            "直接因果が認められないため除外。"
        )
    return (
        f"事故損傷部位（{', '.join(damaged_zones)}）と修理区画の空間因果が検証できないため除外"
        f"（ontology_reason={reason_code}）。"
    )


def evaluate_claims_dynamically(items, casualty_profile, scorer=None):
    """
    Evaluate each specification item against the casualty profile.

    Checks in order: (1) drydock dues, (2) naval-architecture compartment causality,
    (3) Negative Pattern Library cosine red-flag scoring, (4) keyword gates.
    Bare 「塗装」「洗浄」 alone never triggers COVERED.

    ``scorer`` may be a NegativePatternScorer (or compatible) for tests; when None,
    the default library-backed scorer is constructed once per call.
    """
    damaged_zones = list(casualty_profile["damaged_components"])
    analyzed = []
    total_claimed = 0
    total_covered = 0
    total_excluded = 0
    npl_scorer = scorer if scorer is not None else NegativePatternScorer()

    has_hull_damage = any(z in damaged_zones for z in ["外板", "球状船首", "貨物タンク", "タンク"])
    has_propulsion_damage = any(z in damaged_zones for z in ["推進器", "舵"])
    has_machinery_damage = any(z in damaged_zones for z in ["機関室"])

    for item in items:
        desc = item["description"]
        cat = item["category"]
        cost = item["estimated_cost"]
        total_claimed += cost

        status = ""
        reason = ""
        clause_ref = ""
        approved_amount = 0
        repair_zone = None
        causality = None
        red_flag = npl_scorer.score_description(desc, category=cat)

        # Rule 1: Common Drydocking charges (入出渠・滞渠) — apportionment, not zone-gated
        if "入出渠" in desc or "滞渠" in desc:
            status = "APPORTIONED (50%)"
            approved_amount = cost * 0.5
            reason = (
                "入出渠基本料・滞渠費は、事故復旧工事と船主定期点検工事の双方が行われたため、"
                "海事鑑定実務（50%ルール）に基づき折半認定。"
            )
            clause_ref = "Marine Insurance Act / ITC-Hulls Apportionment Rule"
        else:
            repair_zone = infer_repair_zone(desc, cat)
            if repair_zone and damaged_zones:
                causality = any_damage_allows_repair(damaged_zones, repair_zone)
                if not causality["valid"]:
                    status = "EXCLUDED (便乗修理)"
                    approved_amount = 0
                    reason = _ontology_exclude_reason(causality, damaged_zones)
                    clause_ref = "普通保険条項 第3条 / 水密隔壁・区画因果制約"

            # Rule 1b: Negative Pattern Library semantic red-flag triage.
            # Skip status override when compartment causality already supports the
            # line item (avoids MiniLM false-positive apportionment on hull work).
            if not status:
                action = red_flag.get("recommended_action")
                citation = red_flag.get("citation") or ""
                ontology_ok = causality is not None and causality.get("valid")
                if action == ACTION_DISALLOWED and not ontology_ok:
                    status = "EXCLUDED (便乗修理)"
                    approved_amount = 0
                    reason = (
                        f"{citation}。"
                        "公開定期検査仕様との意味的一致により便乗修理（通常損耗・法定整備）として全額排斥。"
                    )
                    clause_ref = "普通保険条項 第3条（通常損耗免責） / Negative Pattern Library"
                elif action == ACTION_APPORTIONED and not ontology_ok:
                    status = "APPORTIONED (50%)"
                    approved_amount = cost * 0.5
                    reason = (
                        f"{citation}。"
                        "定期整備との境界領域のため、ドック共通費用実務に準じ50%按分。"
                    )
                    clause_ref = "ITC-Hulls Apportionment / Negative Pattern Library"

            if not status:
                # Rule 2: Outer hull surface restoration (explicit outer-plate terms only)
                if any(k in desc for k in _OUTER_HULL_SURFACE_KEYS):
                    if has_hull_damage and (
                        causality is None or causality.get("valid")
                    ):
                        status = "COVERED"
                        approved_amount = cost
                        hull_bits = [
                            z
                            for z in damaged_zones
                            if z in ["外板", "球状船首", "貨物タンク", "タンク"]
                        ]
                        reason = (
                            f"事故による船体受傷部位（{', '.join(hull_bits)}）の"
                            "外板表面処理・塗装復旧工事として直接因果関係を認定。"
                        )
                        clause_ref = "船舶保険普通保険条項 第1条（保険の目的・填補危険）"
                    else:
                        status = "EXCLUDED (便乗修理)"
                        approved_amount = 0
                        reason = (
                            "事故報告書に船体外板の損傷記録がなく、"
                            "通常の経年防汚塗装（定期検査工事）と判定。"
                        )
                        clause_ref = "普通保険条項 第3条（通常損耗免責）"

                # Rule 3: Bow thruster (before propeller keywords — thruster lines often mention プロペラ)
                elif description_is_bow_thruster_work(desc):
                    if "球状船首" in damaged_zones:
                        status = "REVIEW / PARTIAL"
                        approved_amount = cost * 0.5
                        reason = (
                            "船首部への衝撃による外傷点検は一部認定するが、"
                            "定期検査に伴うスクリュー防汚塗装は経年維持費として按分。"
                        )
                        clause_ref = "船舶保険普通保険条項 第3条"
                    else:
                        status = "EXCLUDED (便乗修理)"
                        approved_amount = 0
                        reason = "船首部損傷がなく、定期検査に伴うルーチン開放点検と判定。"
                        clause_ref = "普通保険条項 第3条"

                # Rule 4: Propeller / Tailshaft — requires propulsion damage + ontology OK
                elif any(k in desc for k in _PROPULSION_KEYS):
                    if has_propulsion_damage and (causality is None or causality.get("valid")):
                        status = "COVERED"
                        approved_amount = cost
                        reason = (
                            "事故報告書に推進器・軸系の曲損・接触損傷が記録されているため、"
                            "復旧工事として認容。"
                        )
                        clause_ref = "船舶保険普通保険条項 第1条"
                    else:
                        status = "EXCLUDED (便乗修理)"
                        approved_amount = 0
                        reason = (
                            f"事故損傷部位（{', '.join(damaged_zones)}）と無関係な"
                            "推進器・プロペラ軸の定期検査工事（便乗修理）として除外。"
                        )
                        clause_ref = "普通保険条項 第3条（通常損耗・固有の瑕疵免責）"

                # Rule 5: Machinery — requires machinery damage + ontology OK
                elif "機関" in cat or any(k in desc for k in _MACHINERY_KEYS):
                    if has_machinery_damage and (causality is None or causality.get("valid")):
                        status = "COVERED"
                        approved_amount = cost
                        reason = "機関室直接損傷の復旧工事として認定。"
                        clause_ref = "普通保険条項 第1条"
                    else:
                        status = "EXCLUDED (便乗修理)"
                        approved_amount = 0
                        reason = (
                            f"事故損傷部位（{', '.join(damaged_zones)}）と空間的・機能的に無関係な"
                            "機関室／補機定期検査工事。便乗修理として全額排斥。"
                        )
                        clause_ref = "普通保険条項 第3条（通常損耗免責） / 因果関係原則"

                # Rule 6: Unmapped or non-casualty preparation
                else:
                    status = "EXCLUDED (定期点検)"
                    approved_amount = 0
                    reason = (
                        "法定属具・定期検査準備作業であり、"
                        "海難事故による直接損傷の復旧とは因果関係が認められないため除外。"
                    )
                    clause_ref = "普通保険条項 第1条・第3条"

        item_result = dict(item)
        item_result["status"] = status
        item_result["approved_amount"] = int(approved_amount)
        item_result["excluded_amount"] = int(cost - approved_amount)
        item_result["reason"] = reason
        item_result["clause_ref"] = clause_ref
        item_result["red_flag_similarity"] = red_flag.get("red_flag_similarity", 0.0)
        item_result["matched_pattern_id"] = red_flag.get("matched_pattern_id")
        item_result["matched_trade_code"] = red_flag.get("matched_trade_code")
        item_result["recommended_action"] = red_flag.get("recommended_action")
        item_result["citation"] = red_flag.get("citation")
        if repair_zone:
            item_result["repair_zone"] = repair_zone
        if causality:
            item_result["ontology"] = {
                "valid": causality.get("valid"),
                "reason": causality.get("reason"),
                "damage_node": causality.get("damage_node"),
                "repair_node": causality.get("repair_node"),
                "hops": causality.get("hops"),
            }

        total_covered += item_result["approved_amount"]
        total_excluded += item_result["excluded_amount"]
        analyzed.append(item_result)

    summary = {
        "casualty_profile": casualty_profile,
        "total_items": len(analyzed),
        "total_claimed_jpy": total_claimed,
        "total_approved_jpy": int(total_covered),
        "total_excluded_jpy": int(total_excluded),
        "leakage_prevention_rate_pct": round((total_excluded / total_claimed) * 100, 1)
        if total_claimed
        else 0.0,
        "items_covered_count": len(
            [x for x in analyzed if "COVERED" in x["status"] or "50%" in x["status"]]
        ),
        "items_excluded_count": len([x for x in analyzed if "EXCLUDED" in x["status"]]),
        "items_review_count": len([x for x in analyzed if "REVIEW" in x["status"]]),
        "pricing_note": (
            "Line-item JPY amounts are model estimates from public standard repair "
            "unit-price heuristics (not shipyard tender figures on the source PDF)."
        ),
    }

    return analyzed, summary


def extract_casualty_profile(casualty_pdf_path):
    """Dynamically extracts vessel identity, incident type, and physical damage zones from casualty report."""
    cmd = ["pdftotext", casualty_pdf_path, "-"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    text = res.stdout

    # 1. Vessel Name / Type
    vessel_name = "一般船舶"
    m_vessel = re.search(r"船\s*種\s*船\s*名\s*\n+([^\n]+)", text)
    if m_vessel:
        vessel_name = m_vessel.group(1).strip()
    else:
        m_vessel2 = re.search(r"（以下「([^\n」]+)」という。）", text)
        if m_vessel2:
            vessel_name = m_vessel2.group(1).strip()

    # 2. Incident Type
    incident_type = "海難事故"
    m_inc = re.search(r"事\s*故\s*種\s*類\s*\n+([^\n]+)", text)
    if m_inc:
        incident_type = m_inc.group(1).strip()

    # 3. Incident Date / Location
    incident_date = "不詳"
    m_date = re.search(r"発\s*生\s*日\s*時\s*\n+([^\n]+)", text)
    if m_date:
        incident_date = m_date.group(1).strip()

    incident_loc = "海域"
    m_loc = re.search(r"発\s*生\s*場\s*所\s*\n+([^\n]+)", text)
    if m_loc:
        incident_loc = m_loc.group(1).strip()

    # 4. Semantic Damage Zone Extraction from dedicated Damage Section
    m_dmg_sec = re.search(r"船舶の損傷に関する情報\s*\n(.*?)(?=\n[１２３４５\d]\.|\n\s*\d+\s+乗組員|\n\s*２\.４)", text, re.DOTALL)
    damage_text = m_dmg_sec.group(1) if m_dmg_sec else text[:4000]

    damaged_components = set()
    damage_evidence = []

    damage_rules = [
        ("球状船首", ["球状船首", "バルバスバウ", "船首部"], "船首部衝撃・擦過傷"),
        ("外板", ["外板", "船側外板", "船底外板", "破口", "亀裂", "擦過傷"], "船体外板破口・損傷"),
        ("甲板", ["甲板", "上甲板", "船首甲板", "圧壊"], "上部構造・甲板圧壊"),
        ("居住区", ["居住区", "船橋", "操舵室"], "居住区圧壊・破損"),
        ("貨物タンク", ["貨物油タンク", "カーゴタンク", "バラストタンク", "タンクの破口"], "タンク構造損傷"),
        ("推進器", ["プロペラ", "推進器", "翼曲損", "プロペラ軸"], "推進器・軸系損傷"),
        ("舵", ["舵", "舵板", "ラダー", "舵頭材"], "舵取装置損傷"),
        ("機関室", ["機関室浸水", "主機損傷", "クランク軸損傷"], "主機・機関室直接損傷"),
    ]

    for comp_name, keywords, label in damage_rules:
        for kw in keywords:
            if kw in damage_text:
                damaged_components.add(comp_name)
                damage_evidence.append(f"{label}（キーワード: {kw} を検出）")
                break

    return {
        "vessel_name": vessel_name,
        "incident_type": incident_type,
        "incident_date": incident_date,
        "incident_location": incident_loc,
        "damaged_components": list(damaged_components),
        "damage_evidence": damage_evidence,
        "source_pdf": os.path.basename(casualty_pdf_path)
    }

def extract_repair_items(spec_pdf_path):
    """Dynamically parses arbitrary drydock repair specification PDF into structured line items."""
    cmd = ["pdftotext", spec_pdf_path, "-"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    lines = [line.strip() for line in res.stdout.split("\n") if line.strip()]

    items = []
    current_category = "【甲板部】"
    item_id = 0

    price_heuristics = {
        "入出渠": 2500000,
        "滞渠": 1800000,
        "高圧清水洗浄": 450000,
        "塗装": 1200000,
        "サンダー": 650000,
        "主機関": 4800000,
        "ピストン": 1800000,
        "燃料噴射弁": 600000,
        "吸排気弁": 750000,
        "プロペラ": 1500000,
        "波止弁": 850000,
        "弁": 400000,
        "亜鉛": 350000,
        "計測": 250000,
        "バウスラスター": 950000,
        "発電機関": 2200000,
        "ポンプ": 550000,
        "電磁弁": 300000,
        "交通艇": 450000,
        "default": 350000
    }

    current_item_text = ""
    current_item_num = ""
    skip_headers = ("番号", "工 事 内 訳", "数量", "単位", "令和")

    def flush():
        nonlocal item_id, current_item_text, current_item_num
        if not current_item_text:
            return
        item_id += 1
        est_cost = price_heuristics["default"]
        for k, v in price_heuristics.items():
            if k in current_item_text:
                est_cost = v
                break
        # Combined drydock dues line often matches 入出渠 first; add 滞渠 if both present.
        if "入出渠" in current_item_text and "滞渠" in current_item_text:
            est_cost = price_heuristics["入出渠"] + price_heuristics["滞渠"]
        items.append({
            "id": item_id,
            "category": current_category,
            "num": current_item_num,
            "description": current_item_text,
            "estimated_cost": est_cost
        })
        current_item_text = ""
        current_item_num = ""

    for line in lines:
        if line.startswith("【") and line.endswith("】"):
            flush()
            current_category = line
            continue

        if any(line.startswith(h) for h in skip_headers):
            continue

        # "2 船体入出渠…" on one line, or circled numbers with text
        m_inline = re.match(r"^(\d+|[\u2460-\u246f])\s+(.+)$", line)
        if m_inline:
            flush()
            current_item_num = m_inline.group(1)
            current_item_text = m_inline.group(2)
            continue

        # Split layout: number alone, description on following lines (common in 仕様書 PDFs)
        m_num_only = re.match(r"^(\d+|[\u2460-\u246f])$", line)
        if m_num_only:
            flush()
            current_item_num = m_num_only.group(1)
            current_item_text = ""
            continue

        if current_item_num != "" or current_item_text:
            # Continuation / description after a lone number
            if not current_item_text:
                current_item_text = line
            else:
                current_item_text += " " + line

    flush()
    return items


def main():
    parser = argparse.ArgumentParser(description="MarineClaims AI Dynamic Claims Analysis Pipeline")
    parser.add_argument("--spec", default=DEFAULT_SPEC_PDF, help="Path to drydock repair specification PDF")
    parser.add_argument("--casualty", default=DEFAULT_CASUALTY_PDF, help="Path to maritime casualty report PDF")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory to save output files")
    parser.add_argument("--tag", default="default", help="Output filename tag")
    parser.add_argument(
        "--export-report",
        nargs="?",
        const="",
        default=None,
        help=(
            "Write Preliminary Survey Report Markdown. "
            "Optional path; default is <output-dir>/preliminary_survey_report[_tag].md"
        ),
    )
    args = parser.parse_args()

    print(f"[1/3] Extracting casualty profile from: {args.casualty}")
    casualty_profile = extract_casualty_profile(args.casualty)
    print(f"      Vessel: {casualty_profile['vessel_name']}, Type: {casualty_profile['incident_type']}")
    print(f"      Damaged Components: {casualty_profile['damaged_components']}")

    print(f"[2/3] Parsing repair specification from: {args.spec}")
    items = extract_repair_items(args.spec)
    print(f"      Extracted {len(items)} repair items.")

    print("[3/3] Running dynamic casualty cross-check & concurrent repair screening...")
    analyzed, summary = evaluate_claims_dynamically(items, casualty_profile)

    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(
        args.output_dir,
        f"claims_analysis_{args.tag}.json" if args.tag != "default" else "claims_analysis_result.json",
    )

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "items": analyzed}, f, ensure_ascii=False, indent=2)

    report_path = None
    if args.export_report is not None:
        if args.export_report:
            report_path = args.export_report
        else:
            report_name = (
                f"preliminary_survey_report_{args.tag}.md"
                if args.tag != "default"
                else "preliminary_survey_report.md"
            )
            report_path = os.path.join(args.output_dir, report_name)
        report_md = render_preliminary_survey_report(summary, analyzed)
        parent = os.path.dirname(report_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)

    cp = summary["casualty_profile"]
    print("\n=== MARINE CLAIMS ANALYSIS RESULT ===")
    print(f"Casualty Vessel  : {cp['vessel_name']} ({cp['incident_type']})")
    print(f"Damaged Zones    : {', '.join(cp['damaged_components'])}")
    print(f"Total Items      : {summary['total_items']} items")
    print(f"Total Claimed    : JPY {summary['total_claimed_jpy']:,}")
    print(f"Approved (Covered): JPY {summary['total_approved_jpy']:,}")
    print(f"Excluded (Leakage): JPY {summary['total_excluded_jpy']:,} ({summary['leakage_prevention_rate_pct']}%)")
    print(f"Pricing note     : {summary.get('pricing_note', '')}")
    print(f"Output JSON      : {json_path}")
    if report_path:
        print(f"Survey report    : {report_path}")


if __name__ == "__main__":
    main()
