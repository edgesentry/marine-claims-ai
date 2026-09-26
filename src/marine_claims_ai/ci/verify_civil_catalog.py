"""
Verify civil precedent catalog links are reachable and (optionally) content-consistent.

Modes:
  alive   — HTTP fetch succeeds and payload is non-trivial (CI default)
  content — also checks title/maritime hints and soft fault/yen evidence

Generic portals (https://www.courts.go.jp/) are skipped (not document-level).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from marine_claims_ai.ingest.civil import load_catalog
from marine_claims_ai.ingest.download import open_url
from marine_claims_ai.ingest.pdf_text import pdf_to_text

GENERIC_EXACT = {
    "https://www.courts.go.jp",
    "https://www.courts.go.jp/",
}

MARITIME_HINTS = ("船舶", "衝突", "海難", "船", "漁船", "貨物船", "海事", "桟橋", "乗揚", "沈没")

KANJI_DIGITS = {
    "〇": "0",
    "零": "0",
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
    "十": "",  # handled in normalize
}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._chunks.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._chunks))


def is_generic_portal(url: str) -> bool:
    normalized = url.strip()
    if normalized in GENERIC_EXACT:
        return True
    parsed = urlparse(normalized)
    return parsed.netloc == "www.courts.go.jp" and parsed.path in ("", "/")


def is_verifiable_document_url(url: str) -> bool:
    if is_generic_portal(url):
        return False
    lower = url.lower()
    return lower.endswith((".pdf", ".htm", ".html")) or "/articles/" in lower


def fetch_bytes(url: str, timeout: int = 45) -> bytes:
    with open_url(url, timeout=timeout) as resp:
        return resp.read()


def decode_html_bytes(data: bytes) -> str:
    head = data[:800].decode("ascii", errors="ignore").lower()
    preferred = []
    if "shift_jis" in head or "shift-jis" in head or "sjis" in head:
        preferred = ["shift_jis", "cp932", "utf-8", "euc-jp"]
    elif "euc-jp" in head or "euc_jp" in head:
        preferred = ["euc-jp", "utf-8", "shift_jis"]
    else:
        preferred = ["utf-8", "shift_jis", "cp932", "euc-jp"]
    for enc in preferred:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_text(url: str, data: bytes, tmp_pdf: str | None = None) -> str:
    lower = url.lower()
    if lower.endswith(".pdf"):
        if not tmp_pdf:
            return ""
        with open(tmp_pdf, "wb") as f:
            f.write(data)
        return pdf_to_text(tmp_pdf)
    raw = decode_html_bytes(data)
    parser = _HTMLTextExtractor()
    try:
        parser.feed(raw)
        text = parser.text()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", text)


def kanji_percent_numbers(text: str) -> set[int]:
    """Extract integers from patterns like 六五パーセント / 65パーセント / ６５％."""
    found: set[int] = set()
    for m in re.finditer(r"([〇零一二三四五六七八九十\d０-９]{1,4})\s*(?:パーセント|％|%)", text):
        token = m.group(1)
        # fullwidth digits
        token = token.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        if token.isdigit():
            found.add(int(token))
            continue
        # simple 十-based kanji up to 99
        n = 0
        if token == "十":
            found.add(10)
            continue
        if "十" in token:
            left, _, right = token.partition("十")
            tens = 1 if left == "" else int(KANJI_DIGITS.get(left, "0") or "0")
            ones = 0 if right == "" else int(KANJI_DIGITS.get(right, "0") or "0")
            n = tens * 10 + ones
        else:
            digits = "".join(KANJI_DIGITS.get(ch, "") for ch in token)
            if digits.isdigit():
                n = int(digits)
        if n:
            found.add(n)
    for m in re.finditer(r"(\d{1,2})\s*[:：対]\s*(\d{1,2})", text):
        found.add(int(m.group(1)))
        found.add(int(m.group(2)))
    return found


def fault_ratio_evidenced(fault_ratio: str | None, text: str) -> bool:
    if not fault_ratio or not text:
        return False
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", fault_ratio.strip())
    if not m:
        return False
    a, b = int(m.group(1)), int(m.group(2))
    nums = kanji_percent_numbers(text)
    if a in nums and b in nums:
        return True
    if a in nums:  # single-sided percent holdings
        return True
    if re.search(r"主因", text) and re.search(r"一因", text):
        return True
    if re.search(r"(過失|責任).{0,16}(割合|程度|パーセント)", text):
        return True
    return False


def title_overlap(title: str, text: str) -> bool:
    if not title or not text:
        return False
    stop = {"事件", "公開", "損害賠償", "関連", "民事", "争点", "要約", "モデル", "類型", "パターン"}
    tokens = [t for t in re.findall(r"[\w一-龥ぁ-んァ-ヶー]{2,}", title) if t not in stop]
    if not tokens:
        return True
    hits = sum(1 for t in tokens if t in text)
    need = 1 if len(tokens) <= 3 else 2
    return hits >= need


def yen_evidenced(record: dict[str, Any], text: str) -> bool:
    amounts = [
        record.get("claimed_repair_jpy"),
        record.get("awarded_damages_jpy"),
        record.get("disallowed_jpy"),
    ]
    seeded = [int(a) for a in amounts if isinstance(a, int)]
    if not seeded:
        return True
    if record.get("source_type") != "court_pdf":
        # Published summaries may model yen without the target page restating figures.
        return True
    if not text:
        return False
    if re.search(r"[0-9〇一二三四五六七八九十百千万億]+円", text) or "損害" in text:
        return True
    return False


def verify_record(record: dict[str, Any], mode: str, tmp_dir: str) -> dict[str, Any]:
    url = str(record.get("url") or "")
    case_id = record.get("case_id")
    result: dict[str, Any] = {"case_id": case_id, "url": url, "status": "ok", "notes": []}

    if not url:
        result["status"] = "fail"
        result["notes"].append("missing url")
        return result

    if is_generic_portal(url) or not is_verifiable_document_url(url):
        result["status"] = "skip_generic"
        result["notes"].append("generic/non-document URL; no document-level check")
        return result

    try:
        data = fetch_bytes(url)
    except Exception as exc:
        result["status"] = "fail"
        result["notes"].append(f"fetch failed: {exc}")
        return result

    if len(data) < 200:
        result["status"] = "fail"
        result["notes"].append(f"response too small ({len(data)} bytes)")
        return result

    result["notes"].append(f"alive bytes={len(data)}")
    if mode == "alive":
        return result

    tmp_pdf = None
    if url.lower().endswith(".pdf"):
        tmp_pdf = os.path.join(tmp_dir, f"case_{case_id}.pdf")
    text = extract_text(url, data, tmp_pdf=tmp_pdf)
    if len(text) < 40:
        result["status"] = "fail"
        result["notes"].append("extracted text too short")
        return result

    title = str(record.get("title") or "")
    has_maritime = any(h in text for h in MARITIME_HINTS)
    has_title = title_overlap(title, text)
    if not has_maritime and not has_title:
        result["status"] = "fail"
        result["notes"].append("no maritime hint or title overlap")
        return result
    if title and not has_title and record.get("holding_kind") in {
        "jmat_major",
        "jmat_saiketsu",
        "civil_judgment",
    }:
        result["status"] = "fail"
        result["notes"].append("title tokens not found in document")
        return result

    fr = record.get("fault_ratio")
    if fr and url.lower().endswith(".pdf") and not fault_ratio_evidenced(str(fr), text):
        result["status"] = "fail"
        result["notes"].append(f"fault_ratio {fr} not evidenced in PDF")
        return result

    if not yen_evidenced(record, text):
        result["status"] = "fail"
        result["notes"].append("yen/damages not evidenced in court PDF")
        return result

    result["notes"].append(f"content ok text_chars={len(text)}")
    return result


def verify_catalog(
    seeds: list[dict[str, Any]] | None = None,
    mode: str = "alive",
    tmp_dir: str | None = None,
) -> dict[str, Any]:
    seeds = seeds if seeds is not None else load_catalog()
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp(prefix="civil_catalog_verify_")
    os.makedirs(tmp_dir, exist_ok=True)
    results = [verify_record(s, mode=mode, tmp_dir=tmp_dir) for s in seeds]
    return {
        "mode": mode,
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "skip_generic": sum(1 for r in results if r["status"] == "skip_generic"),
        "fail": sum(1 for r in results if r["status"] == "fail"),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["alive", "content"],
        default="alive",
        help="alive=HTTP reachability (CI); content=title/fault/yen soft checks",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--fail-on-skip-ratio",
        type=float,
        default=0.5,
        help="Fail if skipped generic URLs exceed this fraction (default 0.5)",
    )
    args = parser.parse_args()

    summary = verify_catalog(mode=args.mode)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"civil catalog verify mode={summary['mode']}: total={summary['total']} "
            f"ok={summary['ok']} skip_generic={summary['skip_generic']} fail={summary['fail']}"
        )
        for r in summary["results"]:
            if r["status"] == "fail":
                print(f"  FAIL case_id={r['case_id']}: {'; '.join(r['notes'])} ({r['url']})")

    if summary["fail"]:
        return 1
    skip_ratio = summary["skip_generic"] / max(1, summary["total"])
    if skip_ratio > args.fail_on_skip_ratio:
        print(
            f"[ERROR] skip_generic ratio {skip_ratio:.2f} > {args.fail_on_skip_ratio} "
            "(replace courts.go.jp portal stubs with concrete document URLs)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
