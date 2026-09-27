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
from marine_claims_ai.demo.i18n import Lang, role_label, situation_label, status_label, t, zone_label
from marine_claims_ai.demo.loaders import (
    load_civil_catalog,
    load_geometries,
    load_jmat_cases,
    load_kaiyomaru_analysis,
)
from marine_claims_ai.legal.colregs_engine import (
    OVERTAKING_RELATIVE_BEARING_MAX_DEG,
    OVERTAKING_RELATIVE_BEARING_MIN_DEG,
    EncounterGeometry,
    classify_encounter,
)
from marine_claims_ai.ontology.compartments import COMPARTMENT_EDGES, ISOLATED_NODES, build_compartment_graph

# Ship-profile-ish layout for NetworkX nodes (x aft←→fwd, y deck↑).
_NODE_XY: dict[str, tuple[float, float]] = {
    "hull_forward": (0.85, 0.35),
    "hull_mid": (0.50, 0.35),
    "hull_aft": (0.15, 0.35),
    "deck_forward": (0.85, 0.65),
    "deck_mid": (0.50, 0.65),
    "deck_aft": (0.15, 0.65),
    "superstructure": (0.45, 0.90),
    "propulsion": (0.08, 0.20),
    "machinery": (0.50, 0.08),
}

_DAMAGE_DEFAULT = "hull_forward"


def build_uc1(lang: Lang = "en", *, sample_excluded: int = 40) -> dict[str, Any]:
    raw = load_kaiyomaru_analysis()
    if raw is None:
        return {"ok": False, "error": t("data_missing", lang)}

    summary = raw.get("summary") or {}
    items = list(raw.get("items") or [])
    damaged = list((summary.get("casualty_profile") or {}).get("damaged_components") or [])
    damage_node = _DAMAGE_DEFAULT

    covered = [i for i in items if i.get("status") == "COVERED"]
    apportioned = [i for i in items if "APPORTIONED" in str(i.get("status") or "")]
    excluded = [i for i in items if "EXCLUDED" in str(i.get("status") or "")]
    review = [i for i in items if "REVIEW" in str(i.get("status") or "")]

    display_items = covered + apportioned + review + excluded[:sample_excluded]
    rows = [
        {
            "id": it.get("id") or it.get("num") or "",
            "description": it.get("description") or it.get("category") or "",
            "status": it.get("status") or "",
            "status_label": status_label(str(it.get("status") or ""), lang),
            "amount": int(it.get("estimated_cost") or 0),
            "reason": it.get("reason") or "",
            "css": _status_css(str(it.get("status") or "")),
        }
        for it in display_items
    ]

    g = build_compartment_graph()
    nodes = []
    for n in g.nodes:
        x, y = _NODE_XY.get(n, (0.5, 0.5))
        kind = "isolated" if n in ISOLATED_NODES else ("damaged" if n == damage_node else "normal")
        nodes.append(
            {
                "id": n,
                "label": zone_label(n, lang),
                "x": x,
                "y": y,
                "kind": kind,
                "kind_label": t(kind if kind != "normal" else "normal", lang),
            }
        )
    edges = [{"source": a, "target": b} for a, b in COMPARTMENT_EDGES]

    return {
        "ok": True,
        "summary": summary,
        "n_items": len(items),
        "claimed": int(summary.get("total_claimed_jpy") or 0),
        "excluded_jpy": int(summary.get("total_excluded_jpy") or 0),
        "approved_jpy": int(summary.get("total_approved_jpy") or 0),
        "rate": summary.get("leakage_prevention_rate_pct"),
        "damaged_labels": damaged,
        "counts": {
            "covered": len(covered),
            "apportioned": len(apportioned),
            "excluded": len(excluded),
            "review": len(review),
        },
        "rows": rows,
        "showing_sample": len(excluded) > sample_excluded,
        "graph": {"nodes": nodes, "edges": edges},
        "items_for_export": items,
        "summary_for_export": summary,
    }


def build_uc2(
    lang: Lang = "en",
    *,
    daily_dock_rate: int = 860_000,
    dock_days: int = 5,
    hire_rate: int = 4_000_000,
    legacy_lead_days: int = 21,
    ai_lead_minutes: int = 15,
) -> dict[str, Any]:
    daily_dock_rate = max(100_000, min(daily_dock_rate, 5_000_000))
    dock_days = max(1, min(dock_days, 30))
    hire_rate = max(100_000, min(hire_rate, 20_000_000))
    legacy_lead_days = max(1, min(legacy_lead_days, 60))
    ai_lead_minutes = max(1, min(ai_lead_minutes, 24 * 60))

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
        RepairLineItem(
            id="safe-1",
            trade_code="SAFE-01",
            cost=Decimal("550000"),
            title="Statutory survey item",
        ),
        RepairLineItem(
            id="dock-1",
            trade_code="DOCK-01",
            cost=dock_total,
            title="Entering / leaving / lay dues",
        ),
    ]
    result = apportion_rule_d(
        lines,
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
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
    # Pitch heuristic: ~3 calendar days of off-hire avoided when lead time collapses.
    effective_saved = min(days_saved, float(legacy_lead_days))
    # Cap presentation to docking-relevant savings (default narrative ≈ 3 days).
    offhire_days = min(3.0, effective_saved) if effective_saved >= 3 else effective_saved
    offhire_jpy = int(offhire_days * hire_rate)

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
        "days_saved": round(offhire_days, 2),
        "offhire_jpy": offhire_jpy,
        "result": result,
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


def build_uc3(lang: Lang = "en", *, case_id: str | None = None) -> dict[str, Any]:
    options = list_uc3_cases(lang)
    if not options:
        return {"ok": False, "error": "No COLREGS fixtures found."}
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
            # Crossing-ish geometry consistent with public Tokyo Bay narrative.
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

    verdict = classify_encounter(geometry)
    prediction = predict_fault_ratio(facts or ruling or title, geometry=geometry)
    fault_ratio = catalog_fault or prediction.fault_ratio

    rel = verdict.relative_bearing_a_to_b_deg
    # Plot target on unit circle: 0° ahead = top of scope.
    rad = math.radians(rel)
    tx = math.sin(rad)
    ty = math.cos(rad)

    return {
        "ok": True,
        "options": options,
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
