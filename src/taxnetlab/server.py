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

import json
import mimetypes
import secrets
import socket
import sys
import threading
import traceback
import webbrowser
from http import HTTPStatus
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

    def __init__(self, api: Api, port: int):
        self.api = api
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
        except Exception as exc:  # pragma: no cover - logged for the console
            traceback.print_exc()
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
            if p == ["runs"]:
                return self._json(200, api.runs())
            if len(p) == 2 and p[0] == "runs":
                return self._json(200, api.run_record(p[1]))
            if len(p) == 4 and p[0] == "runs" and p[2] == "outputs" and p[3].endswith(".csv"):
                return self._csv(api.run_output_csv(p[1], p[3][:-4]), f"{p[1]}_{p[3]}")
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
                return self._json(200, api.import_csv(str(body.get("name") or ""), tables))
            if p == ["runs"]:
                return self._json(200, api.run(body))
            if len(p) == 3 and p[0] == "runs" and p[2] == "replay":
                return self._json(200, api.replay(p[1]))
            if p == ["quit"]:
                self._json(200, {"stopping": True})
                self.server.stop_soon()
                return None
        raise KeyError(f"no API route for {method} /api/{'/'.join(parts)}")

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
        self._send(200, data, ctype, {
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-eval'; "
                                       "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                                       "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"})


def serve(api: Api, port: int | None = None, open_browser: bool = True, ready: threading.Event | None = None,
          holder: list | None = None) -> None:
    server = AppServer(api, port or find_port())
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
