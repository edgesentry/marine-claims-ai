"""Modular Jurisdiction & Regional Tariff Adapter contracts and Japan reference."""

from __future__ import annotations

from marine_claims_ai.adapters.base import (
    DockFeeBreakdown,
    DockFeeMethod,
    EncounterSituation,
    EncounterType,
    GeoPoint,
    JurisdictionAdapter,
    LocalFairwayConstraint,
    PolicyForm,
    PrecedentMatch,
    PSCDeficiency,
    ShipyardTariffAdapter,
    TradeDiscipline,
    WarrantyAssessment,
)
from marine_claims_ai.adapters.japan_reference import JapanJurisdictionAdapter
from marine_claims_ai.adapters.registry import (
    clear_adapter_registries,
    get_default_jurisdiction_adapter,
    get_jurisdiction_adapter,
    get_tariff_adapter,
    list_jurisdiction_adapters,
    list_tariff_adapters,
    register_jurisdiction_adapter,
    register_tariff_adapter,
)

# Out-of-the-box default for public benchmark evaluation.
register_jurisdiction_adapter("JP", JapanJurisdictionAdapter)

__all__ = [
    "DockFeeBreakdown",
    "DockFeeMethod",
    "EncounterSituation",
    "EncounterType",
    "GeoPoint",
    "JapanJurisdictionAdapter",
    "JurisdictionAdapter",
    "LocalFairwayConstraint",
    "PolicyForm",
    "PrecedentMatch",
    "PSCDeficiency",
    "ShipyardTariffAdapter",
    "TradeDiscipline",
    "WarrantyAssessment",
    "clear_adapter_registries",
    "get_default_jurisdiction_adapter",
    "get_jurisdiction_adapter",
    "get_tariff_adapter",
    "list_jurisdiction_adapters",
    "list_tariff_adapters",
    "register_jurisdiction_adapter",
    "register_tariff_adapter",
]
