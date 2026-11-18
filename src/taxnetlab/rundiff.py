"""Compare two runs (plan F9)."""

from __future__ import annotations

from typing import Any


def diff(a: dict[str, Any], b: dict[str, Any], outputs_a: dict[str, dict[str, Any]],
         outputs_b: dict[str, dict[str, Any]], output_keys: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    raise NotImplementedError("F9: scaffold")
