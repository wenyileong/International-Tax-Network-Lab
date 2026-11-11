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

    def import_csv(self, name: str, texts: dict[str, str], mapping: dict[str, dict[str, str]] | None = None,
                   metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        meta = dict(metadata or {"origin": "csv_import"}) | ({"column_mapping": mapping} if mapping else {})
        ds, report = Dataset.from_csv_texts(name, texts, meta, mapping=mapping)
        if ds is None:
            return {"saved": False, "validation": report.to_dict()}
        existed = ds.dataset_id in self.ws.dataset_ids()
        did = self.ws.save_dataset(ds)
        return {"saved": True, "dataset_id": did, "name": self.ws.dataset_meta(did)["name"],
                "validation": report.to_dict(), "already_present": existed}

    def import_zip(self, name: str, data: bytes, mapping: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
        """Import a coding template or any ZIP of table CSV files (plan s 5.4)."""
        from taxnetlab.coding import read_template_zip

        return self.import_csv(name, read_template_zip(data), mapping)

    def derive_dataset(self, base_id: str, name: str, texts: dict[str, str], mode: str = "merge") -> dict[str, Any]:
        """Complete a dataset: a new dataset with some tables added or replaced (the original is unchanged).

        ``merge``: rows supplied replace stored rows with the same primary key and the rest are added;
        ``replace``: each supplied table replaces the stored table entirely. Tables supplied with no rows are
        ignored in ``merge`` mode. The new dataset records what it was derived from.
        """
        import csv
        import io

        if mode not in ("merge", "replace"):
            raise ValueError("mode must be 'merge' or 'replace'")
        base = self._dataset(base_id)
        unknown = sorted(set(texts) - set(SCHEMAS))
        if unknown:
            raise ValueError(f"unknown table(s): {unknown}")
        out = {t: base.csv_text(t) for t in TABLE_ORDER}
        changed = {}
        for table, text in texts.items():
            new_rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
            if mode == "replace":
                out[table] = text
                changed[table] = len(new_rows)
                continue
            if not new_rows:
                continue
            pk = SCHEMAS[table].primary_key
            old_rows = list(csv.DictReader(io.StringIO(out[table])))
            merged = {tuple(r.get(k) or "" for k in pk): r for r in old_rows}
            for r in new_rows:
                merged[tuple((r.get(k) or "").strip() for k in pk)] = r
            cols = SCHEMAS[table].column_names
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
            w.writeheader()
            w.writerows({c: (r.get(c) or "") for c in cols} for r in merged.values())
            out[table] = buf.getvalue()
            changed[table] = len(new_rows)
        if not changed:
            raise ValueError("no rows supplied: nothing to add")
        parent = self.ws.dataset_meta(base_id)
        meta = {"origin": "derived", "derived_from": base_id, "derived_from_name": parent["name"], "mode": mode,
                "tables_changed": changed, "parent_metadata": parent.get("metadata") or {}}
        ds, report = Dataset.from_csv_texts(name or f"{parent['name']} (completed)", out, meta)
        if ds is None:
            return {"saved": False, "validation": report.to_dict()}
        existed = ds.dataset_id in self.ws.dataset_ids()
        did = self.ws.save_dataset(ds)
        return {"saved": True, "dataset_id": did, "name": self.ws.dataset_meta(did)["name"],
                "validation": report.to_dict(), "already_present": existed, "tables_changed": changed}

    def completion_template(self, dataset_id: str) -> bytes:
        """A real-sample coding template (GDP and tax rules) listing the dataset's real jurisdictions."""
        ds = self._dataset(dataset_id)
        codes = [r["jurisdiction_id"] for r in ds.tables["jurisdictions"]
                 if not r.get("fictional") and len(str(r["jurisdiction_id"])) == 3]
        if not codes:
            raise ValueError("the dataset has no real (ISO 3166-1 alpha-3) jurisdictions to complete")
        return self.template("real_sample", codes)

    # ------------------------------------------------------------------ Research Suite (A-share releases)
    @property
    def suite(self):
        if getattr(self, "_suite", None) is None:
            from taxnetlab.suite import SuiteBridge

            self._suite = SuiteBridge(self.ws)
        return self._suite

    def suite_status(self) -> dict[str, Any]:
        from taxnetlab import suite

        return {"core": suite.vendored(), "config": str(suite.suite_config_path()),
                "config_found": suite.suite_config_path().is_file(), "language": suite.suite_language(),
                "projects": self.suite.projects(), "workspace_folder": str(self.suite.folder)}

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

    # ------------------------------------------------------------------ guide (plan s 8, Phase 9)
    @staticmethod
    def guide(locale: str | None = None) -> dict[str, str]:
        """The user guide and method notes; a translated file (``user_guide.<tag>.md``) is used where it exists."""
        from taxnetlab.buildinfo import resource_path

        out = {}
        for name in ("user_guide", "methods"):
            path = resource_path("guide", f"{name}.md")
            if locale and locale.replace("-", "").isalnum():
                translated = resource_path("guide", f"{name}.{locale}.md")
                if translated.is_file():
                    path = translated
            out[name] = path.read_text(encoding="utf-8")
        return out

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

    # ------------------------------------------------------------------ reports and packages (Phase 8)
    def run_report(self, run_id: str) -> str:
        from taxnetlab.buildinfo import software_citation
        from taxnetlab.reports import run_report_html

        return run_report_html(runs.load_record(self.ws, run_id), self._outputs(run_id), software_citation())

    def export_package(self, run_id: str, include_outputs: bool | None = None) -> tuple[bytes, str]:
        from taxnetlab.exports import package

        data, tier = package(self.ws, run_id, include_outputs)
        self.ws.exports_dir.mkdir(parents=True, exist_ok=True)
        (self.ws.exports_dir / f"{run_id}_tier{tier}.zip").write_bytes(data)
        return data, tier

    def reproduce_package(self, data: bytes) -> dict[str, Any]:
        from taxnetlab.exports import reproduce

        return reproduce(self.ws, data)

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
