"""Shared HTTP download helpers for public ingest."""

from __future__ import annotations

import os
import ssl
import time
import urllib.request

try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

USER_AGENT = "Mozilla/5.0 (compatible; marine-claims-ai/0.1; +https://github.com/edgesentry/marine-claims-ai)"


def polite_sleep(seconds: float) -> None:
    if seconds and seconds > 0:
        time.sleep(seconds)


def open_url(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT)


def download_url(url: str, dest_path: str, force: bool = False, timeout: int = 30) -> bool:
    """Download remote URL to dest_path unless it already exists (unless force)."""
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0 and not force:
        print(f"  [SKIP] Already exists: {os.path.basename(dest_path)} ({os.path.getsize(dest_path):,} bytes)")
        return True

    print(f"  [FETCH] Downloading: {url} -> {os.path.basename(dest_path)}")
    try:
        with open_url(url, timeout=timeout) as resp:
            data = resp.read()
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        print(f"  [OK] Saved: {dest_path} ({len(data):,} bytes)")
        return True
    except Exception as e:
        print(f"  [WARN] Failed to download {url}: {e}")
        return False
