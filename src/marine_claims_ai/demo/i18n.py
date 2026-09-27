"""EN/JA message catalog for the interactive demo (no gettext)."""

from __future__ import annotations

from typing import Literal

Lang = Literal["en", "ja"]

MESSAGES: dict[str, dict[Lang, str]] = {
    "app_title": {
        "en": "MarineClaims AI — Executive Demo",
        "ja": "MarineClaims AI — エグゼクティブデモ",
    },
    "nav_uc1": {"en": "1. Topology", "ja": "1. 区画トポロジー"},
    "nav_uc2": {"en": "2. Rule D5", "ja": "2. Rule D5 按分"},
    "nav_uc3": {"en": "3. COLREGS", "ja": "3. COLREGS 航法"},
    "lang_en": {"en": "English", "ja": "English"},
    "lang_ja": {"en": "日本語", "ja": "日本語"},
    "offline_badge": {
        "en": "Offline-ready · local engines only",
        "ja": "オフライン対応 · ローカルエンジンのみ",
    },
    "uc1_title": {
        "en": "Watertight bulkhead topology & owner's work exclusion",
        "ja": "水密隔壁トポロジーと便乗修理の排斥",
    },
    "uc1_lead": {
        "en": "Public Kaiyo Maru repair specification screened against bow-collision damage zones.",
        "ja": "公開・開洋丸修繕仕様を船首衝突の損傷区画に対して自動仕分けします。",
    },
    "metric_items": {"en": "Line items", "ja": "明細数"},
    "metric_claimed": {"en": "Claimed (model)", "ja": "請求額（モデル）"},
    "metric_excluded": {"en": "Excluded", "ja": "除外額"},
    "metric_rate": {"en": "Exclusion rate", "ja": "除外率"},
    "compartment_graph": {"en": "Compartment graph", "ja": "区画グラフ"},
    "line_items": {"en": "Screened line items", "ja": "仕分け明細"},
    "status": {"en": "Status", "ja": "ステータス"},
    "description": {"en": "Description", "ja": "摘要"},
    "amount": {"en": "Amount (JPY)", "ja": "金額（円）"},
    "reason": {"en": "Reason", "ja": "理由"},
    "export_survey_md": {"en": "Download survey (Markdown)", "ja": "査定ドラフト（Markdown）"},
    "export_survey_html": {"en": "Download survey (HTML / print-PDF)", "ja": "査定ドラフト（HTML / 印刷PDF）"},
    "data_missing": {
        "en": "Cached analysis not found under _data/poc_datasets/. Run the appraisal pipeline or copy claims_analysis_kaiyomaru.json.",
        "ja": "_data/poc_datasets/ にキャッシュがありません。査定パイプラインを実行するか claims_analysis_kaiyomaru.json を配置してください。",
    },
    "status_covered": {"en": "COVERED", "ja": "補償対象"},
    "status_apportioned": {"en": "APPORTIONED", "ja": "按分"},
    "status_excluded": {"en": "EXCLUDED", "ja": "除外"},
    "status_review": {"en": "REVIEW", "ja": "要確認"},
    "node_hull_forward": {"en": "Forward hull", "ja": "船首区画"},
    "node_hull_mid": {"en": "Mid hull", "ja": "中央区画"},
    "node_hull_aft": {"en": "Aft hull", "ja": "船尾区画"},
    "node_deck_forward": {"en": "Fwd deck", "ja": "船首甲板"},
    "node_deck_mid": {"en": "Mid deck", "ja": "中央甲板"},
    "node_deck_aft": {"en": "Aft deck", "ja": "船尾甲板"},
    "node_superstructure": {"en": "Superstructure", "ja": "上部構造"},
    "node_propulsion": {"en": "Propulsion", "ja": "推進器"},
    "node_machinery": {"en": "Machinery (isolated)", "ja": "機関室（孤立）"},
    "damaged": {"en": "Damaged", "ja": "損傷"},
    "isolated": {"en": "Watertight barrier", "ja": "水密隔壁"},
    "normal": {"en": "Adjacent", "ja": "隣接"},
    "uc2_title": {
        "en": "AAA Rule D5 dual-causality apportionment & off-hire simulator",
        "ja": "AAA Rule D5 二重因果按分と休航損失シミュレータ",
    },
    "uc2_lead": {
        "en": "Live 50/50 common-dues split and avoided off-hire from faster pre-approval.",
        "ja": "共通入渠費の50/50按分と、予審短縮による休航損失回避額をライブ計算します。",
    },
    "daily_dock_rate": {"en": "Dock daily rate (JPY/day)", "ja": "入渠日額（円/日）"},
    "dock_days": {"en": "Dock days", "ja": "滞渠日数"},
    "hire_rate": {"en": "Daily hire / off-hire rate (JPY/day)", "ja": "休航日額（円/日）"},
    "legacy_lead_days": {"en": "Traditional claims lead time (days)", "ja": "従来の査定リードタイム（日）"},
    "ai_lead_minutes": {"en": "AI pre-approval (minutes)", "ja": "AI予審（分）"},
    "common_dues": {"en": "Common dock dues", "ja": "共通入渠費"},
    "insurer_share": {"en": "Insurer share", "ja": "保険者負担"},
    "owner_share": {"en": "Owner share", "ja": "船主負担"},
    "rule_label": {"en": "Apportionment rule", "ja": "按分ルール"},
    "gantt_title": {"en": "Drydock timeline", "ja": "入渠タイムライン"},
    "lane_casualty": {"en": "Casualty repairs", "ja": "事故復旧工事"},
    "lane_owner": {"en": "Owner's work", "ja": "オーナー工事"},
    "lane_common": {"en": "Common dock dues", "ja": "共通入渠費"},
    "offhire_title": {"en": "Avoided off-hire", "ja": "回避した休航損失"},
    "days_saved": {"en": "Days saved", "ja": "短縮日数"},
    "offhire_saved": {"en": "Off-hire avoided (JPY)", "ja": "休航損失回避額（円）"},
    "export_apportion_md": {"en": "Download apportionment (Markdown)", "ja": "按分ステートメント（Markdown）"},
    "export_apportion_html": {
        "en": "Download apportionment (HTML / print-PDF)",
        "ja": "按分ステートメント（HTML / 印刷PDF）",
    },
    "uc3_title": {
        "en": "COLREGS radar scope & fault-ratio evidence",
        "ja": "COLREGS レーダースコープと過失割合の客観証拠",
    },
    "uc3_lead": {
        "en": "Select a fixture case, classify Rules 13–15, and export an audit-ready draft.",
        "ja": "fixture 案件を選び、第13–15条を分類し、監査可能な査定ドラフトを出力します。",
    },
    "select_case": {"en": "Collision case", "ja": "衝突ケース"},
    "situation": {"en": "Situation", "ja": "局面"},
    "role_a": {"en": "Own vessel (A)", "ja": "本船（A）"},
    "role_b": {"en": "Target (B)", "ja": "相手船（B）"},
    "fault_ratio": {"en": "Fault ratio", "ja": "過失割合"},
    "article": {"en": "Rule / Article", "ja": "条文"},
    "facts": {"en": "Facts", "ja": "事実"},
    "ruling": {"en": "Ruling / holding", "ja": "裁決・判示"},
    "radar_title": {"en": "Relative radar scope", "ja": "相対レーダースコープ"},
    "own_vessel": {"en": "Own vessel", "ja": "本船"},
    "target_vessel": {"en": "Target", "ja": "相手船"},
    "overtaking_sector": {"en": "Overtaking sector 112.5°–247.5°", "ja": "追越し扇形 112.5°–247.5°"},
    "head_on_band": {"en": "Head-on ±5°", "ja": "行会い ±5°"},
    "sit_crossing": {"en": "Crossing", "ja": "横切"},
    "sit_head_on": {"en": "Head-on", "ja": "行会い"},
    "sit_overtaking": {"en": "Overtaking", "ja": "追越し"},
    "sit_safe_passing": {"en": "Safe passing", "ja": "安全航行"},
    "role_give_way": {"en": "Give-way", "ja": "避航船"},
    "role_stand_on": {"en": "Stand-on", "ja": "保持船"},
    "show_all_items": {"en": "Show all line items", "ja": "全明細を表示"},
    "show_sample": {"en": "Showing sample of excluded items", "ja": "除外明細のサンプル表示"},
}

