"""Service layer (plan v2.1, s 4.1). The CLI, the local server and notebooks all use this API;
no front end calls engines directly. Every function returns plain JSON-serialisable data."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from taxnetlab import __version__, runs, synthetic
from taxnetlab.buildinfo import build_manifest, environment
from taxnetlab.canonical import canonical_json
from taxnetlab.datasets import Dataset
from taxnetlab.engines import get_engine, list_engines
from taxnetlab.schema import SCHEMAS, TABLE_ORDER
from taxnetlab.validation import ValidationError
from taxnetlab.views import AGGREGATION_RULES, VIEWS, build_view, jurisdiction_matrix, view_to_json
from taxnetlab.workspace import Workspace

PREVIEW_ROWS = 1000
PREVIEW_CACHE_SIZE = 128
DATASET_CACHE_SIZE = 8


class _LRU:
    """Small thread-safe LRU cache (the server handles requests on several threads)."""

    def __init__(self, size: int):
        self.size, self.data, self.lock = size, OrderedDict(), threading.Lock()

    def get(self, key):
        with self.lock:
            if key in self.data:
                self.data.move_to_end(key)
                return self.data[key]
            return None

    def put(self, key, value) -> None:
        with self.lock:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)


class Api:
    def __init__(self, workspace: Workspace):
        self.ws = workspace.ensure()
        self._datasets = _LRU(DATASET_CACHE_SIZE)  # datasets are content-addressed, so caching is safe
        self._previews = _LRU(PREVIEW_CACHE_SIZE)
        from taxnetlab.jobs import JobManager

        self.jobs = JobManager(self.run)

    def _dataset(self, dataset_id: str):
        ds = self._datasets.get(dataset_id)
        if ds is None:
            ds = self.ws.load_dataset(dataset_id)
            self._datasets.put(dataset_id, ds)
        return ds

    # ------------------------------------------------------------------ about
    def about(self) -> dict[str, Any]:
        return {"name": "International Tax Network Lab", "version": __version__, "workspace": str(self.ws.root),
                "environment": environment(), "build_manifest": build_manifest(),
                "licence": "All rights reserved pending the licence decision (plan s 4.6).",
                "offline": True}

    # ------------------------------------------------------------------ engines
    def engines(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in list_engines()]

    # ------------------------------------------------------------------ datasets
    def ensure_default_dataset(self) -> str | None:
        """On first launch, give the user something to look at: one synthetic world."""
        if self.ws.dataset_ids():
            return None
        return self.ws.save_dataset(synthetic.generate())

    def datasets(self) -> list[dict[str, Any]]:
        out = []
        for did in self.ws.dataset_ids():
            meta = self.ws.dataset_meta(did)
            out.append({k: meta.get(k) for k in ("dataset_id", "name", "data_status", "counts", "metadata")})
        return sorted(out, key=lambda d: d["name"].lower())

    def dataset(self, dataset_id: str) -> dict[str, Any]:
        ds = self._dataset(dataset_id)
        info = ds.describe()
        info["validation"] = ds.validate().to_dict()
        info["schemas"] = {name: {"columns": SCHEMAS[name].column_names, "primary_key": list(SCHEMAS[name].primary_key),
                                  "description": SCHEMAS[name].description} for name in TABLE_ORDER}
        return info

    def table(self, dataset_id: str, table: str, limit: int = PREVIEW_ROWS) -> dict[str, Any]:
        if table not in SCHEMAS:
            raise KeyError(f"unknown table '{table}'")
        ds = self._dataset(dataset_id)
        rows = ds.tables[table]
        return {"table": table, "columns": SCHEMAS[table].column_names, "rows": rows[:limit],
                "total_rows": len(rows), "truncated": len(rows) > limit}

    def table_csv(self, dataset_id: str, table: str) -> str:
        if table not in SCHEMAS:
            raise KeyError(f"unknown table '{table}'")
        return self._dataset(dataset_id).csv_text(table)

    def generate_synthetic(self, params: dict[str, Any]) -> dict[str, Any]:
        allowed = set(synthetic.DEFAULT_PARAMS) | {"name"}
        unknown = set(params) - allowed
        if unknown:
            raise ValueError(f"unknown generator parameter(s): {sorted(unknown)}")
        merged = {**synthetic.DEFAULT_PARAMS, **{k: v for k, v in params.items() if v not in (None, "")}}
        ds = synthetic.generate(**merged)
        did = self.ws.save_dataset(ds)
        return {"dataset_id": did, "name": self.ws.dataset_meta(did)["name"], "validation": ds.validate().to_dict()}

    def import_csv(self, name: str, texts: dict[str, str], mapping: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
        meta = {"origin": "csv_import"} | ({"column_mapping": mapping} if mapping else {})
        ds, report = Dataset.from_csv_texts(name, texts, meta, mapping=mapping)
        if ds is None:
            return {"saved": False, "validation": report.to_dict()}
        did = self.ws.save_dataset(ds)
        return {"saved": True, "dataset_id": did, "name": self.ws.dataset_meta(did)["name"],
                "validation": report.to_dict()}

    def import_zip(self, name: str, data: bytes, mapping: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
        """Import a coding template or any ZIP of table CSV files (plan s 5.4)."""
        from taxnetlab.coding import read_template_zip

        return self.import_csv(name, read_template_zip(data), mapping)

    @staticmethod
    def template(kind: str, candidates: list[str] | None = None) -> bytes:
        from taxnetlab.coding import template_zip

        return template_zip(kind, candidates)

    # ------------------------------------------------------------------ views
    def view(self, dataset_id: str, view: str, rule: str = "count", as_of: str | None = None,
             include_domestic: bool = False) -> dict[str, Any]:
        if view not in VIEWS:
            raise ValueError(f"view must be one of {list(VIEWS)}")
        if rule not in AGGREGATION_RULES:
            raise ValueError(f"rule must be one of {list(AGGREGATION_RULES)}")
        ds = self._dataset(dataset_id)
        return view_to_json(ds, build_view(ds, view, rule, as_of or None, include_domestic))

    def matrix(self, dataset_id: str, rule: str = "count", as_of: str | None = None,
               include_domestic: bool = True) -> dict[str, Any]:
        if rule not in AGGREGATION_RULES:
            raise ValueError(f"rule must be one of {list(AGGREGATION_RULES)}")
        return jurisdiction_matrix(self._dataset(dataset_id), rule, as_of or None, include_domestic)

    # ------------------------------------------------------------------ live previews (plan v2.2, s 8.1)
    def preview(self, engine_id: str, dataset_id: str, parameters: dict[str, Any] | None) -> dict[str, Any]:
        """Execute an engine without storing anything. Previews are exploratory, not results: they carry
        the engine status and become citable only when pinned as a run (same parameters via :meth:`run`)."""
        engine = get_engine(engine_id)
        spec = engine.spec
        base = {"engine_id": spec.engine_id, "status": spec.status, "track": spec.track, "version": spec.version,
                "exploratory": True}
        if not spec.runnable:
            return {**base, "executed": False, "validation": {"ok": False, "summary": {"errors": 1}, "issues": [
                {"level": "error", "code": "engine_not_runnable", "message": spec.next_step, "params": {
                    "engine": spec.engine_id, "status": spec.status}, "table": None, "row": None, "column": None}]}}
        params, report = engine.resolve_parameters(parameters or {})
        if not report.ok:
            return {**base, "executed": False, "validation": report.to_dict()}
        key = (spec.engine_id, spec.version, dataset_id, canonical_json(params))
        cached = self._previews.get(key)
        if cached is not None:
            return {**cached, "cached": True}
        dataset = self._dataset(dataset_id)
        report.extend(engine.validate(dataset, params))
        if not report.ok:
            return {**base, "executed": False, "validation": report.to_dict()}
        started = time.perf_counter()
        result = engine.run(dataset, params)
        out = {**base, "executed": True, "parameters": params, "outcome": result.outcome,
               "warnings": result.warnings, "assumptions": result.assumptions, "trace": result.trace,
               "outputs": result.outputs, "validation": report.to_dict(), "data_status": dataset.data_status,
               "elapsed_ms": round((time.perf_counter() - started) * 1000, 1), "cached": False}
        self._previews.put(key, out)
        return out

    # ------------------------------------------------------------------ runs
    def run(self, spec: dict[str, Any]) -> dict[str, Any]:
        try:
            record = runs.execute(self.ws, runs.RunSpec.from_dict(spec))
        except ValidationError as exc:
            return {"executed": False, "validation": exc.report.to_dict()}
        return {"executed": True, "record": record, "outputs": self._outputs(record["run_id"])}

    def runs(self) -> list[dict[str, Any]]:
        return runs.list_runs(self.ws)

    def run_record(self, run_id: str) -> dict[str, Any]:
        record = runs.load_record(self.ws, run_id)
        return {"record": record, "summary": runs.summarise(record), "outputs": self._outputs(run_id)}

    def run_output_csv(self, run_id: str, name: str) -> str:
        return runs.output_text(self.ws, run_id, name)

    def replay(self, run_id: str) -> dict[str, Any]:
        return runs.replay(self.ws, run_id)

    # ------------------------------------------------------------------ expectation register (plan s 7.5)
    def expectations(self) -> list[dict[str, Any]]:
        from taxnetlab.expectations import Register

        return Register(self.ws.expectations_dir).list()

    def expectation(self, entry_id: str) -> dict[str, Any]:
        from taxnetlab.expectations import Register

        return Register(self.ws.expectations_dir).load(entry_id)

    def freeze_expectation(self, draft: dict[str, Any], frozen_by: str) -> dict[str, Any]:
        from taxnetlab.expectations import Register

        return Register(self.ws.expectations_dir).freeze(draft, frozen_by)

    def check_replication(self, entry_id: str, run_id: str) -> dict[str, Any]:
        """Compare a stored run with a frozen entry; the report is stored once and never rewritten."""
        import json

        from taxnetlab.expectations import compare

        path = self.ws.replications_dir / f"{run_id}__{entry_id}.json"
        record = runs.load_record(self.ws, run_id)
        entry = self.expectation(entry_id)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        outputs = {name: info["rows"] for name, info in self._outputs(run_id).items()}
        report = compare(entry, record, outputs)
        if record.get("_integrity") != "ok":
            report["problems"].append("the run record has been modified")
            report["verdict"] = "invalid"
        report["checked_utc"] = runs._utc_now()
        self.ws.replications_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        return report

    def replications(self) -> list[dict[str, Any]]:
        import json

        if not self.ws.replications_dir.exists():
            return []
        out = []
        for p in sorted(self.ws.replications_dir.glob("*.json")):
            r = json.loads(p.read_text(encoding="utf-8"))
            out.append({k: r.get(k) for k in ("run_id", "entry_id", "verdict", "passed", "total", "checked_utc", "data_status")})
        return out

    def _outputs(self, run_id: str) -> dict[str, Any]:
        import csv
        import io

        record = runs.load_record(self.ws, run_id)
        engine_outputs = {}
        try:
            declared = get_engine(record["engine"]["engine_id"]).spec.outputs
        except KeyError:
            declared = {}
        for name in record["outputs"]:
            text = runs.output_text(self.ws, run_id, name)
            rows = [{k: _typed(v) for k, v in r.items()} for r in csv.DictReader(io.StringIO(text))]
            engine_outputs[name] = {"columns": list(declared.get(name, rows[0].keys() if rows else [])),
                                    "rows": rows}
        return engine_outputs


def _typed(text: str):
    """Numbers in stored output CSVs back to numbers for display (the stored files are unchanged)."""
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text
