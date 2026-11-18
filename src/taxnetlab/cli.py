"""Command-line interface. ``taxnetlab`` with no arguments starts the interface.

    taxnetlab [serve] [--workspace DIR] [--port N] [--no-browser] [--import PATH] [--language TAG]
    taxnetlab import-ashare RELEASE_FOLDER [--project FILE.sqlite | --project-name NAME] [--companies CODES]
              [--assume-consolidated] [--accept-suggestions] [--min-confidence X] [--bring [--name TEXT]]
    taxnetlab suite list | review PROJECT | choose PROJECT NAME=CODE ... | reimport PROJECT | bring PROJECT
    taxnetlab generate [--seed N] [--name TEXT]
    taxnetlab datasets
    taxnetlab run SPEC.json
    taxnetlab replay RUN_ID
    taxnetlab template illustrative|real-sample [--jurisdictions NLD,LUX] [--out FILE]
    taxnetlab import FILE.zip|FOLDER [--name TEXT]
    taxnetlab expect list | freeze FILE --by NAME | check ENTRY_ID --run RUN_ID
    taxnetlab export RUN_ID [--include-outputs] [--report FILE.html]
    taxnetlab reproduce PACKAGE.zip
    taxnetlab selftest
    taxnetlab version
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from taxnetlab import __version__
from taxnetlab.api import Api
from taxnetlab.workspace import Workspace


def _api(args: argparse.Namespace) -> Api:
    return Api(Workspace(args.workspace))


def cmd_serve(args: argparse.Namespace) -> int:
    from taxnetlab.server import serve

    from taxnetlab import logs

    api = _api(args)
    log_path = logs.setup(api.ws.logs_dir)
    logs.LOGGER.info("starting taxnetlab %s; workspace %s", __version__, api.ws.root)
    created = api.ensure_default_dataset()
    if created:
        print(f"Created a synthetic starter dataset ({created}).")
    print(f"Log file: {log_path}")
    try:
        startup = handover(api, getattr(args, "import_path", None), getattr(args, "language", None))
    except (ValueError, OSError, KeyError) as exc:
        print(f"Could not open {args.import_path}: {exc}", file=sys.stderr)
        startup = {"page": "suite"}
    serve(api, port=args.port, open_browser=not args.no_browser, startup=startup)
    return 0


def handover(api: Api, path: str | None, language: str | None) -> dict:
    """What the interface opens on: a release folder, a suite project, a suite Lab export, a ZIP or CSV folder.

    A release is only read, never imported, until the researcher has chosen the import options in the interface.
    The interface language is the one given, otherwise ResearchSuite.exe's, if a saved choice does not exist.
    """
    from taxnetlab import i18n, suite

    startup: dict = {}
    tags = {loc["tag"] for loc in i18n.available_locales()}
    if language:
        lang = {"en": "en-GB", "zh": "zh-Hans", "zh-CN": "zh-Hans", "zh-Hans-CN": "zh-Hans"}.get(language, language)
        if lang in tags:
            startup.update(locale=lang, force_locale=True)
    elif suite.suite_language() in tags:
        startup["locale"] = suite.suite_language()
    if not path:
        return startup
    p = Path(path.strip().strip('"')).expanduser()
    if p.is_dir() and (p / "manifest.json").is_file():
        startup.update(page="suite", release=str(p.resolve()))
    elif p.is_file() and p.suffix.lower() in suite.PROJECT_SUFFIXES:
        detail = api.suite.open_project(p)
        startup.update(page="suite", project=detail["path"])
    elif p.is_dir() and any(p.glob("*.csv")):
        from taxnetlab.suite import is_suite_export

        if is_suite_export(p):
            res = api.suite.import_export_folder(api, p)
        else:  # an ordinary folder of table CSV files: no suite provenance to claim, nothing trimmed
            res = api.import_csv(p.name, {f.stem.lower(): f.read_text(encoding="utf-8-sig") for f in sorted(p.glob("*.csv"))})
        if not res["saved"]:
            raise ValueError("the tables did not validate; open the Data page for the report")
        startup.update(page="overview", dataset_id=res["dataset_id"])
    elif p.is_file() and p.suffix.lower() == ".zip":
        res = api.import_zip(p.stem, p.read_bytes())
        if not res["saved"]:
            raise ValueError("the tables did not validate; open the Data page for the report")
        startup.update(page="overview", dataset_id=res["dataset_id"])
    else:
        raise ValueError("expected an A-share release folder, a suite project (.sqlite), a folder of table CSV files "
                         "or a ZIP")
    return startup


def _print_detail(d: dict) -> None:
    print(f"project {d['name']}: {d['path']}")
    print("  " + ", ".join(f"{k} {v}" for k, v in d["counts"].items() if v))
    rep = d.get("report")
    if not rep:
        print("  no import yet")
        return
    sm = rep["summary"]
    print(f"  latest import {rep['name']} (release {sm.get('release')})")
    for t, n in sorted((sm.get("imported") or {}).items()):
        print(f"    imported {t}: {n}")
    for r in sm.get("rejected") or []:
        print(f"    rejected {r['table']}: {r['rows']}  {r['reason']}")
    for n in sm.get("notes") or []:
        print(f"    note: {n}")
    if rep["review"]:
        print(f"  {len(rep['review'])} name(s) or place(s) need a jurisdiction:")
        for r in rep["review"]:
            print(f"    {r['name']!s:40} {r['status']:32} suggestion={r['suggestion'] or '-':8} rows={r['rows']} "
                  f"chosen={r['chosen'] or '-'}")
        print("  choose with: taxnetlab suite choose PROJECT \"NAME=CODE\" ...; then: taxnetlab suite reimport PROJECT")
    if rep["revenue_conflicts"]:
        print(f"  {len(rep['revenue_conflicts'])} revenue figure(s) disagree: see {rep['folder']}")


def cmd_import_ashare(args: argparse.Namespace) -> int:
    api = _api(args)
    companies = [c for c in (args.companies or "").replace(";", ",").split(",") if c.strip()]
    d = api.suite.import_release(args.project, args.release, project_name=args.project_name, companies=companies,
                                 assume_consolidated=args.assume_consolidated, accept_suggestions=args.accept_suggestions,
                                 min_confidence=args.min_confidence)
    _print_detail(d)
    if args.bring:
        return _bring(api, d["path"], args.name)
    return 0


def _bring(api: Api, project: str, name: str | None) -> int:
    res = api.suite.bring_into_lab(api, project, name)
    for issue in res["validation"]["issues"]:
        if issue["level"] != "info":
            print(f"  {issue['level']}: {issue['code']}: {issue['message']}", file=sys.stderr)
    if not res["saved"]:
        print("Import into the Lab blocked.", file=sys.stderr)
        return 2
    print(f"{res['dataset_id']}  {res['name']}" + ("  (already in the workspace)" if res.get("already_present") else ""))
    return 0


def cmd_suite(args: argparse.Namespace) -> int:
    api = _api(args)
    b = api.suite
    if args.action == "list":
        for p in b.projects():
            counts = p.get("counts") or {}
            state = "missing" if not p["exists"] else ("damaged" if p.get("error") else "")
            print(f"{p['origin']:7} {counts.get('entities', ''):>6} entities {counts.get('ownership', ''):>6} relations  "
                  f"{p['path']} {state}")
        return 0
    if not args.target:
        print("PROJECT (a .sqlite file) is required", file=sys.stderr)
        return 2
    if args.action == "review":
        _print_detail(b.detail(args.target))
        return 0
    if args.action == "choose":
        choices = {}
        for item in args.choices:
            if "=" not in item:
                print(f"expected NAME=CODE, got {item!r}", file=sys.stderr)
                return 2
            name, code = item.rsplit("=", 1)
            choices[name] = code
        _print_detail(b.save_overrides(args.target, choices))
        return 0
    if args.action == "reimport":
        _print_detail(b.reimport(args.target))
        return 0
    if args.action == "bring":
        return _bring(api, args.target, args.name)
    return 2


def cmd_generate(args: argparse.Namespace) -> int:
    params = {"seed": args.seed}
    if args.name:
        params["name"] = args.name
    out = _api(args).generate_synthetic(params)
    print(f"{out['dataset_id']}  {out['name']}")
    return 0


def cmd_datasets(args: argparse.Namespace) -> int:
    for d in _api(args).datasets():
        counts = d["counts"]
        print(f"{d['dataset_id']}  {d['data_status']:9}  {counts['entities']:5} entities  "
              f"{counts['ownership']:5} relations  {d['name']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = _api(args).run(spec)
    if not out["executed"]:
        print("Run blocked:", file=sys.stderr)
        for issue in out["validation"]["issues"]:
            if issue["level"] == "error":
                print(f"  {issue['code']}: {issue['message']}", file=sys.stderr)
        return 2
    rec = out["record"]
    print(f"run {rec['run_id']}  outcome={rec['outcome']}  engine={rec['engine']['engine_id']} "
          f"({rec['engine']['status']})")
    for name, info in rec["outputs"].items():
        print(f"  {name}: {info['rows']} rows  sha256={info['sha256']}")
    return 0 if rec["outcome"] == "ok" else 3


def cmd_replay(args: argparse.Namespace) -> int:
    rep = _api(args).replay(args.run_id)
    print(json.dumps(rep, indent=2))
    return 0 if rep.get("match") else 1


def cmd_template(args: argparse.Namespace) -> int:
    from taxnetlab.coding import template_zip

    kind = args.kind.replace("-", "_")
    cands = [c for c in (args.jurisdictions or "").split(",") if c.strip()] or None
    out = Path(args.out or f"taxnetlab_{kind}_template.zip")
    out.write_bytes(template_zip(kind, cands))
    print(f"wrote {out}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    path = Path(args.path)
    api = _api(args)
    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8")) if args.mapping else None
    if path.is_dir():
        res = api.import_csv(args.name or path.name, {f.stem: f.read_text(encoding="utf-8-sig") for f in path.glob("*.csv")},
                             mapping)
    else:
        res = api.import_zip(args.name or path.stem, path.read_bytes(), mapping)
    for issue in res["validation"]["issues"]:
        if issue["level"] != "info":
            print(f"  {issue['level']}: {issue['code']}: {issue['message']}" + (f" ({issue['table']} row {issue['row']})" if issue.get("table") else ""),
                  file=sys.stderr)
    if not res["saved"]:
        print("Import blocked.", file=sys.stderr)
        return 2
    print(f"{res['dataset_id']}  {res['name']}")
    return 0


def cmd_expect(args: argparse.Namespace) -> int:
    api = _api(args)
    if args.action == "list":
        for e in api.expectations():
            print(f"{e['entry_id']:40} {e['state']:8} {e['frozen_utc'] or '':21} {e['title'] or e['error']}")
        return 0
    if args.action == "freeze":
        if not args.by:
            print("--by NAME is required to freeze an entry", file=sys.stderr)
            return 2
        entry = api.freeze_expectation(json.loads(Path(args.target).read_text(encoding="utf-8")), args.by)
        print(f"frozen {entry['entry_id']}  sha256={entry['entry_sha256']}")
        return 0
    if args.action == "check":
        if not args.run:
            print("--run RUN_ID is required", file=sys.stderr)
            return 2
        rep = api.check_replication(args.target, args.run)
        print(json.dumps(rep, indent=2))
        return 0 if rep["verdict"] in ("replicated", "replicated_with_discrepancies") else 1
    return 2


def cmd_export(args: argparse.Namespace) -> int:
    api = _api(args)
    inc = True if args.include_outputs else None
    data, tier = api.export_package(args.run_id, inc)
    out = Path(args.out or f"run_{args.run_id}_tier{tier}.zip")
    out.write_bytes(data)
    print(f"wrote {out} (tier {tier})")
    if args.report:
        Path(args.report).write_text(api.run_report(args.run_id), encoding="utf-8")
        print(f"wrote {args.report}")
    return 0


def cmd_reproduce(args: argparse.Namespace) -> int:
    rep = _api(args).reproduce_package(Path(args.package).read_bytes())
    print(json.dumps(rep, indent=2))
    return 0 if rep.get("reproduced") else 1


def cmd_version(args: argparse.Namespace) -> int:
    from taxnetlab.buildinfo import environment

    print(json.dumps(environment(), indent=2))
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """End-to-end check used by CI on the built executable (plan v2.1, s 11.1)."""
    from taxnetlab.server import TOKEN_HEADER, AppServer, find_port

    def check(cond: bool, what: str) -> None:
        print(("PASS " if cond else "FAIL ") + what)
        if not cond:
            raise SystemExit(1)

    with tempfile.TemporaryDirectory(prefix="taxnetlab selftest é ") as tmp:  # spaces and non-ASCII on purpose
        api = Api(Workspace(Path(tmp) / "work space"))
        check(api.ensure_default_dataset() is not None, "starter dataset created")
        did = api.datasets()[0]["dataset_id"]
        check(api.dataset(did)["validation"]["ok"], "dataset validates")
        out = api.run({"engine_id": "demo.link_summary", "dataset_id": did, "parameters": {},
                       "research_question": "selftest"})
        check(out["executed"] and out["record"]["outcome"] == "ok", "demonstration run executed")
        run_id = out["record"]["run_id"]
        check(api.replay(run_id)["match"], "replay reproduces output hashes")
        blocked = api.run({"engine_id": "us10417262.tda", "dataset_id": did})
        check(not blocked["executed"], "interface-status engine is blocked")
        overrides = [{"kind": "cit", "jurisdiction": "FIC_A", "value": 0.4}]
        prev = api.preview("vtrl2018.tax_routing", did, {"overrides": overrides})
        check(prev["executed"] and prev["outcome"] == "ok" and prev["exploratory"], "tax routing live preview computes")
        check(all(r["best_te"] <= r["direct_te"] + 1e-12 for r in prev["outputs"]["pairs"]),
              "cheapest route never dearer than the direct route")
        pinned = api.run({"engine_id": "vtrl2018.tax_routing", "dataset_id": did, "parameters": {"overrides": overrides}})
        check(pinned["executed"] and api.replay(pinned["record"]["run_id"])["match"], "pinned tax routing run replays")
        gb = api.preview("gb2017.conduits_sinks", did, {"sink_threshold": 3.0})
        rows = gb["outputs"]["jurisdictions"] if gb.get("executed") else []
        check(gb.get("executed") and gb["outcome"] == "ok", "conduits and sinks live preview computes")
        check(abs(sum(r["value_in"] - r["value_out"] for r in rows)) < 1e-6, "conduits and sinks: net value flows balance")
        ph = api.preview("ph.vietoris_rips", did, {})
        check(ph.get("executed") and ph["outcome"] == "ok", "persistent homology live preview computes")
        h0 = [r for r in ph["outputs"]["diagram"] if r["dimension"] == 0]
        check(sum(r["essential"] for r in h0) == 1 and len(h0) == len(ph["outputs"]["points"]),
              "persistent homology: one essential cluster, one H0 bar per jurisdiction")
        ph_run = api.run({"engine_id": "ph.vietoris_rips", "dataset_id": did, "parameters": {"metric": "manhattan"}})
        check(ph_run["executed"] and api.replay(ph_run["record"]["run_id"])["match"], "pinned persistent homology run replays")
        cmp = api.preview("compare.models", did, {})
        check(cmp.get("executed") and cmp["outcome"] == "ok", "model comparison computes")
        check(all(r["agreed"] == (r["rank"] is not None) for r in cmp["outputs"]["agreement"]),
              "model comparison: a rank is given only where every reading agrees")
        strict = api.preview("vtrl2018.tax_routing", did, {"eligibility": "strict"})
        check(strict.get("executed") and strict["outcome"] == "ok", "tax routing with treaty conditions computes")
        from taxnetlab.coding import template_zip

        imported = api.import_zip("Illustrative template", template_zip("illustrative"))
        check(imported["saved"], "illustrative coding template imports")
        job = api.jobs.wait(api.jobs.submit({"engine_id": "demo.link_summary", "dataset_id": did})["job_id"], 60)
        check(job["state"] == "done" and api.replay(job["run_id"])["match"], "background job runs and replays")
        pkg, tier = api.export_package(pinned["record"]["run_id"])
        other = Api(Workspace(Path(tmp) / "second researcher"))
        check(tier == "C" and other.reproduce_package(pkg)["reproduced"], "export package reproduces in another workspace")
        check("<script" not in api.run_report(pinned["record"]["run_id"]), "run report is static HTML")
        from rscore import demo

        from taxnetlab.suite import vendored as suite_vendored

        release = demo.build(Path(tmp) / "ashare release")
        detail = api.suite.import_release(None, release)
        check(detail["counts"]["entities"] > 0 and len(api.suite.jurisdictions()) > 200,
              "A-share release imported with the Research Suite core (registry data bundled)")
        detail = api.suite.save_overrides(detail["path"], {"维尔京群岛": "VGB"})
        detail = api.suite.reimport(detail["path"])
        brought = api.suite.bring_into_lab(api, detail["path"])
        ds = api.ws.load_dataset(brought["dataset_id"]) if brought["saved"] else None
        check(ds is not None and "VGB" in {r["jurisdiction_id"] for r in ds.tables["jurisdictions"]},
              "suite project brought into the Lab with the review choices applied")
        check(demo.PERSON not in "".join(ds.csv_text(t) for t in ds.tables), "natural persons never reach the Lab")
        check(suite_vendored().get("commit") is not None, "vendored core records its source commit")
        import zipfile as _zf

        run_a = api.run({"engine_id": "vtrl2018.tax_routing", "dataset_id": did, "parameters": {}})["record"]["run_id"]
        run_b = api.run({"engine_id": "vtrl2018.tax_routing", "dataset_id": did,
                         "parameters": {"minimum_tax_rate": 0.15}})["record"]["run_id"]
        diff = api.run_diff(run_a, run_b)
        check([x["name"] for x in diff["parameters"]] == ["minimum_tax_rate"], "minimum tax scenario runs; run comparison")
        with _zf.ZipFile(io.BytesIO(api.appendix(run_b, "docx"))) as z:
            check("minimum" in z.read("word/document.xml").decode("utf-8"), "methods appendix written as Word")

        server = AppServer(api, find_port(18766))
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            base = server.url
            html = urllib.request.urlopen(base, timeout=10).read().decode("utf-8")
            check("International Tax Network Lab" in html and server.token in html, "interface page served")
            js = urllib.request.urlopen(base + "vendor/plotly.min.js", timeout=10).read()
            check(len(js) > 1_000_000, "bundled Plotly served offline")
            loc = json.loads(urllib.request.urlopen(base + "api/locales/en-GB", timeout=10).read())
            check(len(loc["strings"]) > 50, "locale strings served")
            zh = json.loads(urllib.request.urlopen(base + "api/locales/zh-Hans", timeout=10).read())
            check(zh["strings"]["nav.suite"] == "研究工具套件" and len(zh["strings"]) == len(loc["strings"]),
                  "Simplified Chinese strings served")
            guide = json.loads(urllib.request.urlopen(base + "api/guide?locale=zh-Hans", timeout=10).read())
            check(guide["user_guide"].startswith("# 用户指南"), "Simplified Chinese guide served")
            icon = urllib.request.urlopen(base + "icon.svg", timeout=10).read()
            check(icon.startswith(b"<svg"), "interface icon served")
            view = json.loads(urllib.request.urlopen(base + f"api/datasets/{did}/view?view=value_flow", timeout=10).read())
            check(view["meta"]["direction"] == "held -> holder", "value-flow view reverses direction")
            req = urllib.request.Request(base + "api/runs", data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=10)
                check(False, "POST without token rejected")
            except urllib.error.HTTPError as exc:
                check(exc.code == 403, "POST without token rejected")
            body = json.dumps({"engine_id": "demo.link_summary", "dataset_id": did}).encode()
            req = urllib.request.Request(base + "api/runs", data=body, method="POST",
                                         headers={"Content-Type": "application/json", TOKEN_HEADER: server.token})
            res = json.loads(urllib.request.urlopen(req, timeout=30).read())
            check(res["executed"], "POST with token executes a run")
        finally:
            server.shutdown()
            server.server_close()
            time.sleep(0.2)
    print("Self-test passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taxnetlab", description="International Tax Network Lab")
    parser.add_argument("--version", action="version", version=f"taxnetlab {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workspace", help="workspace folder (default: Documents\\TaxNetLab or ~/TaxNetLab)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("serve", parents=[common], help="start the interface (default)")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--import", dest="import_path", metavar="PATH",
                   help="open on an A-share release folder, a suite project (.sqlite), a suite Lab export or a ZIP")
    p.add_argument("--language", help="interface language, for example en-GB or zh-Hans")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("import-ashare", parents=[common],
                       help="import an A-share Company Intelligence release with the Research Suite's converter")
    p.add_argument("release", help="the release folder (holding manifest.json and csv/)")
    p.add_argument("--project", help="an existing suite project (.sqlite); default: a new project in the workspace")
    p.add_argument("--project-name", help="name of the new project (default: the release name)")
    p.add_argument("--companies", help="security codes to import, comma-separated (default: all)")
    p.add_argument("--assume-consolidated", action="store_true",
                   help="treat revenue with no stated scope as consolidated")
    p.add_argument("--accept-suggestions", action="store_true",
                   help="accept holder jurisdictions suggested from names without review")
    p.add_argument("--min-confidence", type=float, default=0.0, help="drop extracted rows below this confidence (0 to 1)")
    p.add_argument("--bring", action="store_true", help="then import the project into the Lab as a dataset")
    p.add_argument("--name", help="dataset name for --bring")
    p.set_defaults(func=cmd_import_ashare)

    p = sub.add_parser("suite", parents=[common], help="Research Suite projects: list, review, choose, reimport, bring")
    p.add_argument("action", choices=("list", "review", "choose", "reimport", "bring"))
    p.add_argument("target", nargs="?", help="the project file (.sqlite)")
    p.add_argument("choices", nargs="*", help="choose: NAME=CODE pairs (an empty CODE removes a choice)")
    p.add_argument("--name", help="dataset name for bring")
    p.set_defaults(func=cmd_suite)

    p = sub.add_parser("generate", parents=[common], help="create a synthetic dataset")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--name")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("datasets", parents=[common], help="list datasets")
    p.set_defaults(func=cmd_datasets)

    p = sub.add_parser("run", parents=[common], help="execute a run specification (JSON file)")
    p.add_argument("spec")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("replay", parents=[common], help="re-execute a stored run and compare hashes")
    p.add_argument("run_id")
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("selftest", help="end-to-end self-test in a temporary workspace")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("template", help="write a legal coding template (ZIP)")
    p.add_argument("kind", choices=("illustrative", "real-sample"))
    p.add_argument("--jurisdictions", help="comma-separated ISO alpha-3 codes for the real-sample template")
    p.add_argument("--out")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("import", parents=[common], help="import a coding template ZIP or a folder of table CSV files")
    p.add_argument("path")
    p.add_argument("--name")
    p.add_argument("--mapping", help="JSON file: {table: {schema_column: source_header or =constant}}")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("expect", parents=[common], help="expectation register: list, freeze FILE --by NAME, check ID --run RUN")
    p.add_argument("action", choices=("list", "freeze", "check"))
    p.add_argument("target", nargs="?", help="draft JSON file (freeze) or entry id (check)")
    p.add_argument("--by", help="who freezes the entry")
    p.add_argument("--run", help="run id to check")
    p.set_defaults(func=cmd_expect)

    p = sub.add_parser("export", parents=[common], help="export a run as a package by reproducibility tier")
    p.add_argument("run_id")
    p.add_argument("--out")
    p.add_argument("--include-outputs", action="store_true", help="tier B: include outputs (only if the licence permits)")
    p.add_argument("--report", help="also write the HTML run report to this file")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("reproduce", parents=[common], help="re-run a packaged run and compare output hashes")
    p.add_argument("package")
    p.set_defaults(func=cmd_reproduce)

    p = sub.add_parser("version", help="show version and environment")
    p.set_defaults(func=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):  # a console or pipe that cannot show a name must not stop the program
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    if not argv or (argv[0].startswith("--") and argv[0] not in ("--help", "-h", "--version")):
        argv = ["serve", *argv]
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        args = build_parser().parse_args(["serve", *argv])
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
