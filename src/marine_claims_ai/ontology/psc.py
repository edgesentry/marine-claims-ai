"""
IMO / MOU Port State Control deficiency taxonomy and action helpers.

Universal open-core constants — jurisdiction adapters must not redefine these.
Primary sources: Paris & Tokyo MOU Deficiency Codes (July 2026) and
PSCC59/2026/03 action-taken guidance; procedures in IMO A.1155(32).
See ``docs/psc_deficiency_vector.md``.
"""

from __future__ import annotations

import re
from typing import Any, Final, Mapping

# Standardized PSC action codes (IMO / MOU practice).
ACTION_RECTIFY_BEFORE_DEPARTURE: Final[str] = "15"
ACTION_RECTIFY_WITHIN_14_DAYS: Final[str] = "16"
ACTION_RECTIFY: Final[str] = "17"
ACTION_DETENTION: Final[str] = "30"

DETENTION_ACTION_CODES: Final[frozenset[str]] = frozenset({ACTION_DETENTION})

# Issue #31 / engineering weights (PSCC59 defines 15/16/17; 30 = detention marker).
ACTION_CODE_SEVERITY: Final[dict[str, float]] = {
    ACTION_DETENTION: 1.0,
    ACTION_RECTIFY: 0.5,
    ACTION_RECTIFY_BEFORE_DEPARTURE: 0.4,
    ACTION_RECTIFY_WITHIN_14_DAYS: 0.25,
}
DEFAULT_ACTION_SEVERITY: Final[float] = 0.1

# 3-digit deficiency prefixes → convention articles (Tokyo/Paris MOU July 2026).
# Note: ``071`` is Fire safety (SOLAS II-2), NOT Safety of Navigation (``101``).
DEFICIENCY_CATEGORY_MAP: Final[dict[str, dict[str, str]]] = {
    "011": {
        "label": "Certificate & Documentation - Ship Certificates",
        "convention": "SOLAS",
        "chapter": "Certificates",
    },
    "012": {
        "label": "Certificate & Documentation - Crew Certificates",
        "convention": "STCW",
        "chapter": "Crew certification",
    },
    "013": {
        "label": "Certificate & Documentation - Documents",
        "convention": "SOLAS",
        "chapter": "Documents",
    },
    "021": {
        "label": "Structural Conditions",
        "convention": "SOLAS",
        "chapter": "II-1",
    },
    "041": {
        "label": "Emergency Systems",
        "convention": "SOLAS",
        "chapter": "II-1/II-2",
    },
    "071": {
        "label": "Fire safety",
        "convention": "SOLAS",
        "chapter": "II-2",
    },
    "081": {
        "label": "Alarms",
        "convention": "SOLAS",
        "chapter": "II-1/II-2",
    },
    "101": {
        "label": "Safety of Navigation",
        "convention": "SOLAS",
        "chapter": "V",
    },
    "131": {
        "label": "Propulsion and auxiliary machinery",
        "convention": "SOLAS",
        "chapter": "II-1",
    },
    "141": {
        "label": "Pollution prevention - MARPOL Annex I",
        "convention": "MARPOL",
        "chapter": "Annex I",
    },
    "142": {
        "label": "Pollution prevention - MARPOL Annex II",
        "convention": "MARPOL",
        "chapter": "Annex II",
    },
    "143": {
        "label": "Pollution prevention - MARPOL Annex III",
        "convention": "MARPOL",
        "chapter": "Annex III",
    },
    "144": {
        "label": "Pollution prevention - MARPOL Annex IV",
        "convention": "MARPOL",
        "chapter": "Annex IV",
    },
    "145": {
        "label": "Pollution prevention - MARPOL Annex V",
        "convention": "MARPOL",
        "chapter": "Annex V",
    },
    "146": {
        "label": "Pollution prevention - MARPOL Annex VI",
        "convention": "MARPOL",
        "chapter": "Annex VI",
    },
    "147": {
        "label": "Pollution prevention - Anti Fouling",
        "convention": "MARPOL",
        "chapter": "AFS",
    },
    "148": {
        "label": "Pollution prevention - Ballast Water",
        "convention": "MARPOL",
        "chapter": "BWM",
    },
    "151": {
        "label": "ISM",
        "convention": "ISM",
        "chapter": "SOLAS IX",
    },
}

