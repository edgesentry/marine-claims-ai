"""
AAA Rules of Practice Rule D5 — drydock common-dues apportionment (DuckDB SQL).

Codifies London AAA Rule D5 (DRY DOCK EXPENSES): shared entering/leaving and
dock dues are 100% underwriter (¶1) or 50/50 owner/underwriter (¶2(a)/¶2(b)).
Regional tariffs enter only via ``DockFeeBreakdown`` parameters — never hardcoded.

See ``docs/aaa_rule_d5_drydock_apportionment.md``.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Sequence

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from marine_claims_ai.adapters.base import DockFeeBreakdown

STATUTORY_OWNER_PREFIXES: tuple[str, ...] = ("SAFE", "PROP")
COMMON_DOCK_PREFIX: str = "DOCK"
SYNTHETIC_DOCK_ID: str = "dock-fee-injected"


class DockingContext(StrEnum):
    """D5 docking situation (required; not inferred from trade codes alone)."""

    CASUALTY_IMMEDIATE = "casualty_immediate"
    DEFERRED_TO_ROUTINE = "deferred_to_routine"


class WorkParty(StrEnum):
    """Who bears a discrete repair line (common dues use trade_code DOCK*)."""

    CASUALTY = "casualty"
    OWNER = "owner"
    COMMON = "common"


class OwnerNecessity(StrEnum):
    """Seaworthiness necessity of owners' account work."""

    STATUTORY_SEAWORTHINESS = "statutory_seaworthiness"
    DEFERRED = "deferred"
    UNSPECIFIED = "unspecified"


class ApportionmentRule(StrEnum):
    """Audit label for how a line was treated."""

    RULE_D5_100_UNDERWRITER = "RULE_D5_100_UNDERWRITER"
    RULE_D5_50_50 = "RULE_D5_50_50"
    DISCRETE = "DISCRETE"


class RepairLineItem(BaseModel):
    """Single tender / repair line for D5 apportionment."""

    model_config = ConfigDict(extra="forbid")

    id: str
    trade_code: str = ""
    cost: Decimal = Field(default=Decimal("0"))
    work_party: WorkParty | None = None
    necessity: OwnerNecessity = OwnerNecessity.UNSPECIFIED
    title: str = ""


class ApportionedLine(BaseModel):
    """Per-line D5 apportionment result."""

    model_config = ConfigDict(extra="forbid")

    id: str
    trade_code: str
    cost: Decimal
    is_common_dock_charge: bool
    insurer_share: Decimal
    owner_share: Decimal
    apportionment_rule: ApportionmentRule
    title: str = ""


class RuleDResult(BaseModel):
    """Aggregate D5 apportionment over a docking."""

    model_config = ConfigDict(extra="forbid")

    docking_context: DockingContext
    has_statutory_owner_repair: bool
    common_dues_total: Decimal
    insurer_common_share: Decimal
    owner_common_share: Decimal
    apportionment_rule: ApportionmentRule
    lines: list[ApportionedLine]
    claimed_total: Decimal
    insurer_total: Decimal
    owner_total: Decimal


def _trade_prefix(trade_code: str) -> str:
    code = (trade_code or "").strip().upper()
    if "-" in code:
        return code.split("-", 1)[0]
    return code


def is_common_dock_charge(trade_code: str) -> bool:
    return _trade_prefix(trade_code) == COMMON_DOCK_PREFIX


def is_statutory_owner_trade(trade_code: str, necessity: OwnerNecessity) -> bool:
    if necessity == OwnerNecessity.STATUTORY_SEAWORTHINESS:
        return True
    return _trade_prefix(trade_code) in STATUTORY_OWNER_PREFIXES


def infer_work_party(item: RepairLineItem) -> WorkParty:
    if item.work_party is not None:
        return item.work_party
    if is_common_dock_charge(item.trade_code):
        return WorkParty.COMMON
    prefix = _trade_prefix(item.trade_code)
    if prefix in STATUTORY_OWNER_PREFIXES or prefix in {"ENG", "VALVE"}:
        return WorkParty.OWNER
    if item.necessity in {
        OwnerNecessity.STATUTORY_SEAWORTHINESS,
        OwnerNecessity.DEFERRED,
    }:
        return WorkParty.OWNER
    return WorkParty.CASUALTY


