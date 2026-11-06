"""Structured logging setup.

Uses `rich` for a clean handler when logging to a console, but keeps messages
structured (key=value) so nothing leaks stack traces to the web UI - the web
layer catches exceptions and returns sanitized errors instead.
"""

from __future__ import annotations

import logging
import os

from rich.logging import RichHandler

_CONFIGURED = False


def setup_logging(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = (level or os.environ.get("NUMINT_LOG_LEVEL", "WARNING")).upper()
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=False, show_path=False)],
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"numint.{name}")
