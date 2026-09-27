"""Naval architecture ontology and compartment constraints."""

from marine_claims_ai.ontology.psc import (
    ACTION_CODE_SEVERITY,
    ACTION_DETENTION,
    ACTION_RECTIFY,
    ACTION_RECTIFY_BEFORE_DEPARTURE,
    ACTION_RECTIFY_WITHIN_14_DAYS,
    DEFICIENCY_CATEGORY_MAP,
    DETENTION_ACTION_CODES,
    action_severity,
    category_prefix,
    convention_for_code,
    is_detention_action,
    normalize_action_code,
    normalize_deficiency_code,
)

__all__ = [
    "ACTION_CODE_SEVERITY",
    "ACTION_DETENTION",
    "ACTION_RECTIFY",
    "ACTION_RECTIFY_BEFORE_DEPARTURE",
    "ACTION_RECTIFY_WITHIN_14_DAYS",
    "DEFICIENCY_CATEGORY_MAP",
    "DETENTION_ACTION_CODES",
    "action_severity",
    "category_prefix",
    "convention_for_code",
    "is_detention_action",
    "normalize_action_code",
    "normalize_deficiency_code",
]
