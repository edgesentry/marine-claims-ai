"""EN/JA message catalog for the interactive demo (no gettext)."""

from __future__ import annotations

from typing import Literal

Lang = Literal["en", "ja"]

MESSAGES: dict[str, dict[Lang, str]] = {
    "app_title": {
        "en": "MarineClaims AI — Executive Demo",
        "ja": "MarineClaims AI — エグゼクティブデモ",
    },
    "nav_uc2": {"en": "1. Rule D5", "ja": "1. Rule D5 按分"},
    "nav_uc3": {"en": "2. COLREGS", "ja": "2. COLREGS 航法"},
    "lang_en": {"en": "English", "ja": "English"},
    "lang_ja": {"en": "日本語", "ja": "日本語"},
    "clear_cache": {"en": "Clear cache", "ja": "キャッシュクリア"},
    "clear_cache_confirm": {
        "en": "Clear demo analysis results, PDF page images, and uploads? Source PDFs are kept.",
        "ja": "デモの査定結果・PDFページ画像・アップロードを削除しますか？（元の公開PDFは残します）",
    },
    "cache_cleared": {
        "en": "Demo cache cleared. Run analysis again to refresh results.",
        "ja": "キャッシュをクリアしました。結果を出すには再度「この書類で査定する」を実行してください。",
    },
    "offline_badge": {
        "en": "Offline-ready · local engines only",
        "ja": "オフライン対応 · ローカルエンジンのみ",
    },
    "err_pdftotext": {
        "en": "A PDF text extraction tool (pdftotext) is required on this computer.",
        "ja": "このコンピュータに PDF の文字を読み取るツール（pdftotext）が必要です。",
    },
    "err_pdf_missing": {
        "en": "The selected PDF was not found. Place it under _data/poc_datasets/ or open a file.",
        "ja": "選択した PDF が見つかりません。_data/poc_datasets/ に置くか、ファイルを開いてください。",
    },
    "err_parse_failed": {
        "en": "Could not read the document. Check that it is a readable PDF.",
        "ja": "書類を読み取れませんでした。読める PDF かご確認ください。",
    },
    "err_no_line_items": {
        "en": "No repair line items were found in this specification PDF.",
        "ja": "この修繕仕様 PDF から工事明細を抽出できませんでした。",
    },
    "err_pdf_empty_text": {
        "en": "No text could be extracted from this PDF (it may be image-only).",
        "ja": "この PDF から文字を取り出せませんでした（画像のみの可能性）。",
    },
    "err_no_colregs_cases": {
        "en": "No collision cases available.",
        "ja": "衝突ケースがありません。",
    },
    "err_upload_failed": {
        "en": "Could not open that file.",
        "ja": "そのファイルを開けませんでした。",
    },
    "doc_spec": {"en": "Repair specification (PDF)", "ja": "修繕仕様書（PDF）"},
    "analyzed_ok": {
        "en": "Analysis finished. Results are shown below.",
        "ja": "解析が完了しました。下に結果を表示しています。",
    },
    "source_docs": {"en": "Source documents", "ja": "入力書類"},
    "open_pdf": {"en": "View document", "ja": "書類を見る"},
    "pdf_text_preview": {"en": "Extracted text", "ja": "抽出テキスト"},
    "pdf_embed_title": {"en": "Original document", "ja": "原本"},
    "pdf_pages_hint": {
        "en": "First pages rendered for reliable on-screen review.",
        "ja": "画面上で確実に確認できるよう、先頭ページを画像化しています。",
    },
    "pdf_page_label": {"en": "Page", "ja": "ページ"},
    "pdf_embed_hint": {
        "en": "If this pane is blank, use “Open original” or “Download” above (some browsers block in-page PDF viewing).",
        "ja": "ここに何も出ない場合は、上の「原本を開く」または「ダウンロード」を使ってください（ブラウザによってはページ内表示できません）。",
    },
    "pdf_open_native": {"en": "Open original PDF", "ja": "原本PDFを開く"},
    "pdf_download": {"en": "Download", "ja": "ダウンロード"},
    "pdf_no_text": {
        "en": "(No extractable text — the PDF may be image-only.)",
        "ja": "（抽出できる文字がありません。画像のみの PDF の可能性があります。）",
    },
    "from_document": {"en": "Result from live document analysis", "ja": "書類をその場で解析した結果"},
    "uc2_explain_usecase": {
        "en": "Split common drydock dues under AAA Rule D5 and estimate off-hire avoided by faster screening.",
        "ja": "AAA Rule D5 で共通入渠費を按分し、予審短縮による休航損失回避額を見積もる。",
    },
    "uc2_explain_input": {
        "en": "Drydock / repair specification PDF (list or open file), plus dock rate, days, and docking context.",
        "ja": "入渠・修繕仕様 PDF（リストまたはファイルを開く）と、入渠日額・日数・入渠の事情。",
    },
    "uc2_explain_process": {
        "en": "Extract works from the PDF, classify casualty vs owner's vs common dues, then apply Rule D5 (50/50 or 100% underwriter) and off-hire estimate.",
        "ja": "PDF から工事を抽出し、事故復旧／船主工事／共通入渠費に分け、Rule D5（50/50 または保険者100%）と休航回避額を計算する。",
    },
    "uc2_explain_output": {
        "en": "How dues are split, insurer/owner shares, timeline, off-hire estimate, statement export.",
        "ja": "按分の仕方、保険者／船主負担、タイムライン、休航回避額、ステートメント出力。",
    },
    "uc3_explain_usecase": {
        "en": "Read a collision ruling or report, classify the encounter (Rules 13–15), and show fault-ratio evidence.",
        "ja": "衝突の裁決・報告を読み、局面（第13–15条）を分類し、過失割合の根拠を示す。",
    },
    "uc3_explain_input": {
        "en": "Tribunal / court / casualty PDF (list or open file), optional heading/bearing overrides.",
        "ja": "審判・判決・事故報告 PDF（リストまたはファイルを開く）。必要なら針路・方位を調整。",
    },
    "uc3_explain_process": {
        "en": "Extract text and navigational facts, classify crossing / head-on / overtaking, estimate fault ratio.",
        "ja": "本文と航法事実を取り出し、横切・行会い・追越しを判定し、過失割合を見積もる。",
    },
    "uc3_explain_output": {
        "en": "Situation, give-way / stand-on roles, fault ratio, radar sketch, memo export.",
        "ja": "局面、避航／保持の役割、過失割合、レーダー概略、メモ出力。",
    },
    "status_covered": {"en": "Covered", "ja": "補償対象"},
    "status_apportioned": {"en": "Apportioned", "ja": "按分"},
    "status_excluded": {"en": "Excluded", "ja": "除外"},
    "status_review": {"en": "Needs review", "ja": "要確認"},
    "node_hull_forward": {"en": "Forward hull", "ja": "船首区画"},
    "node_hull_mid": {"en": "Mid hull", "ja": "中央区画"},
    "node_hull_aft": {"en": "Aft hull", "ja": "船尾区画"},
    "node_deck_forward": {"en": "Fwd deck", "ja": "船首甲板"},
    "node_deck_mid": {"en": "Mid deck", "ja": "中央甲板"},
    "node_deck_aft": {"en": "Aft deck", "ja": "船尾甲板"},
    "node_superstructure": {"en": "Superstructure", "ja": "上部構造"},
    "node_propulsion": {"en": "Propulsion", "ja": "推進器"},
    "node_machinery": {"en": "Machinery (isolated)", "ja": "機関室（孤立）"},
    "uc2_lead": {
        "en": "Open a drydock repair PDF, split common dues under Rule D5, and estimate avoided off-hire.",
        "ja": "入渠・修繕の PDF を開き、Rule D5 で共通入渠費を按分し、休航損失回避額を見積もります。",
    },
    "daily_dock_rate": {"en": "Dock daily rate (JPY/day)", "ja": "入渠日額（円/日）"},
    "dock_days": {"en": "Dock days", "ja": "滞渠日数"},
    "hire_rate": {"en": "Daily hire / off-hire rate (JPY/day)", "ja": "休航日額（円/日）"},
    "legacy_lead_days": {"en": "Traditional claims lead time (days)", "ja": "従来の査定リードタイム（日）"},
    "ai_lead_minutes": {"en": "AI pre-approval (minutes)", "ja": "AI予審（分）"},
    "common_dues": {"en": "Common dock dues", "ja": "共通入渠費"},
    "insurer_share": {"en": "Insurer share", "ja": "保険者負担"},
    "owner_share": {"en": "Owner share", "ja": "船主負担"},
    "rule_label": {"en": "How common dock dues are split", "ja": "共通入渠費の分け方"},
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
        "en": "Open a ruling or casualty PDF, classify Rules 13–15, and export an audit-ready draft.",
        "ja": "裁決・事故報告の PDF を開き、第13–15条を分類し、監査可能な査定ドラフトを出力します。",
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
    "explain_usecase": {"en": "Use case", "ja": "ユースケース"},
    "explain_input": {"en": "Inputs", "ja": "入力"},
    "explain_process": {"en": "Processing", "ja": "処理"},
    "explain_output": {"en": "Outputs", "ja": "出力"},
    "docs_link": {"en": "Full write-up", "ja": "詳細ドキュメント"},
    "try_conditions": {"en": "Change conditions", "ja": "条件を変える"},
    "docking_context": {"en": "Why the vessel entered drydock", "ja": "入渠の事情"},
    "ctx_immediate": {"en": "Entered right after the casualty", "ja": "事故の直後に入渠"},
    "ctx_deferred": {"en": "Deferred to a routine docking", "ja": "定期入渠へ繰延"},
    "include_statutory": {"en": "Include statutory / seaworthiness owner's work", "ja": "法定・堪航性の船主工事を含める"},
    "heading_a": {"en": "Heading A (deg)", "ja": "本船針路 A（度）"},
    "heading_b": {"en": "Heading B (deg)", "ja": "相手針路 B（度）"},
    "bearing_ab": {"en": "True bearing A→B (deg)", "ja": "真方位 A→B（度）"},
    "geometry_override": {"en": "Adjust encounter angles", "ja": "局面の角度を調整"},
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
