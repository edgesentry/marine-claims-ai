"""Locale-aware Markdown / printable HTML exporters for the demo."""

from __future__ import annotations

import html
from typing import Any

from marine_claims_ai.appraisal.report import render_preliminary_survey_report
from marine_claims_ai.demo.i18n import Lang, status_label, t


def survey_markdown(summary: dict[str, Any], items: list[dict[str, Any]], lang: Lang = "en") -> str:
    if lang == "en":
        return render_preliminary_survey_report(summary, items)
    return _survey_ja(summary, items)


def survey_html(summary: dict[str, Any], items: list[dict[str, Any]], lang: Lang = "en") -> str:
    md = survey_markdown(summary, items, lang)
    return _wrap_html(md, title=t("app_title", lang))


def apportionment_markdown(uc2: dict[str, Any], lang: Lang = "en") -> str:
    if lang == "ja":
        lines = [
            "# AAA Rule D5 按分ステートメント（予備）",
            "",
            f"- 按分ルール: `{uc2.get('rule')}`",
            f"- 共通入渠費合計: ¥{int(uc2.get('dock_total') or 0):,}",
            f"- 保険者負担（共通）: ¥{int(uc2.get('insurer_common') or 0):,}",
            f"- 船主負担（共通）: ¥{int(uc2.get('owner_common') or 0):,}",
            f"- 休航短縮日数: {uc2.get('days_saved')}",
            f"- 休航損失回避額: ¥{int(uc2.get('offhire_jpy') or 0):,}",
            "",
            "## 明細",
            "",
            "| ID | 摘要 | 費用 | 保険者 | 船主 | ルール |",
            "| :--- | :--- | ---: | ---: | ---: | :--- |",
        ]
    else:
        lines = [
            "# AAA Rule D5 Apportionment Statement (Preliminary)",
            "",
            f"- Rule: `{uc2.get('rule')}`",
            f"- Common dock dues total: JPY {int(uc2.get('dock_total') or 0):,}",
            f"- Insurer common share: JPY {int(uc2.get('insurer_common') or 0):,}",
            f"- Owner common share: JPY {int(uc2.get('owner_common') or 0):,}",
            f"- Days saved (off-hire heuristic): {uc2.get('days_saved')}",
            f"- Off-hire avoided: JPY {int(uc2.get('offhire_jpy') or 0):,}",
            "",
            "## Line items",
            "",
            "| ID | Title | Cost | Insurer | Owner | Rule |",
            "| :--- | :--- | ---: | ---: | ---: | :--- |",
        ]
    for row in uc2.get("line_rows") or []:
        lines.append(
            f"| {row['id']} | {row['title']} | {row['cost']:,} | "
            f"{row['insurer']:,} | {row['owner']:,} | `{row['rule']}` |"
        )
    lines.extend(
        [
            "",
            "> Final indemnity remains with the appointed surveyor / claims adjuster.",
            "",
        ]
    )
    return "\n".join(lines)


def apportionment_html(uc2: dict[str, Any], lang: Lang = "en") -> str:
    return _wrap_html(apportionment_markdown(uc2, lang), title=t("uc2_title", lang))


def colregs_survey_markdown(uc3: dict[str, Any], lang: Lang = "en") -> str:
    if lang == "ja":
        lines = [
            "# 予備調査・航法過失割合メモ",
            "",
            f"**案件:** {uc3.get('title')}",
            f"**局面:** {uc3.get('situation_label')} (`{uc3.get('situation')}`)",
            f"**本船:** {uc3.get('role_a_label')}",
            f"**相手船:** {uc3.get('role_b_label')}",
            f"**過失割合:** {uc3.get('fault_ratio')}",
            f"**相対方位:** {uc3.get('relative_bearing')}°",
            "",
            "## 条文",
            "",
        ]
        for c in uc3.get("rule_citations") or []:
            lines.append(f"- {c}")
        lines.extend(["", "## 事実", "", uc3.get("facts") or "—", "", "## 裁決・判示", "", uc3.get("ruling") or "—", ""])
    else:
        lines = [
            "# Preliminary COLREGS Fault Evidence Memo",
            "",
            f"**Case:** {uc3.get('title')}",
            f"**Situation:** {uc3.get('situation_label')} (`{uc3.get('situation')}`)",
            f"**Own vessel (A):** {uc3.get('role_a_label')}",
            f"**Target (B):** {uc3.get('role_b_label')}",
            f"**Fault ratio:** {uc3.get('fault_ratio')}",
            f"**Relative bearing A→B:** {uc3.get('relative_bearing')}°",
            "",
            "## Rule citations",
            "",
        ]
        for c in uc3.get("rule_citations") or []:
            lines.append(f"- {c}")
        lines.extend(["", "## Facts", "", uc3.get("facts") or "—", "", "## Ruling / holding", "", uc3.get("ruling") or "—", ""])
    lines.extend(
        [
            "",
            "> Deterministic COLREGS geometry + heuristic fault blend. Subject to surveyor confirmation.",
            "",
        ]
    )
    return "\n".join(lines)


