"""Project workspace: a folder holding datasets and run records (plan v2.1, s 1.3).

The workspace is always outside the application's own folder. Location, in order of precedence:
an explicit path, the ``TAXNETLAB_WORKSPACE`` environment variable, then
``Documents\\TaxNetLab`` on Windows or ``~/TaxNetLab`` elsewhere.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from taxnetlab import STORAGE_SCHEMA_VERSION, __version__
from taxnetlab.datasets import Dataset


def default_workspace_path() -> Path:
    env = os.environ.get("TAXNETLAB_WORKSPACE")
    if env:
        return Path(env).expanduser()
    home = Path.home()
    if sys.platform.startswith("win"):
        docs = home / "Documents"
        return (docs if docs.exists() else home) / "TaxNetLab"
    return home / "TaxNetLab"


class Workspace:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root).expanduser().resolve() if root else default_workspace_path().resolve()
        self.datasets_dir = self.root / "datasets"
        self.runs_dir = self.root / "runs"
        self.exports_dir = self.root / "exports"
        self.expectations_dir = self.root / "expectations"
        self.replications_dir = self.root / "replications"
        self.logs_dir = self.root / "logs"
        self.suite_dir = self.root / "suite_projects"

    def ensure(self) -> "Workspace":
        for d in (self.root, self.datasets_dir, self.runs_dir, self.exports_dir):
            d.mkdir(parents=True, exist_ok=True)
        self._remove_stale_temporaries()
        marker = self.root / "workspace.json"
        if not marker.exists():
            marker.write_text(json.dumps({"storage_schema_version": STORAGE_SCHEMA_VERSION,
                                          "created_by": f"taxnetlab {__version__}"}, indent=2), encoding="utf-8")
        else:
            info = json.loads(marker.read_text(encoding="utf-8"))
            if str(info.get("storage_schema_version")) != STORAGE_SCHEMA_VERSION:
                raise RuntimeError(
                    f"workspace {self.root} uses storage schema {info.get('storage_schema_version')}; "
                    f"this build uses {STORAGE_SCHEMA_VERSION}")
        return self

    def _remove_stale_temporaries(self, max_age_s: float = 3600.0) -> None:
        """Remove temporary folders left by an interrupted write (for example a closed console window).
        Completed datasets and run records are never touched."""
        now = time.time()
        for parent in (self.datasets_dir, self.runs_dir):
            for tmp in parent.glob(".tmp-*"):
                try:
                    if tmp.is_dir() and now - tmp.stat().st_mtime > max_age_s:
                        shutil.rmtree(tmp)
                except OSError:
                    pass

    # datasets ---------------------------------------------------------------
    def save_dataset(self, dataset: Dataset) -> str:
        dataset.save(self.datasets_dir)
        return dataset.dataset_id

    def dataset_ids(self) -> list[str]:
        if not self.datasets_dir.exists():
            return []
        return sorted(p.name for p in self.datasets_dir.iterdir()
                      if p.is_dir() and not p.name.startswith(".") and (p / "dataset.json").exists())

    def dataset_meta(self, dataset_id: str) -> dict[str, Any]:
        return json.loads((self._dataset_dir(dataset_id) / "dataset.json").read_text(encoding="utf-8"))

    def load_dataset(self, dataset_id: str) -> Dataset:
        return Dataset.load(self._dataset_dir(dataset_id))

    def _dataset_dir(self, dataset_id: str) -> Path:
        if not dataset_id or "/" in dataset_id or "\\" in dataset_id or dataset_id.startswith("."):
            raise KeyError(f"invalid dataset id '{dataset_id}'")
        path = self.datasets_dir / dataset_id
        if not (path / "dataset.json").exists():
            raise KeyError(f"unknown dataset '{dataset_id}'")
        return path
