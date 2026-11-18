"""Methods appendix (plan F8): a run described in prose, with citations, as Markdown, HTML and Word."""

from __future__ import annotations

from typing import Any


def appendix(record: dict[str, Any], outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    raise NotImplementedError("F8: scaffold")


def to_markdown(doc: dict[str, Any]) -> str:
    raise NotImplementedError("F8: scaffold")


def to_html(doc: dict[str, Any]) -> str:
    raise NotImplementedError("F8: scaffold")


def to_docx(doc: dict[str, Any]) -> bytes:
    raise NotImplementedError("F8: scaffold")
