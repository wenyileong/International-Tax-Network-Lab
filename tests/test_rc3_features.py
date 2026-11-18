"""Features of 1.0.0rc3 (plan docs/PLAN_1_0_RC3_SCAFFOLD.md), written against the scaffold before the code."""

import io
import itertools
import json
import math
import random
import threading
import time
import zipfile

import pytest

from taxnetlab import synthetic
from taxnetlab.api import Api
from taxnetlab.engines import get_engine

WDI = (
    '"Data Source","World Development Indicators",\n\n"Last Updated Date","2026-10-30",\n\n'
    '"Country Name","Country Code","Indicator Name","Indicator Code","2023","2024","2025",\n'
    '"China","CHN","GDP (current US$)","NY.GDP.MKTP.CD","17794782039552.2","18743803170827.2","",\n'
    '"Hong Kong SAR, China","HKG","GDP (current US$)","NY.GDP.MKTP.CD","380812000000","407107000000","",\n'
    '"British Virgin Islands","VGB","GDP (current US$)","NY.GDP.MKTP.CD","","","",\n'
    '"East Asia & Pacific","EAS","GDP (current US$)","NY.GDP.MKTP.CD","31000000000000","32000000000000","",\n'
    '"World","WLD","GDP (current US$)","NY.GDP.MKTP.CD","105000000000000","110000000000000","",\n'
)


@pytest.fixture
def api(workspace):
    return Api(workspace)


# ---------------------------------------------------------------- F1 reference GDP
def test_world_bank_csv_is_read_exactly_and_aggregates_dropped(api):
    ref = api.add_reference(WDI.encode("utf-8"), retrieved="2026-11-01", filename="API_NY.GDP.MKTP.CD.csv")
    assert ref["indicator"] == "NY.GDP.MKTP.CD" and ref["jurisdictions"] == 2
    assert ref["periods"] == ["2023", "2024"] and ref["retrieved"] == "2026-11-01"
    values = api.reference_values(ref["reference_id"])
    assert values["CHN"]["2024"] == 18743803170827.2 and "EAS" not in values and "WLD" not in values
    assert "VGB" not in values  # no value: never filled
    again = api.add_reference(WDI.encode("utf-8"), retrieved="2026-11-01")
    assert again["reference_id"] == ref["reference_id"] and len(api.references()) == 1
    with pytest.raises(ValueError):
        api.add_reference(b"not,a,world,bank,file\n", retrieved="2026-11-01")
    with pytest.raises(ValueError):
        api.add_reference(WDI.encode("utf-8"), retrieved="yesterday")


def test_completion_from_reference_feeds_conduits_and_sinks(tmp_path, api):
    from rscore import demo

    release = demo.build(tmp_path / "release")
    d = api.suite.import_release(None, release)
    did = api.suite.bring_into_lab(api, d["path"])["dataset_id"]
    ref = api.add_reference(WDI.encode("utf-8"), retrieved="2026-11-01")
    res = api.complete_from_reference(did, ref["reference_id"], "2024")
    assert res["saved"], res["validation"]
    meta = api.ws.dataset_meta(res["dataset_id"])["metadata"]
    assert meta["origin"] == "derived" and meta["reference"]["reference_id"] == ref["reference_id"]
    ds = api.ws.load_dataset(res["dataset_id"])
    gdp = {(r["jurisdiction_id"], r["period"]): r["value"] for r in ds.tables["jurisdiction_attributes"]
           if r["attribute"] == "gdp"}
    assert gdp[("CHN", "2024")] == 18743803170827.2
    src = [s for s in ds.tables["sources"] if s["source_id"] == res["source_id"]]
    assert src and src[0]["licence_class"] == "public_attribution" and "World Bank" in src[0]["title"]
    assert {"CYM", "GBR"} <= set(res["missing"]) and "CYM" not in res["filled"]  # reported, never filled
    with pytest.raises(ValueError):
        api.complete_from_reference(did, ref["reference_id"], "1990")


