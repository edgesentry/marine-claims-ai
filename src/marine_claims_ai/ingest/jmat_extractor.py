"""
Extract navigational telemetry from Japanese JMAT / JTSB collision narratives.

Deterministic regex + maritime text normalization for headings, relative
sighting bearings, speeds, and statutory article citations (Arts. 13–15).

See Issue #39 and ``docs/public_benchmarks_and_accuracy_evaluation.md``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from marine_claims_ai.ingest.geometry import EncounterGeometry, normalize_deg

# ---------------------------------------------------------------------------
# Numeral / encoding normalization
# ---------------------------------------------------------------------------

_FULLWIDTH = str.maketrans(
    "０１２３４５６７８９．．，：％",
    "0123456789..,:%",
)

# Cardinal / intercardinal points → true degrees (north = 0).
_COMPASS_POINTS: dict[str, float] = {
    "北": 0.0,
    "北北東": 22.5,
    "北東": 45.0,
    "東北東": 67.5,
    "東": 90.0,
    "東南東": 112.5,
    "南東": 135.0,
    "南南東": 157.5,
    "南": 180.0,
    "南南西": 202.5,
    "南西": 225.0,
    "西南西": 247.5,
    "西": 270.0,
    "西北西": 292.5,
    "北西": 315.0,
    "北北西": 337.5,
}

# Longer keys first so 「北北東」 wins over 「北」.
_COMPASS_KEYS = sorted(_COMPASS_POINTS.keys(), key=len, reverse=True)
_COMPASS_ALT = {
    "の微北": -5.0,
    "の微東": 5.0,
    "の微南": 5.0,
    "の微西": -5.0,
    "微北": -5.0,
    "微東": 5.0,
}

_VESSEL_A = re.compile(
    r"(?:本船\s*[ＡA甲]?|甲船|Ａ船|A船|船舶Ａ|船舶A)",
    re.IGNORECASE,
)
_VESSEL_B = re.compile(
    r"(?:相手船\s*[ＢB乙]?|乙船|Ｂ船|B船|船舶Ｂ|船舶B|他船)",
    re.IGNORECASE,
)

_ALT_SUFFIX = "|".join(
    re.escape(k) for k in sorted(_COMPASS_ALT.keys(), key=len, reverse=True)
)
_HEADING_ANY = re.compile(
    r"針路\s*約?\s*(?:([0-9]{1,3})\s*度|("
    + "|".join(re.escape(k) for k in _COMPASS_KEYS)
    + r")(?:"
    + _ALT_SUFFIX
    + r")?)",
)
_SPEED = re.compile(r"速力\s*約?\s*([0-9]+(?:\.[0-9]+)?)\s*ノット")
_ARTICLE = re.compile(
    r"(?:海上衝突予防法)?\s*第\s*(13|14|15|１３|１４|１５)\s*条",
)

# Relative bearing from own ship (A) toward target (B).
_REL_STARBOARD_BOW = re.compile(r"右舷前\s*約?\s*([0-9]{1,3})\s*度")
_REL_PORT_BOW = re.compile(r"左舷前\s*約?\s*([0-9]{1,3})\s*度")
_REL_STARBOARD_QUARTER = re.compile(r"右舷(?:正横後|後方|船尾方)\s*約?\s*([0-9]{1,3})\s*度?")
_REL_PORT_QUARTER = re.compile(r"左舷(?:正横後|後方|船尾方)\s*約?\s*([0-9]{1,3})\s*度?")
_REL_PHRASE = [
    (re.compile(r"船首方向|正船首|ほとんど船首"), 0.0),
    (re.compile(r"右舷正横(?!後)"), 90.0),
    (re.compile(r"左舷正横(?!後)"), 270.0),
    (re.compile(r"右舷正横後"), 135.0),
    (re.compile(r"左舷正横後"), 225.0),
    (re.compile(r"船尾方向|正船尾"), 180.0),
]


@dataclass
class JmatTelemetryExtraction:
    """Structured telemetry parsed from a raw collision narrative."""

    heading_a_deg: float | None = None
    heading_b_deg: float | None = None
    relative_bearing_a_to_b_deg: float | None = None
    speed_a_kn: float | None = None
    speed_b_kn: float | None = None
    ruling_article: int | None = None
    extraction_ok: bool = False
    evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_encounter_geometry(self) -> EncounterGeometry | None:
        """Build EncounterGeometry when required fields were extracted."""
        if (
            self.heading_a_deg is None
            or self.heading_b_deg is None
            or self.relative_bearing_a_to_b_deg is None
        ):
            return None
        true_bearing = normalize_deg(self.heading_a_deg + self.relative_bearing_a_to_b_deg)
        return EncounterGeometry(
            heading_a_deg=float(self.heading_a_deg),
            heading_b_deg=float(self.heading_b_deg),
            true_bearing_a_to_b_deg=true_bearing,
            speed_a_kn=self.speed_a_kn,
            speed_b_kn=self.speed_b_kn,
        )


def normalize_maritime_text(text: str) -> str:
    """NFKC + fullwidth digits; collapse whitespace; keep Japanese punctuation."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.translate(_FULLWIDTH)
    t = t.replace("\u3000", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def _parse_compass(token: str) -> float | None:
    token = token.strip()
    for alt, delta in _COMPASS_ALT.items():
        if token.endswith(alt):
            base = token[: -len(alt)]
            if base in _COMPASS_POINTS:
                return normalize_deg(_COMPASS_POINTS[base] + delta)
    if token in _COMPASS_POINTS:
        return _COMPASS_POINTS[token]
    for key in _COMPASS_KEYS:
        if token.startswith(key):
            return _COMPASS_POINTS[key]
    return None


def _heading_from_any_match(m: re.Match[str]) -> float | None:
    if m.group(1):
        return float(int(m.group(1)) % 360)
    if m.group(2):
        token = m.string[m.start(2) : m.end()]
        return _parse_compass(token)
    return None


def _find_heading_near(text: str, vessel_re: re.Pattern[str]) -> float | None:
    """Prefer a 針路 within ~120 chars after a vessel label."""
    for vm in vessel_re.finditer(text):
        window = text[vm.end() : vm.end() + 120]
        m = _HEADING_ANY.search(window)
        if m:
            return _heading_from_any_match(m)
    return None


def extract_headings(text: str) -> tuple[float | None, float | None]:
    """Return (heading_a, heading_b) from normalized narrative."""
    ha = _find_heading_near(text, _VESSEL_A)
    hb = _find_heading_near(text, _VESSEL_B)
    if ha is not None and hb is not None:
        return ha, hb

    ordered: list[float] = []
    for m in _HEADING_ANY.finditer(text):
        v = _heading_from_any_match(m)
        if v is not None:
            ordered.append(v)

    if ha is None and ordered:
        ha = ordered[0]
    if hb is None and len(ordered) >= 2:
        hb = ordered[1]
    return ha, hb


def extract_relative_bearing(text: str) -> float | None:
    """Relative bearing of target from own ship: 0=ahead, 90=starboard."""
    m = _REL_STARBOARD_BOW.search(text)
    if m:
        return float(int(m.group(1)) % 360)
    m = _REL_PORT_BOW.search(text)
    if m:
        return normalize_deg(-float(int(m.group(1))))
    m = _REL_STARBOARD_QUARTER.search(text)
    if m:
        # Degrees abaft starboard beam → 90 + n
        return normalize_deg(90.0 + float(int(m.group(1))))
    m = _REL_PORT_QUARTER.search(text)
    if m:
        return normalize_deg(270.0 - float(int(m.group(1))))
    for pat, val in _REL_PHRASE:
        if pat.search(text):
            return val
    return None


def extract_speeds(text: str) -> tuple[float | None, float | None]:
    """Return (speed_a, speed_b) preferring vessel-scoped windows, else order."""
    sa = sb = None
    for vm in _VESSEL_A.finditer(text):
        window = text[vm.end() : vm.end() + 100]
        m = _SPEED.search(window)
        if m:
            sa = float(m.group(1))
            break
    for vm in _VESSEL_B.finditer(text):
        window = text[vm.end() : vm.end() + 100]
        m = _SPEED.search(window)
        if m:
            sb = float(m.group(1))
            break
    speeds = [float(m.group(1)) for m in _SPEED.finditer(text)]
    if sa is None and speeds:
        sa = speeds[0]
    if sb is None and len(speeds) >= 2:
        sb = speeds[1]
    return sa, sb


def extract_ruling_article(text: str) -> int | None:
    """Extract operative Art. 13/14/15 from 原因 / 主文 style ruling text."""
    m = _ARTICLE.search(text)
    if not m:
        return None
    raw = m.group(1).translate(_FULLWIDTH)
    return int(raw)


def extract_telemetry(
    facts_text: str,
    ruling_text: str = "",
) -> JmatTelemetryExtraction:
    """
    Parse encounter telemetry from facts narrative and optional ruling text.

    ``extraction_ok`` is True only when both headings and a relative bearing
    are available (sufficient to build ``EncounterGeometry``).
    """
    facts = normalize_maritime_text(facts_text)
    ruling = normalize_maritime_text(ruling_text)
    ha, hb = extract_headings(facts)
    rel = extract_relative_bearing(facts)
    sa, sb = extract_speeds(facts)
    article = extract_ruling_article(ruling) or extract_ruling_article(facts)

    ok = ha is not None and hb is not None and rel is not None
    evidence_parts: list[str] = []
    if ha is not None:
        evidence_parts.append(f"heading_a={ha}")
    if hb is not None:
        evidence_parts.append(f"heading_b={hb}")
    if rel is not None:
        evidence_parts.append(f"rel={rel}")
    if article is not None:
        evidence_parts.append(f"art={article}")

    return JmatTelemetryExtraction(
        heading_a_deg=ha,
        heading_b_deg=hb,
        relative_bearing_a_to_b_deg=rel,
        speed_a_kn=sa,
        speed_b_kn=sb,
        ruling_article=article,
        extraction_ok=ok,
        evidence="; ".join(evidence_parts) if evidence_parts else None,
    )
