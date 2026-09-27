"""Pure view-model builders for demo use cases."""

from __future__ import annotations

import math
from decimal import Decimal
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
from marine_claims_ai.demo import live_analysis
from marine_claims_ai.demo.documents import label_for_pdf, list_pdfs
from marine_claims_ai.demo.i18n import Lang, role_label, situation_label, t
from marine_claims_ai.demo.loaders import (
    load_civil_catalog,
    load_geometries,
    load_jmat_cases,
)
from marine_claims_ai.legal.colregs_engine import (
    OVERTAKING_RELATIVE_BEARING_MAX_DEG,
    OVERTAKING_RELATIVE_BEARING_MIN_DEG,
    EncounterGeometry,
    classify_encounter,
)


def _doc_options(role: str, lang: Lang) -> list[dict[str, str]]:
    return [{"id": e.id, "label": e.label(lang), "uploaded": e.uploaded} for e in list_pdfs(role=role)]



def build_uc2(
    lang: Lang = "en",
    *,
    daily_dock_rate: int = 860_000,
    dock_days: int = 5,
    hire_rate: int = 4_000_000,
    legacy_lead_days: int = 21,
    ai_lead_minutes: int = 15,
    docking_context: str = DockingContext.CASUALTY_IMMEDIATE.value,
    include_statutory: bool = True,
    spec_pdf: str | None = None,
    analyze: bool = False,
) -> dict[str, Any]:
    daily_dock_rate = max(100_000, min(daily_dock_rate, 5_000_000))
    dock_days = max(1, min(dock_days, 30))
    hire_rate = max(100_000, min(hire_rate, 20_000_000))
    legacy_lead_days = max(1, min(legacy_lead_days, 60))
    ai_lead_minutes = max(1, min(ai_lead_minutes, 24 * 60))

    doc_opts = _doc_options("uc2", lang)
    if not doc_opts:
        doc_opts = _doc_options("spec", lang)
    chosen = spec_pdf or (doc_opts[0]["id"] if doc_opts else None)

    if analyze and chosen:
        live = live_analysis.run_uc2_from_pdf(
            chosen,
            lang=lang,
            daily_dock_rate=daily_dock_rate,
            dock_days=dock_days,
            hire_rate=hire_rate,
            legacy_lead_days=legacy_lead_days,
            ai_lead_minutes=ai_lead_minutes,
            docking_context=docking_context,
            include_statutory=include_statutory,
        )
        live["spec_options"] = doc_opts
        live["spec_pdf"] = chosen
        live["spec_pdf_label"] = label_for_pdf(chosen, lang)
        return live

    try:
        ctx = DockingContext(docking_context)
    except ValueError:
        ctx = DockingContext.CASUALTY_IMMEDIATE

    dock_total = Decimal(daily_dock_rate) * Decimal(dock_days)
    lines = [
        RepairLineItem(
            id="hull-1",
            trade_code="HULL-01",
            cost=Decimal("4500000"),
            work_party=WorkParty.CASUALTY,
            title="Bow shell plating repair",
        ),
        RepairLineItem(
            id="eng-1",
            trade_code="ENG-02",
            cost=Decimal("1800000"),
            necessity=OwnerNecessity.DEFERRED,
            title="Piston overhaul (owner)",
        ),
    ]
    if include_statutory:
        lines.append(
            RepairLineItem(
                id="safe-1",
                trade_code="SAFE-01",
                cost=Decimal("550000"),
                title="Statutory survey item",
            )
        )
    lines.append(
        RepairLineItem(
            id="dock-1",
            trade_code="DOCK-01",
            cost=dock_total,
            title="Entering / leaving / lay dues",
        )
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

    gantt = [
        {"lane": t("lane_casualty", lang), "start": 0, "days": max(2, dock_days - 1), "css": "casualty"},
        {"lane": t("lane_owner", lang), "start": 1, "days": max(1, dock_days - 2), "css": "owner"},
        {"lane": t("lane_common", lang), "start": 0, "days": dock_days, "css": "common"},
    ]

    return {
        "ok": True,
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
        "gantt": gantt,
        "days_saved": round(days_saved, 2),
        "offhire_jpy": offhire_jpy,
        "result": result,
        "spec_options": doc_opts,
        "spec_pdf": chosen or "",
        "spec_pdf_label": label_for_pdf(chosen, lang),
        "from_document": False,
    }


def list_uc3_cases(lang: Lang = "en") -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for c in load_jmat_cases():
        cases.append(
            {
                "id": str(c.get("case_id")),
                "title": str(c.get("title") or c.get("case_id")),
                "source": "jmat",
            }
        )
    for c in load_civil_catalog():
        if int(c.get("case_id") or 0) == 7:
            cases.insert(
                0,
                {
                    "id": "civil_7",
                    "title": str(c.get("title") or "Atago / Seitoku Maru"),
                    "source": "civil",
                },
            )
            break
    return cases


def build_uc3(
    lang: Lang = "en",
    *,
    case_id: str | None = None,
    heading_a_deg: float | None = None,
    heading_b_deg: float | None = None,
    true_bearing_a_to_b_deg: float | None = None,
    doc_pdf: str | None = None,
    analyze: bool = False,
) -> dict[str, Any]:
    doc_opts = _doc_options("uc3", lang)
    options = list_uc3_cases(lang)

    if analyze and doc_pdf:
        live = live_analysis.run_uc3_from_pdf(
            doc_pdf,
            lang=lang,
            heading_a_deg=heading_a_deg,
            heading_b_deg=heading_b_deg,
            true_bearing_a_to_b_deg=true_bearing_a_to_b_deg,
        )
        if not live.get("ok"):
            live["options"] = options
            live["doc_options"] = doc_opts
            live["doc_pdf"] = doc_pdf
            live["doc_pdf_label"] = label_for_pdf(doc_pdf, lang)
            return live
        verdict = live["verdict"]
        rel = live["relative_bearing"]
        rad = math.radians(rel)
        live.update(
            {
                "options": options,
                "doc_options": doc_opts,
                "doc_pdf_label": label_for_pdf(live.get("doc_pdf") or doc_pdf, lang),
                "situation_label": situation_label(live["situation"], lang),
                "role_a_label": role_label(live.get("role_a"), lang),
                "role_b_label": role_label(live.get("role_b"), lang),
                "radar": {
                    "target_x": round(math.sin(rad), 4),
                    "target_y": round(math.cos(rad), 4),
                    "overtaking_min": OVERTAKING_RELATIVE_BEARING_MIN_DEG,
                    "overtaking_max": OVERTAKING_RELATIVE_BEARING_MAX_DEG,
                },
            }
        )
        return live

    if not options:
        return {
            "ok": False,
            "error": t("err_no_colregs_cases", lang),
            "doc_options": doc_opts,
            "options": [],
        }
    selected = case_id or options[0]["id"]
    if selected not in {o["id"] for o in options}:
        selected = options[0]["id"]

    facts = ""
    ruling = ""
    title = selected
    geometry: EncounterGeometry | None = None
    catalog_fault: str | None = None

    if selected == "civil_7":
        civil = next((c for c in load_civil_catalog() if int(c.get("case_id") or 0) == 7), None)
        if civil:
            title = str(civil.get("title") or title)
            facts = str(civil.get("input_facts") or "")
            ruling = str(civil.get("holding") or "")
            catalog_fault = str(civil.get("fault_ratio") or "70:30")
            geometry = EncounterGeometry(
                heading_a_deg=30,
                heading_b_deg=300,
                true_bearing_a_to_b_deg=70,
                speed_a_kn=12,
                speed_b_kn=10,
                range_nm=0.8,
            )
    else:
        jmat = next((c for c in load_jmat_cases() if str(c.get("case_id")) == selected), None)
        if jmat:
            title = str(jmat.get("title") or title)
            facts = str(jmat.get("facts_text") or "")
            ruling = str(jmat.get("ruling_text") or "")
            geometry = _geometry_for_expected(str(jmat.get("expected_situation") or "crossing"))

    if geometry is None:
        geometry = EncounterGeometry(
            heading_a_deg=0,
            heading_b_deg=270,
            true_bearing_a_to_b_deg=45,
            speed_a_kn=12,
            speed_b_kn=10,
            range_nm=1.0,
        )

    overrides_applied = any(v is not None for v in (heading_a_deg, heading_b_deg, true_bearing_a_to_b_deg))
    if overrides_applied:
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
        catalog_fault = None

    verdict = classify_encounter(geometry)
    prediction = predict_fault_ratio(facts or ruling or title, geometry=geometry)
    fault_ratio = catalog_fault or prediction.fault_ratio

    rel = verdict.relative_bearing_a_to_b_deg
    rad = math.radians(rel)
    tx = math.sin(rad)
    ty = math.cos(rad)

    return {
        "ok": True,
        "options": options,
        "doc_options": doc_opts,
        "doc_pdf": doc_pdf or (doc_opts[0]["id"] if doc_opts else ""),
        "doc_pdf_label": label_for_pdf(doc_pdf or (doc_opts[0]["id"] if doc_opts else ""), lang),
        "from_document": False,
        "case_id": selected,
        "title": title,
        "facts": facts,
        "ruling": ruling,
        "situation": verdict.situation.value,
        "situation_label": situation_label(verdict.situation.value, lang),
        "role_a": verdict.role_a.value if verdict.role_a else None,
        "role_b": verdict.role_b.value if verdict.role_b else None,
        "role_a_label": role_label(verdict.role_a.value if verdict.role_a else None, lang),
        "role_b_label": role_label(verdict.role_b.value if verdict.role_b else None, lang),
        "rule_citations": list(verdict.rule_citations),
        "fault_ratio": fault_ratio,
        "prediction": prediction,
        "relative_bearing": round(rel, 1),
        "radar": {
            "target_x": round(tx, 4),
            "target_y": round(ty, 4),
            "overtaking_min": OVERTAKING_RELATIVE_BEARING_MIN_DEG,
            "overtaking_max": OVERTAKING_RELATIVE_BEARING_MAX_DEG,
        },
        "geometry": geometry.model_dump(),
        "overrides_applied": overrides_applied,
        "verdict": verdict,
    }


def _geometry_for_expected(situation: str) -> EncounterGeometry:
    for g in load_geometries():
        if str(g.get("expected_situation")) == situation:
            return EncounterGeometry(
                heading_a_deg=float(g["heading_a_deg"]),
                heading_b_deg=float(g["heading_b_deg"]),
                true_bearing_a_to_b_deg=float(g["true_bearing_a_to_b_deg"]),
                speed_a_kn=12.0,
                speed_b_kn=10.0,
                range_nm=1.0,
            )
    defaults = {
        "head_on": (0.0, 180.0, 0.0),
        "overtaking": (0.0, 0.0, 180.0),
        "crossing": (0.0, 270.0, 45.0),
    }
    a, b, brg = defaults.get(situation, (0.0, 270.0, 45.0))
    return EncounterGeometry(
        heading_a_deg=a,
        heading_b_deg=b,
        true_bearing_a_to_b_deg=brg,
        speed_a_kn=12.0,
        speed_b_kn=10.0,
        range_nm=1.0,
    )


def _status_css(status: str) -> str:
    s = status.upper()
    if "COVERED" in s:
        return "covered"
    if "APPORTIONED" in s:
        return "apportioned"
    if "EXCLUDED" in s:
        return "excluded"
    if "REVIEW" in s:
        return "review"
    return ""