# ---------------------------------------------------------------- F3 minimum tax
def _oracle_min_tax(ds, period, m, c):
    dom = {r["jurisdiction_id"]: r for r in ds.tables["tax_domestic"] if r["period"] == period}
    codes = sorted(dom)
    cit = {k: dom[k]["cit_rate"] for k in codes}
    borne = {k: cit[k] + max(0.0, m - cit[k]) * (1 - c) for k in codes}
    wht = {k: dom[k]["dividend_wht_rate"] for k in codes}
    rel = {k: dom[k]["relief_method"] for k in codes}
    tr = {(r["payer_jurisdiction"], r["recipient_jurisdiction"]): r["dividend_wht_rate"]
          for r in ds.tables["tax_treaty_dividends"] if r["period"] == period}
    rp = {(r["relieving_jurisdiction"], r["taxing_jurisdiction"]): r["relief_method"]
          for r in ds.tables["tax_relief_overrides"] if r["period"] == period}
    tbar = {k: math.fsum(borne[j] for j in codes if j != k) / (len(codes) - 1) for k in codes}

    def d(s, p, first):
        w, meth, tp = tr.get((s, p), wht[s]), rp.get((p, s), rel[p]), cit[p]
        if meth == "exemption":
            return w
        if meth == "deduction":
            return 1 - (1 - w) * (1 - tp)
        ts = borne[s] if first else tbar[s]
        return min(max(w, (tp - ts) / (1 - ts)), 1.0)

    out = {}
    for s, p in itertools.permutations(codes, 2):
        others = [k for k in codes if k not in (s, p)]
        best = None
        for n in range(len(others) + 1):
            for mid in itertools.permutations(others, n):
                r = [s, *mid, p]
                ret = math.prod(1 - max(d(r[i], r[i + 1], i == 0), 0.0) for i in range(len(r) - 1))
                key = (-math.log(ret) + 1e-4 * n, n)
                if best is None or key < best[0]:
                    best = (key, 1 - (1 - borne[s]) * ret)
        out[(s, p)] = best[1]
    return out


def test_minimum_tax_matches_the_oracle():
    rnd = random.Random(3)
    eng = get_engine("vtrl2018.tax_routing")
    for seed in range(10):
        ds = synthetic.generate(seed=300 + seed, n_jurisdictions=rnd.randint(3, 5))
        m, c = rnd.choice([0.15, 0.2]), rnd.choice([0.0, 0.3])
        p, rep = eng.resolve_parameters({"minimum_tax_rate": m, "substance_carve_out": c, "max_intermediates": 6,
                                         "penalty": 1e-4, "centrality_weights": "unweighted"})
        assert rep.ok
        assert eng.validate(ds, p).ok
        res = eng.run(ds, p)
        ref = _oracle_min_tax(ds, p["period"], m, c)
        for row in res.outputs["pairs"]:
            assert row["best_te"] == pytest.approx(ref[(row["host"], row["home"])], abs=1e-9)
        assert any("minimum tax" in a.lower() for a in res.assumptions)


def test_minimum_tax_floor_and_neutral_settings():
    eng = get_engine("vtrl2018.tax_routing")
    ds = synthetic.generate(seed=11, n_jurisdictions=6)

    codes = sorted({r["jurisdiction_id"] for r in ds.tables["tax_domestic"]})
    haven = [{"kind": "cit", "jurisdiction": codes[0], "value": 0.0}, {"kind": "wht", "jurisdiction": codes[0], "value": 0.0},
             {"kind": "relief", "jurisdiction": codes[1], "value": "exemption"}]

    def best(**kw):
        p, rep = eng.resolve_parameters({"overrides": haven, **kw})
        assert rep.ok, rep.to_dict()
        assert eng.validate(ds, p).ok
        return {(r["host"], r["home"]): r["best_te"] for r in eng.run(ds, p).outputs["pairs"]}

    off = best()
    assert min(off.values()) < 0.15  # the floor must bind somewhere, or the test proves nothing
    assert best(minimum_tax_rate=0.15, substance_carve_out=1.0) == off  # full carve-out: no top-up
    on = best(minimum_tax_rate=0.15)
    assert min(on.values()) >= 0.15 - 1e-12
    assert all(on[k] >= off[k] - 1e-12 for k in off)
    p, rep = eng.resolve_parameters({"minimum_tax_rate": 0.9})
    assert not rep.ok and rep.errors[0].code == "bad_parameter"


# ---------------------------------------------------------------- F5 change over time
def test_ownership_changes_between_two_dates():
    from taxnetlab.datasets import Dataset
    from taxnetlab.timecompare import ownership_changes

    ds = synthetic.generate(seed=2, n_jurisdictions=5)
    texts = {t: ds.csv_text(t) for t in ds.tables}
    lines = texts["ownership"].splitlines()
    head = lines[0].split(",")
    i_to, i_from, i_frac = head.index("valid_to"), head.index("valid_from"), head.index("fraction")
    row1 = lines[1].split(",")
    row1[i_from], row1[i_to] = "2010-01-01", "2020-06-30"  # held from 2010, ended in mid-2020
    lines[1] = ",".join(row1)
    texts["ownership"] = "\n".join(lines) + "\n"
    moved, rep = Dataset.from_csv_texts("dated", texts, {})
    assert moved is not None, rep.to_dict()
    ch = ownership_changes(moved, "2020-01-01", "2021-01-01")
    assert ch["counts"]["removed"] == 1 and ch["counts"]["added"] >= 0
    assert ch["removed"][0]["relation_id"] == moved.tables["ownership"][0]["relation_id"]
    same = ownership_changes(moved, "2021-01-01", "2021-01-01")
    assert same["counts"] == {"added": 0, "removed": 0, "changed": 0}
    assert {"jurisdiction_id", "gained", "lost"} <= set(ch["jurisdictions"][0])
    with pytest.raises(ValueError):
        ownership_changes(moved, "2021-13-01", "2021-01-01")
    assert i_from >= 0 and i_frac >= 0


