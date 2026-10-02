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
  nav_psc: { en: "3. PSC", ja: "3. PSC 耐航性" },
  lang_en: { en: "English", ja: "English" },
  lang_ja: { en: "日本語", ja: "日本語" },
  lang_label: { en: "Language", ja: "言語" },
  pwa_install_btn: { en: "Install App", ja: "アプリをインストール" },
  uc2_lead: {
    en: "Try the docking conditions and a repair PDF below to draft that statement here.",
    ja: "下の入渠条件と修繕 PDF で、その下書きをこの場で作れます。",
  },
  uc3_lead: {
    en: "Open a ruling or casualty PDF below, adjust headings if needed, and draft that COLREGS memo here.",
    ja: "下の裁決・事故報告 PDF を開き、必要なら針路を調整して、その航法メモをこの場で作れます。",
  },
  psc_lead: {
    en: "Pick a public MOU-style fixture, drop a PSC PDF/HTML, or paste a deficiency list — then draft an underwriter screening memo here.",
    ja: "公開の MOU 型フィクスチャを選ぶか、PSC の PDF/HTML をドロップ／欠陥リストを貼り付けて、引受スクリーニングメモをこの場で作れます。",
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
  ruling_jtsb: {
    en: "Cause finding (investigation)",
    ja: "原因認定（調査結果）",
  },
  facts_pdf_notice: {
    en: "Imported from PDF: layout may differ from the original; we show the facts section when we can find it.",
    ja: "PDF 取り込みです。原本の組版とは異なる場合があります。見出し（理由・事実など）があればその付近を表示しています。",
  },
  facts_empty: {
    en: "No facts text could be extracted from this document.",
    ja: "この文書から事実欄に載せる本文を取り出せませんでした。",
  },
  ruling_empty: {
    en: "No operative holding was extracted. Civil judgments and tribunal rulings with fault-ratio language may fill this field; accident investigation reports often have no separate “holding” block—that is normal.",
    ja: "判示・主文相当の抜粋は取り出せませんでした。民事判決や海難裁決で過失割合の記載があればここに出ます。運輸安全委員会の事故調査報告など、判示欄がない文書では空欄になるのが正常です。",
  },
  radar_title: { en: "Relative radar scope", ja: "相対レーダースコープ" },
  heading_a: { en: "Heading A (deg)", ja: "本船針路 A（度）" },
  heading_b: { en: "Heading B (deg)", ja: "相手針路 B（度）" },
  bearing_ab: { en: "True bearing A→B (deg)", ja: "真方位 A→B（度）" },
  geometry_override: { en: "Adjust encounter angles", ja: "局面の角度を調整" },
  geometry_narrative_derived: {
    en: "Values shown are taken from the case narrative (not manually set).",
    ja: "表示角度は叙述から抽出した値です（手動設定ではありません）。",
  },
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
  briefing_label: { en: "Use-case briefing", ja: "ユースケースの前提" },
  briefing_title_uc2: {
    en: "What Rule D5 apportionment is for",
    ja: "Rule D5 按分とは何か",
  },
  briefing_title_uc3: {
    en: "What COLREGS fault evidence is for",
    ja: "COLREGS 航法・過失根拠とは何か",
  },
  briefing_title_psc: {
    en: "What PSC seaworthiness screening is for",
    ja: "PSC 耐航性スクリーニングとは何か",
  },
  uc2_briefing_p1: {
    en: "When a ship goes into drydock after a casualty and owners’ work shares that same docking, the cost of entering and leaving—and the dock dues for the stay—become common dues. London AAA Rule D5 is the market practice that says whether underwriters take those dues in full or split them fifty-fifty with the owner. It does not invent a new indemnity theory; it settles who pays for the shared dock when two agendas meet in one yard.",
    ja: "事故のあとに船が入渠し、その同じドック滞在で船主工事も並行するとき、入出渠や滞渠料は「共通入渠費」になります。ロンドンの平均精算人協会が定める Rule D5 は、その共通費を保険者が全額見るのか、船主と折半するのかを決める業界慣行です。新しい填補理論を作るのではなく、二つの工事が一つのヤードで重なったときに、誰がドック代を持つかを落ち着かせるための規則です。",
  },
  uc2_briefing_p2: {
    en: "Hull claims handlers, surveyors, and average adjusters do this work—usually at the desk or yard, reading the repair specification against the docking story. They draft a split that can travel between underwriter and owner before anyone signs a settlement. Final indemnity still sits with the appointed surveyor or adjuster; this screen only speeds the pre-approval draft.",
    ja: "手を動かすのは、主に船体保険のクレーム担当、サーベイヤー、アベレージアジャスターです。机上や現場で修繕仕様と入渠の事情を読み合わせ、保険者と船主のあいだを先に通る按分案を作ります。最終の填補判断は任命されたサーベイヤーやアジャスターに残り、この画面はその予審の下書きを早くするためのものです。",
  },
  uc2_briefing_p3: {
    en: "Why bother: when casualty repair and owners’ work overlap, each side can push the dock bill onto the other, and delay in the split stretches screening time and off-hire. What you should expect here is not a signed payment figure, but a rule-backed answer—underwriter 100% or half-and-half—plus line-level shares, a rough off-hire saving from faster screening, and a statement you can challenge or accept.",
    ja: "なぜ必要かといえば、事故復旧とオーナー工事が重なると負担の押し付け合いが起きやすく、按分の根拠が遅れるほど査定も休航も伸びるからです。ここで期待するのは支払額の確定ではありません。共通入渠費が保険者100%か折半かのルール帰結、明細ごとの負担、査定が早くなった分の休航損失の概算、そして反論も採択もできるステートメントです。",
  },
  uc3_briefing_p1: {
    en: "After a ship collision—or when screening a claim that rests on one—someone has to say what the encounter was under the Collision Regulations: crossing, head-on, or overtaking, and which ship was give-way or stand-on. That geometry comes from COLREGS Rules 13–15 (and Japan’s Maritime Collision Prevention Act Arts. 13–15). The point is not to invent a court judgment; it is to pin the navigational situation so fault-ratio evidence has a shared starting map.",
    ja: "船舶が衝突したあと、あるいは衝突を前提にしたクレームを見るとき、まず「横切・行会い・追越しのどれか」「どちらが避航船でどちらが保持船か」を海上衝突予防法（COLREGS 第13–15条）の言葉で固定する必要があります。ここでやるのは判決そのものの創作ではなく、過失割合の議論が同じ地図の上で始まるように、航法局面を押さえることです。",
  },
  uc3_briefing_p2: {
    en: "Claims handlers, marine lawyers, surveyors, and adjusters do this when they read a tribunal ruling, court judgment, or accident investigation PDF—on shore, before settlement talks harden. They pull facts and holdings, check headings and relative bearing, and draft a memo that underwriter and assured can argue from. Final civil percentages still belong to the tribunal, the court, or the appointed adjuster; this screen is a fast evidence draft.",
    ja: "手を動かすのは、クレーム担当、海事弁護士、サーベイヤー、アジャスターです。海難審判の裁決、民事判決、事故調査報告の PDF を机上で読み、事実と判示を取り出し、針路と相対方位を照合して、保険者と被保険者のあいだで先に通るメモを作ります。最終の民事過失割合は審判・裁判所・任命されたアジャスターに残り、この画面はその根拠ドラフトを早くするためのものです。",
  },
  uc3_briefing_p3: {
    en: "Why it matters: without a clear encounter label, fault talk drifts into narrative. What you should expect here is a situation and role call, a working fault-ratio estimate grounded in public patterns, a simple radar sketch, and an exportable memo—not a binding liability award.",
    ja: "なぜ必要かといえば、局面ラベルが曖昧なままでは過失の話が物語に流れるからです。ここで期待するのは拘束力のある責任認定ではなく、局面と役割の判定、公開先例に寄せた作業用の過失割合、簡単なレーダー概略、そして反論・採択できるメモです。",
  },
  psc_briefing_p1: {
    en: "Before renewing cover—or when screening a vessel after a casualty—underwriters ask whether recent Port State Control findings show a repeat safety risk. Tokyo and Paris MOU deficiency codes, together with action codes such as 17 (rectify) and 30 (detention), map onto public convention families (SOLAS, MARPOL, ISM). The point is not to rewrite warranty doctrine; it is to turn a public deficiency list into an explainable Defect Score.",
    ja: "更改の前や事故後のスクリーニングで、引受側は「最近の PSC 欠陥が繰返しの安全リスクを示すか」を見ます。東京・パリ MOU の欠陥コードと、是正（17）や拘留（30）などのアクションコードは、SOLAS・MARPOL・ISM といった公開の条約族に対応します。ここでやるのは保証約款の書き換えではなく、公開の欠陥リストを説明可能な Defect Score にすることです。",
  },
  psc_briefing_p2: {
    en: "Claims and underwriting desks do this when they read an anonymized inspection log or portal export—on shore, offline after assets are cached. They normalize codes, weight severity, apply a lookback window for critical-system repeats, and draft a short memo. Final warranty conclusions stay with counsel and the appointed surveyor; this screen is a public-data screening draft.",
    ja: "クレームと引受の机上で、匿名化された検査ログやポータル出力を読みます。コードを正規化し、重大度を重み付けし、重大システムの繰返しに Lookback を当て、短いメモを作ります。最終の保証判断はリーガルと任命サーベイヤーに残り、この画面は公開データだけのスクリーニング下書きです。",
  },
  psc_briefing_p3: {
    en: "Why it matters: without a shared score and code list, “is this ship risky?” stays anecdotal. What you should expect here is a Defect Score with a low / elevated / critical band, top deficiencies with action and repeat flags, and an exportable underwriter memo—not a binding seaworthiness warranty opinion.",
    ja: "なぜ必要かといえば、共有のスコアとコード一覧が無いと「この船は危ないか」が逸話に留まるからです。ここで期待するのは拘束力のある堪航性保証意見ではなく、low / elevated / critical の帯付き Defect Score、アクションと繰返しフラグ付きの主要欠陥、そして反論・採択できる引受メモです。",
  },
  uc2_explain_usecase: {
    en: "Draft AAA Rule D5 common-dues apportionment and a screening-time off-hire estimate from a drydock repair PDF.",
    ja: "入渠・修繕 PDF から AAA Rule D5 の共通入渠費按分案と、予審短縮による休航損失見積を作る。",
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
  psc_explain_usecase: {
    en: "Score public MOU-style PSC deficiencies into a seaworthiness Defect Score for underwriting refresh.",
    ja: "公開の MOU 型 PSC 欠陥を Defect Score に採点し、更改・引受スクリーニングに使う。",
  },
  psc_explain_input: {
    en: "Bundled anonymized fixture, MOU-style PDF/HTML/image, or pasted JSON / CSV deficiency list, plus lookback months.",
    ja: "同梱の匿名フィクスチャ、MOU 型 PDF/HTML/画像、または貼り付けた JSON／CSV の欠陥リストと Lookback（月）。",
  },
  psc_explain_process: {
    en: "Normalize deficiency and action codes, weight severity, apply repeat multiplier inside the lookback window.",
    ja: "欠陥・アクションコードを正規化し、重大度を重み付けし、Lookback 内の繰返しに倍率を掛ける。",
  },
  psc_explain_output: {
    en: "Defect Score and band, top deficiencies with Code 17/30 and repeat flags, underwriter memo export.",
    ja: "Defect Score と帯、Code 17/30 と繰返しフラグ付きの主要欠陥、引受メモ出力。",
  },
  drop_pdf: { en: "Drop a PDF here or click to open", ja: "PDF をドロップ、またはクリックして開く" },
  analyze: { en: "Analyze", ja: "査定する" },
  use_synthetic: { en: "Use synthetic demo lines", ja: "合成デモ明細を使う" },
  export_colregs_md: { en: "Download memo (Markdown)", ja: "メモ（Markdown）" },
  export_colregs_html: { en: "Download memo (HTML)", ja: "メモ（HTML）" },
  export_psc_md: { en: "Download PSC memo (Markdown)", ja: "PSCメモ（Markdown）" },
  export_psc_html: { en: "Download PSC memo (HTML)", ja: "PSCメモ（HTML）" },
  select_psc_fixture: { en: "Inspection fixture", ja: "検査フィクスチャ" },
  psc_lookback: { en: "Lookback window (months)", ja: "Lookback（月）" },
  psc_paste: {
    en: "Paste deficiency JSON or CSV (optional)",
    ja: "欠陥 JSON / CSV を貼付け（任意）",
  },
  psc_paste_hint: {
    en: "JSON fixture/inspection, or CSV with deficiency_code,action_taken,nature[,inspection_date]",
    ja: "JSON のフィクスチャ／検査、または deficiency_code,action_taken,nature[,inspection_date] の CSV",
  },
  psc_apply_paste: { en: "Score pasted list", ja: "貼付けを採点" },
  psc_clear_paste: { en: "Back to fixtures", ja: "フィクスチャに戻る" },
  drop_psc: {
    en: "Drop PSC PDF / HTML / image, or click to open",
    ja: "PSC の PDF / HTML / 画像をドロップ、またはクリックして開く",
  },
  psc_load_sample: {
    en: "Load sample MOU HTML",
    ja: "サンプル MOU HTML を読込",
  },
  psc_err_document: {
    en: "Could not extract deficiencies from this document.",
    ja: "この文書から欠陥を取り出せませんでした。",
  },
  psc_defect_score: { en: "Defect Score", ja: "Defect Score" },
  psc_risk_band: { en: "Risk band", ja: "リスク帯" },
  psc_detention: { en: "Detention (Code 30)", ja: "拘留（Code 30）" },
  psc_repeat_flags: { en: "Repeat critical systems", ja: "繰返し重大システム" },
  psc_col_code: { en: "Code", ja: "コード" },
  psc_col_action: { en: "Action", ja: "アクション" },
  psc_col_nature: { en: "Nature", ja: "内容" },
  psc_col_repeat: { en: "Repeat?", ja: "繰返し？" },
  psc_col_contrib: { en: "Contrib", ja: "寄与" },
  psc_yes: { en: "yes", ja: "はい" },
  psc_no: { en: "no", ja: "いいえ" },
  psc_present: { en: "present", ja: "あり" },
  psc_absent: { en: "absent", ja: "なし" },
  psc_band_low: { en: "low", ja: "low（低）" },
  psc_band_elevated: { en: "elevated", ja: "elevated（注意）" },
  psc_band_critical: { en: "critical", ja: "critical（重大）" },
  psc_disclaimer: {
    en: "Public-taxonomy screening only — not a legal warranty-of-seaworthiness opinion.",
    ja: "公開タクソノミに基づくスクリーニングであり、堪航性保証の法的意見ではありません。",
  },
  psc_err_paste: {
    en: "Could not parse the pasted JSON or CSV.",
    ja: "貼り付けた JSON / CSV を解析できませんでした。",
  },
  psc_err_empty: {
    en: "No deficiencies found in the pasted input.",
    ja: "貼り付け内容から欠陥を取り出せませんでした。",
  },
  err_pdf_empty_text: {
    en: "No text could be extracted from this PDF (it may be image-only).",
    ja: "この PDF から文字を取り出せませんでした（画像のみの可能性）。",
  },
  ocr_in_progress: {
    en: "No text layer — running in-browser OCR (jpn+eng)…",
    ja: "テキスト層なし — ブラウザ内 OCR（日本語+英語）を実行中…",
  },
  ocr_failed: {
    en: "OCR could not read this PDF. Stage B was not run. Try a clearer scan or a text-embedded PDF.",
    ja: "OCR でこの PDF を読み取れませんでした。Stage B は実行していません。鮮明なスキャンか、テキスト埋め込み PDF をお試しください。",
  },
  ocr_source_hint: {
    en: "Text from in-browser OCR — Stage A confidence is lowered; confirm before Stage B.",
    ja: "ブラウザ内 OCR 由来のテキストです — Stage A 信頼度を下げています。Stage B 前に確認してください。",
  },
  err_no_line_items: {
    en: "No repair line items were found in this specification PDF.",
    ja: "この修繕仕様 PDF から工事明細を抽出できませんでした。",
  },
  err_schema_invalid: {
    en: "Extracted data failed the Stage A schema check and was not scored.",
    ja: "抽出結果が Stage A スキーマ検証に失敗したため、採点しませんでした。",
  },
  human_review_title: {
    en: "HUMAN_REVIEW_REQUIRED",
    ja: "HUMAN_REVIEW_REQUIRED（要人間確認）",
  },
  human_review_body: {
    en: "Stage A confidence is below the engineering threshold. Stage B scoring is paused until you confirm or edit the structured fields.",
    ja: "Stage A の信頼度が工学的閾値を下回ったため、Stage B 採点を保留しています。構造化フィールドを確認・編集してから確定してください。",
  },
  human_review_not_legal: {
    en: "Abstention is an engineering safety rail — not a legal opinion, warranty finding, or statutory determination.",
    ja: "棄権（abstention）は工学的な安全レールであり、法的意見・保証判断・法令上の結論ではありません。",
  },
  confidence_label: {
    en: "Document confidence",
    ja: "文書信頼度",
  },
  confirm_and_score: {
    en: "Confirm & score",
    ja: "確認して採点",
  },
  review_edit_hint: {
    en: "Edit fields below, then confirm to run Stage B.",
    ja: "下のフィールドを編集し、確認後に Stage B を実行します。",
  },
  analyzed_ok: {
    en: "Analysis finished. Results are shown below.",
    ja: "解析が完了しました。下に結果を表示しています。",
  },
  analyzed_pending_review: {
    en: "Extraction ready — human review required before scoring.",
    ja: "抽出完了 — 採点前に人間確認が必要です。",
  },
  router_detected: {
    en: "Detected document type",
    ja: "検出した文書種別",
  },
  router_override: {
    en: "Override type (before Analyze)",
    ja: "種別を上書き（解析前）",
  },
  router_override_none: {
    en: "Use detected type",
    ja: "検出結果を使う",
  },
  router_analyze: {
    en: "Analyze",
    ja: "解析する",
  },
  router_confidence: {
    en: "Router confidence",
    ja: "ルーター信頼度",
  },
  router_blocked_unknown: {
    en: "Document type is unknown — Stage B will not run. Choose an override type, or upload a clearer sample.",
    ja: "文書種別が不明なため Stage B は実行しません。種別を上書きするか、より明確なサンプルをアップロードしてください。",
  },
  router_blocked_mismatch: {
    en: "Detected type does not match this tab — Stage B will not run until you override to an allowed type.",
    ja: "検出種別がこのタブと一致しないため、許容種別に上書きするまで Stage B は実行しません。",
  },
  router_ready: {
    en: "Type matches this tab. Click Analyze to run Stage A → Stage B.",
    ja: "種別はこのタブと一致しています。解析する を押すと Stage A → Stage B を実行します。",
  },
  router_type_repair_spec: { en: "Repair specification", ja: "修繕仕様書" },
  router_type_civil_judgment: { en: "Civil judgment", ja: "民事判決" },
  router_type_jmat_ruling: { en: "JMAT ruling", ja: "海難審判裁決" },
  router_type_jtsb_report: { en: "JTSB investigation report", ja: "運輸安全委員会報告書" },
  router_type_psc_inspection: { en: "PSC inspection", ja: "PSC 検査" },
  router_type_unknown: { en: "Unknown", ja: "不明" },
  col_id: { en: "ID", ja: "ID" },
  col_title: { en: "Title", ja: "摘要" },
  col_cost: { en: "Cost", ja: "費用" },
  col_insurer: { en: "Insurer", ja: "保険者" },
  col_owner: { en: "Owner", ja: "船主" },
  col_rule: { en: "Rule", ja: "区分" },
  pipeline_statuses: { en: "Screening results", ja: "スクリーニング結果" },
  causality_check: {
    en: "Causality check (bow → machinery)",
    ja: "因果確認（船首 → 機関）",
  },
  causality_valid: { en: "linked", ja: "連関あり" },
  causality_invalid: { en: "not linked", ja: "連関なし" },
  rule_RULE_D5_50_50: {
    en: "Rule D5 — common dues 50/50",
    ja: "Rule D5 — 共通入渠費を折半",
  },
  rule_RULE_D5_100_UNDERWRITER: {
    en: "Rule D5 — common dues 100% underwriter",
    ja: "Rule D5 — 共通入渠費は保険者全額",
  },
  rule_DISCRETE: {
    en: "Discrete line (not common dues)",
    ja: "個別工事（共通入渠費以外）",
  },
  status_EXCLUDED_scheduled: { en: "Excluded (scheduled survey)", ja: "除外（定期点検）" },
  status_EXCLUDED_piggyback: { en: "Excluded (piggyback repair)", ja: "除外（便乗修理）" },
  status_COVERED: { en: "Covered", ja: "填補対象" },
  status_APPORTIONED_50: { en: "Apportioned (50%)", ja: "按分（50%）" },
  status_REVIEW: { en: "Review / partial", ja: "要確認／一部" },
  line_hull_bow: { en: "Bow shell plating repair", ja: "船首外板修繕" },
  line_piston_owner: { en: "Piston overhaul (owner)", ja: "ピストン整備（船主工事）" },
  line_statutory: { en: "Statutory survey item", ja: "法定検査工事" },
  line_dock_dues: { en: "Entering / leaving / lay dues", ja: "入出渠・滞渠料" },
  reason_watertight_barrier_violation: {
    en: "Blocked by watertight boundary",
    ja: "水密区画で遮断",
  },
  reason_path_exists: { en: "Damage path exists", ja: "損傷伝播経路あり" },
  reason_same_compartment: { en: "Same compartment", ja: "同一区画" },
  reason_unknown_zone: { en: "Unknown zone", ja: "区画不明" },
  reason_adjacent_compartment: { en: "Adjacent compartment", ja: "隣接区画" },
  reason_beyond_casualty_propagation_limit: {
    en: "Beyond casualty propagation limit",
    ja: "事故伝播の想定範囲外",
  },
  reason_no_damage_zones: { en: "No damage zones", ja: "損傷区画なし" },
};

export function t(key: string, lang: Lang = "en"): string {
  const entry = MESSAGES[key];
  if (!entry) return key;
  return entry[lang] || entry.en || key;
}

export function displayRule(rule: string, lang: Lang): string {
  const key = `rule_${rule}`;
  return MESSAGES[key] ? t(key, lang) : rule;
}

export function displayStatus(status: string, lang: Lang): string {
  if (status.includes("定期点検") || /EXCLUDED.*survey|scheduled/i.test(status)) {
    return t("status_EXCLUDED_scheduled", lang);
  }
  if (status.includes("便乗") || /piggyback/i.test(status)) {
    return t("status_EXCLUDED_piggyback", lang);
  }
  if (status.includes("APPORTIONED") || status.includes("50%")) {
    return t("status_APPORTIONED_50", lang);
  }
  if (status.includes("COVERED")) return t("status_COVERED", lang);
  if (status.includes("REVIEW")) return t("status_REVIEW", lang);
  return status;
}

export function displayCausalityReason(reason: string, lang: Lang): string {
  const key = `reason_${reason}`;
  return MESSAGES[key] ? t(key, lang) : reason;
}

const LINE_TITLE_KEYS: Record<string, string> = {
  "Bow shell plating repair": "line_hull_bow",
  "Piston overhaul (owner)": "line_piston_owner",
  "Statutory survey item": "line_statutory",
  "Statutory survey (assumed concurrent)": "line_statutory",
  "Entering / leaving / lay dues": "line_dock_dues",
};

export function displayLineTitle(title: string, lang: Lang): string {
  const key = LINE_TITLE_KEYS[title];
  return key ? t(key, lang) : title;
}

export function lineTitle(key: "hull_bow" | "piston_owner" | "statutory" | "dock_dues", lang: Lang): string {
  return t(`line_${key}`, lang);
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
