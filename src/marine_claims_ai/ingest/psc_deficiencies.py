"""
Paris / Tokyo MOU PSC deficiency vector parser and seaworthiness risk scoring.

Universal open-core: normalizes inspection deficiency records against the MOU
5-digit taxonomy and action-code severities, then aggregates a compound
Seaworthiness Defect Score. Jurisdiction warranty doctrine stays in adapters.

See ``docs/psc_deficiency_vector.md`` and Issue #31.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from marine_claims_ai.adapters.base import PSCDeficiency
from marine_claims_ai.ontology.psc import (
    REPEAT_MULTIPLIER,
    action_severity,
    category_base_weight,
    category_prefix,
    citation_for_code,
    convention_for_code,
    critical_system_id,
    is_detention_action,
    lookup_category,
    normalize_action_code,
    normalize_deficiency_code,
)
from marine_claims_ai.paths import REPO_ROOT

DEFAULT_PSC_FIXTURES_PATH = REPO_ROOT / "config" / "psc_inspection_fixtures.json"


class NormalizedDeficiency(BaseModel):
    """Single normalized PSC deficiency observation."""

    model_config = ConfigDict(extra="forbid")

    code: str
    action_code: str | None = None
    description: str = ""
    inspection_date: str | None = None
    mou_id: str | None = None
    prefix: str | None = None
    convention: str | None = None
    category_label: str | None = None
    citation: str | None = None
    severity_weight: float = 0.0
    category_weight: float = 0.0
    critical_system: str | None = None
    contribution: float = 0.0
    is_repeat_critical: bool = False


class SeaworthinessRiskReport(BaseModel):
    """Structured seaworthiness risk report for pre-casualty screening."""

    model_config = ConfigDict(extra="forbid")

    defect_score: float = 0.0
    detention_present: bool = False
    deficiencies: list[NormalizedDeficiency] = Field(default_factory=list)
    repeat_critical_flags: list[str] = Field(default_factory=list)
    convention_citations: list[str] = Field(default_factory=list)
    active_statutory_risks: list[str] = Field(default_factory=list)
    mou_id: str | None = None
    notes: str = ""


def _first_str(raw: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key not in raw:
            continue
        value = raw[key]
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _deficiency_rows(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Extract deficiency dicts from a Paris/Tokyo-style inspection record."""
    for key in ("deficiencies", "deficiency_list", "items", "findings"):
        rows = raw.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, Mapping)]
    # Single-deficiency record
    if any(k in raw for k in ("deficiency_code", "code", "def_code", "nature_of_deficiency")):
        return [raw]
    return []


def parse_deficiency_item(
    item: Mapping[str, Any],
    *,
    default_date: str | None = None,
    default_mou: str | None = None,
) -> NormalizedDeficiency | None:
    """Normalize one deficiency row; return None if no code can be recovered."""
    code = normalize_deficiency_code(
        _first_str(item, "deficiency_code", "code", "def_code", "defective_item_code")
    )
    if not code:
        return None
    action = normalize_action_code(
        _first_str(item, "action_taken", "action_code", "action", "action_taken_code")
    )
    description = (
        _first_str(item, "nature", "nature_of_deficiency", "description", "defective_item", "text")
        or ""
    )
    date = _first_str(item, "inspection_date", "date", "survey_date") or default_date
    mou = _first_str(item, "mou_id", "mou", "region") or default_mou
    cat = lookup_category(code)
    prefix = category_prefix(code)
    return NormalizedDeficiency(
        code=code,
        action_code=action,
        description=description,
        inspection_date=date,
        mou_id=mou,
        prefix=prefix,
        convention=convention_for_code(code),
        category_label=(cat or {}).get("label"),
        citation=citation_for_code(code),
        severity_weight=action_severity(action),
        category_weight=category_base_weight(code),
        critical_system=critical_system_id(code, description),
    )


def parse_inspection_record(raw: Mapping[str, Any]) -> list[NormalizedDeficiency]:
    """
    Parse a Paris/Tokyo MOU-style inspection record into normalized deficiencies.

    Accepted top-level keys include ``deficiencies`` / ``items`` lists, or a
    single deficiency-shaped dict. Field aliases cover common portal exports.
    """
    default_date = _first_str(raw, "inspection_date", "date", "survey_date")
    default_mou = _first_str(raw, "mou_id", "mou", "region")
    out: list[NormalizedDeficiency] = []
    for row in _deficiency_rows(raw):
        parsed = parse_deficiency_item(row, default_date=default_date, default_mou=default_mou)
        if parsed is not None:
            out.append(parsed)
    return out


def _prior_critical_systems(prior: Sequence[NormalizedDeficiency] | None) -> set[str]:
    if not prior:
        return set()
    return {d.critical_system for d in prior if d.critical_system}


