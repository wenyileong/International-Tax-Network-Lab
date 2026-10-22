"""Progress reporting and cooperative cancellation for long runs (plan s 11: background runs).

Engines call :func:`report` at natural checkpoints. Outside a job it does nothing. Inside a job it records
the fraction done and raises :class:`Cancelled` if the user asked to stop; the run then leaves no record
(run records are written atomically after the engine returns).
"""

from __future__ import annotations

import contextvars
import threading
import time
from dataclasses import dataclass, field


class Cancelled(Exception):
    """The user cancelled the run."""


@dataclass
class Tracker:
    fraction: float = 0.0
    message: str = ""
    updated: float = field(default_factory=time.monotonic)
    cancel_event: threading.Event = field(default_factory=threading.Event)

    def cancel(self) -> None:
        self.cancel_event.set()


_current: contextvars.ContextVar[Tracker | None] = contextvars.ContextVar("taxnetlab_progress", default=None)


def report(done: float, total: float, message: str = "") -> None:
    tracker = _current.get()
    if tracker is None:
        return
    if tracker.cancel_event.is_set():
        raise Cancelled("cancelled by the user")
    tracker.fraction = 0.0 if total <= 0 else max(0.0, min(1.0, done / total))
    if message:
        tracker.message = message
    tracker.updated = time.monotonic()


class tracking:
    """Context manager: ``with tracking(tracker): engine.run(...)``."""

    def __init__(self, tracker: Tracker):
        self.tracker = tracker
        self._token = None

    def __enter__(self) -> Tracker:
        self._token = _current.set(self.tracker)
        return self.tracker

    def __exit__(self, *exc) -> None:
        _current.reset(self._token)
