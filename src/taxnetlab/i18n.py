"""Language infrastructure.

Interface strings live in ``web/locales/<tag>.json`` (BCP 47 tags, for example ``en-GB``). Each file
has a ``_meta`` block (``name``, ``native_name``, ``dir`` for text direction, ``fallback``) and a flat
``strings`` map. Missing keys fall back along the ``fallback`` chain, ending at ``en-GB``. Validation
issues carry codes and parameters so that they can be translated in the interface; see the
``issue.<code>`` keys. To add a language, copy ``en-GB.json``, translate the values and set ``_meta``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from taxnetlab.buildinfo import resource_path

DEFAULT_LOCALE = "en-GB"
_TAG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def locales_dir() -> Path:
    return resource_path("web", "locales")


def available_locales() -> list[dict[str, Any]]:
    out = []
    for path in sorted(locales_dir().glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data.get("_meta", {})
        out.append({"tag": path.stem, "name": meta.get("name", path.stem),
                    "native_name": meta.get("native_name", meta.get("name", path.stem)),
                    "dir": meta.get("dir", "ltr"), "complete": meta.get("complete", False)})
    return out


def load_locale(tag: str) -> dict[str, Any]:
    if not _TAG_RE.match(tag or ""):
        raise KeyError(f"invalid locale tag '{tag}'")
    path = locales_dir() / f"{tag}.json"
    if not path.exists():
        raise KeyError(f"unknown locale '{tag}'")
    return json.loads(path.read_text(encoding="utf-8"))


def resolved_strings(tag: str) -> dict[str, str]:
    """Strings for ``tag`` with the fallback chain applied (cycle-safe)."""
    chain, seen = [], set()
    current: str | None = tag
    while current and current not in seen:
        seen.add(current)
        data = load_locale(current)
        chain.append(data.get("strings", {}))
        current = data.get("_meta", {}).get("fallback") or (DEFAULT_LOCALE if current != DEFAULT_LOCALE else None)
    merged: dict[str, str] = {}
    for strings in reversed(chain):
        merged.update(strings)
    return merged
