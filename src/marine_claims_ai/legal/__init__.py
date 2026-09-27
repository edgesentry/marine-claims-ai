"""COLREGS / collision-prevention legal logic (universal open core)."""

from marine_claims_ai.legal.colregs_engine import (
    EncounterGeometry,
    EncounterSituation,
    EncounterVerdict,
    VesselRole,
    classify_encounter,
    course_difference_deg,
    is_crossing,
    is_head_on,
    is_overtaking,
    relative_bearing_deg,
)

__all__ = [
    "EncounterGeometry",
    "EncounterSituation",
    "EncounterVerdict",
    "VesselRole",
    "classify_encounter",
    "course_difference_deg",
    "is_crossing",
    "is_head_on",
    "is_overtaking",
    "relative_bearing_deg",
]
