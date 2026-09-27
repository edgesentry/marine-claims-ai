"""Unit tests for Modular Jurisdiction & Regional Tariff Adapter contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from marine_claims_ai.adapters import (
    DockFeeBreakdown,
    DockFeeMethod,
    EncounterSituation,
    EncounterType,
    GeoPoint,
    JapanJurisdictionAdapter,
    JurisdictionAdapter,
    PolicyForm,
    PrecedentMatch,
    PSCDeficiency,
    ShipyardTariffAdapter,
    TradeDiscipline,
    clear_adapter_registries,
    get_default_jurisdiction_adapter,
    get_jurisdiction_adapter,
    get_tariff_adapter,
    list_jurisdiction_adapters,
    register_jurisdiction_adapter,
    register_tariff_adapter,
)
from marine_claims_ai.adapters.base import LocalFairwayConstraint, WarrantyAssessment


@pytest.fixture(autouse=True)
def _restore_default_jp_adapter():
    """Keep the open-core JP default registered across tests that clear registries."""
    yield
    clear_adapter_registries()
    register_jurisdiction_adapter("JP", JapanJurisdictionAdapter)


def test_jurisdiction_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        JurisdictionAdapter()  # type: ignore[abstract]


def test_tariff_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        ShipyardTariffAdapter()  # type: ignore[abstract]


def test_japan_adapter_is_jurisdiction_adapter():
    adapter = JapanJurisdictionAdapter()
    assert isinstance(adapter, JurisdictionAdapter)


def test_japan_lookup_precedents_from_public_catalog():
    adapter = JapanJurisdictionAdapter()
    situation = EncounterSituation(
        situation_type=EncounterType.CROSSING,
        facts="貨物船同士が横切る態勢で接近し衝突 見張り不十分",
    )
    matches = adapter.lookup_precedents(situation, domain="civil_court")
    assert matches
    assert all(isinstance(m, PrecedentMatch) for m in matches)
    assert all(m.holding_kind in {"civil_judgment", "civil_published_summary"} for m in matches)
    assert matches[0].fault_ratio  # catalog rows carry fault splits


def test_japan_lookup_jmat_domain_filters_holding_kind():
    adapter = JapanJurisdictionAdapter()
    matches = adapter.lookup_precedents(
        EncounterSituation(situation_type=EncounterType.UNKNOWN, facts="衝突"),
        domain="jmat",
    )
    assert matches
    assert all(m.holding_kind in {"jmat_major", "jmat_saiketsu"} for m in matches)


def test_japan_fairway_uraga_and_unknown():
    adapter = JapanJurisdictionAdapter()
    pos = GeoPoint(lat=35.2, lon=139.7)
    uraga = adapter.evaluate_fairway_rules(pos, "uraga")
    assert isinstance(uraga, LocalFairwayConstraint)
    assert uraga.applies is True
    assert uraga.rule_citations

    unknown = adapter.evaluate_fairway_rules(pos, "dover")
    assert unknown.applies is False


def test_japan_seaworthiness_art815_no_privity():
    adapter = JapanJurisdictionAdapter()
    detention = PSCDeficiency(code="07105", action_code="30", description="Fire pumps")
    assessment = adapter.evaluate_seaworthiness_warranty([detention], PolicyForm.NK_HULL)
    assert isinstance(assessment, WarrantyAssessment)
    assert assessment.standard_id == "JP_Commercial_Code_Art815"
    assert assessment.privity_required is False
    assert assessment.breached is True

    clean = adapter.evaluate_seaworthiness_warranty([], PolicyForm.NK_HULL)
    assert clean.breached is False


def test_default_jurisdiction_adapter_is_japan():
    adapter = get_default_jurisdiction_adapter()
    assert isinstance(adapter, JapanJurisdictionAdapter)
    assert "JP" in list_jurisdiction_adapters()


def test_international_jurisdiction_adapter_registration_mock():
    class FakeUKJurisdictionAdapter(JurisdictionAdapter):
        def lookup_precedents(self, encounter_situation, domain):
            return [
                PrecedentMatch(
                    case_id="uk-1",
                    title="Mock Admiralty precedent",
                    domain=domain,
                    fault_ratio="60:40",
                    score=1.0,
                )
            ]

        def evaluate_fairway_rules(self, vessel_position, channel_id):
            return LocalFairwayConstraint(
                channel_id=channel_id,
                applies=channel_id == "dover",
                rule_citations=["CALDOVREP (mock)"],
                notes="UK mock fairway",
            )

        def evaluate_seaworthiness_warranty(self, psc_deficiencies, policy_form):
            return WarrantyAssessment(
                standard_id="UK_MIA_1906_Sec39",
                privity_required=True,
                breached=None,
                rationale="Mock English law assessment",
                policy_form=policy_form,
            )

    clear_adapter_registries()
    register_jurisdiction_adapter("JP", JapanJurisdictionAdapter)
    register_jurisdiction_adapter("UK", FakeUKJurisdictionAdapter)

    uk = get_jurisdiction_adapter("UK")
    assert isinstance(uk, FakeUKJurisdictionAdapter)
    hits = uk.lookup_precedents(EncounterSituation(), domain="admiralty")
    assert hits[0].fault_ratio == "60:40"
    fairway = uk.evaluate_fairway_rules(GeoPoint(lat=51.1, lon=1.3), "dover")
    assert fairway.applies is True
    warranty = uk.evaluate_seaworthiness_warranty([], PolicyForm.ITC_HULLS)
    assert warranty.privity_required is True


def test_international_tariff_adapter_registration_mock():
    class FakeSingaporeTariffAdapter(ShipyardTariffAdapter):
        def get_hourly_labor_rate(self, trade_discipline, region):
            return Decimal("42.00")

        def get_docking_fee_structure(self, vessel_gt, dock_days):
            daily = Decimal("1500.00")
            total = daily * Decimal(dock_days)
            return DockFeeBreakdown(
                method=DockFeeMethod.DAILY_LAY,
                currency="USD",
                total=total,
                daily_rate=daily,
                vessel_gt=vessel_gt,
                dock_days=dock_days,
                components={"lay_days": total},
                notes="Jurong mock tariff",
            )

    clear_adapter_registries()
    register_jurisdiction_adapter("JP", JapanJurisdictionAdapter)
    register_tariff_adapter("SG", FakeSingaporeTariffAdapter)

    tariff = get_tariff_adapter("SG")
    assert isinstance(tariff, ShipyardTariffAdapter)
    assert tariff.get_hourly_labor_rate(TradeDiscipline.HULL, "jurong") == Decimal("42.00")
    breakdown = tariff.get_docking_fee_structure(vessel_gt=25000.0, dock_days=3)
    assert breakdown.total == Decimal("4500.00")
    assert breakdown.method == DockFeeMethod.DAILY_LAY


def test_unknown_adapter_raises_key_error():
    with pytest.raises(KeyError, match="No jurisdiction adapter"):
        get_jurisdiction_adapter("XX")
    with pytest.raises(KeyError, match="No tariff adapter"):
        get_tariff_adapter("XX")
