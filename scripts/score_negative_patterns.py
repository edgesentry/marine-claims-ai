#!/usr/bin/env python3
"""CLI: score repair line items against the Negative Pattern Library."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from marine_claims_ai.appraisal.negative_patterns import (
    NegativePatternScorer,
    score_line_items,
)
from marine_claims_ai.paths import DEFAULT_NEGATIVE_PATTERN_PATH


def _load_items(path: Path | None, texts: list[str]) -> list[dict]:
    if path is not None:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and isinstance(data.get("items"), list):
            items = data["items"]
        else:
            raise SystemExit("Input JSON must be a list of items or {\"items\": [...]}")
        for i, item in enumerate(items):
            if "description" not in item:
                raise SystemExit(f"Item {i} missing 'description'")
        return items
    return [{"id": i + 1, "description": t} for i, t in enumerate(texts)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--library",
        default=str(DEFAULT_NEGATIVE_PATTERN_PATH),
        help="Path to config/negative_pattern_library.json",
    )
    parser.add_argument(
        "--items-json",
        default=None,
        help="JSON file: list of {description, ...} or {items: [...]}",
    )
    parser.add_argument(
        "--text",
        action="append",
        default=[],
        help="Line-item description (repeatable). Used when --items-json is omitted.",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write scored JSON",
    )
    args = parser.parse_args()

    if not args.items_json and not args.text:
        parser.error("Provide --items-json or one or more --text descriptions")

    items = _load_items(Path(args.items_json) if args.items_json else None, args.text)
    scorer = NegativePatternScorer(library_path=args.library)
    scored = score_line_items(items, scorer=scorer)
    payload = {
        "library": str(args.library),
        "thresholds": {
            "disallow_min": scorer.disallow_min,
            "apportion_min": scorer.apportion_min,
        },
        "items": scored,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {out}", file=sys.stderr)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
