"""Service layer (plan v2.1, s 4.1). The CLI, the local server and notebooks all use this API;
no front end calls engines directly. Every function returns plain JSON-serialisable data."""

from __future__ import annotations

from typing import Any

from taxnetlab import __version__, runs, synthetic
from taxnetlab.buildinfo import build_manifest, environment
from taxnetlab.datasets import Dataset
from taxnetlab.engines import get_engine, list_engines
from taxnetlab.schema import SCHEMAS, TABLE_ORDER
from taxnetlab.validation import ValidationError
from taxnetlab.views import AGGREGATION_RULES, VIEWS, build_view, jurisdiction_matrix, view_to_json
from taxnetlab.workspace import Workspace

PREVIEW_ROWS = 1000


class Api:
    def __init__(self, workspace: Workspace):
        self.ws = workspace.ensure()

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
        ds = self.ws.load_dataset(dataset_id)
        info = ds.describe()
        info["validation"] = ds.validate().to_dict()
        info["schemas"] = {name: {"columns": SCHEMAS[name].column_names, "primary_key": list(SCHEMAS[name].primary_key),
                                  "description": SCHEMAS[name].description} for name in TABLE_ORDER}
        return info

    def table(self, dataset_id: str, table: str, limit: int = PREVIEW_ROWS) -> dict[str, Any]:
        if table not in SCHEMAS:
            raise KeyError(f"unknown table '{table}'")
        ds = self.ws.load_dataset(dataset_id)
        rows = ds.tables[table]
        return {"table": table, "columns": SCHEMAS[table].column_names, "rows": rows[:limit],
                "total_rows": len(rows), "truncated": len(rows) > limit}

    def table_csv(self, dataset_id: str, table: str) -> str:
        if table not in SCHEMAS:
            raise KeyError(f"unknown table '{table}'")
        return self.ws.load_dataset(dataset_id).csv_text(table)

    def generate_synthetic(self, params: dict[str, Any]) -> dict[str, Any]:
        allowed = set(synthetic.DEFAULT_PARAMS) | {"name"}
        unknown = set(params) - allowed
        if unknown:
            raise ValueError(f"unknown generator parameter(s): {sorted(unknown)}")
        merged = {**synthetic.DEFAULT_PARAMS, **{k: v for k, v in params.items() if v not in (None, "")}}
        ds = synthetic.generate(**merged)
        did = self.ws.save_dataset(ds)
        return {"dataset_id": did, "name": self.ws.dataset_meta(did)["name"], "validation": ds.validate().to_dict()}

    def import_csv(self, name: str, texts: dict[str, str]) -> dict[str, Any]:
        ds, report = Dataset.from_csv_texts(name, texts, {"origin": "csv_import"})
        if ds is None:
            return {"saved": False, "validation": report.to_dict()}
        did = self.ws.save_dataset(ds)
        return {"saved": True, "dataset_id": did, "name": self.ws.dataset_meta(did)["name"],
                "validation": report.to_dict()}

    # ------------------------------------------------------------------ views
    def view(self, dataset_id: str, view: str, rule: str = "count", as_of: str | None = None,
             include_domestic: bool = False) -> dict[str, Any]:
        if view not in VIEWS:
            raise ValueError(f"view must be one of {list(VIEWS)}")
        if rule not in AGGREGATION_RULES:
            raise ValueError(f"rule must be one of {list(AGGREGATION_RULES)}")
        ds = self.ws.load_dataset(dataset_id)
        return view_to_json(ds, build_view(ds, view, rule, as_of or None, include_domestic))

    def matrix(self, dataset_id: str, rule: str = "count", as_of: str | None = None,
               include_domestic: bool = True) -> dict[str, Any]:
        if rule not in AGGREGATION_RULES:
            raise ValueError(f"rule must be one of {list(AGGREGATION_RULES)}")
        return jurisdiction_matrix(self.ws.load_dataset(dataset_id), rule, as_of or None, include_domestic)

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
