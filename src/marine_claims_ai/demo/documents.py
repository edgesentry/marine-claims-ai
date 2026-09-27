"""Local public / uploaded PDF catalog for the executive demo (Zero-Dataset)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from marine_claims_ai.paths import DEFAULT_DATA_DIR, DEFAULT_DATASET_DIR, LEGACY_DATASET_DIR

DocRole = Literal["spec", "casualty", "judgment", "any"]

UPLOAD_DIR = DEFAULT_DATA_DIR / "demo_uploads"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# Known public demo documents (basename → EN/JA short labels).
_KNOWN: dict[str, dict[str, str]] = {
    "fukuoka_kaiyomaru_spec.pdf": {
        "en": "Fukuoka Kaiyo Maru repair specification",
        "ja": "福岡・開洋丸 修繕仕様書",
        "roles": "spec,uc2",
    },
    "sample_drydock_repair_specification.pdf": {
        "en": "Sample drydock repair specification",
        "ja": "サンプル入渠修繕仕様書",
        "roles": "spec,uc2",
    },
    "jtsb_cargo_collision_report.pdf": {
        "en": "JTSB cargo vessel collision report",
        "ja": "運輸安全委員会・貨物船衝突報告書",
        "roles": "casualty,uc3",
    },
    "jtsb_tanker_bridge_collision_report.pdf": {
        "en": "JTSB tanker bridge collision report",
        "ja": "運輸安全委員会・タンカー橋脚衝突報告書",
        "roles": "casualty,uc3",
    },
    "fukuoka_ship_bid_result.pdf": {
        "en": "Fukuoka ship repair bid result",
        "ja": "福岡・船舶修繕落札結果",
        "roles": "uc2",
    },
}

_DEFAULT_UC1_SPEC = "fukuoka_kaiyomaru_spec.pdf"
_DEFAULT_UC1_CASUALTY = "jtsb_cargo_collision_report.pdf"


@dataclass(frozen=True)
class DocEntry:
    id: str
    path: Path
    label_en: str
    label_ja: str
    roles: frozenset[str]
    uploaded: bool = False

    def label(self, lang: str = "en") -> str:
        return self.label_ja if lang == "ja" else self.label_en


def ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def dataset_search_dirs() -> list[Path]:
    dirs: list[Path] = []
    for d in (DEFAULT_DATASET_DIR, LEGACY_DATASET_DIR, UPLOAD_DIR):
        if d.is_dir() and d not in dirs:
            dirs.append(d)
    return dirs


def resolve_pdf(name_or_path: str | Path | None) -> Path | None:
    """Resolve a basename or absolute/relative path to an existing PDF."""
    if not name_or_path:
        return None
    raw = Path(str(name_or_path)).expanduser()
    if raw.is_file() and raw.suffix.lower() == ".pdf":
        return raw.resolve()
    name = raw.name
    for base in dataset_search_dirs():
        cand = base / name
        if cand.is_file():
            return cand.resolve()
    return None


def list_pdfs(*, role: str | None = None) -> list[DocEntry]:
    """List discoverable PDFs; optional role filter (spec/casualty/uc2/uc3/any)."""
    found: dict[str, DocEntry] = {}
    for base in dataset_search_dirs():
        uploaded = base == UPLOAD_DIR
        for path in sorted(base.glob("*.pdf")):
            meta = _KNOWN.get(path.name)
            if meta:
                roles = frozenset(meta["roles"].split(","))
                label_en, label_ja = meta["en"], meta["ja"]
            else:
                roles = frozenset({"any", "spec", "casualty", "uc2", "uc3"})
                stem = path.stem.replace("_", " ")
                label_en = stem
                label_ja = path.name
            entry = DocEntry(
                id=path.name,
                path=path.resolve(),
                label_en=label_en,
                label_ja=label_ja,
                roles=roles,
                uploaded=uploaded,
            )
            # Prefer _data over _inputs / uploads when same basename
            prev = found.get(path.name)
            if prev is None or (not uploaded and prev.uploaded):
                found[path.name] = entry
            elif not uploaded and prev.path.parts != path.resolve().parts:
                if DEFAULT_DATASET_DIR in path.parents or str(path).startswith(str(DEFAULT_DATASET_DIR)):
                    found[path.name] = entry

    entries = list(found.values())
    if role and role != "any":
        entries = [e for e in entries if role in e.roles or "any" in e.roles]
    return sorted(entries, key=lambda e: (e.uploaded, e.label_en.lower()))


def default_uc1_pair() -> tuple[Path | None, Path | None]:
    return resolve_pdf(_DEFAULT_UC1_SPEC), resolve_pdf(_DEFAULT_UC1_CASUALTY)


def sanitize_upload_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-()\u3040-\u30ff\u4e00-\u9fff]+", "_", base, flags=re.UNICODE)
    if not base.lower().endswith(".pdf"):
        base = f"{base}.pdf"
    if base.startswith("."):
        base = f"doc{base}"
    return base[:180] or "upload.pdf"


def save_upload(filename: str, data: bytes) -> Path:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"file_too_large:{MAX_UPLOAD_BYTES}")
    if not data[:8].startswith(b"%PDF"):
        # Allow empty check soft — some PDFs have BOM; still require %PDF somewhere early
        if b"%PDF" not in data[:1024]:
            raise ValueError("not_a_pdf")
    ensure_upload_dir()
    safe = sanitize_upload_filename(filename)
    dest = UPLOAD_DIR / safe
    dest.write_bytes(data)
    return dest.resolve()


def pdftotext_available() -> bool:
    import shutil

    return shutil.which("pdftotext") is not None