def _cic_multiplier(prefix: str | None, cic_weights: Mapping[str, float] | None) -> float:
    if not cic_weights or not prefix:
        return 1.0
    if prefix in cic_weights:
        return float(cic_weights[prefix])
    if len(prefix) >= 2 and prefix[:2] in cic_weights:
        return float(cic_weights[prefix[:2]])
    return 1.0


def score_seaworthiness(
    deficiencies: Sequence[NormalizedDeficiency],
    *,
    prior: Sequence[NormalizedDeficiency] | None = None,
    mou_id: str | None = None,
    cic_weights: Mapping[str, float] | None = None,
) -> SeaworthinessRiskReport:
    """
    Aggregate a compound Seaworthiness Defect Score.

    ``contrib = category_base × action_severity × repeat_mult × cic_mult``
    with ``repeat_mult = 1.5`` when the same critical system appeared in ``prior``.
    """
    prior_systems = _prior_critical_systems(prior)
    scored: list[NormalizedDeficiency] = []
    total = 0.0
    repeat_flags: list[str] = []
    citations: list[str] = []
    risks: list[str] = []
    detention = False
    resolved_mou = mou_id

    for d in deficiencies:
        resolved_mou = resolved_mou or d.mou_id
        is_repeat = bool(d.critical_system and d.critical_system in prior_systems)
        repeat_mult = REPEAT_MULTIPLIER if is_repeat else 1.0
        cic_mult = _cic_multiplier(d.prefix, cic_weights)
        contrib = d.category_weight * d.severity_weight * repeat_mult * cic_mult
        total += contrib
        updated = d.model_copy(
            update={
                "contribution": round(contrib, 6),
                "is_repeat_critical": is_repeat,
                "mou_id": d.mou_id or mou_id,
            }
        )
        scored.append(updated)
        if is_detention_action(d.action_code):
            detention = True
        if is_repeat and d.critical_system and d.critical_system not in repeat_flags:
            repeat_flags.append(d.critical_system)
        if d.citation and d.citation not in citations:
            citations.append(d.citation)
        if d.convention:
            risk = f"{d.convention}: {d.code}"
            if d.action_code:
                risk += f" (action {d.action_code})"
            if risk not in risks:
                risks.append(risk)

    notes_parts: list[str] = []
    if detention:
        notes_parts.append("IMO/MOU detention action (Code 30) present.")
    if repeat_flags:
        notes_parts.append(
            "Repeat critical-system deficiencies: " + ", ".join(sorted(repeat_flags)) + "."
        )
    if cic_weights:
        notes_parts.append("Regional CIC weights applied.")

    return SeaworthinessRiskReport(
        defect_score=round(total, 6),
        detention_present=detention,
        deficiencies=scored,
        repeat_critical_flags=sorted(repeat_flags),
        convention_citations=citations,
        active_statutory_risks=risks,
        mou_id=resolved_mou,
        notes=" ".join(notes_parts),
    )


def to_adapter_deficiencies(
    deficiencies: Iterable[NormalizedDeficiency],
) -> list[PSCDeficiency]:
    """Convert normalized rows into adapter ``PSCDeficiency`` DTOs."""
    out: list[PSCDeficiency] = []
    for d in deficiencies:
        severity: str | None = None
        if is_detention_action(d.action_code):
            severity = "detention"
        elif d.critical_system:
            severity = "high"
        elif d.severity_weight >= 0.5:
            severity = "high"
        elif d.severity_weight >= 0.25:
            severity = "medium"
        out.append(
            PSCDeficiency(
                code=d.code,
                action_code=d.action_code,
                description=d.description,
                severity=severity,
            )
        )
    return out


def load_psc_fixtures(path: str | Path | None = None) -> dict[str, Any]:
    """Load anonymized inspection fixtures from ``config/psc_inspection_fixtures.json``."""
    fixture_path = Path(path) if path else DEFAULT_PSC_FIXTURES_PATH
    with open(fixture_path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid PSC fixtures (expected object): {fixture_path}")
    return raw


def score_fixture_case(
    case: Mapping[str, Any],
    *,
    cic_weights: Mapping[str, float] | None = None,
) -> SeaworthinessRiskReport:
    """Parse and score one fixture case, optionally applying prior inspection rows."""
    current = parse_inspection_record(case.get("inspection") or case)
    prior_raw = case.get("prior_inspection")
    prior = parse_inspection_record(prior_raw) if isinstance(prior_raw, Mapping) else None
    weights = cic_weights
    if weights is None and isinstance(case.get("cic_weights"), Mapping):
        weights = {str(k): float(v) for k, v in case["cic_weights"].items()}
    return score_seaworthiness(
        current,
        prior=prior,
        mou_id=_first_str(case, "mou_id") or None,
        cic_weights=weights,
    )
