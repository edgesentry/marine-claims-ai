/**
 * Client-side PDF text extraction + repair-line heuristics (Tier-1 only).
 */
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { OwnerNecessity, RepairLineItem, WorkParty } from "../engines/ruleD5";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

export async function extractPdfText(file: File | ArrayBuffer): Promise<string> {
  const data = file instanceof File ? await file.arrayBuffer() : file;
  const doc = await pdfjs.getDocument({ data }).promise;
  const parts: string[] = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const content = await page.getTextContent();
    const line = content.items
      .map((it) => ("str" in it ? String(it.str) : ""))
      .join(" ");
    parts.push(line);
  }
  return parts.join("\n");
}

const YEN_RE = /(?:¥|￥|JPY)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})/g;

export interface ExtractedItem {
  description: string;
  estimated_cost: number;
}

export function extractRepairItemsFromText(text: string): ExtractedItem[] {
  const items: ExtractedItem[] = [];
  for (const raw of text.split(/\n+/)) {
    const line = raw.trim();
    if (line.length < 4) continue;
    YEN_RE.lastIndex = 0;
    const amounts: number[] = [];
    let m: RegExpExecArray | null;
    while ((m = YEN_RE.exec(line))) {
      amounts.push(parseInt(m[1]!.replace(/,/g, ""), 10));
    }
    if (!amounts.length) continue;
    const cost = amounts[amounts.length - 1]!;
    if (cost < 1000) continue;
    const description = line.replace(YEN_RE, "").replace(/\s+/g, " ").trim().slice(0, 120);
    if (!description) continue;
    items.push({ description, estimated_cost: cost });
  }
  return items.slice(0, 40);
}

export function repairItemsToRuleDLines(
  items: ExtractedItem[],
  opts: {
    dailyDockRate: number;
    dockDays: number;
    includeStatutory: boolean;
  },
): RepairLineItem[] {
  const dockTotal = opts.dailyDockRate * opts.dockDays;
  const lines: RepairLineItem[] = [];
  let sawDock = false;
  let sawStatutory = false;
  let n = 0;

  for (const it of items) {
    const desc = it.description;
    const cost = it.estimated_cost;
    if (cost <= 0) continue;
    n += 1;
    const id = `pdf-${n}`;

    if (/入出渠|滞渠|入渠/.test(desc)) {
      sawDock = true;
      lines.push({ id, trade_code: "DOCK-01", cost: dockTotal, title: desc.slice(0, 80) });
      continue;
    }
    if (/法定|検査証書|SOLAS|船級|年次検査|中間検査/.test(desc)) {
      sawStatutory = true;
      if (opts.includeStatutory) {
        lines.push({
          id,
          trade_code: "SAFE-01",
          cost,
          necessity: "statutory_seaworthiness" as OwnerNecessity,
          title: desc.slice(0, 80),
        });
      }
      continue;
    }
    if (/主機関|ピストン|プロペラ軸|減速機|発電機関|カロリー/.test(desc)) {
      lines.push({
        id,
        trade_code: "ENG-02",
        cost,
        necessity: "deferred" as OwnerNecessity,
        title: desc.slice(0, 80),
      });
      continue;
    }
    if (/外板|球状船首|船首|バウスラスター|塗装|洗浄/.test(desc)) {
      lines.push({
        id,
        trade_code: "HULL-01",
        cost,
        work_party: "casualty" as WorkParty,
        title: desc.slice(0, 80),
      });
      continue;
    }
    if (lines.filter((x) => x.necessity === "deferred").length < 3) {
      lines.push({
        id,
        trade_code: "OWN-01",
        cost: Math.min(cost, 2_000_000),
        necessity: "deferred",
        title: desc.slice(0, 80),
      });
    }
  }

  if (!sawDock) {
    lines.push({
      id: "dock-1",
      trade_code: "DOCK-01",
      cost: dockTotal,
      title: "Entering / leaving / lay dues",
    });
  } else {
    for (let i = 0; i < lines.length; i++) {
      if ((lines[i]!.trade_code || "").startsWith("DOCK")) {
        lines[i] = { ...lines[i]!, cost: dockTotal };
      }
    }
  }

  if (opts.includeStatutory && !sawStatutory) {
    lines.push({
      id: "safe-1",
      trade_code: "SAFE-01",
      cost: 550_000,
      necessity: "statutory_seaworthiness",
      title: "Statutory survey item",
    });
  }

  if (!lines.some((ln) => ln.work_party === "casualty")) {
    lines.unshift({
      id: "hull-1",
      trade_code: "HULL-01",
      cost: 4_500_000,
      work_party: "casualty",
      title: "Bow shell plating repair",
    });
  }

  return lines;
}

export function syntheticUc2Lines(
  dailyDockRate: number,
  dockDays: number,
  includeStatutory: boolean,
): RepairLineItem[] {
  const dockTotal = dailyDockRate * dockDays;
  const lines: RepairLineItem[] = [
    {
      id: "hull-1",
      trade_code: "HULL-01",
      cost: 4_500_000,
      work_party: "casualty",
      title: "Bow shell plating repair",
    },
    {
      id: "eng-1",
      trade_code: "ENG-02",
      cost: 1_800_000,
      necessity: "deferred",
      title: "Piston overhaul (owner)",
    },
  ];
  if (includeStatutory) {
    lines.push({
      id: "safe-1",
      trade_code: "SAFE-01",
      cost: 550_000,
      title: "Statutory survey item",
    });
  }
  lines.push({
    id: "dock-1",
    trade_code: "DOCK-01",
    cost: dockTotal,
    title: "Entering / leaving / lay dues",
  });
  return lines;
}
