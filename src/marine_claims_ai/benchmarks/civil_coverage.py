"""Summarize Field 4 coverage — real precedents and synthetic regression, separately."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from marine_claims_ai.ingest.civil import (
    CIVIL_JSON,
    REAL_DOD_FAULT_RATIO,
    REAL_DOD_YEN,
    SYNTHETIC_JSON,
    catalog_stats,
    load_catalog,
    load_synthetic_catalog,
    real_dod_status,
)
from marine_claims_ai.paths import DEFAULT_DATASET_DIR


def coverage_from_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        raise ValueError(f"Expected list in {path}")
    stats = catalog_stats(cases)
    stats["path"] = str(path)
    return stats


def _print_lane(label: str, stats: dict, check_dod: bool) -> None:
    print(f"=== {label} ===")
    print(f"path: {stats['path']}")
    print(f"total: {stats['total']}")
    print(f"non_synthetic: {stats['non_synthetic']}")
    print(f"non_synthetic_with_fault_ratio: {stats['non_synthetic_with_fault_ratio']}")
    print(f"non_synthetic_with_yen: {stats['non_synthetic_with_yen']}")
    print(f"non_synthetic_with_concrete_url: {stats.get('non_synthetic_with_concrete_url', 0)}")
    print(f"synthetic: {stats['synthetic']}")
    if check_dod:
        dod = real_dod_status(stats)
        print(
            f"DoD real fault_ratio>={REAL_DOD_FAULT_RATIO}: "
            f"{'PASS' if dod['fault_ratio'] else 'FAIL'}"
        )
        print(f"DoD real yen>={REAL_DOD_YEN}: {'PASS' if dod['yen'] else 'FAIL'}")
        print(
            f"DoD all real rows have concrete URL: {'PASS' if dod['concrete_url'] else 'FAIL'}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument(
        "--lane",
        choices=["real", "synthetic", "both"],
        default="both",
        help="Which lane to report (default both)",
    )
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="Report tracked config catalogs instead of _inputs JSON",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    out: dict = {}
    if args.lane in ("real", "both"):
        if args.catalog:
            stats = catalog_stats(load_catalog())
            stats["path"] = "config/civil_precedent_catalog.json"
        else:
            path = os.path.join(args.data_dir, CIVIL_JSON)
            if not os.path.exists(path):
                print(f"[ERROR] Missing {path}. Run fetch --field 4 --force")
                return 1
            stats = coverage_from_json(path)
        out["real"] = stats
        if not args.json:
            _print_lane("REAL precedents (eval)", stats, check_dod=True)

    if args.lane in ("synthetic", "both"):
        if args.catalog:
            stats = catalog_stats(load_synthetic_catalog())
            stats["path"] = "config/civil_synthetic_benchmarks.json"
        else:
            path = os.path.join(args.data_dir, SYNTHETIC_JSON)
            if not os.path.exists(path):
                print(f"[WARN] Missing synthetic file {path}")
                stats = {
                    "path": path,
                    "total": 0,
                    "non_synthetic": 0,
                    "non_synthetic_with_fault_ratio": 0,
                    "non_synthetic_with_yen": 0,
                    "non_synthetic_with_concrete_url": 0,
                    "synthetic": 0,
                }
            else:
                stats = coverage_from_json(path)
        out["synthetic"] = stats
        if not args.json:
            _print_lane("SYNTHETIC regression (tests)", stats, check_dod=False)

    if args.json:
        print(json.dumps(out if args.lane == "both" else out.get(args.lane, out), ensure_ascii=False, indent=2))

    if args.lane in ("real", "both") and "real" in out:
        dod = real_dod_status(out["real"])
        if not all(dod.values()):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
