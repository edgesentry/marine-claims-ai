#!/usr/bin/env python3
"""Fail when the Field 1 JMAT cache looks mojibake-corrupted."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from marine_claims_ai.ingest.public_datasets import JMAT_JSON, field1_case_issues
from marine_claims_ai.paths import DEFAULT_DATASET_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sanity-check Field 1 JMAT cache Japanese text")
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_DATASET_DIR / JMAT_JSON,
        help="Path to benchmark_field1_jmat_cases.json",
    )
    args = parser.parse_args(argv)
    if not args.path.is_file():
        print(f"[Field 1] [ERROR] Cache not found: {args.path}", file=sys.stderr)
        return 1
    cases = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        print(f"[Field 1] [ERROR] Expected a JSON list: {args.path}", file=sys.stderr)
        return 1
    failed = 0
    for case in cases:
        issues = field1_case_issues(case)
        if issues:
            failed += 1
            print(
                f"[Field 1] [FAIL] case {case.get('case_id')} {case.get('title', '')}: "
                f"{'; '.join(issues)}"
            )
    if failed:
        print(f"[Field 1] [ERROR] {failed} case(s) failed sanity check")
        return 1
    print(f"[Field 1] [OK] {len(cases)} cases passed sanity check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
