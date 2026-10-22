"""Logging to the workspace (plan s 11, Phase 9: error handling and logging).

The interface server logs start-up, failed requests, failed background runs and unhandled exceptions to
``<workspace>/logs/taxnetlab.log`` (rotated at 1 MB, three files kept). Nothing is logged about the content
of datasets, and nothing leaves the computer.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import threading
from pathlib import Path

LOGGER = logging.getLogger("taxnetlab")


def setup(logs_dir: Path) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "taxnetlab.log"
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in LOGGER.handlers):
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s"))
        LOGGER.addHandler(handler)
        LOGGER.setLevel(logging.INFO)

        def hook(exc_type, exc, tb):
            LOGGER.critical("unhandled exception", exc_info=(exc_type, exc, tb))
            sys.__excepthook__(exc_type, exc, tb)

        def thread_hook(args):
            LOGGER.critical("unhandled exception in thread %s", args.thread.name if args.thread else "?",
                            exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

        sys.excepthook = hook
        threading.excepthook = thread_hook
    return path
