"""
Noise-resilient OCR cleanup and table reconstruction for scanned drydock invoices.

Issue #45 — deskew / contrast / stamp suppression / table grid → RepairItem.
Browser live path stays Tesseract.js (#94); this module is the offline / eval path.

Image ops require optional extras::

    pip install 'marine-claims-ai[ocr]'

Pure-Python tabular extraction (``extract_tabular_lines``) needs no extras.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from marine_claims_ai.paths import DEFAULT_OCR_CACHE_DIR, REPO_ROOT

DEFAULT_DEGRADED_FIXTURES_PATH = (
    REPO_ROOT / "config" / "degraded_invoice_fixtures" / "manifest.json"
)

_OCR_INSTALL_HINT = (
    "OCR image ops require optional deps. Install with: "
    "pip install 'marine-claims-ai[ocr]'  (or: uv sync --extra ocr)"
)

# Align with web/src/pdf/repairLines.ts yen heuristic.
_YEN_RE = re.compile(r"(?:¥|￥|JPY)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})")
_HAS_AMOUNT_RE = re.compile(r"(?:¥|￥|JPY)?\s*[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,}")


class RepairItem(BaseModel):
    """Single repair line item — Stage A schema contract shared with PWA ExtractedItem."""

    model_config = ConfigDict(extra="forbid")

    description: str
    estimated_cost: int
    row_index: int | None = None
    source_quote: str | None = None
    bbox: tuple[int, int, int, int] | None = None  # x0, y0, x1, y1


class Cell(BaseModel):
    """Detected table cell bounding box (pixel coordinates)."""

    model_config = ConfigDict(extra="forbid")

    x0: int
    y0: int
    x1: int
    y1: int
    row: int = 0
    col: int = 0


class CellText(BaseModel):
    """OCR text associated with a table cell."""

    model_config = ConfigDict(extra="forbid")

    cell: Cell
    text: str = ""


def _require_cv2():
    try:
        import cv2  # noqa: F401
        import numpy as np  # noqa: F401
    except ImportError as exc:
        raise ImportError(_OCR_INSTALL_HINT) from exc
    import cv2
    import numpy as np

    return cv2, np


def _require_pil():
    try:
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise ImportError(_OCR_INSTALL_HINT) from exc
    from PIL import Image

    return Image


def _require_tesseract():
    try:
        import pytesseract  # noqa: F401
    except ImportError as exc:
        raise ImportError(_OCR_INSTALL_HINT) from exc
    import pytesseract

    return pytesseract


def load_image(path: Path | str):
    """Load an image as a BGR ndarray (OpenCV convention)."""
    cv2, np = _require_cv2()
    path = Path(path)
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    return image


def deskew(image):
    """Estimate and correct small skew angles via min-area rectangle of ink pixels."""
    cv2, np = _require_cv2()
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(binary > 0))
    if coords.size == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    # OpenCV returns angle in [-90, 0); normalize to a small skew.
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    # Clamp extreme estimates (handwriting / stamps can confuse minAreaRect).
    if abs(angle) > 15:
        angle = 0.0
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def normalize_contrast(image):
    """CLAHE contrast normalization on the luminance channel."""
    cv2, _np = _require_cv2()
    if len(image.shape) == 2:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    merged = cv2.merge([l_ch, a_ch, b_ch])
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def suppress_stamp_noise(image):
    """Attenuate high-saturation red/orange stamp-like blobs while keeping print ink."""
    cv2, np = _require_cv2()
    if len(image.shape) != 3:
        return image
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Japanese hanko / red stamps: hue near 0/180, high saturation.
    lower1 = np.array([0, 80, 80], dtype=np.uint8)
    upper1 = np.array([12, 255, 255], dtype=np.uint8)
    lower2 = np.array([168, 80, 80], dtype=np.uint8)
    upper2 = np.array([180, 255, 255], dtype=np.uint8)
    mask = cv2.bitwise_or(
        cv2.inRange(hsv, lower1, upper1),
        cv2.inRange(hsv, lower2, upper2),
    )
    # Keep only large connected components (stamps), not thin red underlines.
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cleaned = mask.copy()
    cleaned[:] = 0
    min_area = max(80, (image.shape[0] * image.shape[1]) // 8000)
    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area >= min_area:
            cleaned[labels == i] = 255
    if not np.any(cleaned):
        return image
    out = image.copy()
    out[cleaned > 0] = (255, 255, 255)
    return out


def detect_table_grid(image) -> list[Cell]:
    """Detect table-like cell regions via morphological line extraction + projections."""
    cv2, np = _require_cv2()
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10
    )
    h, w = binary.shape[:2]
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 30, 20), 1))
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 30, 20)))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horiz_kernel, iterations=1)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vert_kernel, iterations=1)

    def _line_positions(mask, axis: int, min_fill: float) -> list[int]:
        """axis=0 → row sums (horizontal lines); axis=1 → col sums (vertical lines)."""
        sums = mask.sum(axis=axis).astype(np.float64)
        length = mask.shape[1 - axis]
        threshold = min_fill * 255.0 * length
        peaks = np.where(sums >= threshold)[0]
        if peaks.size == 0:
            return []
        # Cluster contiguous peak indices into single line positions.
        groups: list[list[int]] = [[int(peaks[0])]]
        for p in peaks[1:]:
            p_i = int(p)
            if p_i - groups[-1][-1] <= 3:
                groups[-1].append(p_i)
            else:
                groups.append([p_i])
        return [int(sum(g) / len(g)) for g in groups]

    y_lines = _line_positions(horizontal, axis=1, min_fill=0.35)
    x_lines = _line_positions(vertical, axis=0, min_fill=0.25)

    # Fallback: invent a simple row grid from ink density when rule lines are weak.
    if len(y_lines) < 2:
        row_density = binary.sum(axis=1).astype(np.float64)
        thresh = 0.08 * 255.0 * w
        ink_rows = np.where(row_density > thresh)[0]
        if ink_rows.size:
            bands: list[list[int]] = [[int(ink_rows[0])]]
            for r in ink_rows[1:]:
                r_i = int(r)
                if r_i - bands[-1][-1] <= 4:
                    bands[-1].append(r_i)
                else:
                    bands.append([r_i])
            y_lines = []
            for band in bands:
                y_lines.append(max(0, band[0] - 2))
                y_lines.append(min(h - 1, band[-1] + 2))
            y_lines = sorted(set(y_lines))

    if len(x_lines) < 2:
        x_lines = [0, w // 3, (2 * w) // 3, w - 1]
    if len(y_lines) < 2:
        y_lines = [0, h // 4, h // 2, (3 * h) // 4, h - 1]

    cells: list[Cell] = []
    for ri, (y0, y1) in enumerate(zip(y_lines[:-1], y_lines[1:])):
        if y1 - y0 < 8:
            continue
        for ci, (x0, x1) in enumerate(zip(x_lines[:-1], x_lines[1:])):
            if x1 - x0 < 8:
                continue
            cells.append(Cell(x0=int(x0), y0=int(y0), x1=int(x1), y1=int(y1), row=ri, col=ci))
    return cells


def reconstruct_cells(image, cells: Sequence[Cell]) -> list[CellText]:
    """OCR each cell (pytesseract) or return empty text if tesseract is unavailable."""
    cv2, _np = _require_cv2()
    try:
        pytesseract = _require_tesseract()
    except ImportError:
        return [CellText(cell=c, text="") for c in cells]

    results: list[CellText] = []
    for cell in cells:
        crop = image[cell.y0 : cell.y1, cell.x0 : cell.x1]
        if crop.size == 0:
            results.append(CellText(cell=cell, text=""))
            continue
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop
        try:
            text = pytesseract.image_to_string(gray, lang="jpn+eng", config="--psm 6")
        except Exception:
            text = ""
        results.append(CellText(cell=cell, text=(text or "").strip()))
    return results


def normalize_ocr_yen_text(text: str) -> str:
    """Light OCR cleanup for yen amounts (mirrors web normalizeOcrYenText)."""
    text = re.sub(r"(\d)F9", r"\1円", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d)\.(?=\d{3}(?:\D|$))", r"\1,", text)
    return text


def reconstruct_table_lines(text: str) -> str:
    """Merge broken OCR rows (description without amount + following amount line)."""
    lines = [ln.strip() for ln in text.splitlines()]
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue
        if not _HAS_AMOUNT_RE.search(line) and i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt and _HAS_AMOUNT_RE.search(nxt):
                # Description on this line, amount on next (possibly with more desc).
                if _HAS_AMOUNT_RE.fullmatch(nxt.replace(" ", "")) or len(nxt) < 40:
                    merged.append(f"{line} {nxt}".strip())
                    i += 2
                    continue
                # Amount-only fragment after description.
                if re.match(r"^[¥￥JPY\s0-9,円\.]+$", nxt, flags=re.IGNORECASE):
                    merged.append(f"{line} {nxt}".strip())
                    i += 2
                    continue
        merged.append(line)
        i += 1
    return "\n".join(merged)


def extract_tabular_lines(
    ocr_lines: Sequence[str] | Sequence[CellText] | str,
) -> list[RepairItem]:
    """
    Yen-line extractor resilient to column misalignment and broken lines.

    Accepts raw OCR text, a list of lines, or CellText rows (joined left-to-right).
    Compatible with PWA ``ExtractedItem``: ``{description, estimated_cost}``.
    """
    if isinstance(ocr_lines, str):
        text = ocr_lines
    elif ocr_lines and isinstance(ocr_lines[0], CellText):
        # Group cells by row, join by column order.
        by_row: dict[int, list[CellText]] = {}
        for ct in ocr_lines:  # type: ignore[assignment]
            assert isinstance(ct, CellText)
            by_row.setdefault(ct.cell.row, []).append(ct)
        rows: list[str] = []
        for row_idx in sorted(by_row):
            cells = sorted(by_row[row_idx], key=lambda c: c.cell.col)
            rows.append(" ".join(c.text for c in cells if c.text).strip())
        text = "\n".join(rows)
    else:
        text = "\n".join(str(x) for x in ocr_lines)

    text = reconstruct_table_lines(normalize_ocr_yen_text(text))
    items: list[RepairItem] = []
    for idx, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if len(line) < 4:
            continue
        amounts = [int(m.group(1).replace(",", "")) for m in _YEN_RE.finditer(line)]
        if not amounts:
            continue
        cost = amounts[-1]
        if cost < 1000:
            continue
        description = _YEN_RE.sub("", line)
        description = re.sub(r"\s+", " ", description).strip()[:120]
        if not description:
            continue
        items.append(
            RepairItem(
                description=description,
                estimated_cost=cost,
                row_index=idx,
                source_quote=line[:200],
            )
        )
        if len(items) >= 40:
            break
    return items


def preprocess_invoice_image(image):
    """Deskew → stamp suppress → contrast normalize (OpenCV pipeline)."""
    return normalize_contrast(suppress_stamp_noise(deskew(image)))


def ocr_full_image(image) -> str:
    """Run Tesseract on a full page image (jpn+eng)."""
    cv2, _np = _require_cv2()
    pytesseract = _require_tesseract()
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    try:
        return (pytesseract.image_to_string(gray, lang="jpn+eng", config="--psm 6") or "").strip()
    except Exception:
        return ""


def process_invoice_image(
    path: Path | str,
    *,
    cache_dir: Path | None = None,
    cache_key: str | None = None,
    write_cache: bool = True,
) -> list[RepairItem]:
    """
    Full #45 pipeline: load → preprocess → grid → cell/page OCR → RepairItem list.

    Intermediate JSON (Zero-Dataset) lands under ``_data/cache/ocr/`` when write_cache.
    """
    cv2, _np = _require_cv2()
    path = Path(path)
    image = load_image(path)
    cleaned = preprocess_invoice_image(image)
    cells = detect_table_grid(cleaned)
    cell_texts = reconstruct_cells(cleaned, cells)
    items = extract_tabular_lines(cell_texts)
    page_text = ""
    if len(items) < 2:
        # Fallback: full-page OCR when grid cells are empty / weak.
        page_text = ocr_full_image(cleaned)
        items = extract_tabular_lines(page_text)

    if write_cache:
        out_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_OCR_CACHE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        key = cache_key or path.stem
        payload = {
            "source": str(path),
            "items": [it.model_dump() for it in items],
            "ocr_text": page_text or "\n".join(ct.text for ct in cell_texts if ct.text),
            "cells": [c.model_dump() for c in cells],
        }
        cache_path = out_dir / f"{key}.json"
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # Also stash a cleaned PNG for local inspection (gitignored via _data/).
        png_path = out_dir / f"{key}_cleaned.png"
        cv2.imencode(".png", cleaned)[1].tofile(str(png_path))

    return items


def load_degraded_fixtures(path: Path | None = None) -> dict[str, Any]:
    """Load tracked degraded-invoice manifest (Zero-Dataset allowlist under config/)."""
    fixture_path = path or DEFAULT_DEGRADED_FIXTURES_PATH
    return json.loads(Path(fixture_path).read_text(encoding="utf-8"))


def line_item_recall(
    predicted: Sequence[RepairItem],
    expected: Sequence[Mapping[str, Any]],
) -> tuple[float, float]:
    """
    Return (item_recall, amount_recall) in [0, 1].

    A gold row matches if estimated_cost equals and description is a substring
    match either way (OCR noise tolerant).
    """
    if not expected:
        return 1.0, 1.0
    matched_items = 0
    matched_amounts = 0
    used: set[int] = set()
    for gold in expected:
        gold_cost = int(gold["estimated_cost"])
        gold_desc = str(gold.get("description", "")).strip()
        amount_hit = any(p.estimated_cost == gold_cost for p in predicted)
        if amount_hit:
            matched_amounts += 1
        found = False
        for i, pred in enumerate(predicted):
            if i in used:
                continue
            if pred.estimated_cost != gold_cost:
                continue
            if not gold_desc or gold_desc in pred.description or pred.description in gold_desc:
                used.add(i)
                found = True
                break
        if found:
            matched_items += 1
    n = len(expected)
    return matched_items / n, matched_amounts / n


def render_synthetic_invoice(
    lines: Sequence[str],
    *,
    skew_degrees: float = 0.0,
    blur_radius: float = 0.0,
    noise_sigma: float = 0.0,
    stamp: bool = False,
) -> Any:
    """
    Render a synthetic drydock invoice image with optional degradation (Pillow + OpenCV).

    Used by tests / local fixtures — never commit generated PNGs (Zero-Dataset).
    """
    Image = _require_pil()
    cv2, np = _require_cv2()

    width, height = 900, 200 + 36 * len(lines)
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    # Default bitmap font is Latin-only; draw ASCII-safe amounts plus JP via UTF-8
    # by encoding text as image using PIL's default when Japanese fonts are absent.
    # Prefer a system font that supports Japanese when available.
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for candidate in (
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ):
        try:
            font = ImageFont.truetype(candidate, 22)
            break
        except OSError:
            continue

    y = 40
    draw.text((40, 12), "Repair specification (synthetic scan)", fill=(0, 0, 0), font=font)
    for line in lines:
        draw.text((40, y), line, fill=(0, 0, 0), font=font)
        # Light horizontal rule for grid detection.
        draw.line([(30, y + 28), (width - 30, y + 28)], fill=(180, 180, 180), width=1)
        y += 36
    # Vertical-ish column guides.
    draw.line([(520, 30), (520, height - 20)], fill=(200, 200, 200), width=1)

    if stamp:
        # Red circular stamp (hanko-like) overlapping text.
        cx, cy, r = width - 120, 90, 45
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(200, 30, 30), width=4)
        draw.text((cx - 28, cy - 10), "印", fill=(200, 30, 30), font=font)

    arr = np.array(img)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    if abs(skew_degrees) > 0.01:
        (h, w) = bgr.shape[:2]
        matrix = cv2.getRotationMatrix2D((w // 2, h // 2), skew_degrees, 1.0)
        bgr = cv2.warpAffine(bgr, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    if blur_radius > 0:
        k = max(1, int(blur_radius) * 2 + 1)
        bgr = cv2.GaussianBlur(bgr, (k, k), blur_radius)

    if noise_sigma > 0:
        noise = np.random.normal(0, noise_sigma, bgr.shape).astype(np.float32)
        noisy = bgr.astype(np.float32) + noise
        bgr = np.clip(noisy, 0, 255).astype(np.uint8)

    return bgr


def save_image(path: Path | str, image) -> Path:
    """Write a BGR image to disk (creates parents)."""
    cv2, _np = _require_cv2()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise ValueError(f"Failed to encode image for {path}")
    buf.tofile(str(path))
    return path
