"""A-share Company Intelligence releases and Research Suite projects in the Lab (build 1.0.0rc2).

The converter is the vendored Research Suite core, so these tests check the integration (the pinned copy, the
review loop, the hand-over into a Lab dataset and its provenance), not the converter's rules, which are tested
in research-suite-core.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from taxnetlab.api import Api
from taxnetlab.suite import REASONS, SuiteBridge, SuiteError, suite_language, trim_unused_jurisdictions

ROOT = Path(__file__).resolve().parents[1]
RSCORE = ROOT / "src" / "rscore"


@pytest.fixture
def release(tmp_path):
    from rscore import demo

    return demo.build(tmp_path / "release")


@pytest.fixture
def api(workspace):
    return Api(workspace)


def test_vendored_core_is_unedited():
    meta = json.loads((RSCORE / "VENDORED.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"[0-9a-f]{40}", meta["commit"])
    for rel, digest in meta["files"].items():
        data = (RSCORE / rel).read_bytes().replace(b"\r\n", b"\n")  # a Windows checkout may convert line endings
        assert hashlib.sha256(data).hexdigest() == digest, f"src/rscore/{rel} differs from the pinned copy; sync instead"
    on_disk = {p.relative_to(RSCORE).as_posix() for p in RSCORE.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert on_disk - {"VENDORED.json"} == set(meta["files"]), "files added to or missing from the vendored copy"


def test_reason_codes_match_the_vendored_importer():
    src = (RSCORE / "importers" / "ashare.py").read_text(encoding="utf-8")
    rejects = set(re.findall(r'reject\([^)]*"([a-z_0-9]+)"\)', src))
    assert rejects <= set(REASONS), sorted(rejects - set(REASONS))


def test_release_inspection_reads_without_importing(api, release):
    info = api.suite.inspect_release(release)
    assert info["name"] == "example_release_invented_data" and info["pseudonymised"]
    assert [c["security_code"] for c in info["companies"]] == ["DEMO01", "DEMO02"]
    assert not api.suite.folder.exists()  # nothing written
    with pytest.raises(SuiteError):
        api.suite.inspect_release(release / "csv")


def test_import_review_reimport_and_bring_into_lab(api, release):
    b = api.suite
    d = b.import_release(None, release)
    assert Path(d["path"]).parent == b.folder and d["counts"]["entities"] > 0
    rep = d["report"]
    reasons = {r["reason"] for r in rep["summary"]["rejected"]}
    assert "natural_person_excluded" in reasons and reasons <= set(REASONS)
    names = {r["name"]: r for r in rep["review"]}
    assert names["香港中央结算有限公司"]["suggestion"] == "HKG"
    before = d["counts"]["ownership"]
    with pytest.raises(ValueError):
        b.save_overrides(d["path"], {"维尔京群岛": "XXX"})
    d = b.save_overrides(d["path"], {"维尔京群岛": "VGB", "香港中央结算有限公司": "HKG"})
    assert d["overrides"] == {"维尔京群岛": "VGB", "香港中央结算有限公司": "HKG"}
    d = b.reimport(d["path"])
    assert d["counts"]["ownership"] > before
    assert {r["name"] for r in d["report"]["review"]} == {"欧洲"}  # left out by choice
    res = b.bring_into_lab(api, d["path"])
    assert res["saved"] and not res["already_present"]
    meta = api.ws.dataset_meta(res["dataset_id"])["metadata"]
    assert meta["origin"] == "research_suite" and meta["release"] == "example_release_invented_data"
    assert meta["suite_project"] == d["path"] and meta["review_outstanding"] == 1 and meta["import_settings"]["overrides_used"] == 2
    assert re.fullmatch(r"[0-9a-f]{40}", meta["commit"]) and meta["unused_registry_jurisdictions_dropped"] > 200
    ds = api.ws.load_dataset(res["dataset_id"])
    assert "VGB" in {r["jurisdiction_id"] for r in ds.tables["jurisdictions"]}
    text = "".join(ds.csv_text(t) for t in ds.tables)
    assert "张三" not in text  # natural persons never reach the Lab
    again = b.bring_into_lab(api, d["path"])
    assert again["dataset_id"] == res["dataset_id"] and again["already_present"]
    listed = b.projects()
    assert listed[0]["origin"] == "lab" and listed[0]["lab_exports"]


def test_import_into_existing_project_and_subset(api, release):
    b = api.suite
    project = b.create_project("Mine")
    d = b.import_release(project.path, release, companies=["DEMO01"], min_confidence=0.5)
    assert d["name"] == "Mine" and d["report"]["settings"]["companies"] == ["DEMO01"]
    with pytest.raises(SuiteError):
        b.import_release(project.path, release, min_confidence=2)
    for bad in ("", "a/b", "x" * 81, "con:"):
        with pytest.raises(SuiteError):
            b.create_project(bad)
    with pytest.raises(SuiteError):
        b.project("notes.txt")
    with pytest.raises(KeyError):
        b.project(b.folder / "absent.sqlite")


def test_suite_launcher_recent_projects_are_listed(tmp_path, api, release):
    from rscore import services

    outside = services.create_project(tmp_path / "elsewhere" / "Theirs.sqlite")
    cfg = tmp_path / "launcher.json"
    cfg.write_text(json.dumps({"version": 1, "language": "zh-Hans",
                               "recent_projects": [str(outside.path), str(tmp_path / "gone.sqlite")]}), encoding="utf-8")
    b = SuiteBridge(api.ws, config_path=cfg)
    listed = {Path(p["path"]).name: p for p in b.projects()}
    assert listed["Theirs.sqlite"]["origin"] == "suite" and listed["Theirs.sqlite"]["exists"]
    assert not listed["gone.sqlite"]["exists"]
    assert suite_language(cfg) == "zh-Hans" and suite_language(tmp_path / "none.json") is None


def test_trim_keeps_referenced_jurisdictions_and_parents():
    texts = {"jurisdictions": "jurisdiction_id,display_name,iso3,fictional,parent_jurisdiction_id\n"
                              "GBR,UK,GBR,false,\nVGB,BVI,VGB,false,GBR\nFRA,France,FRA,false,\n",
             "entities": "entity_id,jurisdiction_id\ne1,VGB\n"}
    text, dropped = trim_unused_jurisdictions(texts)
    assert dropped == 1 and "FRA" not in text and "GBR" in text and "VGB" in text


def test_complete_a_dataset(api, release):
    d = api.suite.import_release(None, release)
    did = api.suite.bring_into_lab(api, d["path"])["dataset_id"]
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(api.completion_template(did))) as z:
        attrs = z.read("jurisdiction_attributes.csv").decode("utf-8")
    assert "CHN" in attrs and "FIC_" not in attrs
    used = sorted({e["jurisdiction_id"] for e in api.ws.load_dataset(did).tables["entities"]})
    gdp = "jurisdiction_id,attribute,period,value,unit,currency,source_id\n" + "".join(
        f"{j},gdp,2025,{1.0e11 * (k + 1)},currency_units,USD,WB\n" for k, j in enumerate(used))
    src = "source_id,title,custodian,retrieval_date,licence_class\nWB,World Bank WDI,World Bank,2026-11-01,public_attribution\n"
    res = api.derive_dataset(did, "with GDP", {"jurisdiction_attributes": gdp, "sources": src})
    assert res["saved"], res["validation"]
    new = api.ws.load_dataset(res["dataset_id"])
    old = api.ws.load_dataset(did)
    assert len(new.tables["sources"]) == len(old.tables["sources"]) + 1
    assert new.tables["entities"] == old.tables["entities"]
    meta = api.ws.dataset_meta(res["dataset_id"])["metadata"]
    assert meta["derived_from"] == did and meta["parent_metadata"]["origin"] == "research_suite"
    # the GDP now lets conduits and sinks get past its data check
    prev = api.preview("gb2017.conduits_sinks", res["dataset_id"], {})
    assert not any(i["code"] == "gdp_missing" for i in prev["validation"]["issues"])
    with pytest.raises(ValueError):
        api.derive_dataset(did, "x", {"jurisdiction_attributes": "jurisdiction_id,attribute,period,value\n"})
    with pytest.raises(ValueError):
        api.derive_dataset(did, "x", {"nonsense": "a\n1\n"})
    synthetic = api.generate_synthetic({"seed": 5})["dataset_id"]
    with pytest.raises(ValueError):
        api.completion_template(synthetic)


def test_persistent_homology_without_period_uses_link_features(api, release):
    d = api.suite.import_release(None, release)
    did = api.suite.bring_into_lab(api, d["path"])["dataset_id"]
    blocked = api.preview("ph.vietoris_rips", did, {})
    assert not blocked["executed"] and blocked["validation"]["issues"][0]["code"] == "no_period"
    ok = api.preview("ph.vietoris_rips", did, {"features": "outward_links,inward_links"})
    assert ok["executed"] and ok["outcome"] == "ok"


def test_cli_import_ashare_and_suite_commands(tmp_path, release, capsys):
    from taxnetlab.cli import main

    ws = str(tmp_path / "cli_ws")
    assert main(["import-ashare", str(release), "--workspace", ws, "--bring"]) == 0
    out = capsys.readouterr().out
    assert "need a jurisdiction" in out and "(Research Suite)" in out
    project = str(tmp_path / "cli_ws" / "suite_projects" / "example_release_invented_data.sqlite")
    assert main(["suite", "choose", project, "维尔京群岛=VGB", "--workspace", ws]) == 0
    assert main(["suite", "choose", project, "nonsense", "--workspace", ws]) == 2
    assert main(["suite", "reimport", project, "--workspace", ws]) == 0
    assert main(["suite", "bring", project, "--workspace", ws]) == 0
    assert main(["suite", "list", "--workspace", ws]) == 0
    assert project in capsys.readouterr().out


def test_handover_from_command_line(tmp_path, api, release):
    from taxnetlab.cli import handover

    assert handover(api, None, "zh") == {"locale": "zh-Hans", "force_locale": True}
    assert handover(api, None, "xx-NOPE") == {}
    s = handover(api, str(release), None)
    assert s == {"page": "suite", "release": str(release.resolve())}
    d = api.suite.import_release(None, release)
    s = handover(api, f'"{d["path"]}"', "en-GB")
    assert s["page"] == "suite" and s["project"] == d["path"] and s["locale"] == "en-GB"
    from rscore import services

    folder = services.export_lab(api.suite.project(d["path"]))
    s = handover(api, str(folder), None)
    assert s["page"] == "overview" and s["dataset_id"] in api.ws.dataset_ids()
    with pytest.raises(ValueError):
        handover(api, str(tmp_path), None)


def test_startup_is_escaped_into_the_page(workspace):
    import threading
    import urllib.request

    from taxnetlab.server import AppServer, find_port

    srv = AppServer(Api(workspace), find_port(19480), {"page": "suite", "release": 'C:\\a "b" <c>'})
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        html = urllib.request.urlopen(srv.url, timeout=10).read().decode("utf-8")
    finally:
        srv.shutdown()
        srv.server_close()
    meta = re.search(r'<meta name="taxnetlab-startup" content="([^"]*)">', html).group(1)
    import html as h

    assert json.loads(h.unescape(meta))["release"] == 'C:\\a "b" <c>' and "<c>" not in meta


# ---------------------------------------------------------------- review of 1.0.0rc2 (fixed in 1.0.0rc3)
def test_a_file_that_is_not_a_suite_project_is_refused_and_left_unchanged(tmp_path, api, release):
    import sqlite3

    foreign = tmp_path / "places.sqlite"
    conn = sqlite3.connect(foreign)
    conn.execute("create table bookmarks (url text)")
    conn.commit()
    conn.close()
    before = foreign.read_bytes()
    for call in (lambda: api.suite.detail(foreign), lambda: api.suite.open_project(foreign),
                 lambda: api.suite.import_release(foreign, release), lambda: api.suite.bring_into_lab(api, foreign)):
        with pytest.raises(SuiteError):
            call()
    assert foreign.read_bytes() == before and not (tmp_path / "places_files").exists()
    garbage = tmp_path / "notes.sqlite"
    garbage.write_text("not a database", encoding="utf-8")
    with pytest.raises(SuiteError):
        api.suite.detail(garbage)
    listed = {Path(p["path"]).name: p for p in SuiteBridge(api.ws).projects()}
    assert "places.sqlite" not in listed  # never remembered


def test_new_project_never_silently_reuses_an_existing_one(api, release):
    b = api.suite
    first = b.import_release(None, release)
    second = b.import_release(None, release)
    assert second["path"] != first["path"] and second["name"].endswith("(2)")
    with pytest.raises(SuiteError):
        b.create_project(first["name"])
    with pytest.raises(SuiteError):
        b.import_release(None, release, project_name=first["name"])
    with pytest.raises(SuiteError):
        b.create_project("NUL")


def test_malformed_release_is_refused_and_leaves_no_project(tmp_path, api):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "manifest.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(SuiteError):
        api.suite.inspect_release(bad)
    (bad / "manifest.json").write_text('{"name": 5, "software": "x", "row_counts": 3}', encoding="utf-8")
    assert api.suite.inspect_release(bad)["name"] == "5"
    with pytest.raises(SuiteError):
        api.suite.import_release(None, bad)
    (bad / "csv").mkdir()
    (bad / "csv" / "companies.csv").write_text("security_code\nX1\n", encoding="utf-8")
    with pytest.raises((SuiteError, ValueError)):
        api.suite.import_release(None, bad)
    assert not list(api.suite.folder.glob("*")) if api.suite.folder.exists() else True
    with pytest.raises(SuiteError):
        api.suite.inspect_release("~no_such_user_zz/x")


def test_completion_template_round_trip_keeps_stored_rows(api, release):
    from taxnetlab.coding import read_template_zip

    d = api.suite.import_release(None, release)
    did = api.suite.bring_into_lab(api, d["path"])["dataset_id"]
    texts = read_template_zip(api.completion_template(did))
    assert texts["jurisdictions"].strip().count("\n") == 0  # header only: stored jurisdictions are not replaced
    with pytest.raises(ValueError, match="no filled rows"):
        api.derive_dataset(did, "x", texts)  # an untouched template adds nothing and blocks nothing
    lines = texts["jurisdiction_attributes"].splitlines()
    first = lines[1].split(",")
    lines[1] = ",".join(first[:3] + ["1.5e13", "currency_units", "USD", "SRC_01"])
    texts["jurisdiction_attributes"] = "\n".join(lines) + "\n"
    texts["sources"] = "Source_ID,Title,Licence_Class\nSRC_01,World Bank WDI,public_attribution\n"  # header case differs
    res = api.derive_dataset(did, "with one GDP", texts)
    assert res["saved"], res["validation"]
    assert res["tables_changed"] == {"jurisdiction_attributes": 1, "sources": 1}
    assert res["unfilled_rows_skipped"]["jurisdiction_attributes"] == len(lines) - 2
    old, new = api.ws.load_dataset(did), api.ws.load_dataset(res["dataset_id"])
    assert new.tables["jurisdictions"] == old.tables["jurisdictions"]  # parents and names untouched


def test_handover_of_an_ordinary_csv_folder_claims_no_suite_provenance(tmp_path, api):
    from taxnetlab.cli import handover

    src = api.ws.load_dataset(api.generate_synthetic({"seed": 77})["dataset_id"])
    folder = tmp_path / "my tables"
    folder.mkdir()
    for table in src.tables:
        text = src.csv_text(table)
        if table == "entities":
            text = text.replace("Example Group", "Sample Group")  # different content, so a new dataset
        (folder / f"{table}.csv").write_text(text, encoding="utf-8")
    s = handover(api, str(folder), None)
    meta = api.ws.dataset_meta(s["dataset_id"])
    assert meta["metadata"]["origin"] == "csv_import" and meta["name"] == "my tables"
    assert len(api.ws.load_dataset(s["dataset_id"]).tables["jurisdictions"]) == len(src.tables["jurisdictions"])


def test_cli_output_survives_a_console_that_cannot_show_chinese(tmp_path, release):
    import os
    import subprocess
    import sys

    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONPATH": str(ROOT / "src")}
    out = subprocess.run([sys.executable, "-m", "taxnetlab", "import-ashare", str(release), "--workspace",
                          str(tmp_path / "ws")], env=env, capture_output=True, timeout=120)
    assert out.returncode == 0, out.stderr.decode("cp1252", "replace")
    assert b"need a jurisdiction" in out.stdout


def test_bad_names_and_types_are_client_errors(workspace):
    import threading
    import urllib.error
    import urllib.request

    from taxnetlab.server import AppServer, find_port

    api = Api(workspace)
    did = api.ensure_default_dataset()
    srv = AppServer(api, find_port(19520))
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def status(method, path, body=None):
        req = urllib.request.Request(srv.url.rstrip("/") + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-TaxNetLab-Token": srv.token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    try:
        long = "a" * 300
        assert status("GET", f"/api/datasets/{long}") == 404
        assert status("GET", f"/api/runs/{long}") == 404
        assert status("GET", f"/{long}") == 404
        assert status("GET", f"/api/guide?locale={long}") == 200
        assert status("POST", "/api/datasets/synthetic", {"name": 5}) == 400
        assert status("POST", "/api/datasets/import", {"name": "x", "tables": {"entities": 1}}) == 400
        assert status("POST", "/api/expectations", {"entry": "x", "frozen_by": "me"}) == 400
        assert status("POST", "/api/suite/inspect", {"release": "9" * 400}) == 400
        assert status("POST", f"/api/datasets/{did}/derive", {"tables": {"sources": 3}}) == 400
    finally:
        srv.shutdown()
        srv.server_close()
