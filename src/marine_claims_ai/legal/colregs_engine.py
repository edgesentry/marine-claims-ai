"""
COLREGS 1972 Part B Section II — encounter geometry predicate engine (Rules 13–15).

Encodes invariant relative-bearing / course-difference thresholds from the
International Regulations for Preventing Collisions at Sea, identically mirrored
in Japan's Act on Preventing Collisions at Sea (海上衝突予防法) Arts. 13–15.

Jurisdiction-local fault-split catalogs stay in Modular Jurisdiction Adapters;
this module returns only convention-grounded situation labels and vessel roles.

See ``docs/colregs_encounter_engine.md``.
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# Rule 13 / Art. 13(2): more than 22.5° (二十二度三十分) abaft the beam
# → relative bearing of approacher from overtaken in (112.5°, 247.5°).
# Confirmed against USCG NavRules Handbook + e-Gov 海上衝突予防法 (see docs/).
OVERTAKING_ABAFT_BEAM_DEG: float = 22.5
OVERTAKING_RELATIVE_BEARING_MIN_DEG: float = 90.0 + OVERTAKING_ABAFT_BEAM_DEG  # 112.5
OVERTAKING_RELATIVE_BEARING_MAX_DEG: float = 360.0 - OVERTAKING_RELATIVE_BEARING_MIN_DEG  # 247.5

# Rule 14 / Art. 14: statute says "nearly reciprocal" / 「ほとんど真向かい」 and
# "nearly ahead" / 「ほとんど船首方向」 — no numeric band. ±5° is an explicit
# engineering encoding (Issue #30), not a value copied from the primary text.
HEAD_ON_COURSE_TOLERANCE_DEG: float = 5.0
HEAD_ON_BEARING_TOLERANCE_DEG: float = 5.0

RULE_13: str = "COLREGS Rule 13 / 海上衝突予防法 第13条"
RULE_14: str = "COLREGS Rule 14 / 海上衝突予防法 第14条"
RULE_15: str = "COLREGS Rule 15 / 海上衝突予防法 第15条"
RULE_16: str = "COLREGS Rule 16 / 海上衝突予防法 第16条"
RULE_17: str = "COLREGS Rule 17 / 海上衝突予防法 第17条"


class EncounterSituation(StrEnum):
    """COLREGS encounter geometry class (Rules 13–15)."""

    HEAD_ON = "head_on"
    OVERTAKING = "overtaking"
    CROSSING = "crossing"
    SAFE_PASSING = "safe_passing"


class VesselRole(StrEnum):
    """Operational obligation under Rules 14–17."""

    GIVE_WAY = "give_way"
    STAND_ON = "stand_on"


class EncounterGeometry(BaseModel):
    """Input telemetry for a two-vessel encounter (own ship = A, target = B)."""

    model_config = ConfigDict(extra="forbid")

    heading_a_deg: float = Field(..., description="True heading of vessel A (degrees)")
    heading_b_deg: float = Field(..., description="True heading of vessel B (degrees)")
    true_bearing_a_to_b_deg: float = Field(
        ...,
        description="True bearing from A to B (degrees)",
    )
    power_driven_a: bool = True
    power_driven_b: bool = True
    range_nm: float | None = Field(default=None, ge=0.0)
    speed_a_kn: float | None = Field(default=None, ge=0.0)
    speed_b_kn: float | None = Field(default=None, ge=0.0)


class EncounterVerdict(BaseModel):
    """Deterministic COLREGS classification for one encounter."""

    model_config = ConfigDict(extra="forbid")

    situation: EncounterSituation
    role_a: VesselRole | None
    role_b: VesselRole | None
    relative_bearing_a_to_b_deg: float
    relative_bearing_b_to_a_deg: float
    course_difference_deg: float
    bearing_starboard_a: bool
    mutual_starboard_alteration: bool = False
    rule_citations: list[str] = Field(default_factory=list)
    cpa_nm: float | None = None
    tcpa_min: float | None = None


def normalize_deg(angle: float) -> float:
    """Normalize an angle in degrees to the half-open interval [0, 360)."""
    return float(angle) % 360.0


def angular_distance_deg(a: float, b: float) -> float:
    """Smallest absolute angular separation in degrees, in [0, 180]."""
    return min(normalize_deg(a - b), normalize_deg(b - a))


def relative_bearing_deg(true_bearing: float, heading: float) -> float:
    """
    Relative bearing of a contact from an observer.

    θ_rel = (TrueBearing − Heading) mod 360
    Convention: 0° ahead, 90° starboard beam, 180° astern, 270° port beam.
    """
    return normalize_deg(true_bearing - heading)


def course_difference_deg(heading_a: float, heading_b: float) -> float:
    """
    Course difference Δψ = |Heading_A − Heading_B| mod 360, result in [0, 360).
    """
    return normalize_deg(abs(normalize_deg(heading_a) - normalize_deg(heading_b)))


def reciprocal_bearing_deg(true_bearing: float) -> float:
    """Bearing of the reverse line of sight (A→B ⇒ B→A)."""
    return normalize_deg(true_bearing + 180.0)


def is_overtaking(aspect_angle: float) -> bool:
    """
    Rule 13: vessel is coming up from more than 22.5° abaft the other's beam.

    ``aspect_angle`` is the relative bearing of the approaching vessel as seen
    from the vessel being approached (overtaken). Overtaking sector:
    (112.5°, 247.5°).
    """
    theta = normalize_deg(aspect_angle)
    return OVERTAKING_RELATIVE_BEARING_MIN_DEG < theta < OVERTAKING_RELATIVE_BEARING_MAX_DEG


def is_head_on(course_diff: float, relative_bearing: float) -> bool:
    """
    Rule 14: nearly reciprocal courses and contact nearly ahead.

    ``course_diff`` is Δψ in [0, 360); reciprocal band is 180° ± 5°.
    ``relative_bearing`` is θ_rel of the other vessel from own ship.
    """
    dpsi = normalize_deg(course_diff)
    nearly_reciprocal = abs(dpsi - 180.0) <= HEAD_ON_COURSE_TOLERANCE_DEG
    nearly_ahead = angular_distance_deg(relative_bearing, 0.0) <= HEAD_ON_BEARING_TOLERANCE_DEG
    return nearly_reciprocal and nearly_ahead


def is_crossing(course_diff: float, relative_bearing: float) -> bool:
    """
    Rule 15 geometric predicate (power-driven crossing with risk of collision).

    True when courses are neither nearly parallel nor head-on-reciprocal, the
    contact is not in the overtaking (astern) sector from own ship, and the
    contact is forward of 22.5° abaft either beam (crossing arc).
    """
    dpsi = normalize_deg(course_diff)
    theta = normalize_deg(relative_bearing)
    if abs(dpsi - 180.0) <= HEAD_ON_COURSE_TOLERANCE_DEG:
        return False
    if angular_distance_deg(dpsi, 0.0) <= HEAD_ON_COURSE_TOLERANCE_DEG:
        return False
    if is_overtaking(theta):
        return False
    # Forward of 22.5° abaft beam on either side: [0, 112.5] ∪ [247.5, 360).
    return theta <= OVERTAKING_RELATIVE_BEARING_MIN_DEG or theta >= OVERTAKING_RELATIVE_BEARING_MAX_DEG


def bearing_starboard(relative_bearing: float) -> bool:
    """True when the contact lies on own starboard side (0° < θ_rel < 180°)."""
    theta = normalize_deg(relative_bearing)
    return 0.0 < theta < 180.0


def _velocity_components(speed_kn: float, heading_deg: float) -> tuple[float, float]:
    """East / North speed components (kn) for a true heading."""
    rad = math.radians(normalize_deg(heading_deg))
    # Heading 0° = North: north = cos, east = sin
    east = speed_kn * math.sin(rad)
    north = speed_kn * math.cos(rad)
    return east, north


def cpa_tcpa_nm_min(
    range_nm: float,
    relative_bearing_a_to_b_deg: float,
    heading_a_deg: float,
    heading_b_deg: float,
    speed_a_kn: float,
    speed_b_kn: float,
) -> tuple[float | None, float | None]:
    """
    Closest Point of Approach (nmi) and TCPA (minutes) from relative kinematics.

    Returns ``(None, None)`` when relative speed is zero (parallel equal SOG).
    Negative TCPA means the CPA is in the past (diverging).
    """
    if range_nm < 0.0:
        raise ValueError("range_nm must be non-negative")
    theta = normalize_deg(relative_bearing_a_to_b_deg)
    # Position of B relative to A in East/North (nmi), using relative bearing from A's heading.
    # Convert relative bearing to true bearing of the line of sight from A:
    # we already pass relative bearing; absolute LoS in own-ship frame:
    # x_east = range * sin(rel), y_north = range * cos(rel) in ship's body frame
    # rotated by heading_a into North-East:
    body_e = range_nm * math.sin(math.radians(theta))
    body_n = range_nm * math.cos(math.radians(theta))
    hdg = math.radians(normalize_deg(heading_a_deg))
    pos_e = body_e * math.cos(hdg) + body_n * math.sin(hdg)
    pos_n = -body_e * math.sin(hdg) + body_n * math.cos(hdg)

    va_e, va_n = _velocity_components(speed_a_kn, heading_a_deg)
    vb_e, vb_n = _velocity_components(speed_b_kn, heading_b_deg)
    rel_e = vb_e - va_e
    rel_n = vb_n - va_n
    rel_speed_sq = rel_e * rel_e + rel_n * rel_n
    if rel_speed_sq < 1e-12:
        return None, None
    # tcpa_hours = - (pos · v_rel) / |v_rel|^2
    tcpa_h = -(pos_e * rel_e + pos_n * rel_n) / rel_speed_sq
    cpa_e = pos_e + rel_e * tcpa_h
    cpa_n = pos_n + rel_n * tcpa_h
    cpa_nm = math.hypot(cpa_e, cpa_n)
    return cpa_nm, tcpa_h * 60.0


def classify_encounter(geometry: EncounterGeometry) -> EncounterVerdict:
    """
    Classify a two-vessel encounter under COLREGS Rules 13–15.

    Priority: Rule 13 (overtaking) → Rule 14 (head-on) → Rule 15 (crossing) →
    safe passing. Identical inputs always yield identical obligations.
    """
    rel_a = relative_bearing_deg(geometry.true_bearing_a_to_b_deg, geometry.heading_a_deg)
    bearing_b_to_a = reciprocal_bearing_deg(geometry.true_bearing_a_to_b_deg)
    rel_b = relative_bearing_deg(bearing_b_to_a, geometry.heading_b_deg)
    dpsi = course_difference_deg(geometry.heading_a_deg, geometry.heading_b_deg)
    starboard_a = bearing_starboard(rel_a)

    cpa_nm: float | None = None
    tcpa_min: float | None = None
    if (
        geometry.range_nm is not None
        and geometry.speed_a_kn is not None
        and geometry.speed_b_kn is not None
    ):
        cpa_nm, tcpa_min = cpa_tcpa_nm_min(
            geometry.range_nm,
            rel_a,
            geometry.heading_a_deg,
            geometry.heading_b_deg,
            geometry.speed_a_kn,
            geometry.speed_b_kn,
        )

    both_power = geometry.power_driven_a and geometry.power_driven_b

    # Rule 13 — A overtaking B (aspect of A as seen from B).
    if is_overtaking(rel_b):
        return EncounterVerdict(
            situation=EncounterSituation.OVERTAKING,
            role_a=VesselRole.GIVE_WAY,
            role_b=VesselRole.STAND_ON,
            relative_bearing_a_to_b_deg=rel_a,
            relative_bearing_b_to_a_deg=rel_b,
            course_difference_deg=dpsi,
            bearing_starboard_a=starboard_a,
            rule_citations=[RULE_13, RULE_16, RULE_17],
            cpa_nm=cpa_nm,
            tcpa_min=tcpa_min,
        )

    # Rule 13 — B overtaking A.
    if is_overtaking(rel_a):
        return EncounterVerdict(
            situation=EncounterSituation.OVERTAKING,
            role_a=VesselRole.STAND_ON,
            role_b=VesselRole.GIVE_WAY,
            relative_bearing_a_to_b_deg=rel_a,
            relative_bearing_b_to_a_deg=rel_b,
            course_difference_deg=dpsi,
            bearing_starboard_a=starboard_a,
            rule_citations=[RULE_13, RULE_16, RULE_17],
            cpa_nm=cpa_nm,
            tcpa_min=tcpa_min,
        )

    if both_power and is_head_on(dpsi, rel_a):
        return EncounterVerdict(
            situation=EncounterSituation.HEAD_ON,
            role_a=VesselRole.GIVE_WAY,
            role_b=VesselRole.GIVE_WAY,
            relative_bearing_a_to_b_deg=rel_a,
            relative_bearing_b_to_a_deg=rel_b,
            course_difference_deg=dpsi,
            bearing_starboard_a=starboard_a,
            mutual_starboard_alteration=True,
            rule_citations=[RULE_14],
            cpa_nm=cpa_nm,
            tcpa_min=tcpa_min,
        )

    if both_power and is_crossing(dpsi, rel_a):
        if starboard_a:
            role_a, role_b = VesselRole.GIVE_WAY, VesselRole.STAND_ON
        else:
            role_a, role_b = VesselRole.STAND_ON, VesselRole.GIVE_WAY
        return EncounterVerdict(
            situation=EncounterSituation.CROSSING,
            role_a=role_a,
            role_b=role_b,
            relative_bearing_a_to_b_deg=rel_a,
            relative_bearing_b_to_a_deg=rel_b,
            course_difference_deg=dpsi,
            bearing_starboard_a=starboard_a,
            rule_citations=[RULE_15, RULE_16, RULE_17],
            cpa_nm=cpa_nm,
            tcpa_min=tcpa_min,
        )

    return EncounterVerdict(
        situation=EncounterSituation.SAFE_PASSING,
        role_a=None,
        role_b=None,
        relative_bearing_a_to_b_deg=rel_a,
        relative_bearing_b_to_a_deg=rel_b,
        course_difference_deg=dpsi,
        bearing_starboard_a=starboard_a,
        rule_citations=[],
        cpa_nm=cpa_nm,
        tcpa_min=tcpa_min,
    )
