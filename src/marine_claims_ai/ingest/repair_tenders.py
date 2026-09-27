"""Idempotent crawler for public ship-repair / drydock tender PDFs.

Writes only under ``_inputs/repairs/{specs,bids}/`` (gitignored).
URL list is tracked in ``config/repair_tender_manifest.json``.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from marine_claims_ai.ingest.download import download_url, polite_sleep
from marine_claims_ai.paths import (
    DEFAULT_DATASET_DIR,
    DEFAULT_INPUT_REPAIRS_DIR,
    LEGACY_DATASET_DIR,
    REPO_ROOT,
)

DEFAULT_MANIFEST = REPO_ROOT / "config" / "repair_tender_manifest.json"


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_MANIFEST
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("entries"), list):
        raise ValueError(f"Invalid repair tender manifest: {cfg_path}")
    return data


def _kind_dir(kind: str, repairs_root: Path) -> Path:
    if kind == "bid":
        return repairs_root / "bids"
    return repairs_root / "specs"


def _resolve_seed(local_seed: str) -> Path | None:
    name = Path(local_seed).name
    for base in (DEFAULT_DATASET_DIR, LEGACY_DATASET_DIR, DEFAULT_INPUT_REPAIRS_DIR / "specs"):
        candidate = base / name
        if candidate.is_file():
            return candidate
    # Also allow bids seed under repairs/bids or flat dataset
    for base in (DEFAULT_INPUT_REPAIRS_DIR / "bids",):
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def fetch_repair_tenders(
    *,
    manifest_path: str | Path | None = None,
    repairs_dir: str | Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    limit: int = 0,
) -> dict[str, Any]:
    """
    Download (or seed-copy) manifest entries into ``_inputs/repairs/{specs,bids}/``.

    Returns a summary dict suitable for CLI / tests. Failures are WARN-level and
    do not abort the batch.
    """
    manifest = load_manifest(manifest_path)
    root = Path(repairs_dir) if repairs_dir else DEFAULT_INPUT_REPAIRS_DIR
    sleep_s = float(manifest.get("polite_sleep_seconds") or 0.0)
    entries = list(manifest["entries"])
    if limit and limit > 0:
        entries = entries[:limit]

    summary: dict[str, Any] = {
        "repairs_dir": str(root),
        "dry_run": dry_run,
        "fetched": 0,
        "skipped": 0,
        "seeded": 0,
        "failed": 0,
        "missing_url": 0,
        "results": [],
    }

    for entry in entries:
        kind = str(entry.get("kind") or "spec")
        filename = str(entry.get("filename") or entry.get("id") or "unknown.pdf")
        dest_dir = _kind_dir(kind, root)
        dest = dest_dir / filename
        url = entry.get("url")
        local_seed = entry.get("local_seed")
        row: dict[str, Any] = {
            "id": entry.get("id"),
            "kind": kind,
            "filename": filename,
            "dest": str(dest),
            "url": url,
        }

        if dry_run:
            row["action"] = "dry_run"
            exists = dest.is_file() and dest.stat().st_size > 0
            row["would_skip"] = exists and not force
            summary["results"].append(row)
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)

        if dest.is_file() and dest.stat().st_size > 0 and not force:
            row["action"] = "skip_exists"
            summary["skipped"] += 1
            summary["results"].append(row)
            print(f"  [SKIP] {filename}")
            continue

        if url:
            ok = download_url(str(url), str(dest), force=force, timeout=60)
            if ok:
                row["action"] = "fetched"
                summary["fetched"] += 1
            else:
                row["action"] = "failed"
                summary["failed"] += 1
            summary["results"].append(row)
            polite_sleep(sleep_s)
            continue

        if local_seed:
            seed = _resolve_seed(str(local_seed))
            if seed is None:
                row["action"] = "missing_seed"
                summary["failed"] += 1
                summary["missing_url"] += 1
                print(f"  [WARN] No URL and seed missing for {filename}")
            else:
                if seed.resolve() != dest.resolve():
                    shutil.copy2(seed, dest)
                row["action"] = "seeded"
                row["seed"] = str(seed)
                summary["seeded"] += 1
                print(f"  [SEED] {filename} ← {seed}")
            summary["results"].append(row)
            continue

        row["action"] = "missing_url"
        summary["failed"] += 1
        summary["missing_url"] += 1
        print(f"  [WARN] No URL/seed for {filename}")
        summary["results"].append(row)

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument(
        "--repairs-dir",
        default=str(DEFAULT_INPUT_REPAIRS_DIR),
        help="Destination root (default: _inputs/repairs)",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    print("=== Public repair tender crawler ===")
    print(f"Manifest: {args.manifest}")
    print(f"Dest: {args.repairs_dir}")
    summary = fetch_repair_tenders(
        manifest_path=args.manifest,
        repairs_dir=args.repairs_dir,
        force=args.force,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    print(
        f"[done] fetched={summary['fetched']} seeded={summary['seeded']} "
        f"skipped={summary['skipped']} failed={summary['failed']} dry_run={summary['dry_run']}"
    )
    return 0 if summary["failed"] == 0 or args.dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
