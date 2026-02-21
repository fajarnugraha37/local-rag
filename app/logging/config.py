from __future__ import annotations

import logging
from typing import Optional

_CONFIGURED = False


def configure_logging(level: str | int = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    normalized_level: int
    if isinstance(level, str):
        normalized_level = getattr(logging, level.upper(), logging.INFO)
    else:
        normalized_level = int(level)

    logging.basicConfig(
        level=normalized_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name or "easy-local-rag")
