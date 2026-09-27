"""Unit tests for AAA Rule D5 drydock common-dues apportionment."""

from __future__ import annotations

from decimal import Decimal

from marine_claims_ai.adapters.base import DockFeeBreakdown, DockFeeMethod
from marine_claims_ai.analytics.rule_d_solver import (
    ApportionmentRule,
    DockingContext,
    OwnerNecessity,
    RepairLineItem,
    WorkParty,
    apportion_rule_d,
)


def _dock(cost: int = 4_300_000) -> RepairLineItem:
    return RepairLineItem(
        id="dock-1",
        trade_code="DOCK-01",
        cost=Decimal(cost),
        title="入出渠・滞渠",
    )


def _hull(cost: int = 450_000) -> RepairLineItem:
    return RepairLineItem(
        id="hull-1",
        trade_code="HULL-01",
        cost=Decimal(cost),
        work_party=WorkParty.CASUALTY,
        title="外板損傷修繕",
    )


def _eng_deferred(cost: int = 1_800_000) -> RepairLineItem:
    return RepairLineItem(
        id="eng-1",
        trade_code="ENG-02",
        cost=Decimal(cost),
        necessity=OwnerNecessity.DEFERRED,
        title="ピストン抜出",
    )


def _safe_statutory(cost: int = 550_000) -> RepairLineItem:
    return RepairLineItem(
        id="safe-1",
        trade_code="SAFE-01",
        cost=Decimal(cost),
        title="JG 定期検査",
    )


def _prop_statutory(cost: int = 2_200_000) -> RepairLineItem:
    return RepairLineItem(
        id="prop-1",
        trade_code="PROP-02",
        cost=Decimal(cost),
        title="尾軸抜出点検",
    )


def test_case_a_d5_2a_statutory_owner_5050():
    """D5 ¶2(a): casualty_immediate + statutory owner → common dues 50/50."""
    result = apportion_rule_d(
        [_hull(), _safe_statutory(), _dock(4_300_000)],
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
    )
    assert result.has_statutory_owner_repair is True
    assert result.apportionment_rule == ApportionmentRule.RULE_D5_50_50
    assert result.common_dues_total == Decimal("4300000")
    assert result.insurer_common_share == Decimal("2150000")
    assert result.owner_common_share == Decimal("2150000")
    assert result.insurer_common_share + result.owner_common_share == result.common_dues_total
    dock = next(ln for ln in result.lines if ln.is_common_dock_charge)
    assert dock.apportionment_rule == ApportionmentRule.RULE_D5_50_50
    # Discrete: hull → UW, SAFE → owner
    assert result.insurer_total == Decimal("450000") + Decimal("2150000")
    assert result.owner_total == Decimal("550000") + Decimal("2150000")
    assert result.insurer_total + result.owner_total == result.claimed_total


def test_case_b_d5_1_deferred_only_100_underwriter():
    """D5 ¶1: casualty_immediate + deferred owners' work only → common dues 100% UW."""
    result = apportion_rule_d(
        [_hull(), _eng_deferred(), _dock(4_300_000)],
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
    )
    assert result.has_statutory_owner_repair is False
    assert result.apportionment_rule == ApportionmentRule.RULE_D5_100_UNDERWRITER
    assert result.insurer_common_share == Decimal("4300000")
    assert result.owner_common_share == Decimal("0")
    assert result.insurer_common_share + result.owner_common_share == result.common_dues_total
    assert result.owner_total == Decimal("1800000")  # ENG only
    assert result.insurer_total == Decimal("450000") + Decimal("4300000")


def test_case_c_d5_2b_deferred_to_routine_5050():
    """D5 ¶2(b): deferred_to_routine → 50/50 even without statutory owner work."""
    result = apportion_rule_d(
        [_hull(), _eng_deferred(), _dock(4_300_000)],
        docking_context=DockingContext.DEFERRED_TO_ROUTINE,
    )
    assert result.has_statutory_owner_repair is False
    assert result.apportionment_rule == ApportionmentRule.RULE_D5_50_50
    assert result.insurer_common_share == Decimal("2150000")
    assert result.owner_common_share == Decimal("2150000")


def test_case_d_dock_fee_injection():
    """Tariff DockFeeBreakdown injects common dues when no DOCK invoice lines."""
    fee = DockFeeBreakdown(
        method=DockFeeMethod.DAILY_LAY,
        currency="USD",
        total=Decimal("4500.00"),
        daily_rate=Decimal("1500.00"),
        dock_days=3,
    )
    result = apportion_rule_d(
        [_hull(), _prop_statutory()],
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
        dock_fee=fee,
    )
    assert result.common_dues_total == Decimal("4500.00")
    assert result.has_statutory_owner_repair is True
    assert result.apportionment_rule == ApportionmentRule.RULE_D5_50_50
    assert result.insurer_common_share == Decimal("2250.00")
    assert result.owner_common_share == Decimal("2250.00")


def test_case_e_dock_separated_from_machinery():
    """Machinery lines must not be half-allocated as common dues."""
    result = apportion_rule_d(
        [_hull(1_000_000), _eng_deferred(2_000_000), _dock(800_000)],
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
    )
    eng = next(ln for ln in result.lines if ln.trade_code.startswith("ENG"))
    hull = next(ln for ln in result.lines if ln.trade_code.startswith("HULL"))
    dock = next(ln for ln in result.lines if ln.is_common_dock_charge)
    assert eng.apportionment_rule == ApportionmentRule.DISCRETE
    assert eng.owner_share == Decimal("2000000")
    assert eng.insurer_share == Decimal("0")
    assert hull.insurer_share == Decimal("1000000")
    assert hull.owner_share == Decimal("0")
    # No statutory → dock 100% UW
    assert dock.insurer_share == Decimal("800000")
    assert dock.owner_share == Decimal("0")


def test_necessity_flag_overrides_trade_prefix():
    """Explicit statutory necessity on ENG triggers ¶2(a) 50/50."""
    eng = RepairLineItem(
        id="eng-stat",
        trade_code="ENG-01",
        cost=Decimal("1000000"),
        necessity=OwnerNecessity.STATUTORY_SEAWORTHINESS,
        work_party=WorkParty.OWNER,
    )
    result = apportion_rule_d(
        [_hull(), eng, _dock(2_000_000)],
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
    )
    assert result.has_statutory_owner_repair is True
    assert result.apportionment_rule == ApportionmentRule.RULE_D5_50_50
    assert result.insurer_common_share == Decimal("1000000")


def test_dock_fee_ignored_when_dock_lines_present():
    fee = DockFeeBreakdown(
        method=DockFeeMethod.GT_LUMP_SUM,
        currency="JPY",
        total=Decimal("999999"),
        lump_sum=Decimal("999999"),
    )
    result = apportion_rule_d(
        [_dock(4_000_000)],
        docking_context=DockingContext.CASUALTY_IMMEDIATE,
        dock_fee=fee,
    )
    assert result.common_dues_total == Decimal("4000000")
    assert all(ln.id != "dock-fee-injected" for ln in result.lines)
