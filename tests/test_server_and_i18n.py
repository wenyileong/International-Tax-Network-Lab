"""Local server protections and language infrastructure (plan v2.1, s 4.4)."""

import http.client
import json
import re
import threading
from pathlib import Path

import pytest

from taxnetlab import i18n
from taxnetlab.api import Api
from taxnetlab.server import TOKEN_HEADER, AppServer, find_port

WEB = Path(__file__).resolve().parents[1] / "src" / "taxnetlab" / "web"
SRC = Path(__file__).resolve().parents[1] / "src" / "taxnetlab"


@pytest.fixture
def server(workspace):
    api = Api(workspace)
    api.ensure_default_dataset()
    srv = AppServer(api, find_port(19300))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def request(srv, method, path, body=None, headers=None, host=None):
    port = srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Host": host or f"127.0.0.1:{port}"}
    h.update(headers or {})
    conn.request(method, path, body=body, headers=h)
    res = conn.getresponse()
    data = res.read()
    conn.close()
    return res.status, data


def test_binds_loopback_only(server):
    assert server.server_address[0] == "127.0.0.1"


def test_host_header_checked(server):
    status, _ = request(server, "GET", "/api/about", host="evil.example:80")
    assert status == 421


def test_post_needs_token_and_json(server):
    status, _ = request(server, "POST", "/api/datasets/synthetic", b"{}", {"Content-Type": "application/json"})
    assert status == 403
    status, _ = request(server, "POST", "/api/datasets/synthetic", b"{}", {TOKEN_HEADER: server.token,
                                                                           "Content-Type": "text/plain"})
    assert status == 415
    status, data = request(server, "POST", "/api/datasets/synthetic", json.dumps({"seed": 4}).encode(),
                           {TOKEN_HEADER: server.token, "Content-Type": "application/json"})
    assert status == 200 and json.loads(data)["dataset_id"]


def test_no_cors_headers(server):
    status, _ = request(server, "GET", "/api/about")
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", "/api/about", headers={"Host": f"127.0.0.1:{port}", "Origin": "https://evil.example"})
    res = conn.getresponse()
    res.read()
    assert res.getheader("Access-Control-Allow-Origin") is None


def test_static_paths_cannot_escape(server):
    for path in ("/../server.py", "/%2e%2e/server.py", "/locales/en-GB.json", "/nope.js"):
        status, _ = request(server, "GET", path)
        assert status == 404, path


def test_index_carries_token_and_csp(server):
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", "/", headers={"Host": f"127.0.0.1:{port}"})
    res = conn.getresponse()
    body = res.read().decode()
    assert server.token in body and "default-src 'self'" in res.getheader("Content-Security-Policy")


def test_api_errors_are_json(server):
    status, data = request(server, "GET", "/api/datasets/unknown")
    assert status == 404 and json.loads(data)["error"]["code"] == "not_found"
    status, data = request(server, "GET", "/api/datasets/" + server.api.datasets()[0]["dataset_id"] + "/view?view=x")
    assert status == 400


def test_run_blocked_returns_validation(server):
    did = server.api.datasets()[0]["dataset_id"]
    body = json.dumps({"engine_id": "us10417262.tda", "dataset_id": did}).encode()
    status, data = request(server, "POST", "/api/runs", body, {TOKEN_HEADER: server.token,
                                                              "Content-Type": "application/json"})
    out = json.loads(data)
    assert status == 200 and not out["executed"]
    assert any(i["code"] == "engine_not_runnable" for i in out["validation"]["issues"])


# ---------------------------------------------------------------------- i18n
def _strings():
    return i18n.resolved_strings("en-GB")


