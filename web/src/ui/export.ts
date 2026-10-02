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
}

function wrapHtml(md: string, title: string): string {
  const escaped = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem;white-space:pre-wrap;line-height:1.5}</style>
</head><body>${escaped}</body></html>`;
}

export function apportionmentMarkdown(uc2: Uc2View, lang: Lang): string {
  const lines =
    lang === "ja"
      ? [
          "# AAA Rule D5 按分ステートメント（予備）",
          "",
          `- 按分ルール: \`${uc2.rule}\``,
          `- 共通入渠費合計: ¥${uc2.dock_total.toLocaleString()}`,
          `- 保険者負担（共通）: ¥${uc2.insurer_common.toLocaleString()}`,
          `- 船主負担（共通）: ¥${uc2.owner_common.toLocaleString()}`,
          `- 休航短縮日数: ${uc2.days_saved}`,
          `- 休航損失回避額: ¥${uc2.offhire_jpy.toLocaleString()}`,
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
          `- Common dock dues total: JPY ${uc2.dock_total.toLocaleString()}`,
          `- Insurer common share: JPY ${uc2.insurer_common.toLocaleString()}`,
          `- Owner common share: JPY ${uc2.owner_common.toLocaleString()}`,
          `- Days saved (off-hire heuristic): ${uc2.days_saved}`,
          `- Off-hire avoided: JPY ${uc2.offhire_jpy.toLocaleString()}`,
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

export function apportionmentHtml(uc2: Uc2View, lang: Lang): string {
  return wrapHtml(apportionmentMarkdown(uc2, lang), t("app_title", lang));
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
  lines.push(lang === "ja" ? "## 裁決・判示" : "## Ruling", "", uc3.ruling || "—", "");
  return lines.join("\n");
}

export function colregsHtml(uc3: Uc3View, lang: Lang): string {
  return wrapHtml(colregsMarkdown(uc3, lang), t("app_title", lang));
}

export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