# Major 2-digit category fallbacks when only the chapter group is known.
DEFICIENCY_MAJOR_CATEGORY_MAP: Final[dict[str, dict[str, str]]] = {
    "01": {
        "label": "Certificate & Documentation",
        "convention": "SOLAS",
        "chapter": "Certificates",
    },
    "04": {
        "label": "Emergency Systems",
        "convention": "SOLAS",
        "chapter": "II-1/II-2",
    },
    "07": {
        "label": "Fire safety",
        "convention": "SOLAS",
        "chapter": "II-2",
    },
    "10": {
        "label": "Safety of Navigation",
        "convention": "SOLAS",
        "chapter": "V",
    },
    "13": {
        "label": "Propulsion and auxiliary machinery",
        "convention": "SOLAS",
        "chapter": "II-1",
    },
    "14": {
        "label": "Pollution prevention",
        "convention": "MARPOL",
        "chapter": "Annexes",
    },
    "15": {
        "label": "ISM",
        "convention": "ISM",
        "chapter": "SOLAS IX",
    },
}

CATEGORY_BASE_WEIGHT: Final[dict[str, float]] = {
    "041": 1.0,
    "071": 1.0,
    "101": 1.0,
    "131": 1.0,
    "151": 1.0,
    "021": 0.85,
    "081": 0.7,
    "011": 0.6,
    "012": 0.6,
    "013": 0.6,
    "141": 0.85,
    "142": 0.85,
    "143": 0.85,
    "144": 0.85,
    "145": 0.85,
    "146": 0.85,
    "147": 0.7,
    "148": 0.85,
}
DEFAULT_CATEGORY_BASE_WEIGHT: Final[float] = 0.4

# Codes / keywords treated as safety-critical for repeat-deficiency flags.
CRITICAL_SYSTEM_CODES: Final[frozenset[str]] = frozenset(
    {
        "02105",  # Steering gear
        "04102",  # Emergency fire pump and its pipes
        "04106",  # Emergency steering position
        "08104",  # Steering gear alarm
    }
)
CRITICAL_SYSTEM_PREFIXES: Final[frozenset[str]] = frozenset({"151"})
CRITICAL_SYSTEM_KEYWORDS: Final[tuple[tuple[str, str], ...]] = (
    ("steering", "steering_gear"),
    ("emergency fire pump", "emergency_fire_pump"),
    ("ism", "ism"),
)

REPEAT_MULTIPLIER: Final[float] = 1.5
DEFAULT_LOOKBACK_MONTHS: Final[int] = 24

# Prefer full MOU 4–5 digit codes over leading item indexes ("Item 12: 04102").
_CODE_LONG = re.compile(r"(?<!\d)(\d{4,5})(?!\d)")
_CODE_SHORT = re.compile(r"(?<!\d)(\d{2,3})(?!\d)")
_ISM_WORD = re.compile(r"\bism\b", re.IGNORECASE)


def normalize_action_code(action_code: str | None) -> str | None:
    if action_code is None:
        return None
    text = str(action_code).strip()
    if not text:
        return None
    # Accept "Code 30", "30", "action_30"
    match = re.search(r"(\d{1,3})", text)
    return match.group(1) if match else text


def is_detention_action(action_code: str | None) -> bool:
    """Return True when ``action_code`` is an IMO detention action (Code 30)."""
    code = normalize_action_code(action_code)
    return code in DETENTION_ACTION_CODES if code is not None else False


def action_severity(action_code: str | None) -> float:
    """Return the Universal Core severity weight for an action code."""
    code = normalize_action_code(action_code)
    if code is None:
        return DEFAULT_ACTION_SEVERITY
    return ACTION_CODE_SEVERITY.get(code, DEFAULT_ACTION_SEVERITY)


