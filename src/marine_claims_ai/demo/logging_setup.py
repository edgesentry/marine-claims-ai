"""Local file + stderr logging for the executive demo (diagnosis aid)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from marine_claims_ai.paths import DEFAULT_DATA_DIR

DEMO_LOG_DIR = DEFAULT_DATA_DIR / "logs"
DEMO_LOG_PATH = DEMO_LOG_DIR / "demo.log"

_CONFIGURED = False


def setup_demo_logging(*, level: int = logging.INFO) -> Path:
    """Configure ``marine_claims_ai.demo`` loggers to write ``_data/logs/demo.log``.

    Idempotent. Also mirrors to stderr so ``serve`` terminals show the same lines.
    """
    global _CONFIGURED
    DEMO_LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("marine_claims_ai.demo")
    root.setLevel(level)
    if _CONFIGURED:
        return DEMO_LOG_PATH

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = RotatingFileHandler(
        DEMO_LOG_PATH,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.setLevel(level)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(level)
    root.addHandler(sh)

    root.propagate = False
    _CONFIGURED = True
    root.info("demo logging → %s", DEMO_LOG_PATH)
    return DEMO_LOG_PATH


def get_demo_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"marine_claims_ai.demo.{name}")
    return logging.getLogger("marine_claims_ai.demo")
