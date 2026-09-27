"""Rasterize PDF pages for in-browser preview (pdftoppm / Poppler).

Many embedded browsers (and some Chromium builds) leave ``<iframe src=*.pdf>``
blank. Page PNGs render everywhere and keep the demo offline.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from marine_claims_ai.paths import DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)

PREVIEW_DIR = DEFAULT_DATA_DIR / "demo_pdf_pages"
DEFAULT_MAX_PAGES = 8
DEFAULT_DPI = 120


def ensure_pdf_page_previews(
    pdf_path: Path,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    dpi: int = DEFAULT_DPI,
) -> list[Path]:
    """Return PNG paths for the first ``max_pages`` of ``pdf_path`` (cached)."""
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        return []

    out_dir = PREVIEW_DIR / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    marker = out_dir / ".source_mtime"
    pdf_mtime = str(pdf_path.stat().st_mtime_ns)
    existing = sorted(out_dir.glob("page-*.png"))
    if existing and marker.is_file() and marker.read_text(encoding="utf-8") == pdf_mtime:
        return existing[:max_pages]

    if shutil.which("pdftoppm") is None:
        logger.warning("pdftoppm not found; cannot rasterize %s", pdf_path.name)
        return []

    # Clear stale pages for this stem.
    for old in out_dir.glob("page-*.png"):
        old.unlink(missing_ok=True)

    prefix = out_dir / "page"
    try:
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                str(dpi),
                "-f",
                "1",
                "-l",
                str(max_pages),
                str(pdf_path),
                str(prefix),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("pdftoppm failed for %s: %s", pdf_path.name, exc)
        return []

    marker.write_text(pdf_mtime, encoding="utf-8")
    return sorted(out_dir.glob("page-*.png"))[:max_pages]


def page_index_from_name(name: str) -> int | None:
    """Parse ``page-3.png`` → 3."""
    stem = Path(name).stem  # page-3
    if not stem.startswith("page-"):
        return None
    try:
        return int(stem.split("-", 1)[1])
    except ValueError:
        return None
