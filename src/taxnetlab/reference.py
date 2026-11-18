"""Reference data (plan docs/PLAN_1_0_RC3_SCAFFOLD.md, F1): GDP read from the World Bank's own CSV download.

A reference set is content-addressed and never edited: ``workspace/reference/<id>/`` holds the original file,
``values.json`` (jurisdiction -> period -> value) and ``meta.json``. The Lab never downloads anything; the
researcher downloads the file and records the date it was retrieved.
"""

from __future__ import annotations

from typing import Any

WDI_GDP = "NY.GDP.MKTP.CD"


class ReferenceError(ValueError):
    pass


def parse_wdi_csv(data: bytes, known_codes: set[str]) -> dict[str, Any]:
    """Values by jurisdiction and year from a World Bank indicator CSV; aggregates dropped."""
    raise NotImplementedError("F1: scaffold")


class ReferenceStore:
    def __init__(self, folder):
        self.folder = folder

    def add(self, data: bytes, retrieved: str, filename: str = "") -> dict[str, Any]:
        raise NotImplementedError("F1: scaffold")

    def list(self) -> list[dict[str, Any]]:
        raise NotImplementedError("F1: scaffold")

    def values(self, reference_id: str) -> dict[str, dict[str, float]]:
        raise NotImplementedError("F1: scaffold")
