"""Load jurisdiction plugin JSON from ``config/jurisdictions/``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from marine_claims_ai.adapters.base import EncounterType
from marine_claims_ai.paths import DEFAULT_JURISDICTIONS_DIR


class FairwayRuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applies: bool = True
    rule_citations: list[str] = Field(default_factory=list)
    notes: str = ""
    traffic_direction: str | None = None
    speed_limit_kn: float | None = None


class WarrantyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standard_id: str
    privity_required: bool = False
    critical_severities: list[str] = Field(default_factory=list)


class JurisdictionPluginConfig(BaseModel):
    """Typed view of ``config/jurisdictions/<code>.json``."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    jurisdiction_code: str
    description: str = ""
    warranty: WarrantyConfig
    domain_holding_kinds: dict[str, list[str]] = Field(default_factory=dict)
    situation_tokens: dict[str, list[str]] = Field(default_factory=dict)
    fairways: dict[str, FairwayRuleConfig] = Field(default_factory=dict)

    def holding_kinds_for(self, domain: str) -> frozenset[str] | None:
        key = (domain or "").strip().lower()
        kinds = self.domain_holding_kinds.get(key)
        if kinds is None:
            return None
        return frozenset(kinds)

    def tokens_for(self, situation_type: EncounterType | str) -> tuple[str, ...]:
        key = situation_type.value if isinstance(situation_type, EncounterType) else str(situation_type)
        return tuple(self.situation_tokens.get(key, []) or [])


def jurisdiction_config_path(
    code: str,
    *,
    jurisdictions_dir: str | Path | None = None,
) -> Path:
    root = Path(jurisdictions_dir) if jurisdictions_dir else DEFAULT_JURISDICTIONS_DIR
    return root / f"{code.strip().lower()}.json"


def load_jurisdiction_config(
    code: str = "JP",
    *,
    path: str | Path | None = None,
    jurisdictions_dir: str | Path | None = None,
) -> JurisdictionPluginConfig:
    """Load and validate a jurisdiction plugin config (uncached)."""
    config_path = Path(path) if path else jurisdiction_config_path(code, jurisdictions_dir=jurisdictions_dir)
    with open(config_path, encoding="utf-8") as f:
        raw: Any = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid jurisdiction config (expected object): {config_path}")
    return JurisdictionPluginConfig.model_validate(raw)


@lru_cache(maxsize=8)
def get_jurisdiction_config(code: str = "JP") -> JurisdictionPluginConfig:
    """Cached loader for the default ``config/jurisdictions/<code>.json`` path."""
    return load_jurisdiction_config(code)


def clear_jurisdiction_config_cache() -> None:
    get_jurisdiction_config.cache_clear()
