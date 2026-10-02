"""DuckDB financial apportionment analytics (AAA Rule D5 SQL view helpers).

Runtime Rule D5 apportionment lives in ``web/src/engines/ruleD5.ts``.
This module only hosts the DuckDB VIEW SQL used by ``index.build``.
"""

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