def _apply_dock_fee_injection(
    items: Sequence[RepairLineItem],
    dock_fee: DockFeeBreakdown | None,
) -> list[RepairLineItem]:
    lines = [RepairLineItem.model_validate(i.model_dump()) for i in items]
    if dock_fee is None:
        return lines
    if any(is_common_dock_charge(i.trade_code) for i in lines):
        return lines
    if dock_fee.total <= 0:
        return lines
    lines.append(
        RepairLineItem(
            id=SYNTHETIC_DOCK_ID,
            trade_code="DOCK-FEE",
            cost=dock_fee.total,
            work_party=WorkParty.COMMON,
            title=f"Injected dock fee ({dock_fee.currency})",
        )
    )
    return lines


def apportion_rule_d(
    items: Sequence[RepairLineItem],
    *,
    docking_context: DockingContext,
    dock_fee: DockFeeBreakdown | None = None,
) -> RuleDResult:
    """
    Apportion drydock common dues per AAA Rule D5 using in-process DuckDB SQL.

    Discrete (non-DOCK) casualty lines → underwriter 100%; owners' account lines →
    owner 100%. Common DOCK lines follow D5 ¶1 / ¶2(a) / ¶2(b).
    """
    prepared = _apply_dock_fee_injection(items, dock_fee)
    if not prepared:
        return RuleDResult(
            docking_context=docking_context,
            has_statutory_owner_repair=False,
            common_dues_total=Decimal("0"),
            insurer_common_share=Decimal("0"),
            owner_common_share=Decimal("0"),
            apportionment_rule=ApportionmentRule.RULE_D5_100_UNDERWRITER,
            lines=[],
            claimed_total=Decimal("0"),
            insurer_total=Decimal("0"),
            owner_total=Decimal("0"),
        )

    rows = []
    for item in prepared:
        party = infer_work_party(item)
        statutory = False
        if party == WorkParty.OWNER:
            statutory = is_statutory_owner_trade(item.trade_code, item.necessity)
        rows.append(
            {
                "id": item.id,
                "trade_code": item.trade_code or "",
                "title": item.title or "",
                "cost": str(item.cost),
                "work_party": party.value,
                "is_common_dock": is_common_dock_charge(item.trade_code),
                "is_statutory_owner": statutory,
            }
        )

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE repair_lines (
                id VARCHAR,
                trade_code VARCHAR,
                title VARCHAR,
                cost DECIMAL(38, 10),
                work_party VARCHAR,
                is_common_dock BOOLEAN,
                is_statutory_owner BOOLEAN
            )
            """
        )
        con.executemany(
            """
            INSERT INTO repair_lines
            VALUES (?, ?, ?, CAST(? AS DECIMAL(38, 10)), ?, ?, ?)
            """,
            [
                (
                    r["id"],
                    r["trade_code"],
                    r["title"],
                    r["cost"],
                    r["work_party"],
                    r["is_common_dock"],
                    r["is_statutory_owner"],
                )
                for r in rows
            ],
        )

        # D5 ¶2(b): deferred routine docking → 50/50 regardless of statutory predicate.
        # D5 ¶2(a): casualty_immediate + statutory owner repair → 50/50.
        # D5 ¶1: casualty_immediate without statutory owner repair → 100% underwriter.
        ctx = docking_context.value
        flags = con.execute(
            """
            SELECT
                COALESCE(BOOL_OR(is_statutory_owner AND work_party = 'owner'), FALSE)
                    AS has_statutory_owner_repair,
                COALESCE(SUM(cost) FILTER (WHERE is_common_dock), 0) AS common_dues_total
            FROM repair_lines
            """
        ).fetchone()
        assert flags is not None
        has_statutory = bool(flags[0])
        apply_5050 = ctx == DockingContext.DEFERRED_TO_ROUTINE.value or (
            ctx == DockingContext.CASUALTY_IMMEDIATE.value and has_statutory
        )
        rule = (
            ApportionmentRule.RULE_D5_50_50
            if apply_5050
            else ApportionmentRule.RULE_D5_100_UNDERWRITER
        )

        result_rows = con.execute(
            """
            WITH params AS (
                SELECT
                    ?::BOOLEAN AS apply_5050,
                    ?::VARCHAR AS dock_rule
            )
            SELECT
                r.id,
                r.trade_code,
                r.title,
                r.cost,
                r.is_common_dock,
                CASE
                    WHEN r.is_common_dock AND p.apply_5050 THEN r.cost * 0.5
                    WHEN r.is_common_dock AND NOT p.apply_5050 THEN r.cost
                    WHEN r.work_party = 'casualty' THEN r.cost
                    ELSE CAST(0 AS DECIMAL(38, 10))
                END AS insurer_share,
                CASE
                    WHEN r.is_common_dock AND p.apply_5050 THEN r.cost * 0.5
                    WHEN r.is_common_dock AND NOT p.apply_5050 THEN CAST(0 AS DECIMAL(38, 10))
                    WHEN r.work_party = 'owner' THEN r.cost
                    ELSE CAST(0 AS DECIMAL(38, 10))
                END AS owner_share,
                CASE
                    WHEN r.is_common_dock THEN p.dock_rule
                    ELSE 'DISCRETE'
                END AS apportionment_rule
            FROM repair_lines r
            CROSS JOIN params p
            ORDER BY r.id
            """,
            [apply_5050, rule.value],
        ).fetchall()
    finally:
        con.close()

    lines: list[ApportionedLine] = []
    for row in result_rows:
        lines.append(
            ApportionedLine(
                id=row[0],
                trade_code=row[1],
                title=row[2] or "",
                cost=Decimal(str(row[3])),
                is_common_dock_charge=bool(row[4]),
                insurer_share=Decimal(str(row[5])),
                owner_share=Decimal(str(row[6])),
                apportionment_rule=ApportionmentRule(row[7]),
            )
        )

    common_total = sum((ln.cost for ln in lines if ln.is_common_dock_charge), Decimal("0"))
    insurer_common = sum(
        (ln.insurer_share for ln in lines if ln.is_common_dock_charge), Decimal("0")
    )
    owner_common = sum((ln.owner_share for ln in lines if ln.is_common_dock_charge), Decimal("0"))
    claimed = sum((ln.cost for ln in lines), Decimal("0"))
    insurer_total = sum((ln.insurer_share for ln in lines), Decimal("0"))
    owner_total = sum((ln.owner_share for ln in lines), Decimal("0"))

    return RuleDResult(
        docking_context=docking_context,
        has_statutory_owner_repair=has_statutory,
        common_dues_total=common_total,
        insurer_common_share=insurer_common,
        owner_common_share=owner_common,
        apportionment_rule=rule,
        lines=lines,
        claimed_total=claimed,
        insurer_total=insurer_total,
        owner_total=owner_total,
    )


# SQL fragment reusable by DuckDB analytics VIEW (default: casualty_immediate).
DRYDOCK_APPORTIONMENT_VIEW_SQL = """
CREATE OR REPLACE VIEW drydock_apportionment AS
WITH repair AS (
    SELECT *
    FROM line_items
    WHERE domain = 'repair'
),
flags AS (
    SELECT
        COALESCE(
            BOOL_OR(
                starts_with(upper(coalesce(trade_code, '')), 'SAFE')
                OR starts_with(upper(coalesce(trade_code, '')), 'PROP')
            ),
            FALSE
        ) AS has_statutory_owner_repair
    FROM repair
)
SELECT
    li.id,
    li.domain,
    li.title,
    li.trade_code,
    li.cost_jpy,
    li.casualty_related,
    CASE
        WHEN li.domain <> 'repair' THEN NULL
        WHEN starts_with(upper(coalesce(li.trade_code, '')), 'DOCK')
            AND f.has_statutory_owner_repair
            THEN CAST(li.cost_jpy AS BIGINT) / 2
        WHEN starts_with(upper(coalesce(li.trade_code, '')), 'DOCK')
            AND NOT f.has_statutory_owner_repair
            THEN li.cost_jpy
        WHEN li.casualty_related THEN li.cost_jpy
        ELSE 0
    END AS insurer_share_jpy,
    CASE
        WHEN li.domain <> 'repair' THEN NULL
        WHEN starts_with(upper(coalesce(li.trade_code, '')), 'DOCK')
            AND f.has_statutory_owner_repair
            THEN CAST(li.cost_jpy AS BIGINT) / 2
        WHEN starts_with(upper(coalesce(li.trade_code, '')), 'DOCK')
            AND NOT f.has_statutory_owner_repair
            THEN 0
        WHEN li.casualty_related THEN 0
        ELSE li.cost_jpy
    END AS owner_share_jpy,
    CASE
        WHEN li.domain <> 'repair' THEN NULL
        WHEN starts_with(upper(coalesce(li.trade_code, '')), 'DOCK')
            AND f.has_statutory_owner_repair
            THEN CAST(li.cost_jpy AS DOUBLE) * 0.5
        ELSE 0
    END AS drydock_fee_5050_jpy
FROM line_items li
CROSS JOIN flags f
"""