ZONE_KEYS = {
    "hull_forward": "node_hull_forward",
    "hull_mid": "node_hull_mid",
    "hull_aft": "node_hull_aft",
    "deck_forward": "node_deck_forward",
    "deck_mid": "node_deck_mid",
    "deck_aft": "node_deck_aft",
    "superstructure": "node_superstructure",
    "propulsion": "node_propulsion",
    "machinery": "node_machinery",
}


def t(key: str, lang: Lang = "en") -> str:
    """Return localized string; missing keys fall back to the key name."""
    entry = MESSAGES.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get("en") or key


def zone_label(node: str, lang: Lang = "en") -> str:
    key = ZONE_KEYS.get(node)
    return t(key, lang) if key else node


def status_label(status: str, lang: Lang = "en") -> str:
    s = (status or "").upper()
    if "COVERED" in s:
        return t("status_covered", lang)
    if "APPORTIONED" in s:
        return t("status_apportioned", lang)
    if "EXCLUDED" in s:
        return t("status_excluded", lang)
    if "REVIEW" in s:
        return t("status_review", lang)
    return status or "—"


def situation_label(situation: str, lang: Lang = "en") -> str:
    mapping = {
        "crossing": "sit_crossing",
        "head_on": "sit_head_on",
        "overtaking": "sit_overtaking",
        "safe_passing": "sit_safe_passing",
    }
    key = mapping.get((situation or "").lower())
    return t(key, lang) if key else situation


def role_label(role: str | None, lang: Lang = "en") -> str:
    if not role:
        return "—"
    mapping = {"give_way": "role_give_way", "stand_on": "role_stand_on"}
    key = mapping.get(role.lower())
    return t(key, lang) if key else role
