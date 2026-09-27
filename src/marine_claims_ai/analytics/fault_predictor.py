"""
End-to-end collision fault-ratio prediction (Issue #44).

Maps a factual narrative (and optional COLREGS geometry) to an audit-defensible
contributory-negligence split such as ``70:30``, by combining:

1. Judicial baseline splits keyed by encounter situation
2. Narrative modifier factors (過失修正要素)
3. Offline precedent kNN over ``config/civil_precedent_catalog.json``

Numerical percentages are jurisdiction-practice heuristics, not COLREGS statute.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from marine_claims_ai.adapters.base import EncounterType, PrecedentMatch
from marine_claims_ai.adapters.japan_reference import JapanJurisdictionAdapter
from marine_claims_ai.legal.colregs_engine import (
    EncounterGeometry,
    EncounterSituation,
    EncounterVerdict,
    VesselRole,
    classify_encounter,
)
from marine_claims_ai.paths import DEFAULT_CIVIL_CATALOG_PATH, REPO_ROOT

DEFAULT_FAULT_RATIO_RULES_PATH = REPO_ROOT / "config" / "fault_ratio_rules.json"

_TOKEN_RE = re.compile(r"[\w\u3040-\u30ff\u3400-\u9fff]+", re.UNICODE)

_SITUATION_TO_ENCOUNTER_TYPE: dict[str, EncounterType] = {
    EncounterSituation.CROSSING.value: EncounterType.CROSSING,
    EncounterSituation.HEAD_ON.value: EncounterType.HEAD_ON,
    EncounterSituation.OVERTAKING.value: EncounterType.OVERTAKING,
    EncounterSituation.SAFE_PASSING.value: EncounterType.UNKNOWN,
}


class ModifierHit(BaseModel):
    """One contributory-negligence modifier detected in the narrative."""

    model_config = ConfigDict(extra="forbid")

    modifier_id: str
    delta_primary_pp: int
    citation: str
    matched_pattern: str


class FaultPrediction(BaseModel):
    """Audit-defensible fault-ratio prediction with itemized citations."""

    model_config = ConfigDict(extra="forbid")

    fault_ratio: str
    primary_pct: int
    secondary_pct: int
    baseline_ratio: str
    situation: str
    role_a: str | None = None
    role_b: str | None = None
    rule_adjusted_ratio: str
    knn_ratio: str | None = None
    modifiers: list[ModifierHit] = Field(default_factory=list)
    precedent_matches: list[PrecedentMatch] = Field(default_factory=list)
    rule_citations: list[str] = Field(default_factory=list)
    rationale: str = ""


def parse_fault_ratio(ratio: str) -> tuple[int, int]:
    """Parse ``A:B`` into integer percentages that sum to 100."""
    text = (ratio or "").strip().replace("：", ":").replace("対", ":")
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid fault ratio {ratio!r}; expected 'A:B'")
    a, b = int(parts[0].strip()), int(parts[1].strip())
    if a < 0 or b < 0 or a + b != 100:
        raise ValueError(f"Fault ratio sides must be non-negative and sum to 100: {ratio!r}")
    return a, b


def format_fault_ratio(primary_pct: int, secondary_pct: int | None = None) -> str:
    """Format primary/secondary percentages as ``A:B``."""
    secondary = 100 - primary_pct if secondary_pct is None else secondary_pct
    return f"{int(primary_pct)}:{int(secondary)}"


def load_fault_ratio_rules(path: str | Path | None = None) -> dict[str, Any]:
    rules_path = Path(path) if path else DEFAULT_FAULT_RATIO_RULES_PATH
    with open(rules_path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid fault_ratio_rules (expected object): {rules_path}")
    return raw


@lru_cache(maxsize=4)
def _cached_rules(path_str: str) -> dict[str, Any]:
    return load_fault_ratio_rules(path_str)


def _rules(path: str | Path | None = None) -> dict[str, Any]:
    return _cached_rules(str(Path(path) if path else DEFAULT_FAULT_RATIO_RULES_PATH))


def _coerce_geometry(geometry: EncounterGeometry | dict | None) -> EncounterGeometry | None:
    if geometry is None:
        return None
    if isinstance(geometry, EncounterGeometry):
        return geometry
    if isinstance(geometry, dict):
        return EncounterGeometry.model_validate(geometry)
    raise TypeError(f"geometry must be EncounterGeometry, dict, or None; got {type(geometry)!r}")


def infer_situation_from_text(
    narrative: str,
    *,
    situation_tokens: dict[str, list[str]] | None = None,
) -> EncounterSituation:
    """Heuristic COLREGS situation from Japanese / English narrative markers."""
    text = (narrative or "").lower()
    tokens = situation_tokens
    if tokens is None:
        from marine_claims_ai.adapters.jurisdiction_config import load_jurisdiction_config

        tokens = load_jurisdiction_config("JP").situation_tokens

    # Priority mirrors COLREGS engine: overtaking > head-on > crossing.
    for key, situation in (
        ("overtaking", EncounterSituation.OVERTAKING),
        ("head_on", EncounterSituation.HEAD_ON),
        ("crossing", EncounterSituation.CROSSING),
    ):
        for marker in tokens.get(key, []) or []:
            if marker and marker.lower() in text:
                return situation
    return EncounterSituation.SAFE_PASSING  # treated as unknown baseline key via mapping


def resolve_situation(
    narrative: str,
    geometry: EncounterGeometry | dict | None = None,
) -> tuple[EncounterSituation, EncounterVerdict | None, VesselRole | None, VesselRole | None]:
    """Return situation (+ optional COLREGS verdict / roles)."""
    geom = _coerce_geometry(geometry)
    if geom is not None:
        verdict = classify_encounter(geom)
        return verdict.situation, verdict, verdict.role_a, verdict.role_b
    situation = infer_situation_from_text(narrative)
    # SAFE_PASSING from text inference means "unknown" for baseline purposes.
    if situation == EncounterSituation.SAFE_PASSING:
        return EncounterSituation.SAFE_PASSING, None, None, None
    return situation, None, None, None


def baseline_ratio_for(
    situation: EncounterSituation | str,
    rules: dict[str, Any] | None = None,
    *,
    treat_safe_passing_as_unknown: bool = False,
) -> str:
    cfg = rules or _rules()
    baselines: dict[str, str] = dict(cfg.get("baselines") or {})
    key = situation.value if isinstance(situation, EncounterSituation) else str(situation)
    if treat_safe_passing_as_unknown and key == EncounterSituation.SAFE_PASSING.value:
        key = "unknown"
    return str(baselines.get(key) or baselines.get("unknown") or "75:25")


# When fog / mutual fault is present, bilateral lookout/radar/signal/speed
# failures should not stack as additional primary-side increases.
_BILATERAL_POSITIVE_IDS = frozenset({"lookout", "radar", "sound_signals", "speed"})


def extract_modifiers(
    narrative: str,
    *,
    rules: dict[str, Any] | None = None,
) -> list[ModifierHit]:
    """Detect 過失修正要素 patterns and return itemized citation hits."""
    cfg = rules or _rules()
    text = narrative or ""
    text_lower = text.lower()
    hits: list[ModifierHit] = []
    for mod in cfg.get("modifiers") or []:
        patterns = list(mod.get("patterns") or [])
        matched: str | None = None
        for pat in patterns:
            if not pat:
                continue
            if pat.lower() in text_lower or pat in text:
                matched = pat
                break
        if matched is None:
            continue
        hits.append(
            ModifierHit(
                modifier_id=str(mod.get("id") or matched),
                delta_primary_pp=int(mod.get("delta_primary_pp") or 0),
                citation=str(mod.get("citation") or ""),
                matched_pattern=matched,
            )
        )
    hit_ids = {h.modifier_id for h in hits}
    if hit_ids & {"fog", "mutual_fault"}:
        adjusted: list[ModifierHit] = []
        for hit in hits:
            if hit.modifier_id in _BILATERAL_POSITIVE_IDS and hit.delta_primary_pp > 0:
                # Keep the citation for audit, but do not inflate primary share.
                adjusted.append(hit.model_copy(update={"delta_primary_pp": 0}))
            else:
                adjusted.append(hit)
        return adjusted
    return hits


def apply_modifier_deltas(
    baseline_primary: int,
    modifiers: list[ModifierHit],
    *,
    clamp_min: int = 50,
    clamp_max: int = 95,
) -> int:
    primary = baseline_primary
    for hit in modifiers:
        primary += hit.delta_primary_pp
    return max(clamp_min, min(clamp_max, primary))


def round_primary_pp(primary: float, step: int = 5) -> int:
    if step <= 0:
        return int(round(primary))
    return int(round(primary / step) * step)


def _score_seed_like_adapter(
    seed: dict[str, Any],
    *,
    facts: str,
    situation_type: EncounterType,
    situation_tokens: dict[str, list[str]],
) -> float:
    """Mirror JapanJurisdictionAdapter._score_seed for leave-one-out filtering."""
    blob = " ".join(
        str(seed.get(k) or "") for k in ("title", "input_facts", "holding", "court")
    ).lower()
    score = 0.0
    tokens = [t.lower() for t in _TOKEN_RE.findall(facts or "") if len(t) >= 2]
    if tokens:
        hits = sum(1 for tok in tokens if tok in blob)
        score += hits / max(len(tokens), 1)
    markers = situation_tokens.get(situation_type.value, []) or []
    for marker in markers:
        if marker and marker.lower() in blob:
            score += 0.5
            break
    if seed.get("fault_ratio"):
        score += 0.05
    return score


def knn_fault_ratios(
    narrative: str,
    situation: EncounterSituation,
    *,
    catalog_path: Path | None = None,
    exclude_case_id: int | str | None = None,
    top_k: int = 3,
    situation_tokens: dict[str, list[str]] | None = None,
) -> tuple[str | None, list[PrecedentMatch], float]:
    """
    Weighted-average fault ratio from top-k catalog neighbors.

    Returns ``(ratio_or_none, matches, best_score)``.
    """
    from marine_claims_ai.adapters.jurisdiction_config import load_jurisdiction_config
    from marine_claims_ai.ingest.civil import load_catalog

    tokens = situation_tokens
    if tokens is None:
        tokens = load_jurisdiction_config("JP").situation_tokens

    encounter_type = _SITUATION_TO_ENCOUNTER_TYPE.get(situation.value, EncounterType.UNKNOWN)
    seeds = load_catalog(catalog_path or DEFAULT_CIVIL_CATALOG_PATH)
    scored: list[tuple[float, dict[str, Any]]] = []
    exclude = None if exclude_case_id is None else str(exclude_case_id)
    for seed in seeds:
        if exclude is not None and str(seed.get("case_id") or "") == exclude:
            continue
        score = _score_seed_like_adapter(
            seed,
            facts=narrative,
            situation_type=encounter_type,
            situation_tokens=tokens,
        )
        scored.append((score, seed))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("case_id") or "")))
    top = scored[: max(1, top_k)]

    matches: list[PrecedentMatch] = []
    weighted_sum = 0.0
    weight_total = 0.0
    best_score = top[0][0] if top else 0.0
    for score, seed in top:
        match = JapanJurisdictionAdapter._to_match(seed, domain="catalog", score=score)
        matches.append(match)
        if not seed.get("fault_ratio"):
            continue
        try:
            a, _ = parse_fault_ratio(str(seed["fault_ratio"]))
        except ValueError:
            continue
        w = max(score, 1e-6)
        weighted_sum += a * w
        weight_total += w

    if weight_total <= 0:
        return None, matches, best_score
    avg = weighted_sum / weight_total
    return format_fault_ratio(int(round(avg))), matches, best_score


def _blend_primaries(
    rule_primary: int,
    knn_primary: int | None,
    *,
    rule_weight: float,
    knn_weight: float,
    min_knn_score: float,
    knn_score: float,
    round_step: int,
    clamp_min: int,
    clamp_max: int,
) -> int:
    if knn_primary is None or knn_score < min_knn_score:
        blended = float(rule_primary)
    else:
        blended = rule_weight * rule_primary + knn_weight * knn_primary
    rounded = round_primary_pp(blended, round_step)
    return max(clamp_min, min(clamp_max, rounded))


def predict_fault_ratio(
    narrative: str,
    geometry: EncounterGeometry | dict | None = None,
    *,
    catalog_path: str | Path | None = None,
    rules_path: str | Path | None = None,
    exclude_case_id: int | str | None = None,
    top_k: int | None = None,
) -> FaultPrediction:
    """
    Predict an audit-defensible contributory negligence ratio from a collision narrative.

    Parameters
    ----------
    narrative:
        Factual description of the collision (Japanese or English).
    geometry:
        Optional COLREGS ``EncounterGeometry`` (or dict) for deterministic situation / roles.
    catalog_path:
        Override path to ``civil_precedent_catalog.json``.
    exclude_case_id:
        When evaluating leave-one-out, exclude this catalog ``case_id`` from kNN.
    """
    rules = _rules(rules_path)
    blend = dict(rules.get("blend") or {})
    clamp_min = int(blend.get("clamp_primary_min", 50))
    clamp_max = int(blend.get("clamp_primary_max", 95))
    round_step = int(blend.get("round_to_pp", 5))
    k = int(top_k if top_k is not None else blend.get("top_k", 3))

    situation, verdict, role_a, role_b = resolve_situation(narrative, geometry)
    from_geometry = verdict is not None
    baseline = baseline_ratio_for(
        situation,
        rules,
        treat_safe_passing_as_unknown=not from_geometry,
    )

    baseline_primary, _ = parse_fault_ratio(baseline)
    modifiers = extract_modifiers(narrative, rules=rules)
    rule_primary = apply_modifier_deltas(
        baseline_primary,
        modifiers,
        clamp_min=clamp_min,
        clamp_max=clamp_max,
    )
    rule_adjusted = format_fault_ratio(rule_primary)

    knn_ratio_str, matches, knn_score = knn_fault_ratios(
        narrative,
        situation,
        catalog_path=Path(catalog_path) if catalog_path else None,
        exclude_case_id=exclude_case_id,
        top_k=k,
    )
    knn_primary: int | None = None
    if knn_ratio_str is not None:
        knn_primary, _ = parse_fault_ratio(knn_ratio_str)

    final_primary = _blend_primaries(
        rule_primary,
        knn_primary,
        rule_weight=float(blend.get("rule_weight", 0.45)),
        knn_weight=float(blend.get("knn_weight", 0.55)),
        min_knn_score=float(blend.get("min_knn_score", 0.15)),
        knn_score=knn_score,
        round_step=round_step,
        clamp_min=clamp_min,
        clamp_max=clamp_max,
    )
    fault_ratio = format_fault_ratio(final_primary)

    mod_bits = [f"{m.modifier_id}({m.delta_primary_pp:+d}pp)" for m in modifiers] or ["none"]
    knn_bit = (
        f"kNN={knn_ratio_str} (score={knn_score:.3f}, n={len(matches)})"
        if knn_ratio_str is not None
        else "kNN=unavailable"
    )
    rationale = (
        f"Situation={situation.value} baseline={baseline} → rule-adjusted={rule_adjusted} "
        f"via modifiers[{', '.join(mod_bits)}]; {knn_bit}; blended={fault_ratio}."
    )
    rule_citations = list(verdict.rule_citations) if verdict is not None else []
    for m in modifiers:
        if m.citation and m.citation not in rule_citations:
            rule_citations.append(m.citation)

    return FaultPrediction(
        fault_ratio=fault_ratio,
        primary_pct=final_primary,
        secondary_pct=100 - final_primary,
        baseline_ratio=baseline,
        situation=situation.value,
        role_a=role_a.value if isinstance(role_a, VesselRole) else (str(role_a) if role_a else None),
        role_b=role_b.value if isinstance(role_b, VesselRole) else (str(role_b) if role_b else None),
        rule_adjusted_ratio=rule_adjusted,
        knn_ratio=knn_ratio_str,
        modifiers=modifiers,
        precedent_matches=matches,
        rule_citations=rule_citations,
        rationale=rationale,
    )
