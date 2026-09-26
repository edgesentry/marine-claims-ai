"""Summarize Field 4 civil precedent coverage (fault ratios + yen)."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from marine_claims_ai.ingest.civil import CIVIL_JSON, catalog_stats, load_catalog
from marine_claims_ai.paths import DEFAULT_DATASET_DIR


def coverage_from_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        raise ValueError(f"Expected list in {path}")
    stats = catalog_stats(cases)
    stats["path"] = str(path)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATASET_DIR),
        help="Directory containing benchmark_court_civil_cases.json",
    )
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="Report coverage of tracked config/civil_precedent_catalog.json instead",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.catalog:
        stats = catalog_stats(load_catalog())
        stats["path"] = "config/civil_precedent_catalog.json"
    else:
        path = os.path.join(args.data_dir, CIVIL_JSON)
        if not os.path.exists(path):
            print(f"[ERROR] Missing {path}. Run: uv run python scripts/fetch_public_datasets.py --field 4 --force")
            return 1
        stats = coverage_from_json(path)

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print(f"path: {stats['path']}")
        print(f"total: {stats['total']}")
        print(f"non_synthetic: {stats['non_synthetic']}")
        print(f"non_synthetic_with_fault_ratio: {stats['non_synthetic_with_fault_ratio']}")
        print(f"non_synthetic_with_yen: {stats['non_synthetic_with_yen']}")
        print(f"synthetic: {stats['synthetic']}")
        dod_fr = stats["non_synthetic_with_fault_ratio"] >= 30
        dod_yen = stats["non_synthetic_with_yen"] >= 15
        print(f"DoD fault_ratio>=30: {'PASS' if dod_fr else 'FAIL'}")
        print(f"DoD yen>=15: {'PASS' if dod_yen else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
