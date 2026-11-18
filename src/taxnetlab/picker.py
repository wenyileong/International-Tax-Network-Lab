"""Native file and folder dialogs for the local interface (plan F10)."""

from __future__ import annotations

from typing import Any

KINDS = ("folder", "sqlite", "zip")


def pick(kind: str, timeout: float = 600.0) -> dict[str, Any]:
    raise NotImplementedError("F10: scaffold")
