"""
Japan reference jurisdiction adapter (public open-core default).

Wires to ``config/civil_precedent_catalog.json`` and
``config/jurisdictions/jp.json``. Lexicons, fairway stubs, and warranty metadata
live in JSON so international plugins can mirror the same layout without forking
adapter code.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from marine_claims_ai.adapters.base import (
    EncounterSituation,
    GeoPoint,
    JurisdictionAdapter,
    LocalFairwayConstraint,
    PolicyForm,
    PrecedentMatch,
    PSCDeficiency,
    WarrantyAssessment,
)
from marine_claims_ai.adapters.jurisdiction_config import (
    JurisdictionPluginConfig,
    load_jurisdiction_config,
)
from marine_claims_ai.ingest.civil import load_catalog
from marine_claims_ai.ontology.psc import is_detention_action
from marine_claims_ai.paths import DEFAULT_CIVIL_CATALOG_PATH

_TOKEN_RE = re.compile(r"[\w\u3040-\u30ff\u3400-\u9fff]+", re.UNICODE)


class JapanJurisdictionAdapter(JurisdictionAdapter):
    """
    Canonical open-core jurisdiction adapter for Japanese public benchmarks.

    Precedent lookup reads the tracked civil / JMAT catalog only (no LanceDB /
    network requirement) so unit tests and CI remain offline-reproducible.
    Jurisdiction-local tokens and fairways come from plugin JSON.
    """

    jurisdiction_code = "JP"

    def __init__(
        self,
        catalog_path: str | Path | None = None,
        *,
        config: JurisdictionPluginConfig | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path) if catalog_path else DEFAULT_CIVIL_CATALOG_PATH
        self.plugin = config or load_jurisdiction_config("JP", path=config_path)
        self._seeds: list[dict[str, Any]] | None = None

    @property
    def warranty_standard_id(self) -> str:
        return self.plugin.warranty.standard_id

    def _load_seeds(self) -> list[dict[str, Any]]:
        if self._seeds is None:
            self._seeds = load_catalog(self.catalog_path)
        return self._seeds

    def lookup_precedents(
        self,
        encounter_situation: EncounterSituation,
        domain: str,
    ) -> list[PrecedentMatch]:
        seeds = self._filter_by_domain(self._load_seeds(), domain)
        scored: list[tuple[float, dict[str, Any]]] = []
        for seed in seeds:
            score = self._score_seed(seed, encounter_situation)
            scored.append((score, seed))
        scored.sort(key=lambda item: (-item[0], str(item[1].get("case_id") or "")))
        return [self._to_match(seed, domain=domain, score=score) for score, seed in scored]

    def evaluate_fairway_rules(
        self,
        vessel_position: GeoPoint,
        channel_id: str | None,
    ) -> LocalFairwayConstraint:
        # Position is accepted for API compatibility; reference table is keyed by channel_id.
        _ = vessel_position
        if not channel_id:
            return LocalFairwayConstraint(
                channel_id=None,
                applies=False,
                notes="No channel_id supplied; no Japan fairway rule applied.",
            )
        key = channel_id.strip().lower()
        known = self.plugin.fairways.get(key)
        if known is not None:
            return LocalFairwayConstraint(
                channel_id=key,
                applies=known.applies,
                rule_citations=list(known.rule_citations),
                notes=known.notes,
                traffic_direction=known.traffic_direction,
                speed_limit_kn=known.speed_limit_kn,
            )
        return LocalFairwayConstraint(
            channel_id=key,
            applies=False,
            notes=f"Unknown Japan channel_id {key!r}; no local fairway constraint.",
        )

    def evaluate_seaworthiness_warranty(
        self,
        psc_deficiencies: list[PSCDeficiency],
        policy_form: PolicyForm,
    ) -> WarrantyAssessment:
        """
        Japanese Commercial Code Art. 815 due-diligence standard.

        Detention detection uses universal IMO PSC action codes; privity and
        standard identity come from the jurisdiction plugin config.
        """
        critical = {s.lower() for s in self.plugin.warranty.critical_severities}
        detention_hits = [
            d
            for d in psc_deficiencies
            if is_detention_action(d.action_code)
            or (d.severity or "").lower() in critical
        ]
        if detention_hits:
            breached: bool | None = True
            rationale = (
                "PSC detention / critical action codes present; under Japanese Commercial "
                "Code Art. 815 due-diligence standards this supports a seaworthiness "
                "warranty concern (heuristic reference assessment)."
            )
        elif psc_deficiencies:
            breached = None
            rationale = (
                "PSC deficiencies present without IMO detention action; due-diligence "
                "assessment inconclusive without fuller survey facts."
            )
        else:
            breached = False
            rationale = "No PSC deficiencies supplied; no seaworthiness breach indicated."

        return WarrantyAssessment(
            standard_id=self.warranty_standard_id,
            privity_required=self.plugin.warranty.privity_required,
            breached=breached,
            rationale=rationale,
            matched_deficiencies=list(detention_hits or psc_deficiencies),
            policy_form=policy_form,
        )

    def _filter_by_domain(self, seeds: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
        kinds = self.plugin.holding_kinds_for(domain)
        if kinds is None:
            return list(seeds)
        return [s for s in seeds if str(s.get("holding_kind") or "") in kinds]

    def _score_seed(self, seed: dict[str, Any], situation: EncounterSituation) -> float:
        blob = " ".join(
            str(seed.get(k) or "")
            for k in ("title", "input_facts", "holding", "court")
        ).lower()
        score = 0.0
        tokens = self._tokens(situation.facts)
        if tokens:
            hits = sum(1 for tok in tokens if tok in blob)
            score += hits / max(len(tokens), 1)
        for marker in self.plugin.tokens_for(situation.situation_type):
            if marker.lower() in blob:
                score += 0.5
                break
        if situation.domain_hint and situation.domain_hint.lower() in blob:
            score += 0.25
        # Stable non-zero floor so catalog rows still surface when facts are sparse.
        if seed.get("fault_ratio"):
            score += 0.05
        return score

    @staticmethod
    def _tokens(text: str) -> list[str]:
        if not text:
            return []
        return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) >= 2]

    @staticmethod
    def _to_match(seed: dict[str, Any], *, domain: str, score: float) -> PrecedentMatch:
        return PrecedentMatch(
            case_id=seed.get("case_id"),
            title=str(seed.get("title") or ""),
            domain=domain,
            fault_ratio=seed.get("fault_ratio"),
            holding=seed.get("holding"),
            url=seed.get("url"),
            source_type=seed.get("source_type"),
            holding_kind=seed.get("holding_kind"),
            claimed_repair_jpy=seed.get("claimed_repair_jpy"),
            disallowed_jpy=seed.get("disallowed_jpy"),
            awarded_damages_jpy=seed.get("awarded_damages_jpy"),
            score=score,
            court=seed.get("court"),
        )
