"""Live document analysis for the executive demo (PDF → engines)."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from marine_claims_ai.adapters.base import DockFeeBreakdown, DockFeeMethod
from marine_claims_ai.analytics import (
    DockingContext,
    OwnerNecessity,
    RepairLineItem,
    WorkParty,
    apportion_rule_d,
    predict_fault_ratio,
)
from marine_claims_ai.appraisal.pipeline import extract_repair_items
from marine_claims_ai.demo.documents import pdftotext_available, resolve_pdf
from marine_claims_ai.demo.i18n import Lang, t
from marine_claims_ai.demo.logging_setup import get_demo_logger
from marine_claims_ai.ingest.civil_judgment_extractor import extract_from_judgment
from marine_claims_ai.ingest.jmat_extractor import extract_telemetry
from marine_claims_ai.ingest.pdf_text import pdf_to_text
from marine_claims_ai.legal.colregs_engine import EncounterGeometry, classify_encounter

log = get_demo_logger("live_analysis")


def require_pdftotext(lang: Lang = "en") -> str | None:
    if pdftotext_available():
        return None
    return t("err_pdftotext", lang)


def repair_items_to_rule_d_lines(
    items: list[dict[str, Any]],
    *,
    daily_dock_rate: int,
    dock_days: int,
    include_statutory: bool,
) -> tuple[list[RepairLineItem], Decimal]:
    """Map extracted spec lines into Rule D5 RepairLineItem list."""
    dock_total = Decimal(daily_dock_rate) * Decimal(dock_days)
    lines: list[RepairLineItem] = []
    saw_dock = False
    saw_statutory = False
    n = 0

    for it in items:
        desc = str(it.get("description") or "")
        cost = Decimal(int(it.get("estimated_cost") or 0))
        if cost <= 0:
            continue
        n += 1
        lid = f"pdf-{n}"

        if "入出渠" in desc or "滞渠" in desc or "入渠" in desc:
            saw_dock = True
            lines.append(
                RepairLineItem(
                    id=lid,
                    trade_code="DOCK-01",
                    cost=dock_total if cost > 0 else dock_total,
                    title=desc[:80] or "Common dock dues",
                )
            )
            continue

        if any(k in desc for k in ("法定", "検査証書", "SOLAS", "船級", "年次検査", "中間検査")):
            saw_statutory = True
            if include_statutory:
                lines.append(
                    RepairLineItem(
                        id=lid,
                        trade_code="SAFE-01",
                        cost=cost,
                        necessity=OwnerNecessity.STATUTORY_SEAWORTHINESS,
                        title=desc[:80],
                    )
                )
            continue

        if any(k in desc for k in ("主機関", "ピストン", "プロペラ軸", "減速機", "発電機関", "カロリー")):
            lines.append(
                RepairLineItem(
                    id=lid,
                    trade_code="ENG-02",
                    cost=cost,
                    necessity=OwnerNecessity.DEFERRED,
                    title=desc[:80],
                )
            )
            continue

        if any(k in desc for k in ("外板", "球状船首", "船首", "バウスラスター", "塗装", "洗浄")):
            lines.append(
                RepairLineItem(
                    id=lid,
                    trade_code="HULL-01",
                    cost=cost,
                    work_party=WorkParty.CASUALTY,
                    title=desc[:80],
                )
            )
            continue

        # Remaining → owner deferred sample (cap count for demo clarity)
        if len([x for x in lines if x.necessity == OwnerNecessity.DEFERRED]) < 3:
            lines.append(
                RepairLineItem(
                    id=lid,
                    trade_code="OWN-01",
                    cost=min(cost, Decimal("2000000")),
                    necessity=OwnerNecessity.DEFERRED,
                    title=desc[:80],
                )
            )

    if not saw_dock:
        lines.append(
            RepairLineItem(
                id="dock-1",
                trade_code="DOCK-01",
                cost=dock_total,
                title="Entering / leaving / lay dues",
            )
        )
    else:
        # Normalize dock line cost to slider total
        for i, ln in enumerate(lines):
            if ln.trade_code.startswith("DOCK"):
                lines[i] = ln.model_copy(update={"cost": dock_total})

    if include_statutory and not saw_statutory:
        lines.append(
            RepairLineItem(
                id="safe-1",
                trade_code="SAFE-01",
                cost=Decimal("550000"),
                necessity=OwnerNecessity.STATUTORY_SEAWORTHINESS,
                title="Statutory survey item",
            )
        )

    # Ensure at least one casualty + one owner for a meaningful D5 demo
    if not any(ln.work_party == WorkParty.CASUALTY for ln in lines):
        lines.insert(
            0,
            RepairLineItem(
                id="hull-1",
                trade_code="HULL-01",
                cost=Decimal("4500000"),
                work_party=WorkParty.CASUALTY,
                title="Casualty hull repair (from document context)",
            ),
        )

    return lines, dock_total


def run_uc2_from_pdf(
    spec_pdf: str | Path,
    *,
    lang: Lang = "en",
    daily_dock_rate: int = 860_000,
    dock_days: int = 5,
    hire_rate: int = 4_000_000,
    legacy_lead_days: int = 21,
    ai_lead_minutes: int = 15,
    docking_context: str = DockingContext.CASUALTY_IMMEDIATE.value,
    include_statutory: bool = True,
) -> dict[str, Any]:
    err = require_pdftotext(lang)
    if err:
        return {"ok": False, "error": err}
    spec = resolve_pdf(spec_pdf)
    if spec is None:
        return {"ok": False, "error": t("err_pdf_missing", lang)}

    try:
        items = extract_repair_items(str(spec))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": t("err_parse_failed", lang) + f" ({type(exc).__name__})"}

    if not items:
        return {"ok": False, "error": t("err_no_line_items", lang)}

    try:
        ctx = DockingContext(docking_context)
    except ValueError:
        ctx = DockingContext.CASUALTY_IMMEDIATE

    lines, dock_total = repair_items_to_rule_d_lines(
        items,
        daily_dock_rate=daily_dock_rate,
        dock_days=dock_days,
        include_statutory=include_statutory,
    )
    result = apportion_rule_d(
        lines,
        docking_context=ctx,
        dock_fee=DockFeeBreakdown(
            method=DockFeeMethod.DAILY_LAY,
            currency="JPY",
            total=dock_total,
            daily_rate=Decimal(daily_dock_rate),
            dock_days=dock_days,
        ),
    )

    ai_days = ai_lead_minutes / (60.0 * 24.0)
    days_saved = max(0.0, float(legacy_lead_days) - ai_days)
    offhire_jpy = int(days_saved * hire_rate)

    return {
        "ok": True,
        "spec_pdf": spec.name,
        "n_extracted": len(items),
        "daily_dock_rate": daily_dock_rate,
        "dock_days": dock_days,
        "hire_rate": hire_rate,
        "legacy_lead_days": legacy_lead_days,
        "ai_lead_minutes": ai_lead_minutes,
        "docking_context": ctx.value,
        "include_statutory": include_statutory,
        "dock_total": int(dock_total),
        "insurer_common": int(result.insurer_common_share),
        "owner_common": int(result.owner_common_share),
        "insurer_total": int(result.insurer_total),
        "owner_total": int(result.owner_total),
        "rule": str(result.apportionment_rule),
        "line_rows": [
            {
                "id": ln.id,
                "title": next((x.title for x in lines if x.id == ln.id), ln.id),
                "trade_code": ln.trade_code,
                "cost": int(ln.cost),
                "insurer": int(ln.insurer_share),
                "owner": int(ln.owner_share),
                "rule": str(ln.apportionment_rule),
            }
            for ln in result.lines
        ],
        "gantt": [
            {"lane": t("lane_casualty", lang), "start": 0, "days": max(2, dock_days - 1), "css": "casualty"},
            {"lane": t("lane_owner", lang), "start": 1, "days": max(1, dock_days - 2), "css": "owner"},
            {"lane": t("lane_common", lang), "start": 0, "days": dock_days, "css": "common"},
        ],
        "days_saved": round(days_saved, 2),
        "offhire_jpy": offhire_jpy,
        "result": result,
        "from_document": True,
    }


def run_uc3_from_pdf(
    doc_pdf: str | Path,
    *,
    lang: Lang = "en",
    heading_a_deg: float | None = None,
    heading_b_deg: float | None = None,
    true_bearing_a_to_b_deg: float | None = None,
) -> dict[str, Any]:
    err = require_pdftotext(lang)
    if err:
        return {"ok": False, "error": err}
    path = resolve_pdf(doc_pdf)
    if path is None:
        return {"ok": False, "error": t("err_pdf_missing", lang)}

    text = pdf_to_text(str(path))
    if not text.strip():
        return {"ok": False, "error": t("err_pdf_empty_text", lang)}

    # Split rough facts / ruling for telemetry
    facts = text
    ruling = ""
    m = re.search(r"(主文|理由|裁決|判示)", text)
    if m and m.start() > 200:
        facts = text[: m.start()]
        ruling = text[m.start() :]

    judgment = extract_from_judgment(text)
    tele = extract_telemetry(facts, ruling)

    geometry: EncounterGeometry
    if tele.extraction_ok:
        # relative bearing from own ship; approximate true bearing ≈ relative when heading_a=0
        ha = float(tele.heading_a_deg or 0)
        hb = float(tele.heading_b_deg or 180)
        rel = float(tele.relative_bearing_a_to_b_deg or 0)
        true_brg = (ha + rel) % 360
        geometry = EncounterGeometry(
            heading_a_deg=ha,
            heading_b_deg=hb,
            true_bearing_a_to_b_deg=true_brg,
            speed_a_kn=float(tele.speed_a_kn or 12),
            speed_b_kn=float(tele.speed_b_kn or 10),
            range_nm=1.0,
        )
    else:
        geometry = EncounterGeometry(
            heading_a_deg=0,
            heading_b_deg=270,
            true_bearing_a_to_b_deg=45,
            speed_a_kn=12,
            speed_b_kn=10,
            range_nm=1.0,
        )

    overrides = any(v is not None for v in (heading_a_deg, heading_b_deg, true_bearing_a_to_b_deg))
    if overrides:
        geometry = EncounterGeometry(
            heading_a_deg=float(heading_a_deg if heading_a_deg is not None else geometry.heading_a_deg),
            heading_b_deg=float(heading_b_deg if heading_b_deg is not None else geometry.heading_b_deg),
            true_bearing_a_to_b_deg=float(
                true_bearing_a_to_b_deg
                if true_bearing_a_to_b_deg is not None
                else geometry.true_bearing_a_to_b_deg
            ),
            speed_a_kn=geometry.speed_a_kn,
            speed_b_kn=geometry.speed_b_kn,
            range_nm=geometry.range_nm,
        )

    verdict = classify_encounter(geometry)
    prediction = predict_fault_ratio(facts[:4000], geometry=geometry)
    fault_ratio = judgment.fault_ratio or prediction.fault_ratio

    holding = judgment.holding_excerpt or (ruling[:800] if ruling else facts[:800])

    return {
        "ok": True,
        "from_document": True,
        "doc_pdf": path.name,
        "case_id": f"pdf:{path.name}",
        "title": path.stem,
        "facts": facts[:2500],
        "ruling": holding or "",
        "situation": verdict.situation.value,
        "role_a": verdict.role_a.value if verdict.role_a else None,
        "role_b": verdict.role_b.value if verdict.role_b else None,
        "rule_citations": list(verdict.rule_citations),
        "fault_ratio": fault_ratio,
        "prediction": prediction,
        "relative_bearing": round(verdict.relative_bearing_a_to_b_deg, 1),
        "geometry": geometry.model_dump(),
        "overrides_applied": overrides,
        "verdict": verdict,
        "telemetry_ok": tele.extraction_ok,
        "options": [],
    }
