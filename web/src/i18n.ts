/**
 * EN/JA message catalog (port of demo/i18n.py).
 */

export type Lang = "en" | "ja";

const MESSAGES: Record<string, Record<Lang, string>> = {
  app_title: {
    en: "MarineClaims AI — Executive Demo",
    ja: "MarineClaims AI — エグゼクティブデモ",
  },
  nav_uc2: { en: "1. Rule D5", ja: "1. Rule D5 按分" },
  nav_uc3: { en: "2. COLREGS", ja: "2. COLREGS 航法" },
  lang_en: { en: "English", ja: "English" },
  lang_ja: { en: "日本語", ja: "日本語" },
  pwa_install_btn: { en: "Install App", ja: "アプリをインストール" },
  uc2_lead: {
    en: "Open a drydock repair PDF, split common dues under Rule D5, and estimate avoided off-hire.",
    ja: "入渠・修繕の PDF を開き、Rule D5 で共通入渠費を按分し、休航損失回避額を見積もります。",
  },
  uc3_lead: {
    en: "Open a ruling or casualty PDF, classify Rules 13–15, and export an audit-ready draft.",
    ja: "裁決・事故報告の PDF を開き、第13–15条を分類し、監査可能な査定ドラフトを出力します。",
  },
  daily_dock_rate: { en: "Dock daily rate (JPY/day)", ja: "入渠日額（円/日）" },
  dock_days: { en: "Dock days", ja: "滞渠日数" },
  hire_rate: { en: "Daily hire / off-hire rate (JPY/day)", ja: "休航日額（円/日）" },
  legacy_lead_days: { en: "Traditional claims lead time (days)", ja: "従来の査定リードタイム（日）" },
  ai_lead_minutes: { en: "AI pre-approval (minutes)", ja: "AI予審（分）" },
  docking_context: { en: "Why the vessel entered drydock", ja: "入渠の事情" },
  ctx_immediate: { en: "Entered right after the casualty", ja: "事故の直後に入渠" },
  ctx_deferred: { en: "Deferred to a routine docking", ja: "定期入渠へ繰延" },
  include_statutory: {
    en: "Include statutory / seaworthiness owner's work",
    ja: "法定・堪航性の船主工事を含める",
  },
  common_dues: { en: "Common dock dues", ja: "共通入渠費" },
  insurer_share: { en: "Insurer share", ja: "保険者負担" },
  owner_share: { en: "Owner share", ja: "船主負担" },
  rule_label: { en: "How common dock dues are split", ja: "共通入渠費の分け方" },
  gantt_title: { en: "Drydock timeline", ja: "入渠タイムライン" },
  lane_casualty: { en: "Casualty repairs", ja: "事故復旧工事" },
  lane_owner: { en: "Owner's work", ja: "オーナー工事" },
  lane_common: { en: "Common dock dues", ja: "共通入渠費" },
  offhire_title: { en: "Avoided off-hire", ja: "回避した休航損失" },
  days_saved: { en: "Days saved", ja: "短縮日数" },
  offhire_saved: { en: "Off-hire avoided (JPY)", ja: "休航損失回避額（円）" },
  export_apportion_md: {
    en: "Download apportionment (Markdown)",
    ja: "按分ステートメント（Markdown）",
  },
  export_apportion_html: {
    en: "Download apportionment (HTML / print-PDF)",
    ja: "按分ステートメント（HTML / 印刷PDF）",
  },
  select_case: { en: "Collision case", ja: "衝突ケース" },
  situation: { en: "Situation", ja: "局面" },
  role_a: { en: "Own vessel (A)", ja: "本船（A）" },
  role_b: { en: "Target (B)", ja: "相手船（B）" },
  fault_ratio: { en: "Fault ratio", ja: "過失割合" },
  article: { en: "Rule / Article", ja: "条文" },
  facts: { en: "Facts", ja: "事実" },
  ruling: { en: "Ruling / holding", ja: "裁決・判示" },
  radar_title: { en: "Relative radar scope", ja: "相対レーダースコープ" },
  heading_a: { en: "Heading A (deg)", ja: "本船針路 A（度）" },
  heading_b: { en: "Heading B (deg)", ja: "相手針路 B（度）" },
  bearing_ab: { en: "True bearing A→B (deg)", ja: "真方位 A→B（度）" },
  geometry_override: { en: "Adjust encounter angles", ja: "局面の角度を調整" },
  sit_crossing: { en: "Crossing", ja: "横切" },
  sit_head_on: { en: "Head-on", ja: "行会い" },
  sit_overtaking: { en: "Overtaking", ja: "追越し" },
  sit_safe_passing: { en: "Safe passing", ja: "安全航行" },
  role_give_way: { en: "Give-way", ja: "避航船" },
  role_stand_on: { en: "Stand-on", ja: "保持船" },
  explain_usecase: { en: "Use case", ja: "ユースケース" },
  explain_input: { en: "Inputs", ja: "入力" },
  explain_process: { en: "Processing", ja: "処理" },
  explain_output: { en: "Outputs", ja: "出力" },
  uc2_explain_usecase: {
    en: "Split common drydock dues under AAA Rule D5 and estimate off-hire avoided by faster screening.",
    ja: "AAA Rule D5 で共通入渠費を按分し、予審短縮による休航損失回避額を見積もる。",
  },
  uc2_explain_input: {
    en: "Drydock / repair specification PDF plus dock rate, days, and docking context.",
    ja: "入渠・修繕仕様 PDF と、入渠日額・日数・入渠の事情。",
  },
  uc2_explain_process: {
    en: "Extract works from the PDF, classify casualty vs owner's vs common dues, then apply Rule D5.",
    ja: "PDF から工事を抽出し、事故復旧／船主工事／共通入渠費に分け、Rule D5 を適用する。",
  },
  uc2_explain_output: {
    en: "How dues are split, insurer/owner shares, timeline, off-hire estimate, statement export.",
    ja: "按分の仕方、保険者／船主負担、タイムライン、休航回避額、ステートメント出力。",
  },
  uc3_explain_usecase: {
    en: "Read a collision ruling or report, classify the encounter (Rules 13–15), and show fault-ratio evidence.",
    ja: "衝突の裁決・報告を読み、局面（第13–15条）を分類し、過失割合の根拠を示す。",
  },
  uc3_explain_input: {
    en: "Tribunal / court / casualty PDF, optional heading/bearing overrides.",
    ja: "審判・判決・事故報告 PDF。必要なら針路・方位を調整。",
  },
  uc3_explain_process: {
    en: "Extract text and navigational facts, classify crossing / head-on / overtaking, estimate fault ratio.",
    ja: "本文と航法事実を取り出し、横切・行会い・追越しを判定し、過失割合を見積もる。",
  },
  uc3_explain_output: {
    en: "Situation, give-way / stand-on roles, fault ratio, radar sketch, memo export.",
    ja: "局面、避航／保持の役割、過失割合、レーダー概略、メモ出力。",
  },
  drop_pdf: { en: "Drop a PDF here or click to open", ja: "PDF をドロップ、またはクリックして開く" },
  analyze: { en: "Analyze", ja: "査定する" },
  use_synthetic: { en: "Use synthetic demo lines", ja: "合成デモ明細を使う" },
  export_colregs_md: { en: "Download memo (Markdown)", ja: "メモ（Markdown）" },
  export_colregs_html: { en: "Download memo (HTML)", ja: "メモ（HTML）" },
  err_pdf_empty_text: {
    en: "No text could be extracted from this PDF (it may be image-only).",
    ja: "この PDF から文字を取り出せませんでした（画像のみの可能性）。",
  },
  err_no_line_items: {
    en: "No repair line items were found in this specification PDF.",
    ja: "この修繕仕様 PDF から工事明細を抽出できませんでした。",
  },
  analyzed_ok: {
    en: "Analysis finished. Results are shown below.",
    ja: "解析が完了しました。下に結果を表示しています。",
  },
};

export function t(key: string, lang: Lang = "en"): string {
  const entry = MESSAGES[key];
  if (!entry) return key;
  return entry[lang] || entry.en || key;
}

export function situationLabel(situation: string, lang: Lang): string {
  const mapping: Record<string, string> = {
    crossing: "sit_crossing",
    head_on: "sit_head_on",
    overtaking: "sit_overtaking",
    safe_passing: "sit_safe_passing",
  };
  const key = mapping[situation.toLowerCase()];
  return key ? t(key, lang) : situation;
}

export function roleLabel(role: string | null | undefined, lang: Lang): string {
  if (!role) return "—";
  const mapping: Record<string, string> = {
    give_way: "role_give_way",
    stand_on: "role_stand_on",
  };
  const key = mapping[role.toLowerCase()];
  return key ? t(key, lang) : role;
}
