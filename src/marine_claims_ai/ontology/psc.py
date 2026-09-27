"""
IMO Resolution A.1155(32) Port State Control action / deficiency helpers.

Universal open-core constants — jurisdiction adapters must not redefine these.
"""

from __future__ import annotations

from typing import Final

# Standardized PSC action codes (IMO / MOU practice).
ACTION_RECTIFY_BEFORE_DEPARTURE: Final[str] = "15"
ACTION_RECTIFY_WITHIN_14_DAYS: Final[str] = "16"
ACTION_RECTIFY: Final[str] = "17"
ACTION_DETENTION: Final[str] = "30"

DETENTION_ACTION_CODES: Final[frozenset[str]] = frozenset({ACTION_DETENTION})


def normalize_action_code(action_code: str | None) -> str | None:
    if action_code is None:
        return None
    text = str(action_code).strip()
    return text or None


def is_detention_action(action_code: str | None) -> bool:
    """Return True when ``action_code`` is an IMO detention action (Code 30)."""
    code = normalize_action_code(action_code)
    return code in DETENTION_ACTION_CODES if code is not None else False
