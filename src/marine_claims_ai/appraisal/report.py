"""Deterministic Preliminary Survey Report renderer (no LLM)."""

from __future__ import annotations

from datetime import date
from typing import Any


def render_preliminary_survey_report(
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    report_date: str | None = None,
) -> str:
    """Render a Lloyd's-style Preliminary Survey & Claims Adjustment Report in Markdown."""
    cp = summary.get("casualty_profile") or {}
    as_of = report_date or date.today().isoformat()
    claimed = int(summary.get("total_claimed_jpy") or 0)
    approved = int(summary.get("total_approved_jpy") or 0)
    excluded = int(summary.get("total_excluded_jpy") or 0)
    rate = summary.get("leakage_prevention_rate_pct")
    pricing = summary.get("pricing_note") or (
        "Line-item JPY amounts may be model estimates from public standard repair "
        "unit-price heuristics when the source specification PDF has no tender prices."
    )

    covered = [i for i in items if i.get("status") == "COVERED"]
    apportioned = [i for i in items if "APPORTIONED" in str(i.get("status") or "")]
    review = [i for i in items if "REVIEW" in str(i.get("status") or "")]
    excluded_items = [i for i in items if "EXCLUDED" in str(i.get("status") or "")]

    lines: list[str] = [
        "# Preliminary Survey & Claims Adjustment Report",
        "",
        f"**Date:** {as_of}  ",
        "**Prepared by:** MarineClaims AI (deterministic concurrent-repair screening)  ",
        "**Status:** Preliminary — subject to surveyor / adjuster confirmation",
        "",
        "## 1. Casualty Particulars",
        "",
        "| Field | Value |",
        "| :--- | :--- |",
        f"| Vessel | {cp.get('vessel_name', 'N/A')} |",
        f"| Incident type | {cp.get('incident_type', 'N/A')} |",
        f"| Date / place | {cp.get('incident_date', 'N/A')} / {cp.get('incident_location', 'N/A')} |",
        f"| Damaged zones | {', '.join(cp.get('damaged_components') or []) or 'N/A'} |",
        f"| Source | {cp.get('source_pdf', 'N/A')} |",
        "",
        "## 2. Financial Summary",
        "",
        "| Metric | JPY |",
        "| :--- | ---: |",
        f"| Total claimed (model) | {claimed:,} |",
        f"| Approved / apportioned | {approved:,} |",
        f"| Excluded (leakage prevention) | {excluded:,} |",
        f"| Exclusion rate | {rate}% |",
        "",
        f"> **Pricing basis:** {pricing}",
        "",
        "## 3. Covered Items (casualty restoration)",
        "",
    ]
    _append_item_table(lines, covered)
    lines.extend(["", "## 4. Apportioned Items (50% drydock dues)", ""])
    _append_item_table(lines, apportioned)
    if review:
        lines.extend(["", "## 5. Items for Surveyor Review", ""])
        _append_item_table(lines, review)
    lines.extend(["", "## 6. Excluded Items (concurrent / periodic repairs)", ""])
    _append_item_table(lines, excluded_items, include_reason=True)
    lines.extend(
        [
            "",
            "## 7. Methodology Notes",
            "",
            "- Causality is gated by the naval-architecture compartment graph "
            "(watertight barrier / adjacency limits).",
            "- Outer-hull surface work requires explicit outer-plate terms; bare "
            "「塗装」「洗浄」 keywords alone do not trigger cover.",
            "- Final indemnity remains with the appointed surveyor / claims adjuster.",
            "",
        ]
    )
    return "\n".join(lines)


def _append_item_table(
    lines: list[str],
    items: list[dict[str, Any]],
    *,
    include_reason: bool = False,
) -> None:
    if not items:
        lines.append("_None._")
        return
    if include_reason:
        lines.append("| ID | Status | Approved JPY | Description | Reason |")
        lines.append("| ---: | :--- | ---: | :--- | :--- |")
        for i in items:
            desc = _cell(i.get("description"))
            reason = _cell(i.get("reason"))
            lines.append(
                f"| {i.get('id')} | {i.get('status')} | {int(i.get('approved_amount') or 0):,} "
                f"| {desc} | {reason} |"
            )
    else:
        lines.append("| ID | Status | Approved JPY | Description |")
        lines.append("| ---: | :--- | ---: | :--- |")
        for i in items:
            desc = _cell(i.get("description"))
            lines.append(
                f"| {i.get('id')} | {i.get('status')} | {int(i.get('approved_amount') or 0):,} "
                f"| {desc} |"
            )


def _cell(value: Any, limit: int = 120) -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text
