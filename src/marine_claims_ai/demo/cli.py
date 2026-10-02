"""CLI entry for MarineClaims AI — browser demo is the WASM PWA under web/.

Engine / appraisal pipeline logic lives in ``web/src/`` (TypeScript).
"""

from __future__ import annotations

import argparse
import sys

_PWA_HELP = """\
MarineClaims AI executive demo & appraisal engines now run in the client-side WASM PWA.

  cd web
  npm install
  npm run build
  npm run preview

Source of truth:
  web/src/engines/      Rule D5 / COLREGS / fault / BFS
  web/src/appraisal/    evaluateClaimsDynamically + NPL
  web/src/pipeline/     Exact Span A4
  web/src/ingest/       Civil A7 extractor
  web/src/benchmarks/   Gate A Priority 1 & 2
  web/tests/            Vitest

Run: cd web && npm run gate-a
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="marine-claims-demo",
        description="Deprecated shim — use the web/ WASM PWA (Issue #76).",
    )
    parser.add_argument(
        "cmd",
        nargs="?",
        default="help",
        help="Ignored; all subcommands print PWA instructions",
    )
    parser.parse_args(argv)
    print(_PWA_HELP, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
