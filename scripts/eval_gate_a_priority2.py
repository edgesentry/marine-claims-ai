#!/usr/bin/env python3
"""Gate A Priority 2 — TypeScript/Vitest is canonical. This is a redirect shim."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gate A Priority 2 redirect — use: cd web && npm run gate-a",
    )
    parser.parse_args(argv)
    print(
        "Gate A Priority 2 Python harness was removed.\n"
        "  cd web && npm run gate-a\n"
        "Source: web/src/benchmarks/gateAPriority2.ts",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
