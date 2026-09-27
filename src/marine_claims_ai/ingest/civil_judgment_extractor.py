"""
Extract fault ratios and monetary awards from Japanese maritime civil judgments.

Handles Arabic, fullwidth, and kanji numeral conventions common in courts.go.jp
PDFs/HTML (e.g. 六五パーセント, 建昌六・五／有漁丸三・五, 八〇七万二三三五円)
and locates operative comparative-negligence holdings (過失相殺 / 責任割合).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Kanji / fullwidth numeral helpers
# ---------------------------------------------------------------------------

_DIGIT = {
    "〇": 0,
    "零": 0,
    "○": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_FULLWIDTH = str.maketrans("０１２３４５６７８９％：．．，", "0123456789%:..,")
_UNIT_SMALL = {"十": 10, "百": 100, "千": 1000}

_KANJI_INT_TOKEN = r"[〇零○一二三四五六七八九十百千万億\d０-９]+"
_ARABIC_YEN = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})円")
_KANJI_YEN = re.compile(rf"({_KANJI_INT_TOKEN})円")

_HOLDING_ANCHORS = (
    "過失相殺",
    "過失割合",
    "責任割合",
    "過失の割合",
    "過失の程度",
    "双方の過失",
    "寄与度",
)


@dataclass(frozen=True)
class FaultRatioHit:
    ratio: str  # "65:35"
    evidence: str
    method: str
    confidence: float


@dataclass(frozen=True)
class YenHit:
    amount_jpy: int
    label: str
    evidence: str


@dataclass
class JudgmentExtraction:
    fault_ratio: str | None = None
    fault_ratio_hits: list[FaultRatioHit] = field(default_factory=list)
    claimed_repair_jpy: int | None = None
    awarded_damages_jpy: int | None = None
    disallowed_jpy: int | None = None
    yen_hits: list[YenHit] = field(default_factory=list)
    holding_excerpt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_judgment_text(text: str) -> str:
    """Normalize whitespace and fullwidth digits; keep Japanese punctuation."""
    if not text:
        return ""
    t = text.translate(_FULLWIDTH)
    t = t.replace("\u3000", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def _parse_digit_run(s: str) -> int | None:
    """Parse 六五 / 八〇七 / 65 style digit runs (no 十百千万億)."""
    if not s:
        return None
    if all(ch in _DIGIT or ch.isdigit() for ch in s):
        out = 0
        for ch in s:
            out = out * 10 + (int(ch) if ch.isdigit() else _DIGIT[ch])
        return out
    return None


def _parse_under_man(s: str) -> int | None:
    """Parse a number fragment below 万 (may use 千百十 or digit-run)."""
    if not s:
        return 0
    digit_run = _parse_digit_run(s)
    if digit_run is not None and not any(ch in _UNIT_SMALL for ch in s):
        return digit_run

    total = 0
    num: int | None = None
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in _DIGIT or ch.isdigit():
            run = 0
            while i < len(s) and (s[i] in _DIGIT or s[i].isdigit()):
                d = int(s[i]) if s[i].isdigit() else _DIGIT[s[i]]
                run = run * 10 + d
                i += 1
            num = run
            continue
        if ch in _UNIT_SMALL:
            coef = num if num is not None else 1
            total += coef * _UNIT_SMALL[ch]
            num = None
            i += 1
            continue
        return None
    if num is not None:
        total += num
    return total


def parse_kanji_int(token: str) -> int | None:
    """
    Parse judicial kanji / mixed numerals up to ~億.

    Digit-run style: 六五 → 65, 八〇 → 80, 三五 → 35.
    Place-value style: 三十五 → 35, 六十五 → 65, 百二十 → 120.
    Myriad style: 八〇七万二三三五 → 8_072_335.
    """
    if not token:
        return None
    token = token.translate(_FULLWIDTH).strip()
    if not token:
        return None
    if re.fullmatch(r"\d+", token):
        return int(token)
    if all(ch in _DIGIT for ch in token):
        return _parse_digit_run(token)

    total = 0
    rest = token
    if "億" in rest:
        left, _, rest = rest.partition("億")
        left_v = _parse_under_man(left) if left else 1
        if left_v is None:
            return None
        total += left_v * 100_000_000
    if "万" in rest:
        left, _, rest = rest.partition("万")
        left_v = _parse_under_man(left) if left else 1
        if left_v is None:
            return None
        total += left_v * 10_000
    tail = _parse_under_man(rest) if rest else 0
    if tail is None:
        return None
    return total + tail


def parse_yen_token(token: str) -> int | None:
    """Parse Arabic (1,234,567円) or kanji (八〇七万二三三五円) yen amounts."""
    token = token.translate(_FULLWIDTH).strip()
    if token.endswith("円"):
        token = token[:-1]
    token = token.replace(",", "").replace("，", "")
    if not token:
        return None
    if token.isdigit():
        return int(token)
    return parse_kanji_int(token)


def _ratio_str(a: int, b: int) -> str | None:
    if a < 0 or b < 0:
        return None
    # Tenths notation: 八、二 → 80:20
    if a + b == 10 and 1 <= a <= 9 and 1 <= b <= 9:
        a, b = a * 10, b * 10
    if a + b != 100:
        return None
    if not (1 <= a <= 99 and 1 <= b <= 99):
        return None
    return f"{a}:{b}"


def _single_percent_ratio(pct: int) -> str | None:
    if not 1 <= pct <= 99:
        return None
    return f"{pct}:{100 - pct}"


# ---------------------------------------------------------------------------
# Fault ratio extraction
# ---------------------------------------------------------------------------

_RE_ARABIC_PAIR = re.compile(
    r"(?:過失割合|責任割合|過失の割合|寄与度)?[^\d]{0,24}"
    r"(\d{1,2})\s*[:：対／/]\s*(\d{1,2})"
)
_RE_ARABIC_PAIR_LOOSE = re.compile(r"(\d{1,2})\s*[:：対／/]\s*(\d{1,2})")
_RE_KANJI_PAIR = re.compile(
    rf"(?:過失割合|責任割合)[^\d〇零一二三四五六七八九]{{0,24}}"
    rf"({_KANJI_INT_TOKEN})\s*[:：対]\s*({_KANJI_INT_TOKEN})"
)
_RE_NAMED_TENTHS = re.compile(
    r"責任割合は[^。]{0,40}?"
    r"([^\s、,]{1,16})"
    r"([〇零一二三四五六七八九十\d]{1,2})"
    r"[、,]"
    r"([^\s、,]{1,16})"
    r"([〇零一二三四五六七八九十\d]{1,2})"
)
_RE_PERCENT = re.compile(
    rf"(?:過失割合|責任割合|過失の割合)[^\d〇零一二三四五六七八九]{{0,32}}"
    rf"({_KANJI_INT_TOKEN}|\d{{1,2}})\s*(?:パーセント|％|%)"
)
_RE_PERCENT_LOOSE = re.compile(rf"({_KANJI_INT_TOKEN}|\d{{1,2}})\s*(?:パーセント|％|%)")
_RE_WARI = re.compile(
    r"(?:過失割合|過失|責任)[^。]{0,24}"
    rf"({_KANJI_INT_TOKEN}|\d{{1,2}})\s*割"
    r"(?:と認める|と判示|とする|である|が相当)?"
)
_RE_MIDDLE_DOT = re.compile(
    # 建昌六・五、有漁丸三・五 → 65:35
    r"(?:責任割合|過失割合)[^。]{0,48}?"
    r"[^\s、,]{1,16}?"
    r"([〇零一二三四五六七八九十\d]{1,2})\s*[・･]\s*"
    r"([〇零一二三四五六七八九十\d])"
    r"[、,]"
    r"[^\s、,]{1,16}?"
    r"([〇零一二三四五六七八九十\d]{1,2})\s*[・･]\s*"
    r"([〇零一二三四五六七八九十\d])"
)


def extract_fault_ratios(text: str) -> list[FaultRatioHit]:
    """Return ranked fault-ratio candidates from judgment text."""
    text = normalize_judgment_text(text)
    hits: list[FaultRatioHit] = []

    def add(a: int, b: int, evidence: str, method: str, confidence: float) -> None:
        ratio = _ratio_str(a, b)
        if ratio:
            hits.append(
                FaultRatioHit(
                    ratio=ratio,
                    evidence=evidence.strip()[:160],
                    method=method,
                    confidence=confidence,
                )
            )

    for m in _RE_ARABIC_PAIR.finditer(text):
        add(int(m.group(1)), int(m.group(2)), m.group(0), "arabic_pair", 0.95)

    for m in _RE_KANJI_PAIR.finditer(text):
        a, b = parse_kanji_int(m.group(1)), parse_kanji_int(m.group(2))
        if a is not None and b is not None:
            add(a, b, m.group(0), "kanji_pair", 0.95)

    for m in _RE_MIDDLE_DOT.finditer(text):
        a_whole = parse_kanji_int(m.group(1))
        a_frac = parse_kanji_int(m.group(2))
        b_whole = parse_kanji_int(m.group(3))
        b_frac = parse_kanji_int(m.group(4))
        if None not in (a_whole, a_frac, b_whole, b_frac):
            add(a_whole * 10 + a_frac, b_whole * 10 + b_frac, m.group(0), "middle_dot_tenths", 0.92)

    for m in _RE_NAMED_TENTHS.finditer(text):
        a, b = parse_kanji_int(m.group(2)), parse_kanji_int(m.group(4))
        if a is not None and b is not None:
            add(a, b, m.group(0), "named_tenths", 0.88)

    for m in _RE_PERCENT.finditer(text):
        pct = parse_kanji_int(m.group(1))
        if pct is not None:
            ratio = _single_percent_ratio(pct)
            if ratio:
                a_s, b_s = ratio.split(":")
                add(int(a_s), int(b_s), m.group(0), "labeled_percent", 0.9)

    for m in _RE_PERCENT_LOOSE.finditer(text):
        window = text[max(0, m.start() - 40) : m.end() + 10]
        if not re.search(r"(責任割合|過失割合|過失)", window):
            continue
        pct = parse_kanji_int(m.group(1))
        if pct is not None and 5 <= pct <= 95:
            ratio = _single_percent_ratio(pct)
            if ratio:
                a_s, b_s = ratio.split(":")
                add(int(a_s), int(b_s), window.strip(), "context_percent", 0.85)

    for m in _RE_WARI.finditer(text):
        wari = parse_kanji_int(m.group(1))
        if wari is not None and 1 <= wari <= 9:
            ratio = _single_percent_ratio(wari * 10)
            if ratio:
                a_s, b_s = ratio.split(":")
                add(int(a_s), int(b_s), m.group(0), "wari", 0.8)

    # 建昌65・有漁丸35 / 65・35 (optional ship name between sides)
    for m in re.finditer(
        r"(\d{1,2})\s*[・･]\s*(?:[^\d\s：:対／/]{0,16})?(\d{1,2})(?!\d)",
        text,
    ):
        window = text[max(0, m.start() - 24) : m.end() + 8]
        if re.search(r"(責任|過失|割合|按分|判示)", window):
            add(int(m.group(1)), int(m.group(2)), window, "compact_dot", 0.87)

    if not any(h.confidence >= 0.85 for h in hits):
        for m in _RE_ARABIC_PAIR_LOOSE.finditer(text):
            window = text[max(0, m.start() - 30) : m.end() + 10]
            if re.search(r"(過失|責任|割合)", window):
                add(int(m.group(1)), int(m.group(2)), window, "loose_arabic", 0.7)

    if re.search(r"主因", text) and re.search(r"一因", text):
        hits.append(
            FaultRatioHit(ratio="70:30", evidence="主因/一因", method="shuin_ichin", confidence=0.65)
        )
    elif re.search(r"によって発生", text) and re.search(r"一因", text):
        hits.append(
            FaultRatioHit(
                ratio="70:30",
                evidence="によって発生+一因",
                method="hassei_ichin",
                confidence=0.6,
            )
        )

    hits.sort(key=lambda h: (-h.confidence, h.ratio))
    seen: set[str] = set()
    unique: list[FaultRatioHit] = []
    for h in hits:
        if h.ratio not in seen:
            seen.add(h.ratio)
            unique.append(h)
    return unique


def best_fault_ratio(text: str) -> str | None:
    hits = extract_fault_ratios(text)
    return hits[0].ratio if hits else None


# ---------------------------------------------------------------------------
# Monetary award extraction
# ---------------------------------------------------------------------------

_YEN_LABELS: list[tuple[str, str]] = [
    ("claimed", r"(?:請求額|請求金額|損害額合計|請求の趣旨|損失補償請求額|本訴請求)"),
    ("awarded", r"(?:認容額|認容|支払を命じ|損害賠償金|支払え|賠償を命)"),
    ("disallowed", r"(?:棄却|否認|排除|認めない|減額)"),
]


def extract_yen_amounts(text: str) -> list[YenHit]:
    text = normalize_judgment_text(text)
    hits: list[YenHit] = []

    for label, pat in _YEN_LABELS:
        for m in re.finditer(pat, text):
            window = text[m.start() : m.start() + 80]
            amount = None
            evidence = window
            am = _ARABIC_YEN.search(window)
            if am:
                amount = parse_yen_token(am.group(1))
                evidence = am.group(0)
            else:
                km = _KANJI_YEN.search(window)
                if km:
                    amount = parse_yen_token(km.group(1))
                    evidence = km.group(0)
            if amount is not None and amount > 0:
                hits.append(YenHit(amount_jpy=amount, label=label, evidence=evidence[:80]))

    for m in _ARABIC_YEN.finditer(text):
        amount = parse_yen_token(m.group(1))
        if amount is not None and amount >= 100_000:
            hits.append(YenHit(amount_jpy=amount, label="unlabeled", evidence=m.group(0)))
    for m in _KANJI_YEN.finditer(text):
        amount = parse_yen_token(m.group(1))
        if amount is not None and amount >= 100_000:
            hits.append(YenHit(amount_jpy=amount, label="unlabeled_kanji", evidence=m.group(0)))

    return hits


def _first_labeled(hits: list[YenHit], label: str) -> int | None:
    for h in hits:
        if h.label == label:
            return h.amount_jpy
    return None


# ---------------------------------------------------------------------------
# Operative holding (過失相殺) excerpt
# ---------------------------------------------------------------------------


def extract_negligence_holding(text: str, *, window: int = 280) -> str | None:
    """Locate the comparative-negligence operative passage."""
    text = normalize_judgment_text(text)
    if not text:
        return None
    best_idx = None
    for anchor in _HOLDING_ANCHORS:
        idx = text.find(anchor)
        if idx >= 0 and (best_idx is None or idx < best_idx):
            best_idx = idx
    if best_idx is None:
        hits = extract_fault_ratios(text)
        if hits and hits[0].evidence:
            return hits[0].evidence
        return None
    start = max(0, best_idx - 40)
    end = min(len(text), best_idx + window)
    excerpt = text[start:end].strip()
    if "。" in excerpt[40:]:
        cut = excerpt.find("。", 40)
        if cut > 0:
            excerpt = excerpt[: cut + 1]
    return excerpt


# ---------------------------------------------------------------------------
# Public pipeline
# ---------------------------------------------------------------------------


def extract_from_judgment(text: str) -> JudgmentExtraction:
    """Run full extraction over a raw judgment / saiketsu text body."""
    text = normalize_judgment_text(text)
    result = JudgmentExtraction()
    if not text:
        return result

    hits = extract_fault_ratios(text)
    result.fault_ratio_hits = hits
    if hits:
        result.fault_ratio = hits[0].ratio

    yen_hits = extract_yen_amounts(text)
    result.yen_hits = yen_hits
    result.claimed_repair_jpy = _first_labeled(yen_hits, "claimed")
    result.awarded_damages_jpy = _first_labeled(yen_hits, "awarded")
    result.disallowed_jpy = _first_labeled(yen_hits, "disallowed")

    if result.awarded_damages_jpy is None and result.claimed_repair_jpy is None:
        unlabeled = [h for h in yen_hits if h.label.startswith("unlabeled")]
        if unlabeled and re.search(r"(損害|賠償|請求|認容)", text):
            result.awarded_damages_jpy = max(h.amount_jpy for h in unlabeled)

    result.holding_excerpt = extract_negligence_holding(text)
    return result


def extraction_matches_gold(
    extracted: JudgmentExtraction,
    gold: dict[str, Any],
    *,
    require_yen: bool = False,
) -> dict[str, Any]:
    """
    Compare extraction to a civil_precedent_catalog seed.

    Fault ratio: exact string match on ``A:B``.
    Yen: exact match when gold field is an int; None gold fields are ignored.
    Unlabeled yen hits that equal the gold amount also count as a match.
    """
    report: dict[str, Any] = {
        "fault_ratio_ok": None,
        "claimed_ok": None,
        "awarded_ok": None,
        "disallowed_ok": None,
    }
    gold_fr = gold.get("fault_ratio")
    if gold_fr:
        report["fault_ratio_ok"] = extracted.fault_ratio == gold_fr
        report["fault_ratio_extracted"] = extracted.fault_ratio
        report["fault_ratio_gold"] = gold_fr

    for field_name, attr in (
        ("claimed_ok", "claimed_repair_jpy"),
        ("awarded_ok", "awarded_damages_jpy"),
        ("disallowed_ok", "disallowed_jpy"),
    ):
        gold_v = gold.get(attr)
        if isinstance(gold_v, int):
            got = getattr(extracted, attr)
            ok = got == gold_v or any(h.amount_jpy == gold_v for h in extracted.yen_hits)
            report[field_name] = ok
            report[f"{attr}_extracted"] = got
            report[f"{attr}_gold"] = gold_v
        elif require_yen:
            report[field_name] = False

    checks = [v for k, v in report.items() if k.endswith("_ok") and v is not None]
    report["all_ok"] = bool(checks) and all(checks)
    report["scored_fields"] = len(checks)
    report["passed_fields"] = sum(1 for v in checks if v)
    return report
