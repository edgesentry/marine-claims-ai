"""
Typed contracts for Modular Jurisdiction & Regional Tariff Adapters.

Universal open-core engines (COLREGS geometry, AAA Rule D5, SOLAS compartment
graphs, IMO PSC taxonomy) remain jurisdiction-neutral. Adapters encapsulate
local precedent catalogs, fairway regulations, seaworthiness legal standards,
and regional shipyard tariff schedules so markets (Japan / UK / Singapore) can
plug in without rewriting core algorithms.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EncounterType(StrEnum):
    """COLREGS-aligned encounter geometry labels."""

    CROSSING = "crossing"
    HEAD_ON = "head_on"
    OVERTAKING = "overtaking"
    UNKNOWN = "unknown"


class PolicyForm(StrEnum):
    """Hull policy form families used when assessing seaworthiness warranties."""

    NK_HULL = "NK_HULL"
    ITC_HULLS = "ITC_HULLS"
    NORDIC_PLAN = "NORDIC_PLAN"
    OTHER = "OTHER"


class TradeDiscipline(StrEnum):
    """Coarse SFI-aligned trade buckets for regional labor rates."""

    HULL = "hull"
    ENGINE = "engine"
    ELECTRICAL = "electrical"
    PIPING = "piping"
    OTHER = "other"


class DockFeeMethod(StrEnum):
    """Local drydock fee convention."""

    DAILY_LAY = "daily_lay"
    GT_LUMP_SUM = "gt_lump_sum"


class GeoPoint(BaseModel):
    """Geographic position in WGS-84 decimal degrees."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class EncounterSituation(BaseModel):
    """Facts describing a collision encounter for precedent lookup."""

    model_config = ConfigDict(extra="forbid")

    situation_type: EncounterType = EncounterType.UNKNOWN
    relative_bearing_deg: float | None = Field(default=None, ge=0.0, le=360.0)
    facts: str = ""
    domain_hint: str | None = None


class PSCDeficiency(BaseModel):
    """Single Port State Control deficiency observation."""

    model_config = ConfigDict(extra="forbid")

    code: str
    action_code: str | None = None
    description: str = ""
    severity: str | None = None


class PrecedentMatch(BaseModel):
    """
    Jurisdiction-local precedent hit.

    Field names align with ``config/civil_precedent_catalog.json`` seeds.
    LanceDB rows map ``fault_ratio``→``fault_split_text``, ``url``→``source_url``,
    ``awarded_damages_jpy``→``awarded_jpy`` when a vector index is used later.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: int | str | None = None
    title: str = ""
    domain: str = ""
    fault_ratio: str | None = None
    holding: str | None = None
    url: str | None = None
    source_type: str | None = None
    holding_kind: str | None = None
    claimed_repair_jpy: int | None = None
    disallowed_jpy: int | None = None
    awarded_damages_jpy: int | None = None
    score: float = 0.0
    court: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class LocalFairwayConstraint(BaseModel):
    """Result of evaluating local waterway / TSS / fairway regulations."""

    model_config = ConfigDict(extra="forbid")

    channel_id: str | None = None
    applies: bool = False
    rule_citations: list[str] = Field(default_factory=list)
    notes: str = ""
    speed_limit_kn: float | None = None
    traffic_direction: str | None = None


class WarrantyAssessment(BaseModel):
    """Jurisdiction-specific seaworthiness warranty evaluation."""

    model_config = ConfigDict(extra="forbid")

    standard_id: str
    privity_required: bool
    breached: bool | None = None
    rationale: str = ""
    matched_deficiencies: list[PSCDeficiency] = Field(default_factory=list)
    policy_form: PolicyForm | None = None


class DockFeeBreakdown(BaseModel):
    """Regional drydock lay-fee / tonnage lump-sum breakdown."""

    model_config = ConfigDict(extra="forbid")

    method: DockFeeMethod
    currency: str
    total: Decimal
    daily_rate: Decimal | None = None
    lump_sum: Decimal | None = None
    vessel_gt: float | None = None
    dock_days: int | None = None
    components: dict[str, Decimal] = Field(default_factory=dict)
    notes: str = ""


class JurisdictionAdapter(ABC):
    """
    Plug-in boundary for jurisdiction-local legal and navigational rules.

    Implementations supply precedent catalogs, fairway constraints, and
    seaworthiness warranty standards without altering universal COLREGS /
    SOLAS / IMO engines in the open core.
    """

    @abstractmethod
    def lookup_precedents(
        self,
        encounter_situation: EncounterSituation,
        domain: str,
    ) -> list[PrecedentMatch]:
        """
        Retrieve precedent collision fault attribution splits for ``domain``.

        Typical domains: ``civil_court``, ``jmat``. Backends may use structured
        catalogs and/or LanceDB vector indexes.
        """

    @abstractmethod
    def evaluate_fairway_rules(
        self,
        vessel_position: GeoPoint,
        channel_id: str | None,
    ) -> LocalFairwayConstraint:
        """Evaluate local waterway regulations for the given channel / position."""

    @abstractmethod
    def evaluate_seaworthiness_warranty(
        self,
        psc_deficiencies: list[PSCDeficiency],
        policy_form: PolicyForm,
    ) -> WarrantyAssessment:
        """Apply jurisdiction-specific legal standards to PSC findings."""


class ShipyardTariffAdapter(ABC):
    """
    Plug-in boundary for regional shipyard labor and docking fee schedules.

    Keeps proprietary or market-specific rates out of universal Rule D /
    apportionment engines; commercial extensions register their own adapters.
    """

    @abstractmethod
    def get_hourly_labor_rate(
        self,
        trade_discipline: TradeDiscipline,
        region: str,
    ) -> Decimal:
        """Return the hourly man-hour rate for ``trade_discipline`` in ``region``."""

    @abstractmethod
    def get_docking_fee_structure(
        self,
        vessel_gt: float,
        dock_days: int,
    ) -> DockFeeBreakdown:
        """Return drydock lay-fee / tonnage lump-sum structure for the vessel."""
