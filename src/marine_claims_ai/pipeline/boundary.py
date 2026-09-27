"""Physical-boundary causality for concurrent-repair screening (Gate A / A2).

Thin public API over ``ontology.compartments`` plus the Critical False Accept
definition used by ``benchmarks.public_appraisal_eval``.
"""

from __future__ import annotations

from typing import Any, Sequence

from marine_claims_ai.benchmarks.public_appraisal_eval import (
    is_critical_false_accept,
    normalize_status_bucket,
)
from marine_claims_ai.ontology.compartments import (
    any_damage_allows_repair,
    infer_repair_zone,
    validate_claims_causality,
)

# Default critical machinery / shaft substrings (aligned with public_appraisal_eval.json).
DEFAULT_CRITICAL_SUBSTRINGS: tuple[str, ...] = (
    "カロリーファイヤー",
    "プロペラ軸",
    "減速機",
    "クラッチ",
    "汚物処理装置",
    "主機関",
    "ピストン",
)


def check_repair_boundary(
    damaged_components: Sequence[str],
    repair_description: str,
    *,
    category: str = "",
    max_hops: int = 1,
) -> dict[str, Any]:
    """
    Map a repair line to a compartment and validate casualty→repair causality.

    Returns a dict with ``repair_zone``, ``valid``, and ontology reason fields.
    When the description cannot be mapped to a zone, ``valid`` is True (no
    boundary evidence to reject) and ``repair_zone`` is None.
    """
    zones = list(damaged_components or [])
    repair_zone = infer_repair_zone(repair_description, category)
    if not repair_zone or not zones:
        return {
            "repair_zone": repair_zone,
            "valid": True,
            "reason": "unmapped_or_no_damage",
            "damage_node": None,
            "repair_node": repair_zone,
            "path": None,
        }
    causality = any_damage_allows_repair(zones, repair_zone, max_hops=max_hops)
    return {"repair_zone": repair_zone, **causality}


def is_bow_machinery_false_accept(
    *,
    damaged_components: Sequence[str],
    description: str,
    predicted_status: str,
    gold_status: str = "EXCLUDED",
    critical_substrings: Sequence[str] | None = None,
) -> bool:
    """
    True when a bow/hull casualty would critically false-accept machinery/shaft work.

    Uses the same Critical FA predicate as Gate A metric A2.
    """
    zones = list(damaged_components or [])
    crit = list(critical_substrings) if critical_substrings is not None else list(
        DEFAULT_CRITICAL_SUBSTRINGS
    )
    return is_critical_false_accept(
        gold_bucket=normalize_status_bucket(gold_status),
        pred_bucket=normalize_status_bucket(predicted_status),
        description=description,
        critical_substrings=crit,
        damaged_zones=zones,
    )


def count_critical_false_accepts(
    items: Sequence[dict[str, Any]],
    *,
    damaged_components: Sequence[str],
    critical_substrings: Sequence[str] | None = None,
) -> int:
    """Count Critical FA rows given items with ``status`` / ``gold_status`` / ``description``."""
    crit = list(critical_substrings) if critical_substrings is not None else list(
        DEFAULT_CRITICAL_SUBSTRINGS
    )
    zones = list(damaged_components or [])
    total = 0
    for row in items:
        if is_critical_false_accept(
            gold_bucket=normalize_status_bucket(row.get("gold_status")),
            pred_bucket=normalize_status_bucket(row.get("status")),
            description=str(row.get("description") or ""),
            critical_substrings=crit,
            damaged_zones=zones,
        ):
            total += 1
    return total


__all__ = [
    "DEFAULT_CRITICAL_SUBSTRINGS",
    "check_repair_boundary",
    "count_critical_false_accepts",
    "is_bow_machinery_false_accept",
    "is_critical_false_accept",
    "infer_repair_zone",
    "validate_claims_causality",
    "any_damage_allows_repair",
]
