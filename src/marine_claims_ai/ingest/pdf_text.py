"""Best-effort PDF text extraction for public judgment / report PDFs."""

from __future__ import annotations

import subprocess


def pdf_to_text(pdf_path: str) -> str:
    """Extract text via pdftotext; empty string if unavailable."""
    try:
        res = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=60,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""
