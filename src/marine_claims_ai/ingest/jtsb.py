"""JTSB (運輸安全委員会) public marine investigation report ingest."""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from marine_claims_ai.ingest.download import download_url, open_url, polite_sleep
from marine_claims_ai.ingest.pdf_text import pdf_to_text

JTSB_LIST_URL = "https://jtsb.mlit.go.jp/jtsb/ship/ship-kensaku-list.php"
# Form values: 1=衝突, 2=衝突（単）
DEFAULT_COLLISION_TYPES = ("1", "2")
PAGE_SIZE = 30


def apply_limit(items: list[Any], limit: int) -> list[Any]:
    """Return all items when limit <= 0; otherwise the first `limit` items."""
    if limit is None or limit <= 0:
        return list(items)
    return list(items)[:limit]


def _strip_script_blocks(html: str) -> str:
    """Remove <script>...</script> blocks without fragile end-tag regexes."""
    out: list[str] = []
    lower = html.lower()
    i = 0
    while True:
        start = lower.find("<script", i)
        if start < 0:
            out.append(html[i:])
            break
        out.append(html[i:start])
        end = lower.find("</script", start)
        if end < 0:
            break
        gt = html.find(">", end)
        if gt < 0:
            break
        i = gt + 1
    return "".join(out)


def parse_jtsb_list_page(html: str) -> list[dict[str, str]]:
    """Extract collision (and related) report rows + PDF URLs from a list page."""
    clean = _strip_script_blocks(html)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", clean, flags=re.S | re.I):
        pdfs = [
            p
            for p in re.findall(r'href="(https?://[^"]+\.pdf)"', tr, flags=re.I)
            if "rep-acci" in p or "rep-inci" in p
        ]
        if not pdfs:
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)
        if len(tds) < 4:
            continue

        def cell(i: int) -> str:
            plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", tds[i]))
            return re.sub(r"\s+", " ", plain).strip()

        pdf_url = pdfs[0]
        if pdf_url in seen:
            continue
        seen.add(pdf_url)
        rows.append(
            {
                "date": cell(0),
                "place": cell(1),
                "title": cell(2),
                "accident_type": cell(3),
                "published": cell(4) if len(tds) > 4 else "",
                "url": pdf_url,
            }
        )
    return rows


def fetch_jtsb_list_html(page: int, accident_types: tuple[str, ...] = DEFAULT_COLLISION_TYPES) -> str:
    # Assemble params without embedding the literal in an f-string that confuses linters
    params: list[tuple[str, str]] = [("accident_type[]", t) for t in accident_types]
    params.append(("page", str(page)))
    url = f"{JTSB_LIST_URL}?{urllib.parse.urlencode(params)}"
    with open_url(url, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def collect_jtsb_metadata(limit: int = 200, delay_s: float = 0.4) -> list[dict[str, str]]:
    """Paginate JTSB collision search until `limit` rows (0 = keep paging until empty)."""
    collected: list[dict[str, str]] = []
    page = 1
    while True:
        if limit > 0 and len(collected) >= limit:
            break
        try:
            html = fetch_jtsb_list_html(page)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"[JTSB] [ERROR] list page {page}: {exc}")
            break
        batch = parse_jtsb_list_page(html)
        if not batch:
            break
        collected.extend(batch)
        print(f"[JTSB] page {page}: +{len(batch)} (total {len(collected)})")
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        polite_sleep(delay_s)
    return apply_limit(collected, limit)


def fetch_jtsb_collisions(output_dir: str, force: bool = False, limit: int = 200) -> None:
    """
    Fetch JTSB collision investigation metadata (+ optional PDF text excerpts).
    Writes benchmark_jtsb_collision_cases.json under output_dir.
    """
    dest_json = os.path.join(output_dir, "benchmark_jtsb_collision_cases.json")
    if os.path.exists(dest_json) and os.path.getsize(dest_json) > 0 and not force:
        print(f"[JTSB] [SKIP] Dataset already exists: {os.path.basename(dest_json)}")
        return

    print(f"[JTSB] Collecting collision report metadata (limit={limit or 'all'})...")
    meta = collect_jtsb_metadata(limit=limit)
    if not meta:
        print("[JTSB] [ERROR] No reports collected")
        return

    pdf_dir = os.path.join(output_dir, "jtsb_pdfs")
    os.makedirs(pdf_dir, exist_ok=True)

    cases: list[dict] = []
    for i, row in enumerate(meta, start=1):
        pdf_url = row["url"]
        pdf_name = os.path.basename(urllib.parse.urlparse(pdf_url).path)
        pdf_path = os.path.join(pdf_dir, pdf_name)
        excerpt = ""
        ok = download_url(pdf_url, pdf_path, force=force, timeout=60)
        if ok:
            text = pdf_to_text(pdf_path)
            if text:
                excerpt = re.sub(r"\s+", " ", text)[:3500]
        facts = (
            f"{row['title']}。発生日: {row['date']}。場所: {row['place']}。"
            f"種類: {row['accident_type']}。"
        )
        if excerpt:
            facts = f"{facts}\n[pdf_excerpt] {excerpt}"
        cases.append(
            {
                "case_id": i,
                "title": row["title"],
                "date": row["date"],
                "place": row["place"],
                "accident_type": row["accident_type"],
                "url": pdf_url,
                "input_facts": facts,
                "source_type": "jtsb_pdf",
            }
        )
        if i % 25 == 0:
            print(f"[JTSB] processed {i}/{len(meta)}")
        polite_sleep(0.15)

    with open(dest_json, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    print(f"[JTSB] [OK] Saved {len(cases)} cases to {dest_json}")
