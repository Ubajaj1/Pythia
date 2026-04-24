"""Logging setup — console (INFO+) and rotating file (DEBUG+, full LLM prompts/responses)."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_FMT = "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(name)-16s | %(message)s"
_DATE = "%H:%M:%S"


def setup_logging(level: str = "INFO", log_dir: str = "data/logs") -> None:
    """Configure root logger. Safe to call multiple times — skips if already configured."""
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, level.upper(), logging.INFO))
    ch.setFormatter(logging.Formatter(_FMT, datefmt=_DATE))
    root.addHandler(ch)

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        Path(log_dir) / "pythia.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, datefmt=_DATE))
    root.addHandler(fh)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
