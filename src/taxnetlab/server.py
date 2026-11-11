"""Local application server (plan v2.1, s 4.4).

Binds to 127.0.0.1 only and serves the offline interface plus a JSON API over :class:`taxnetlab.api.Api`.
Protections for a local server that a browser can reach:

* the ``Host`` header must name the loopback address and the bound port (blocks DNS rebinding);
* every state-changing request needs the per-session token, sent in the ``X-TaxNetLab-Token`` header.
  A custom header cannot be sent cross-origin without a CORS preflight, which this server never
  approves, so other websites cannot drive it;
* request bodies are capped in size; static paths cannot leave the bundled ``web`` folder.
"""

from __future__ import annotations

import html
import json
import logging
import mimetypes
import secrets
import socket
import sys
import threading
import traceback
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from taxnetlab import i18n
from taxnetlab.api import Api
from taxnetlab.buildinfo import resource_path
from taxnetlab.validation import ValidationError

DEFAULT_PORT = 8766  # JAF Rule Bench uses 8765; the two tools can run side by side
PORT_ATTEMPTS = 20
MAX_BODY = 64 * 1024 * 1024

#: Documented HTTP routes (docs/API.md is generated from this list; a test calls every route).
#: POST routes need the session token header and a JSON body.
ROUTES: tuple[tuple[str, str, str], ...] = (
    ("GET", "/api/about", "version, build, source commit, lock-file hash and workspace"),
    ("GET", "/api/locales", "available interface languages"),
    ("GET", "/api/locales/{tag}", "interface strings for a language, with fallback resolved"),
    ("GET", "/api/engines", "every registered engine: status, boundary, parameters, measures, outputs"),
    ("GET", "/api/guide", "the user guide and method notes (Markdown)"),
    ("GET", "/api/datasets", "datasets in the workspace"),
    ("GET", "/api/datasets/{dataset_id}", "one dataset: counts, sources, schema, validation report"),
    ("GET", "/api/datasets/{dataset_id}/tables/{table}", "a table preview (JSON)"),
    ("GET", "/api/datasets/{dataset_id}/tables/{table}.csv", "a table as canonical CSV"),
    ("GET", "/api/datasets/{dataset_id}/view?view=ownership|value_flow|jurisdiction", "a graph view"),
    ("GET", "/api/datasets/{dataset_id}/matrix?rule=count|fraction_sum|value_sum", "jurisdiction matrix"),
    ("GET", "/api/templates/illustrative.zip", "illustrative legal coding template"),
    ("GET", "/api/templates/real_sample.zip?jurisdictions=NLD,LUX", "real-sample legal coding template"),
    ("GET", "/api/runs", "stored runs, with integrity and stale flags"),
    ("GET", "/api/runs/{run_id}", "one run: record, summary and typed outputs"),
    ("GET", "/api/runs/{run_id}/outputs/{name}.csv", "an output table as stored"),
    ("GET", "/api/runs/{run_id}/record.json", "the run record"),
    ("GET", "/api/runs/{run_id}/report.html", "self-contained HTML report"),
    ("GET", "/api/runs/{run_id}/package.zip?include_outputs=true|false", "export package by reproducibility tier"),
    ("GET", "/api/jobs", "background runs"),
    ("GET", "/api/jobs/{job_id}", "one background run: state, progress, run id"),
    ("GET", "/api/expectations", "frozen expectation entries"),
    ("GET", "/api/expectations/{entry_id}", "one frozen entry"),
    ("GET", "/api/replications", "stored replication reports"),
    ("GET", "/api/datasets/{dataset_id}/completion_template.zip", "GDP and tax-rule template for the dataset's jurisdictions"),
    ("GET", "/api/suite", "Research Suite: vendored core, suite settings and the projects found"),
    ("GET", "/api/suite/jurisdictions", "jurisdiction codes and names for review pickers"),
    ("GET", "/api/suite/project?path=FILE.sqlite", "one suite project: counts, latest import report and review"),
    ("POST", "/api/datasets/synthetic", "generate a synthetic dataset {seed, n_jurisdictions, ...}"),
    ("POST", "/api/datasets/import", "import CSV tables {name, tables: {table: csv}, mapping?}"),
    ("POST", "/api/datasets/import_zip", "import a ZIP of table CSV files {name, zip_base64, mapping?}"),
    ("POST", "/api/engines/{engine_id}/preview", "exploratory preview, nothing stored {dataset_id, parameters}"),
    ("POST", "/api/runs", "execute and store a run {engine_id, dataset_id, parameters, research_question}"),
    ("POST", "/api/runs/{run_id}/replay", "re-execute a run and compare output hashes"),
    ("POST", "/api/jobs", "execute a run in the background (same body as /api/runs); 202"),
    ("POST", "/api/jobs/{job_id}/cancel", "cancel a background run; nothing is stored"),
    ("POST", "/api/expectations", "freeze an expectation entry {entry, frozen_by}"),
    ("POST", "/api/replications", "check a run against a frozen entry {entry_id, run_id}"),
    ("POST", "/api/reproduce", "reproduce a run from an export package {zip_base64}"),
    ("POST", "/api/datasets/{dataset_id}/derive", "complete a dataset: add or replace tables {name, tables, mode}"),
    ("POST", "/api/suite/inspect", "read an A-share release folder's manifest {release}"),
    ("POST", "/api/suite/projects", "create a suite project in the workspace {name}"),
    ("POST", "/api/suite/open", "open a suite project file {path}"),
    ("POST", "/api/suite/import", "import an A-share release {release, project?, project_name?, companies?, "
                                  "assume_consolidated?, accept_suggestions?, min_confidence?}"),
    ("POST", "/api/suite/overrides", "save jurisdiction choices for names and places {project, choices}"),
    ("POST", "/api/suite/reimport", "repeat the latest import with the saved choices {project}"),
    ("POST", "/api/suite/bring", "export a suite project and import it as a Lab dataset {project, name?}"),
    ("POST", "/api/suite/import_export", "import a suite Lab-export folder as a dataset {folder, name?}"),
    ("POST", "/api/quit", "stop the server"),
)
TOKEN_HEADER = "X-TaxNetLab-Token"


