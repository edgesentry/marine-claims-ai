"""Adapter registration for jurisdiction and shipyard tariff plugins."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from marine_claims_ai.adapters.base import JurisdictionAdapter, ShipyardTariffAdapter

TJurisdiction = TypeVar("TJurisdiction", bound=JurisdictionAdapter)
TTariff = TypeVar("TTariff", bound=ShipyardTariffAdapter)

JurisdictionFactory = Callable[[], JurisdictionAdapter]
TariffFactory = Callable[[], ShipyardTariffAdapter]

_JURISDICTION_ADAPTERS: dict[str, JurisdictionFactory] = {}
_TARIFF_ADAPTERS: dict[str, TariffFactory] = {}

DEFAULT_JURISDICTION_CODE = "JP"


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def register_jurisdiction_adapter(
    code: str,
    adapter: JurisdictionAdapter | JurisdictionFactory | type[JurisdictionAdapter],
) -> None:
    """Register a jurisdiction adapter under ``code`` (e.g. ``JP``, ``UK``, ``SG``)."""
    key = _normalize_code(code)
    if isinstance(adapter, type):
        _JURISDICTION_ADAPTERS[key] = lambda cls=adapter: cls()  # type: ignore[misc]
    elif callable(adapter) and not isinstance(adapter, JurisdictionAdapter):
        _JURISDICTION_ADAPTERS[key] = adapter  # type: ignore[assignment]
    else:
        instance = adapter  # type: ignore[assignment]
        _JURISDICTION_ADAPTERS[key] = lambda inst=instance: inst  # type: ignore[misc]


def register_tariff_adapter(
    code: str,
    adapter: ShipyardTariffAdapter | TariffFactory | type[ShipyardTariffAdapter],
) -> None:
    """Register a shipyard tariff adapter under ``code``."""
    key = _normalize_code(code)
    if isinstance(adapter, type):
        _TARIFF_ADAPTERS[key] = lambda cls=adapter: cls()  # type: ignore[misc]
    elif callable(adapter) and not isinstance(adapter, ShipyardTariffAdapter):
        _TARIFF_ADAPTERS[key] = adapter  # type: ignore[assignment]
    else:
        instance = adapter  # type: ignore[assignment]
        _TARIFF_ADAPTERS[key] = lambda inst=instance: inst  # type: ignore[misc]


def get_jurisdiction_adapter(code: str = DEFAULT_JURISDICTION_CODE) -> JurisdictionAdapter:
    """Return a jurisdiction adapter instance for ``code``."""
    key = _normalize_code(code)
    factory = _JURISDICTION_ADAPTERS.get(key)
    if factory is None:
        available = ", ".join(sorted(_JURISDICTION_ADAPTERS)) or "(none)"
        raise KeyError(f"No jurisdiction adapter registered for {code!r}; available: {available}")
    return factory()


def get_tariff_adapter(code: str) -> ShipyardTariffAdapter:
    """Return a shipyard tariff adapter instance for ``code``."""
    key = _normalize_code(code)
    factory = _TARIFF_ADAPTERS.get(key)
    if factory is None:
        available = ", ".join(sorted(_TARIFF_ADAPTERS)) or "(none)"
        raise KeyError(f"No tariff adapter registered for {code!r}; available: {available}")
    return factory()


def get_default_jurisdiction_adapter() -> JurisdictionAdapter:
    """Return the out-of-the-box Japan reference adapter for public benchmarks."""
    return get_jurisdiction_adapter(DEFAULT_JURISDICTION_CODE)


def list_jurisdiction_adapters() -> list[str]:
    return sorted(_JURISDICTION_ADAPTERS)


def list_tariff_adapters() -> list[str]:
    return sorted(_TARIFF_ADAPTERS)


def clear_adapter_registries() -> None:
    """Clear all registrations (intended for unit tests)."""
    _JURISDICTION_ADAPTERS.clear()
    _TARIFF_ADAPTERS.clear()