def colregs_survey_html(uc3: dict[str, Any], lang: Lang = "en") -> str:
    return _wrap_html(colregs_survey_markdown(uc3, lang), title=t("uc3_title", lang))


def _survey_ja(summary: dict[str, Any], items: list[dict[str, Any]]) -> str:
    cp = summary.get("casualty_profile") or {}
    claimed = int(summary.get("total_claimed_jpy") or 0)
    approved = int(summary.get("total_approved_jpy") or 0)
    excluded = int(summary.get("total_excluded_jpy") or 0)
    rate = summary.get("leakage_prevention_rate_pct")
    lines = [
        "# 予備調査・クレーム調整報告書",
        "",
        "**作成:** MarineClaims AI（決定論的同時修理スクリーニング）  ",
        "**地位:** 予備 — 鑑定人／損害査定人の確認を要する",
        "",
        "## 1. 事故概要",
        "",
        "| 項目 | 値 |",
        "| :--- | :--- |",
        f"| 船舶 | {cp.get('vessel_name', 'N/A')} |",
        f"| 事故類型 | {cp.get('incident_type', 'N/A')} |",
        f"| 日時 / 場所 | {cp.get('incident_date', 'N/A')} / {cp.get('incident_location', 'N/A')} |",
        f"| 損傷区画 | {', '.join(cp.get('damaged_components') or []) or 'N/A'} |",
        "",
        "## 2. 財務サマリ",
        "",
        "| 指標 | 円 |",
        "| :--- | ---: |",
        f"| 請求合計（モデル） | {claimed:,} |",
        f"| 承認 / 按分 | {approved:,} |",
        f"| 除外（漏出防止） | {excluded:,} |",
        f"| 除外率 | {rate}% |",
        "",
        "## 3. 明細",
        "",
        "| ステータス | 摘要 | 金額 | 理由 |",
        "| :--- | :--- | ---: | :--- |",
    ]
    for it in items:
        st = str(it.get("status") or "")
        lines.append(
            f"| {status_label(st, 'ja')} | "
            f"{(it.get('description') or '')[:80]} | "
            f"{int(it.get('estimated_cost') or 0):,} | "
            f"{(it.get('reason') or '')[:60]} |"
        )
    lines.extend(
        [
            "",
            "## 4. 方法論メモ",
            "",
            "- 因果は船体区画グラフ（水密隔壁 / 隣接制約）でゲートする。",
            "- 最終的な填補判断は任命された鑑定人／損害査定人に帰属する。",
            "",
        ]
    )
    return "\n".join(lines)


def _wrap_html(markdown_text: str, *, title: str) -> str:
    # Minimal printable HTML: escape and preserve newlines as <pre>-like blocks.
    body = html.escape(markdown_text)
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:Georgia,serif;max-width:820px;margin:2rem auto;"
        "line-height:1.45;color:#122} pre{white-space:pre-wrap;font-family:ui-monospace,monospace;"
        "font-size:0.92rem}</style></head><body>"
        f"<h1>{html.escape(title)}</h1><pre>{body}</pre>"
        "<p><em>Print this page to PDF from the browser.</em></p>"
        "</body></html>"
    )