def normalize_deficiency_code(code: str | None) -> str | None:
    """Normalize a deficiency code to digits only (typically 5-digit MOU code)."""
    if code is None:
        return None
    text = str(code).strip()
    if not text:
        return None
    # Prefer 4–5 digit MOU codes over leading item indexes ("Item 12: 04102").
    long_match = _CODE_LONG.search(text)
    if long_match:
        return long_match.group(1)
    # Dotted / hyphenated forms: "07.106", "071-06" → "07106".
    compact = text.replace(" ", "").replace("-", "").replace(".", "")
    long_match = _CODE_LONG.search(compact)
    if long_match:
        return long_match.group(1)
    short_match = _CODE_SHORT.search(text) or _CODE_SHORT.search(compact)
    if short_match:
        return short_match.group(1)
    digits = "".join(ch for ch in compact if ch.isdigit())
    return digits or None


def category_prefix(code: str | None) -> str | None:
    """Return the 3-digit (preferred) or 2-digit major category prefix."""
    digits = normalize_deficiency_code(code)
    if not digits:
        return None
    if len(digits) >= 3:
        return digits[:3]
    if len(digits) >= 2:
        return digits[:2]
    return digits


def lookup_category(code: str | None) -> dict[str, str] | None:
    """Look up MOU category metadata for a deficiency code."""
    digits = normalize_deficiency_code(code)
    if not digits:
        return None
    if len(digits) >= 3:
        entry = DEFICIENCY_CATEGORY_MAP.get(digits[:3])
        if entry is not None:
            return dict(entry)
    if len(digits) >= 2:
        entry = DEFICIENCY_MAJOR_CATEGORY_MAP.get(digits[:2])
        if entry is not None:
            return dict(entry)
    return None


def convention_for_code(code: str | None) -> str | None:
    """Return the convention family string for a deficiency code, if mapped."""
    entry = lookup_category(code)
    if entry is None:
        return None
    chapter = entry.get("chapter") or ""
    convention = entry.get("convention") or ""
    if chapter and convention:
        return f"{convention} {chapter}".strip()
    return convention or None


def category_base_weight(code: str | None) -> float:
    prefix = category_prefix(code)
    if prefix is None:
        return DEFAULT_CATEGORY_BASE_WEIGHT
    if prefix in CATEGORY_BASE_WEIGHT:
        return CATEGORY_BASE_WEIGHT[prefix]
    if len(prefix) >= 2 and prefix[:2] in {"04", "07", "10", "13", "15"}:
        return 1.0
    return DEFAULT_CATEGORY_BASE_WEIGHT


def critical_system_id(code: str | None, description: str = "") -> str | None:
    """
    Return a stable critical-system id when the deficiency touches a watched system.

    Ids: ``steering_gear``, ``emergency_fire_pump``, ``ism``, or ``None``.
    """
    digits = normalize_deficiency_code(code)
    desc = (description or "").lower()
    if digits in CRITICAL_SYSTEM_CODES:
        if digits == "04102":
            return "emergency_fire_pump"
        return "steering_gear"
    prefix = category_prefix(digits)
    if prefix in CRITICAL_SYSTEM_PREFIXES:
        return "ism"
    for needle, system_id in CRITICAL_SYSTEM_KEYWORDS:
        # "ism" must be a whole word — otherwise "mechanism" / "transmission" false-hit.
        if needle == "ism":
            if _ISM_WORD.search(desc):
                return system_id
        elif needle in desc:
            return system_id
    return None


def citation_for_code(code: str | None) -> str | None:
    """Human-readable convention citation for reports."""
    entry = lookup_category(code)
    if entry is None:
        return None
    label = entry.get("label", "")
    convention = convention_for_code(code) or ""
    prefix = category_prefix(code) or ""
    parts = [p for p in (prefix and f"{prefix}xx", label, convention) if p]
    return " — ".join(parts) if parts else None


def as_public_maps() -> Mapping[str, Any]:
    """Expose maps for tests / diagnostics without allowing mutation."""
    return {
        "DEFICIENCY_CATEGORY_MAP": DEFICIENCY_CATEGORY_MAP,
        "ACTION_CODE_SEVERITY": ACTION_CODE_SEVERITY,
        "CRITICAL_SYSTEM_CODES": CRITICAL_SYSTEM_CODES,
    }
