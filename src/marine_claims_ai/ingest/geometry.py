"""Minimal encounter geometry types for JMAT telemetry (ingest-only).

COLREGS classification lives in ``web/src/engines/colregs.ts``.
"""

from __future__ import annotations

from dataclasses import dataclass


def normalize_deg(angle: float) -> float:
    """Normalize degrees into ``[0, 360)``."""
    return float(angle) % 360.0


@dataclass(frozen=True)
class EncounterGeometry:
    """Two-vessel encounter telemetry (own ship = A, target = B)."""

    heading_a_deg: float
    heading_b_deg: float
    true_bearing_a_to_b_deg: float
    power_driven_a: bool = True
    power_driven_b: bool = True
    range_nm: float | None = None
    speed_a_kn: float | None = None
    speed_b_kn: float | None = None
