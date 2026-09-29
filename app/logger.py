"""
logger.py
=========
Call configure_logging() once at startup.
All other modules obtain their logger with logging.getLogger(__name__).
"""

import logging
import sys


def configure_logging(level: str = "INFO", fmt: str | None = None) -> None:
    if fmt is None:
        fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"

    numeric = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric)

    # Quiet noisy third-party loggers
    logging.getLogger("paho").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
