"""Command-line interface. ``taxnetlab`` with no arguments starts the interface.

    taxnetlab [serve] [--workspace DIR] [--port N] [--no-browser]
    taxnetlab generate [--seed N] [--name TEXT]
    taxnetlab datasets
    taxnetlab run SPEC.json
    taxnetlab replay RUN_ID
    taxnetlab template illustrative|real-sample [--jurisdictions NLD,LUX] [--out FILE]
    taxnetlab import FILE.zip|FOLDER [--name TEXT]
    taxnetlab selftest
    taxnetlab version
"""

from __future__ import annotations

import argparse
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

    api = _api(args)
    created = api.ensure_default_dataset()
    if created:
        print(f"Created a synthetic starter dataset ({created}).")
    serve(api, port=args.port, open_browser=not args.no_browser)
    return 0


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
    if path.is_dir():
        res = api.import_csv(args.name or path.name, {f.stem: f.read_text(encoding="utf-8-sig") for f in path.glob("*.csv")})
    else:
        res = api.import_zip(args.name or path.stem, path.read_bytes())
    for issue in res["validation"]["issues"]:
        if issue["level"] != "info":
            print(f"  {issue['level']}: {issue['code']}: {issue['message']}" + (f" ({issue['table']} row {issue['row']})" if issue.get("table") else ""),
                  file=sys.stderr)
    if not res["saved"]:
        print("Import blocked.", file=sys.stderr)
        return 2
    print(f"{res['dataset_id']}  {res['name']}")
    return 0


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
    p.set_defaults(func=cmd_serve)

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
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("version", help="show version and environment")
    p.set_defaults(func=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
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
