"""Native file and folder dialogs for the local interface (plan F10).

A browser cannot hand a folder's path to a page, so the server, which runs on the researcher's own computer,
opens the operating system's dialog (Tk) and returns the chosen path. One dialog at a time; when Tk cannot be
used (no display, or a build without it) the answer says so and the page keeps its typed path field.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Any

KINDS = ("folder", "sqlite", "zip", "csv")
_LOCK = threading.Lock()
TITLES = {"folder": "Choose a folder", "sqlite": "Choose a Research Suite project",
          "zip": "Choose a ZIP file", "csv": "Choose a CSV file"}
TYPES = {"sqlite": [("Research Suite project", "*.sqlite *.db")], "zip": [("ZIP archive", "*.zip")],
         "csv": [("CSV file", "*.csv")]}


def _tk_available() -> bool:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
    return True


def _dialog(kind: str, out: dict[str, Any]) -> None:
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)  # in front of the browser
        if kind == "folder":
            path = filedialog.askdirectory(parent=root, title=TITLES[kind], mustexist=True)
        else:
            path = filedialog.askopenfilename(parent=root, title=TITLES[kind],
                                              filetypes=TYPES[kind] + [("All files", "*.*")])
        out["path"] = os.path.normpath(path) if path else None
    finally:
        root.destroy()


def pick(kind: str, timeout: float = 600.0) -> dict[str, Any]:
    """{"available": bool, "path": str | None}; path None when the dialog was cancelled."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    if not _tk_available():
        return {"available": False, "path": None}
    if not _LOCK.acquire(blocking=False):
        return {"available": True, "path": None, "busy": True}
    try:
        out: dict[str, Any] = {"path": None}
        t = threading.Thread(target=_dialog, args=(kind, out), daemon=True, name="file-dialog")
        t.start()
        t.join(timeout)
        if t.is_alive():
            return {"available": True, "path": None, "timed_out": True}
        return {"available": True, "path": out.get("path")}
    except Exception:  # a broken Tk installation: say so, never fail the request
        return {"available": False, "path": None}
    finally:
        _LOCK.release()
