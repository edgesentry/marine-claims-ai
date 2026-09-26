#!/usr/bin/env python3
"""
Zero-Dataset leak check for the public marine-claims-AI repository.

Fails if tracked files include banned data extensions / non-allowlisted JSON,
or if diffs / tracked text contain private workspace paths or secret-like tokens.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from marine_claims_ai.paths import REPO_ROOT

BANNED_EXTENSIONS = {".pdf", ".csv", ".tsv", ".html", ".htm"}

# Only configuration schemas under config/ may be tracked as JSON.
JSON_ALLOWLIST_PREFIX = "config/"

# Scanner sources embed detection literals; skip during content scan.
SELF_SCAN_SKIP = {
    "src/marine_claims_ai/ci/leak_check.py",
    "scripts/ci/check_zero_dataset_leak.py",
}


def _pat(*parts: str, flags: int = 0) -> re.Pattern[str]:
    """Compile a regex from parts so this file does not self-match path literals."""
    return re.compile("".join(parts), flags)


# Sensitive patterns scanned in added lines (PR) or full tracked text (push / local).
SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "local absolute path (macOS home)",
        _pat(r"/", "Users", r"/[^\s\"'`]+"),
    ),
    (
        "local absolute path (Linux home, excluding Actions runner)",
        _pat(r"/", "home", r"/(?!runner(?:/|\s|$))[^\s\"'`]+"),
    ),
    (
        "local file URI",
        _pat(r"file:///(?:", "Users", r"|", "home", r")/[^\s\)\"'`]+"),
    ),
    (
        "enterprise repository name leak",
        _pat(r"marine-claims-knowledge-", "enterprise", flags=re.IGNORECASE),
    ),
    (
        "API key assignment",
        _pat(r"(?i)\bapi[_-]?key\b\s*[:=]\s*['\"][^'\"]+['\"]"),
    ),
    (
        "AWS secret assignment",
        _pat(r"(?i)\baws[_-]?secret(?:_access_key)?\b\s*[:=]\s*['\"][^'\"]+['\"]"),
    ),
    (
        "private key block",
        _pat(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    ),
]

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".sh",
    ".cfg",
    ".ini",
    ".gitignore",
}


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def list_tracked_files() -> list[str]:
    out = run_git("ls-files", "-z")
    return [p for p in out.split("\0") if p]


def is_json_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith(JSON_ALLOWLIST_PREFIX) and normalized.endswith(".json")


def check_banned_tracked_files(tracked: list[str]) -> list[str]:
    violations: list[str] = []
    for path in tracked:
        suffix = Path(path).suffix.lower()
        if suffix in BANNED_EXTENSIONS:
            violations.append(f"banned extension tracked: {path}")
        elif suffix == ".json" and not is_json_allowed(path):
            violations.append(f"non-allowlisted JSON tracked: {path}")
    return violations


def is_scannable_text(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized in SELF_SCAN_SKIP:
        return False
    name = Path(path).name
    if name in {".gitignore", "Dockerfile", "Makefile"}:
        return True
    suffix = Path(path).suffix.lower()
    return suffix in TEXT_EXTENSIONS or suffix == ""


def scan_line(path: str, line_no: int, line: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in SENSITIVE_PATTERNS:
        if pattern.search(line):
            hits.append(f"{path}:{line_no}: {label}: {line.rstrip()}")
    return hits


def scan_tracked_text(tracked: list[str]) -> list[str]:
    hits: list[str] = []
    for path in tracked:
        if not is_scannable_text(path):
            continue
        full = REPO_ROOT / path
        try:
            text = full.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            hits.extend(scan_line(path, i, line))
    return hits


def resolve_diff_range(explicit_base: str | None) -> str | None:
    """Return git diff range for added-line scan, or None to scan full tree."""
    if explicit_base:
        return f"{explicit_base}...HEAD"

    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event == "pull_request":
        base_ref = os.environ.get("GITHUB_BASE_REF", "main")
        return f"origin/{base_ref}...HEAD"

    # push / local default: full-tree content scan
    return None


def scan_diff_added_lines(diff_range: str) -> list[str]:
    # Unified diff with no context so only added/removed hunks appear.
    out = run_git("diff", "--unified=0", diff_range)
    hits: list[str] = []
    current_file = "(unknown)"
    new_line_no = 0

    for raw in out.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
            continue
        if raw.startswith("@@"):
            # @@ -a,b +c,d @@
            m = re.search(r"\+(\d+)(?:,\d+)?", raw)
            new_line_no = int(m.group(1)) if m else 0
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            if current_file.replace("\\", "/") not in SELF_SCAN_SKIP:
                hits.extend(scan_line(current_file, new_line_no, raw[1:]))
            new_line_no += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        elif raw.startswith("\\"):
            continue
        else:
            # context line (should be rare with -U0)
            new_line_no += 1

    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=None,
        help="Git ref/range base for PR-style added-line scan (e.g. origin/main)",
    )
    parser.add_argument(
        "--full-tree",
        action="store_true",
        help="Always scan full tracked text instead of PR diffs",
    )
    args = parser.parse_args()

    try:
        tracked = list_tracked_files()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    violations = check_banned_tracked_files(tracked)

    if args.full_tree:
        content_hits = scan_tracked_text(tracked)
    else:
        diff_range = resolve_diff_range(args.base)
        if diff_range is None:
            content_hits = scan_tracked_text(tracked)
        else:
            try:
                content_hits = scan_diff_added_lines(diff_range)
            except RuntimeError as exc:
                print(
                    f"WARN: diff scan failed ({exc}); falling back to full-tree scan",
                    file=sys.stderr,
                )
                content_hits = scan_tracked_text(tracked)

    violations.extend(content_hits)

    if violations:
        print("Zero-Dataset / leak check FAILED:\n", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print(
            "\nSee AGENTS.md Zero-Dataset Git Policy. "
            "Only scripts/, config/*.json, and docs/ belong in git.",
            file=sys.stderr,
        )
        return 1

    mode = "full-tree" if args.full_tree or resolve_diff_range(args.base) is None else "diff"
    print(f"Zero-Dataset / leak check passed ({len(tracked)} tracked files, {mode} content scan).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