def test_every_static_key_used_in_interface_exists():
    strings = _strings()
    js = (WEB / "app.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    keys = set(re.findall(r'\bt\("([a-z0-9_.]+)"', js))
    keys |= set(re.findall(r'i18n(?:-title|-placeholder)?[=:]\s*"([a-z0-9_.]+)"', js + html))
    keys |= set(re.findall(r'"data-i18n-placeholder":\s*"([a-z0-9_.]+)"', js))
    prefixes = {k for k in keys if k.endswith(".")}  # dynamic families, checked below
    missing = sorted(k for k in keys - prefixes if k not in strings)
    assert not missing, missing
    assert prefixes <= set(FAMILY_PREFIXES), sorted(prefixes - set(FAMILY_PREFIXES))


FAMILY_PREFIXES = ("status.", "outcome.", "table.", "rule.", "view.", "track.", "col.", "dir.", "level.", "banner.",
                   "gen.", "integrity.", "network.colour.", "overview.band.", "entity_type.", "issue.", "choice.",
                   "param.", "output.", "measure.demo.", "relief.", "routes.basis.", "routes.c.", "routes.ov.", "routes.wa.",
                   "routes.w.", "routes.part.", "routes.k.", "routes.", "guide.", "conduits.", "mode.", "topology.f.")


def test_dynamic_key_families_complete():
    strings = _strings()
    from taxnetlab.engines.base import OUTCOMES, STATUSES
    from taxnetlab.schema import SCHEMAS, TABLE_ORDER
    families = {
        "status.": {s for ladder in STATUSES.values() for s in ladder} | {"synthetic", "real", "mixed", "unknown"},
        "outcome.": set(OUTCOMES), "table.": set(TABLE_ORDER), "rule.": {"count", "fraction_sum", "value_sum"},
        "view.": {"ownership", "value_flow", "jurisdiction"}, "track.": {"reproduction", "original", "demonstration"},
        "col.": {c for s in SCHEMAS.values() for c in s.column_names},
        "dir.": {"holder_held", "held_holder", "holder_jurisdiction_held_jurisdiction"},
        "level.": {"error", "warning", "info"}, "banner.": {"synthetic", "mixed", "unknown"},
        "gen.": {"seed", "n_jurisdictions", "n_groups", "entities_per_group", "cross_holdings"},
        "integrity.": {"ok", "modified", "unreadable"}, "network.colour.": {"fraction", "value"},
        "overview.band.": {f"b{i}" for i in range(1, 7)}, "entity_type.": {"parent", "holding", "finance", "operating"},
        "relief.": {"exemption", "credit", "deduction"}, "routes.ov.": {"cit", "wht", "relief", "treaty", "relief_pair"},
        "routes.basis.": {"treaty", "general", "statutory", "world_average_excluding_conduit", "not_used"},
        "routes.c.": {"btwns", "strct", "occur"}, "routes.wa.": {"unweighted", "gdp"}, "routes.w.": {"gdp_product", "unweighted"},
        "param.": {p.name for e in __import__("taxnetlab.engines", fromlist=["list_engines"]).list_engines() for p in e.parameters},
        "output.": {o for e in __import__("taxnetlab.engines", fromlist=["list_engines"]).list_engines() for o in e.outputs},
        "topology.f.": set(__import__("taxnetlab.features", fromlist=["CATALOGUE"]).CATALOGUE),
        "choice.": {c for e in __import__("taxnetlab.engines", fromlist=["list_engines"]).list_engines()
                    for p in e.parameters for c in (p.choices or ())},
    }
    missing = [p + k for p, ks in families.items() for k in ks if p + k not in strings]
    assert not missing, missing


def test_every_issue_code_has_a_translation():
    strings = _strings()
    found = set()
    for path in SRC.rglob("*.py"):
        found |= set(re.findall(r'\.(?:error|warning|info)\(\s*"([a-z_]+)"', path.read_text(encoding="utf-8")))
    found |= set(re.findall(r'"(bad_identifier|bad_choice|bad_bool|bad_number|out_of_range|bad_date)"',
                            (SRC / "schema.py").read_text(encoding="utf-8")))
    missing = sorted(c for c in found if f"issue.{c}" not in strings)
    assert not missing, missing


def test_placeholders_consistent_with_english():
    strings = _strings()
    for key, value in strings.items():
        assert value.count("{") == value.count("}"), key


def test_fallback_chain(tmp_path, monkeypatch):
    for f in (WEB / "locales").glob("*.json"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "xx-TEST.json").write_text(json.dumps({"_meta": {"name": "Test", "dir": "rtl", "fallback": "en-GB"},
                                                       "strings": {"nav.data": "DATA!"}}), encoding="utf-8")
    monkeypatch.setattr(i18n, "locales_dir", lambda: tmp_path)
    s = i18n.resolved_strings("xx-TEST")
    assert s["nav.data"] == "DATA!" and s["nav.runs"] == "Runs"
    tags = {l["tag"]: l for l in i18n.available_locales()}
    assert tags["xx-TEST"]["dir"] == "rtl" and "en-GB" in tags
    with pytest.raises(KeyError):
        i18n.load_locale("../secrets")


def test_rejected_post_does_not_poison_keep_alive_connection(server):
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    host = {"Host": f"127.0.0.1:{port}"}
    conn.request("POST", "/api/runs", body=b'{"engine_id": "x"}', headers={**host, "Content-Type": "application/json"})
    res = conn.getresponse()
    res.read()
    assert res.status == 403
    conn.request("GET", "/api/about", headers=host)  # same connection
    res = conn.getresponse()
    assert res.status == 200 and json.loads(res.read())["version"]
    conn.close()


def test_invalid_content_length_rejected(server):
    import socket
    port = server.server_address[1]
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(f"POST /api/runs HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Length: -5\r\n\r\n".encode())
        assert b" 400 " in s.recv(4096).split(b"\r\n")[0] + b" "


def test_invalid_json_is_400(server):
    status, data = request(server, "POST", "/api/runs", b"{not json", {TOKEN_HEADER: server.token,
                                                                       "Content-Type": "application/json"})
    assert status == 400 and json.loads(data)["error"]["code"] == "bad_request"



def test_every_chart_guide_has_both_reading_modes():
    strings = _strings()
    js = (WEB / "app.js").read_text(encoding="utf-8")
    ids = set(re.findall(r'guide\("([a-z_.]+)"\)', js))
    assert len(ids) >= 10
    missing = [f"guide.{i}.{m}" for i in ids for m in ("plain", "tech") if f"guide.{i}.{m}" not in strings]
    assert not missing, missing


def test_mode_variants_have_a_base_key():
    strings = _strings()
    orphans = [k for k in strings if k.endswith((".plain", ".tech")) and not k.startswith("guide.")
               and k.rsplit(".", 1)[0] not in strings]
    assert not orphans, orphans


def test_topology_feature_list_matches_catalogue():
    from taxnetlab.features import CATALOGUE
    js = (WEB / "app.js").read_text(encoding="utf-8")
    listed = re.search(r"const PH_FEATURES = \[([^\]]+)\]", js).group(1)
    assert re.findall(r'"([a-z0-9_]+)"', listed) == list(CATALOGUE)
