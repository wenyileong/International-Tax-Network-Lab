"""Build and environment information recorded in every run record (plan v2.1, s 4.4 and s 7.1)."""

from __future__ import annotations

import functools
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from taxnetlab import STORAGE_SCHEMA_VERSION, __version__

_PACKAGE_DIR = Path(__file__).resolve().parent
_MANIFEST = _PACKAGE_DIR / "_build_manifest.json"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_path(*parts: str) -> Path:
    """Path to a bundled resource, both from source and inside the PyInstaller executable."""
    base = Path(getattr(sys, "_MEIPASS", _PACKAGE_DIR.parent)) / "taxnetlab" if is_frozen() else _PACKAGE_DIR
    return base.joinpath(*parts)


@functools.lru_cache(maxsize=1)
def build_manifest() -> dict[str, Any]:
    """Manifest written by ``scripts/write_build_manifest.py`` at packaging time, if present."""
    path = resource_path("_build_manifest.json")
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"error": "build manifest unreadable"}
    return {}


@functools.lru_cache(maxsize=1)
def executable_sha256() -> str | None:
    if not is_frozen():
        return None
    h = hashlib.sha256()
    with open(sys.executable, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@functools.lru_cache(maxsize=1)
def git_state() -> dict[str, Any]:
    """Commit and dirty flag when running from a Git checkout; taken from the manifest when frozen."""
    manifest = build_manifest()
    if manifest.get("git_commit"):
        return {"commit": manifest["git_commit"], "dirty": manifest.get("git_dirty"), "from": "build manifest"}
    root = _PACKAGE_DIR.parent.parent
    if not (root / ".git").exists():
        return {"commit": None, "dirty": None, "from": "unavailable"}
    try:
        commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                                timeout=5, check=True).stdout.strip()
        status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True,
                                timeout=5, check=True).stdout
        return {"commit": commit, "dirty": bool(status.strip()), "from": "git"}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None, "from": "unavailable"}


def environment() -> dict[str, Any]:
    manifest = build_manifest()
    return {
        "taxnetlab_version": __version__,
        "storage_schema_version": STORAGE_SCHEMA_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "frozen": is_frozen(),
        "executable_sha256": executable_sha256(),
        "lock_sha256": manifest.get("lock_sha256"),
        "built_utc": manifest.get("built_utc"),
        "git": git_state(),
    }
