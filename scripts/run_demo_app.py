#!/usr/bin/env python3
"""Launch the offline FastAPI + HTMX executive demo (Web UI).

For CLI parity (Rule D5 + COLREGS without a browser), use:

    uv run python scripts/run_demo_cli.py uc2
    uv run python scripts/run_demo_cli.py serve
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MarineClaims AI interactive demo (FastAPI + HTMX)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    # Delegate to shared CLI so serve forever stays in sync.
    from marine_claims_ai.demo.cli import main as cli_main

    return cli_main(
        [
            "serve",
            "--host",
            args.host,
            "--port",
            str(args.port),
            *(["--reload"] if args.reload else []),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