# ---------------------------------------------------------------- F8 methods appendix, F9 run comparison
def _two_runs(api):
    did = api.ensure_default_dataset() or api.datasets()[0]["dataset_id"]
    a = api.run({"engine_id": "gb2017.conduits_sinks", "dataset_id": did, "parameters": {"sink_threshold": 1.0},
                 "research_question": "Which jurisdictions are sinks?"})
    b = api.run({"engine_id": "gb2017.conduits_sinks", "dataset_id": did, "parameters": {"sink_threshold": 2.0}})
    return a["record"]["run_id"], b["record"]["run_id"]


def test_methods_appendix_in_three_formats(api):
    a, _ = _two_runs(api)
    md = api.appendix(a, "md").decode("utf-8")
    rec = api.run_record(a)["record"]
    assert "Which jurisdictions are sinks?" in md and rec["dataset"]["content_hash"] in md
    for name, value in rec["parameters"].items():
        assert name in md
    for w in rec["warnings"]:
        assert w[:40] in md
    assert "International Tax Network Lab (version" in md and "—" not in md
    html = api.appendix(a, "html").decode("utf-8")
    assert html.startswith("<!doctype html>") and "<script" not in html
    docx = api.appendix(a, "docx")
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        names = set(z.namelist())
        xml = z.read("word/document.xml").decode("utf-8")
    assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= names
    assert "<w:tbl>" in xml and "Which jurisdictions are sinks?" in xml
    with pytest.raises(ValueError):
        api.appendix(a, "pdf")


def test_compare_two_runs(api):
    a, b = _two_runs(api)
    same = api.run_diff(a, a)
    assert same["identical"] and not same["parameters"]
    d = api.run_diff(a, b)
    assert not d["identical"] and [p["name"] for p in d["parameters"]] == ["sink_threshold"]
    juris = d["outputs"]["jurisdictions"]
    assert juris["changed"] >= 0 and juris["added"] == 0 and juris["removed"] == 0
    assert all("columns" in row for row in juris["rows"])
    with pytest.raises(KeyError):
        api.run_diff(a, "nope")


# ---------------------------------------------------------------- F10 dialogs, F12 import progress
def test_picker_reports_unavailable_without_a_display(monkeypatch):
    from taxnetlab import picker

    monkeypatch.setattr(picker, "_tk_available", lambda: False)
    assert picker.pick("folder") == {"available": False, "path": None}
    with pytest.raises(ValueError):
        picker.pick("anything")


def test_suite_import_runs_as_a_job_with_progress(tmp_path, api):
    from rscore import demo

    release = demo.build(tmp_path / "release")
    job = api.submit_suite_import({"release": str(release)})
    deadline = time.time() + 60
    while api.jobs.get(job["job_id"])["state"] in ("queued", "running") and time.time() < deadline:
        time.sleep(0.05)
    done = api.jobs.get(job["job_id"])
    assert done["state"] == "done", done
    assert done["result"]["counts"]["entities"] > 0
    bad = api.submit_suite_import({"release": str(tmp_path / "missing")})
    while api.jobs.get(bad["job_id"])["state"] in ("queued", "running"):
        time.sleep(0.05)
    assert api.jobs.get(bad["job_id"])["state"] == "failed"


def test_new_routes_answer(workspace):
    import urllib.request

    from taxnetlab.server import AppServer, find_port

    api = Api(workspace)
    a, b = _two_runs(api)
    did = api.datasets()[0]["dataset_id"]
    srv = AppServer(api, find_port(19560))
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def get(path):
        req = urllib.request.Request(srv.url.rstrip("/") + path, headers={"X-TaxNetLab-Token": srv.token})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()

    try:
        assert get(f"/api/runs/{a}/appendix.docx")[0] == 200
        assert get(f"/api/runs/{a}/appendix.md")[0] == 200
        assert json.loads(get(f"/api/runs/{a}/diff?other={b}")[1])["parameters"]
        assert "counts" in json.loads(get(f"/api/datasets/{did}/changes?from=2020-01-01&to=2026-01-01")[1])
        assert json.loads(get("/api/reference")[1]) == []
    finally:
        srv.shutdown()
        srv.server_close()