def find_port(start: int = DEFAULT_PORT, attempts: int = PORT_ATTEMPTS) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:  # fall back to any free port
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, api: Api, port: int, startup: dict[str, Any] | None = None):
        self.api = api
        self.startup = dict(startup or {})  # hand-over to the interface: page, dataset, release, project, locale
        self.token = secrets.token_urlsafe(24)
        self.web_root = resource_path("web").resolve()
        super().__init__(("127.0.0.1", port), Handler)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/"

    def stop_soon(self) -> None:
        threading.Thread(target=self.shutdown, daemon=True).start()


def _bool(qs: dict[str, list[str]], key: str, default: bool) -> bool:
    if key not in qs:
        return default
    return qs[key][0].lower() in ("1", "true", "yes")


def _q(qs: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    return qs[key][0] if key in qs and qs[key][0] != "" else default


class Handler(BaseHTTPRequestHandler):
    server: AppServer
    protocol_version = "HTTP/1.1"
    server_version = "TaxNetLab"
    sys_version = ""

    # ------------------------------------------------------------------ plumbing
    def log_message(self, fmt: str, *args: Any) -> None:  # quieter console
        if "/api/" in (self.path or "") and not str(args[1] if len(args) > 1 else "").startswith("2"):
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").lower()
        port = self.server.server_address[1]
        return host in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _send(self, status: int, body: bytes, ctype: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False, default=str).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: int, code: str, message: str, **extra: Any) -> None:
        self._json(status, {"error": {"code": code, "message": message, **extra}})

    def _csv(self, text: str, filename: str) -> None:
        safe = "".join(ch for ch in filename if ch.isalnum() or ch in "._-") or "data.csv"
        self._send(200, text.encode("utf-8"), "text/csv; charset=utf-8",
                   {"Content-Disposition": f'attachment; filename="{safe}"'})

    def _read_body(self) -> bytes | None:
        """Read the whole request body before anything else, so that a rejected request never leaves
        unread bytes on a kept-alive connection. Returns None (and closes the connection) if invalid."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.close_connection = True
            self._error(413 if length > MAX_BODY else 400, "bad_length", "missing, invalid or excessive Content-Length")
            return None
        return self.rfile.read(length) if length else b""

    def _body(self) -> Any:
        raw = self._raw_body or b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON body: {exc}") from None

    # ------------------------------------------------------------------ dispatch
    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_HEAD(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        self._raw_body = b""
        if method == "POST":
            body = self._read_body()
            if body is None:
                return
            self._raw_body = body
        if not self._host_ok():
            self._error(421, "bad_host", "requests must address 127.0.0.1 on this port")
            return
        url = urlparse(self.path)
        path = unquote(url.path)
        qs = parse_qs(url.query)
        try:
            if path.startswith("/api/"):
                if method == "POST" and not secrets.compare_digest(self.headers.get(TOKEN_HEADER) or "",
                                                                   self.server.token):
                    self._error(403, "bad_token", "missing or invalid session token")
                    return
                if method == "POST":
                    ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
                    if ctype != "application/json":
                        self._error(415, "bad_content_type", "expected application/json")
                        return
                self._api(method, path[len("/api/"):].strip("/").split("/"), qs)
            elif method == "GET":
                self._static(path)
            else:
                self._error(405, "method_not_allowed", "method not allowed")
        except ValidationError as exc:
            self._json(422, {"error": {"code": "validation_failed", "message": str(exc)},
                             "validation": exc.report.to_dict()})
        except KeyError as exc:
            self._error(404, "not_found", str(exc.args[0]) if exc.args else "not found")
        except (ValueError, TypeError) as exc:
            self._error(400, "bad_request", str(exc))
        except Exception as exc:  # pragma: no cover - logged for the console and the log file
            traceback.print_exc()
            logging.getLogger("taxnetlab").exception("request failed: %s %s", method, path)
            self._error(500, "internal_error", f"{type(exc).__name__}: {exc}")

    def _api(self, method: str, parts: list[str], qs: dict[str, list[str]]) -> None:
        api = self.server.api
        p = parts
        if method == "GET":
            if p == ["about"]:
                return self._json(200, api.about())
            if p == ["locales"]:
                return self._json(200, {"default": i18n.DEFAULT_LOCALE, "locales": i18n.available_locales()})
            if len(p) == 2 and p[0] == "locales":
                data = i18n.load_locale(p[1])
                return self._json(200, {"tag": p[1], "meta": data.get("_meta", {}),
                                        "strings": i18n.resolved_strings(p[1])})
            if p == ["engines"]:
                return self._json(200, api.engines())
            if p == ["datasets"]:
                return self._json(200, api.datasets())
            if len(p) == 2 and p[0] == "datasets":
                return self._json(200, api.dataset(p[1]))
            if len(p) == 4 and p[0] == "datasets" and p[2] == "tables":
                name = p[3]
                if name.endswith(".csv"):
                    return self._csv(api.table_csv(p[1], name[:-4]), f"{p[1]}_{name}")
                return self._json(200, api.table(p[1], name))
            if len(p) == 3 and p[0] == "datasets" and p[2] == "view":
                return self._json(200, api.view(p[1], _q(qs, "view", "ownership"), _q(qs, "rule", "count"),
                                                _q(qs, "as_of"), _bool(qs, "include_domestic", False)))
            if len(p) == 3 and p[0] == "datasets" and p[2] == "matrix":
                return self._json(200, api.matrix(p[1], _q(qs, "rule", "count"), _q(qs, "as_of"),
                                                  _bool(qs, "include_domestic", True)))
            if len(p) == 2 and p[0] == "templates" and p[1] in ("illustrative.zip", "real_sample.zip"):
                kind = p[1][:-4]
                cands = [c for c in (_q(qs, "jurisdictions") or "").split(",") if c.strip()] or None
                return self._send(200, api.template(kind, cands), "application/zip",
                                  {"Content-Disposition": f'attachment; filename="taxnetlab_{kind}_template.zip"'})
            if p == ["guide"]:
                return self._json(200, api.guide(_q(qs, "locale")))
            if len(p) == 3 and p[0] == "datasets" and p[2] == "completion_template.zip":
                return self._send(200, api.completion_template(p[1]), "application/zip",
                                  {"Content-Disposition": f'attachment; filename="taxnetlab_complete_{p[1]}.zip"'})
            if p == ["suite"]:
                return self._json(200, _suite_call(api.suite_status))
            if p == ["suite", "jurisdictions"]:
                return self._json(200, _suite_call(api.suite.jurisdictions))
            if p == ["suite", "project"]:
                return self._json(200, _suite_call(api.suite.detail, _q(qs, "path") or ""))
            if p == ["expectations"]:
                return self._json(200, api.expectations())
            if len(p) == 2 and p[0] == "expectations":
                return self._json(200, api.expectation(p[1]))
            if p == ["replications"]:
                return self._json(200, api.replications())
            if p == ["jobs"]:
                return self._json(200, api.jobs.list())
            if len(p) == 2 and p[0] == "jobs":
                return self._json(200, api.jobs.get(p[1]))
            if p == ["runs"]:
                return self._json(200, api.runs())
            if len(p) == 2 and p[0] == "runs":
                return self._json(200, api.run_record(p[1]))
            if len(p) == 4 and p[0] == "runs" and p[2] == "outputs" and p[3].endswith(".csv"):
                return self._csv(api.run_output_csv(p[1], p[3][:-4]), f"{p[1]}_{p[3]}")
            if len(p) == 3 and p[0] == "runs" and p[2] == "report.html":
                body = api.run_report(p[1]).encode("utf-8")
                return self._send(200, body, "text/html; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="run_{p[1]}_report.html"'})
            if len(p) == 3 and p[0] == "runs" and p[2] == "package.zip":
                inc = _q(qs, "include_outputs")
                data, tier = api.export_package(p[1], None if inc is None else inc == "true")
                return self._send(200, data, "application/zip",
                                  {"Content-Disposition": f'attachment; filename="run_{p[1]}_tier{tier}.zip"'})
            if len(p) == 3 and p[0] == "runs" and p[2] == "record.json":
                rec = api.run_record(p[1])["record"]
                rec.pop("_integrity", None)
                body = json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
                return self._send(200, body, "application/json; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="run_{p[1]}.json"'})
        else:
            body = self._body()
            if not isinstance(body, dict):
                raise ValueError("expected a JSON object")
            if p == ["datasets", "synthetic"]:
                return self._json(200, api.generate_synthetic(body))
            if p == ["datasets", "import"]:
                tables = body.get("tables")
                if not isinstance(tables, dict):
                    raise ValueError("'tables' must map table names to CSV text")
                mapping = body.get("mapping") or None
                if mapping is not None and not isinstance(mapping, dict):
                    raise ValueError("'mapping' must map table names to column mappings")
                return self._json(200, api.import_csv(str(body.get("name") or ""), tables, mapping))
            if p == ["datasets", "import_zip"]:
                import base64
                import binascii

                try:
                    data = base64.b64decode(str(body.get("zip_base64") or ""), validate=True)
                except binascii.Error:
                    raise ValueError("'zip_base64' must be base64 text") from None
                try:
                    return self._json(200, api.import_zip(str(body.get("name") or ""), data))
                except zipfile.BadZipFile:
                    raise ValueError("the file is not a ZIP archive") from None
            if p == ["reproduce"]:
                import base64
                import binascii

                try:
                    data = base64.b64decode(str(body.get("zip_base64") or ""), validate=True)
                    return self._json(200, api.reproduce_package(data))
                except (binascii.Error, zipfile.BadZipFile, KeyError) as exc:
                    raise ValueError(f"not a valid export package: {exc}") from None
            if p == ["expectations"]:
                return self._json(200, api.freeze_expectation(body.get("entry") or {}, str(body.get("frozen_by") or "")))
            if p == ["replications"]:
                return self._json(200, api.check_replication(str(body.get("entry_id") or ""), str(body.get("run_id") or "")))
            if p == ["jobs"]:
                return self._json(202, api.jobs.submit(body))
            if len(p) == 3 and p[0] == "jobs" and p[2] == "cancel":
                return self._json(200, api.jobs.cancel(p[1]))
            if p == ["runs"]:
                return self._json(200, api.run(body))
            if len(p) == 3 and p[0] == "engines" and p[2] == "preview":
                return self._json(200, api.preview(p[1], str(body.get("dataset_id") or ""), body.get("parameters")))
            if len(p) == 3 and p[0] == "runs" and p[2] == "replay":
                return self._json(200, api.replay(p[1]))
            if len(p) == 3 and p[0] == "datasets" and p[2] == "derive" and "zip_base64" in body:
                import base64
                import binascii

                from taxnetlab.coding import read_template_zip

                try:
                    texts = read_template_zip(base64.b64decode(str(body.get("zip_base64") or ""), validate=True))
                except (binascii.Error, zipfile.BadZipFile):
                    raise ValueError("'zip_base64' must be a base64-encoded ZIP archive") from None
                return self._json(200, api.derive_dataset(p[1], str(body.get("name") or ""), texts,
                                                          str(body.get("mode") or "merge")))
            if len(p) == 3 and p[0] == "datasets" and p[2] == "derive":
                tables = body.get("tables")
                if not isinstance(tables, dict) or not all(isinstance(v, str) for v in tables.values()):
                    raise ValueError("'tables' must map table names to CSV text")
                return self._json(200, api.derive_dataset(p[1], str(body.get("name") or ""), tables,
                                                          str(body.get("mode") or "merge")))
            if len(p) == 2 and p[0] == "suite":
                return self._json(200, self._suite_post(p[1], body))
            if p == ["quit"]:
                self._json(200, {"stopping": True})
                self.server.stop_soon()
                return None
        raise KeyError(f"no API route for {method} /api/{'/'.join(parts)}")

    def _suite_post(self, action: str, body: dict[str, Any]) -> Any:
        api = self.server.api
        b = api.suite
        text = lambda k: str(body.get(k) or "")  # noqa: E731
        if action == "inspect":
            return _suite_call(b.inspect_release, text("release"))
        if action == "projects":
            return _suite_call(lambda: b.detail(b.create_project(text("name")).path))
        if action == "open":
            return _suite_call(b.open_project, text("path"))
        if action == "import":
            companies = body.get("companies") or []
            if isinstance(companies, str):
                companies = [c for c in companies.replace(";", ",").split(",")]
            return _suite_call(b.import_release, text("project") or None, text("release"),
                               project_name=text("project_name") or None, companies=list(companies),
                               assume_consolidated=bool(body.get("assume_consolidated")),
                               accept_suggestions=bool(body.get("accept_suggestions")),
                               min_confidence=body.get("min_confidence") or 0.0)
        if action == "overrides":
            return _suite_call(b.save_overrides, text("project"), body.get("choices") or {})
        if action == "reimport":
            return _suite_call(b.reimport, text("project"))
        if action == "bring":
            return _suite_call(b.bring_into_lab, api, text("project"), text("name") or None,
                               body.get("trim_jurisdictions", True) is not False)
        if action == "import_export":
            return _suite_call(b.import_export_folder, api, text("folder"), text("name") or None,
                               trim_jurisdictions=body.get("trim_jurisdictions", True) is not False)
        raise KeyError(f"no API route for POST /api/suite/{action}")

    def _static(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"
        root = self.server.web_root
        target = (root / path.lstrip("/")).resolve()
        if root not in target.parents and target != root or not target.is_file():
            self._error(404, "not_found", "not found")
            return
        if target.parent.name == "locales":
            self._error(404, "not_found", "use /api/locales")
            return
        data = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".js":
            ctype = "text/javascript"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        if target.name == "index.html":
            data = data.replace(b"__SESSION_TOKEN__", self.server.token.encode("ascii"))
            startup = html.escape(json.dumps(self.server.startup, ensure_ascii=False), quote=True)
            data = data.replace(b"__STARTUP__", startup.encode("utf-8"))
        self._send(200, data, ctype, {
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-eval'; "
                                       "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                                       "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"})


def _suite_call(fn, *args, **kwargs):
    """File-system problems in suite operations are the user's to fix (a moved folder, a locked file): report
    them as bad requests with the message, not as internal errors."""
    try:
        return fn(*args, **kwargs)
    except (FileNotFoundError, NotADirectoryError, PermissionError, IsADirectoryError) as exc:
        raise ValueError(str(exc)) from None
    except __import__("sqlite3").DatabaseError as exc:
        raise ValueError(f"not a Research Suite project, or the file is damaged: {exc}") from None


def serve(api: Api, port: int | None = None, open_browser: bool = True, ready: threading.Event | None = None,
          holder: list | None = None, startup: dict[str, Any] | None = None) -> None:
    server = AppServer(api, port or find_port(), startup)
    if holder is not None:
        holder.append(server)
    print(f"International Tax Network Lab is running at {server.url}")
    print(f"Workspace: {api.ws.root}")
    print("Close this window, or use Quit in the interface, to stop. Nothing is sent over the network.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(server.url)).start()
    if ready is not None:
        ready.set()
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Stopped.")


def web_root() -> Path:
    return resource_path("web")
