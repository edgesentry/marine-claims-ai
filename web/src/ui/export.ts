import type { Lang } from "../i18n";
import { t } from "../i18n";

export interface Uc2View {
  rule: string;
  dock_total: number;
  insurer_common: number;
  owner_common: number;
  insurer_total: number;
  owner_total: number;
  days_saved: number;
  offhire_jpy: number;
  line_rows: Array<{
    id: string;
    title: string;
    trade_code: string;
    cost: number;
    insurer: number;
    owner: number;
    rule: string;
  }>;
}

export interface Uc3View {
  title: string;
  situation: string;
  situation_label: string;
  role_a_label: string;
  role_b_label: string;
  fault_ratio: string;
  relative_bearing: number;
  rule_citations: string[];
  facts: string;
  ruling: string;
  document_kind?: "judgment" | "jtsb";
}

function rulingHeading(uc3: Uc3View, lang: Lang): string {
  if (uc3.document_kind === "jtsb") {
    return lang === "ja" ? "原因認定（調査結果）" : "Cause finding (investigation)";
  }
  return lang === "ja" ? "裁決・判示" : "Ruling";
}

function wrapHtml(body: string, title: string): string {
  const safeTitle = String(title)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${safeTitle}</title>
<style>
  body { font-family: "IBM Plex Sans", "Hiragino Sans", "Noto Sans JP", system-ui, sans-serif; max-width: 880px; margin: 2rem auto; padding: 0 1.25rem; color: #111; line-height: 1.55; }
  h1 { font-size: 1.35rem; margin: 0 0 1rem; }
  h2 { font-size: 1.05rem; margin: 1.5rem 0 0.6rem; }
  ul { padding-left: 1.2rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
  th, td { border: 1px solid #ccc; padding: 0.4rem 0.55rem; text-align: left; }
  th { background: #f3f4f6; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .note { margin-top: 1.25rem; color: #444; font-size: 0.9rem; }
  @media print { body { margin: 0; max-width: none; } }
</style>
</head>
<body>
${body}
</body>
</html>`;
}

function yen(n: number): string {
  return `¥${n.toLocaleString()}`;
}

export function apportionmentMarkdown(uc2: Uc2View, lang: Lang): string {
  const lines =
    lang === "ja"
      ? [
          "# AAA Rule D5 按分ステートメント（予備）",
          "",
          `- 按分ルール: \`${uc2.rule}\``,
          `- 共通入渠費合計: ${yen(uc2.dock_total)}`,
          `- 保険者負担（共通）: ${yen(uc2.insurer_common)}`,
          `- 船主負担（共通）: ${yen(uc2.owner_common)}`,
          `- 休航短縮日数: ${uc2.days_saved}`,
          `- 休航損失回避額: ${yen(uc2.offhire_jpy)}`,
          "",
          "## 明細",
          "",
          "| ID | 摘要 | 費用 | 保険者 | 船主 | ルール |",
          "| :--- | :--- | ---: | ---: | ---: | :--- |",
        ]
      : [
          "# AAA Rule D5 Apportionment Statement (Preliminary)",
          "",
          `- Rule: \`${uc2.rule}\``,
          `- Common dock dues total: ${yen(uc2.dock_total)}`,
          `- Insurer common share: ${yen(uc2.insurer_common)}`,
          `- Owner common share: ${yen(uc2.owner_common)}`,
          `- Days saved (off-hire heuristic): ${uc2.days_saved}`,
          `- Off-hire avoided: ${yen(uc2.offhire_jpy)}`,
          "",
          "## Line items",
          "",
          "| ID | Title | Cost | Insurer | Owner | Rule |",
          "| :--- | :--- | ---: | ---: | ---: | :--- |",
        ];
  for (const row of uc2.line_rows) {
    lines.push(
      `| ${row.id} | ${row.title} | ${row.cost.toLocaleString()} | ${row.insurer.toLocaleString()} | ${row.owner.toLocaleString()} | \`${row.rule}\` |`,
    );
  }
  lines.push("", "> Final indemnity remains with the appointed surveyor / claims adjuster.", "");
  return lines.join("\n");
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function apportionmentHtml(uc2: Uc2View, lang: Lang): string {
  const ja = lang === "ja";
  const rows = uc2.line_rows
    .map(
      (row) => `<tr>
      <td>${escapeHtml(row.id)}</td>
      <td>${escapeHtml(row.title)}</td>
      <td class="num">${escapeHtml(yen(row.cost))}</td>
      <td class="num">${escapeHtml(yen(row.insurer))}</td>
      <td class="num">${escapeHtml(yen(row.owner))}</td>
      <td><code>${escapeHtml(row.rule)}</code></td>
    </tr>`,
    )
    .join("\n");
  const body = `
<h1>${ja ? "AAA Rule D5 按分ステートメント（予備）" : "AAA Rule D5 Apportionment Statement (Preliminary)"}</h1>
<ul>
  <li>${ja ? "按分ルール" : "Rule"}: <code>${escapeHtml(uc2.rule)}</code></li>
  <li>${ja ? "共通入渠費合計" : "Common dock dues total"}: ${escapeHtml(yen(uc2.dock_total))}</li>
  <li>${ja ? "保険者負担（共通）" : "Insurer common share"}: ${escapeHtml(yen(uc2.insurer_common))}</li>
  <li>${ja ? "船主負担（共通）" : "Owner common share"}: ${escapeHtml(yen(uc2.owner_common))}</li>
  <li>${ja ? "休航短縮日数" : "Days saved"}: ${escapeHtml(uc2.days_saved)}</li>
  <li>${ja ? "休航損失回避額" : "Off-hire avoided"}: ${escapeHtml(yen(uc2.offhire_jpy))}</li>
</ul>
<h2>${ja ? "明細" : "Line items"}</h2>
<table>
  <thead>
    <tr>
      <th>ID</th>
      <th>${ja ? "摘要" : "Title"}</th>
      <th>${ja ? "費用" : "Cost"}</th>
      <th>${ja ? "保険者" : "Insurer"}</th>
      <th>${ja ? "船主" : "Owner"}</th>
      <th>${ja ? "ルール" : "Rule"}</th>
    </tr>
  </thead>
  <tbody>
    ${rows}
  </tbody>
</table>
<p class="note">${
    ja
      ? "最終の填補判断は任命されたサーベイヤー／クレームアジャスターに残ります。"
      : "Final indemnity remains with the appointed surveyor / claims adjuster."
  }</p>
<p class="note">${
    ja
      ? "印刷する場合は、ブラウザの「印刷」→「PDFに保存」を使ってください。"
      : "To make a PDF, use the browser Print dialog and choose Save as PDF."
  }</p>`;
  return wrapHtml(body, t("app_title", lang));
}

export function colregsMarkdown(uc3: Uc3View, lang: Lang): string {
  const lines =
    lang === "ja"
      ? [
          "# 予備調査・航法過失割合メモ",
          "",
          `**案件:** ${uc3.title}`,
          `**局面:** ${uc3.situation_label} (\`${uc3.situation}\`)`,
          `**本船:** ${uc3.role_a_label}`,
          `**相手船:** ${uc3.role_b_label}`,
          `**過失割合:** ${uc3.fault_ratio}`,
          `**相対方位:** ${uc3.relative_bearing}°`,
          "",
          "## 条文",
          "",
        ]
      : [
          "# Preliminary COLREGS Fault Evidence Memo",
          "",
          `**Case:** ${uc3.title}`,
          `**Situation:** ${uc3.situation_label} (\`${uc3.situation}\`)`,
          `**Own vessel (A):** ${uc3.role_a_label}`,
          `**Target (B):** ${uc3.role_b_label}`,
          `**Fault ratio:** ${uc3.fault_ratio}`,
          `**Relative bearing:** ${uc3.relative_bearing}°`,
          "",
          "## Citations",
          "",
        ];
  for (const c of uc3.rule_citations) lines.push(`- ${c}`);
  lines.push("", lang === "ja" ? "## 事実" : "## Facts", "", uc3.facts || "—", "");
  lines.push(`## ${rulingHeading(uc3, lang)}`, "", uc3.ruling || "—", "");
  return lines.join("\n");
}

export function colregsHtml(uc3: Uc3View, lang: Lang): string {
  const ja = lang === "ja";
  const citations = (uc3.rule_citations || [])
    .map((c) => `<li>${escapeHtml(c)}</li>`)
    .join("");
  const body = `
<h1>${ja ? "予備調査・航法過失割合メモ" : "Preliminary COLREGS Fault Evidence Memo"}</h1>
<ul>
  <li><strong>${ja ? "案件" : "Case"}:</strong> ${escapeHtml(uc3.title)}</li>
  <li><strong>${ja ? "局面" : "Situation"}:</strong> ${escapeHtml(uc3.situation_label)} (<code>${escapeHtml(uc3.situation)}</code>)</li>
  <li><strong>${ja ? "本船" : "Own vessel (A)"}:</strong> ${escapeHtml(uc3.role_a_label)}</li>
  <li><strong>${ja ? "相手船" : "Target (B)"}:</strong> ${escapeHtml(uc3.role_b_label)}</li>
  <li><strong>${ja ? "過失割合" : "Fault ratio"}:</strong> ${escapeHtml(uc3.fault_ratio)}</li>
  <li><strong>${ja ? "相対方位" : "Relative bearing"}:</strong> ${escapeHtml(uc3.relative_bearing)}°</li>
</ul>
<h2>${ja ? "条文" : "Citations"}</h2>
<ul>${citations || `<li>—</li>`}</ul>
<h2>${ja ? "事実" : "Facts"}</h2>
<p>${escapeHtml(uc3.facts || "—")}</p>
<h2>${escapeHtml(rulingHeading(uc3, lang))}</h2>
<p>${escapeHtml(uc3.ruling || "—")}</p>
<p class="note">${
    ja
      ? "印刷する場合は、ブラウザの「印刷」→「PDFに保存」を使ってください。"
      : "To make a PDF, use the browser Print dialog and choose Save as PDF."
  }</p>`;
  return wrapHtml(body, t("app_title", lang));
}

export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
