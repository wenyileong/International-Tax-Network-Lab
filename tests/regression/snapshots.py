"""Approved-output snapshots ("nothing changes" tests, plan s 6.3).

``python -m regression.snapshots`` (from the tests folder, with src on PYTHONPATH) writes ``approved.json`` with the hash of
every output table of every engine at its default parameters on the regression datasets. Run it only when a
change of outputs is intended and documented; the test compares the current build with the file.
"""

from __future__ import annotations

import json
from pathlib import Path

from taxnetlab.canonical import sha256_text
from taxnetlab.engines import get_engine
from taxnetlab.fixtures import gb_fixture, vtrl_fixture
from taxnetlab.runs import _serialise_outputs
from taxnetlab.synthetic import build_0_1_fixture, generate

APPROVED = Path(__file__).with_name("approved.json")
ENGINES = ("demo.link_summary", "vtrl2018.tax_routing", "gb2017.conduits_sinks", "ph.vietoris_rips", "compare.models", "sensitivity.sweep")
# Tables added after a snapshot was approved are removed before comparison, so that the datasets the
# snapshots were taken on are reproduced exactly.
LATER_TABLES = ("tax_treaty_conditions",)


def datasets():
    from taxnetlab.datasets import Dataset

    raw = {"fixture_0_1": build_0_1_fixture(), "vtrl_fixture": vtrl_fixture(), "gb_fixture": gb_fixture(),
           "synthetic_17": generate(seed=17), "synthetic_7_20": generate(seed=7, n_jurisdictions=20, n_groups=12)}
    out = {}
    for name, ds in raw.items():
        tables = {t: rows for t, rows in ds.tables.items() if t not in LATER_TABLES}
        rebuilt, _ = Dataset.from_rows(ds.name, tables)
        out[name] = rebuilt
    return out


def compute() -> dict[str, dict[str, dict[str, str]]]:
    result: dict[str, dict[str, dict[str, str]]] = {}
    for dname, ds in datasets().items():
        result[dname] = {"dataset_id": ds.dataset_id}
        for eid in ENGINES:
            engine = get_engine(eid)
            params, rep = engine.resolve_parameters({})
            rep.extend(engine.validate(ds, params))
            if not rep.ok:
                result[dname][eid] = {"_outcome": "blocked"}
                continue
            res = engine.run(ds, params)
            entry = {"_outcome": res.outcome}
            if res.outcome == "ok":
                entry.update({k: sha256_text(v) for k, v in _serialise_outputs(engine.spec, res.outputs).items()})
            result[dname][eid] = entry
    return result


if __name__ == "__main__":
    APPROVED.write_text(json.dumps(compute(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {APPROVED}")
