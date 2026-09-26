#!/usr/bin/env python3
"""CLI: Zero-Dataset leak check (CI entrypoint)."""

from marine_claims_ai.ci.leak_check import main

if __name__ == "__main__":
    raise SystemExit(main())
