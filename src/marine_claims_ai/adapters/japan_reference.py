"""
Japan reference jurisdiction adapter (public open-core default).

Wires to ``config/civil_precedent_catalog.json`` (real civil judgments and JMAT
holdings). Serves as the verified reference model for international adapter plugins.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from marine_claims_ai.adapters.base import (
    EncounterSituation,
    EncounterType,
    GeoPoint,
    JurisdictionAdapter,
    LocalFairwayConstraint,
    PolicyForm,
    PrecedentMatch,
    PSCDeficiency,
    WarrantyAssessment,
)
from marine_claims_ai.ingest.civil import load_catalog
from marine_claims_ai.paths import DEFAULT_CIVIL_CATALOG_PATH

# Domain → holding_kind filters against the public civil precedent catalog.
_DOMAIN_HOLDING_KINDS: dict[str, frozenset[str]] = {
    "civil_court": frozenset({"civil_judgment", "civil_published_summary"}),
    "jmat": frozenset({"jmat_major", "jmat_saiketsu"}),
}

# Japanese Maritime Traffic Safety Act style public fairway stubs (reference only).
_FAIRWAY_RULES: dict[str, LocalFairwayConstraint] = {
    "uraga": LocalFairwayConstraint(
        channel_id="uraga",
        applies=True,
        rule_citations=[
            "Japan Maritime Traffic Safety Act (海上交通安全法) — Uraga Channel",
        ],
        notes="Uraga Suido traffic separation / transit duties (public reference stub).",
        traffic_direction="TSS",
    ),
    "kanmon": LocalFairwayConstraint(
        channel_id="kanmon",
        applies=True,
        rule_citations=[
            "Japan Maritime Traffic Safety Act (海上交通安全法) — Kanmon Passage",
        ],
        notes="Kanmon Kaikyo transit constraints (public reference stub).",
        traffic_direction="TSS",
    ),
}

_SITUATION_TOKENS: dict[EncounterType, tuple[str, ...]] = {
    EncounterType.CROSSING: ("横切", "crossing", "交差"),
    EncounterType.HEAD_ON: ("行き会い", "head-on", "head_on", "正面"),
    EncounterType.OVERTAKING: ("追越し", "追越", "overtaking"),
}

_TOKEN_RE = re.compile(r"[\w\u3040-\u30ff\u3400-\u9fff]+", re.UNICODE)

# IMO PSC action code commonly used for detention.
_DETENTION_ACTION = "30"


class JapanJurisdictionAdapter(JurisdictionAdapter):
    """
    Canonical open-core jurisdiction adapter for Japanese public benchmarks.

    Precedent lookup reads the tracked civil / JMAT catalog only (no LanceDB /
    network requirement) so unit tests and CI remain offline-reproducible.
    """

    jurisdiction_code = "JP"
    warranty_standard_id = "JP_Commercial_Code_Art815"

    def __init__(self, catalog_path: str | Path | None = None) -> None:
        self.catalog_path = Path(catalog_path) if catalog_path else DEFAULT_CIVIL_CATALOG_PATH
        self._seeds: list[dict[str, Any]] | None = None

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
        known = _FAIRWAY_RULES.get(key)
        if known is not None:
            return known.model_copy()
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

        Unlike English MIA 1906 §39 time policies, Japanese law does not require
        privity of the assured as a threshold for carrier seaworthiness duties.
        """
        detention_hits = [
            d
            for d in psc_deficiencies
            if (d.action_code or "").strip() == _DETENTION_ACTION
            or (d.severity or "").lower() in {"detention", "high", "critical"}
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
                "PSC deficiencies present without Code 30 detention; due-diligence "
                "assessment inconclusive without fuller survey facts."
            )
        else:
            breached = False
            rationale = "No PSC deficiencies supplied; no seaworthiness breach indicated."

        return WarrantyAssessment(
            standard_id=self.warranty_standard_id,
            privity_required=False,
            breached=breached,
            rationale=rationale,
            matched_deficiencies=list(detention_hits or psc_deficiencies),
            policy_form=policy_form,
        )

    @staticmethod
    def _filter_by_domain(seeds: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
        key = (domain or "").strip().lower()
        kinds = _DOMAIN_HOLDING_KINDS.get(key)
        if kinds is None:
            return list(seeds)
        return [s for s in seeds if str(s.get("holding_kind") or "") in kinds]

    @classmethod
    def _score_seed(cls, seed: dict[str, Any], situation: EncounterSituation) -> float:
        blob = " ".join(
            str(seed.get(k) or "")
            for k in ("title", "input_facts", "holding", "court")
        ).lower()
        score = 0.0
        tokens = cls._tokens(situation.facts)
        if tokens:
            hits = sum(1 for tok in tokens if tok in blob)
            score += hits / max(len(tokens), 1)
        for marker in _SITUATION_TOKENS.get(situation.situation_type, ()):
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
