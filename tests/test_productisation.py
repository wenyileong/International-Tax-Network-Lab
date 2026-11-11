"""Release 1.0 productisation checks (plan Phase 9 and s 11): documented routes, generated documentation,
bundled guide, logging, colour contrast and the installer script."""

import importlib.util
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "taxnetlab" / "web"


def _load(script):
    spec = importlib.util.spec_from_file_location(script, ROOT / "scripts" / f"{script}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_api_reference_is_current():
    assert (ROOT / "docs" / "API.md").read_text(encoding="utf-8") == _load("make_api_docs").build()


def test_user_guide_copy_matches_bundled_guide():
    bundled = (ROOT / "src" / "taxnetlab" / "guide" / "user_guide.md").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8") == bundled
    from taxnetlab.api import Api

    g = Api.guide()
    assert g["user_guide"].startswith("# User guide") and g["methods"].startswith("# Method notes")


def test_every_documented_route_answers(server_url_token):
    from taxnetlab.server import ROUTES

    url, token = server_url_token

    def call(method, path, body=None):
        req = urllib.request.Request(url + path.lstrip("/"), method=method,
                                     data=json.dumps(body or {}).encode() if method == "POST" else None,
                                     headers={"Content-Type": "application/json", "X-TaxNetLab-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    _, body = call("POST", "/api/datasets/synthetic", {"seed": 3})
    did = json.loads(body)["dataset_id"]
    _, body = call("POST", "/api/runs", {"engine_id": "demo.link_summary", "dataset_id": did})
    rid = json.loads(body)["record"]["run_id"]
    status, body = call("POST", "/api/jobs", {"engine_id": "demo.link_summary", "dataset_id": did})
    assert status == 202
    jid = json.loads(body)["job_id"]
    entry = {"entry_id": "route-test", "title": "t", "engine_id": "demo.link_summary", "source": "s",
             "comparisons": [{"label": "x", "kind": "value", "output": "jurisdiction_summary", "key": "jurisdiction_id",
                              "row": "FIC_A", "column": "outbound_links", "expected": 1, "statistic": "absolute", "threshold": 100}],
             "decision_rule": {"discrepancies_if_share_at_least": 0.5}}
    assert call("POST", "/api/expectations", {"entry": entry, "frozen_by": "test"})[0] == 200
    from rscore import demo

    release = demo.build(Path(tempfile.mkdtemp()) / "release")
    status, body = call("POST", "/api/suite/import", {"release": str(release), "project_name": "route test"})
    assert status == 200, body
    project = json.loads(body)["path"]
    status, body = call("POST", "/api/suite/bring", {"project": project})
    real = json.loads(body)["dataset_id"]  # real ISO jurisdictions: a completion template exists
    subs = {"FILE.sqlite": urllib.parse.quote(project), "{dataset_id}/completion_template": real + "/completion_template",
            "{tag}": "en-GB", "{dataset_id}": did, "{table}": "ownership", "{run_id}": rid, "{name}": "jurisdiction_summary",
            "{job_id}": jid, "{entry_id}": "route-test", "{engine_id}": "demo.link_summary"}
    for method, path, _ in ROUTES:
        if path == "/api/quit":
            continue
        concrete = path
        for k, v in subs.items():
            concrete = concrete.replace(k, v)
        concrete = re.sub(r"=([a-z_]+)\|[a-z_|]+", r"=\1", concrete)
        status, _ = call(method, concrete, {})
        assert status != 404 or method == "POST" and "no API route" not in _.decode(), (method, concrete, status)
        if method == "GET":
            assert status == 200, (concrete, status)


def test_log_file_written(tmp_path):
    from taxnetlab import logs

    path = logs.setup(tmp_path / "logs")
    logs.LOGGER.info("hello from the test")
    for h in logs.LOGGER.handlers:
        h.flush()
    assert "hello from the test" in path.read_text(encoding="utf-8")


def _tokens(css: str, block_start: str) -> dict:
    i = css.index(block_start)
    block = css[i:css.index("}", i)]
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block))


def _lum(hex_):
    rgb = [int(hex_[k:k + 2], 16) / 255 for k in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("theme", [":root {", ':root[data-theme="dark"] {'])
def test_text_colours_meet_wcag_aa(theme):
    css = (WEB / "app.css").read_text(encoding="utf-8")
    light = _tokens(css, ":root {")
    tok = {**light, **_tokens(css, theme)}
    pairs = [("text", "bg"), ("text", "surface"), ("muted", "bg"), ("muted", "surface"), ("accent-ink", "accent"),
             ("banner-ink", "banner-bg"), ("guide-ink", "guide-bg")]
    low = [(a, b, round(_ratio(tok[a], tok[b]), 2)) for a, b in pairs if _ratio(tok[a], tok[b]) < 4.5]
    assert not low, low


def test_installer_script_refers_to_existing_files():
    iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss and "{localappdata}" in iss
    found = re.findall(r'Source: "\.\.\\([^"]+)"', iss)
    assert len(found) == 4, found
    for src in found:
        if src.startswith("dist\\"):
            continue
        assert (ROOT / src.replace("\\", "/")).exists(), src


def test_simplified_chinese_is_complete_and_consistent():
    from taxnetlab import i18n
    from taxnetlab.api import Api

    en = i18n.load_locale("en-GB")["strings"]
    zh = i18n.load_locale("zh-Hans")
    assert zh["_meta"]["complete"] and zh["_meta"]["fallback"] == "en-GB"
    assert set(zh["strings"]) == set(en), sorted(set(en) ^ set(zh["strings"]))
    ph = lambda s: sorted(re.findall(r"\{(\w+)\}", s))  # noqa: E731
    assert [k for k in en if ph(en[k]) != ph(zh["strings"][k])] == []
    assert not any("—" in v for v in zh["strings"].values())  # house style: no em dashes
    g = Api.guide("zh-Hans")
    assert g["user_guide"].startswith("# 用户指南") and g["methods"].startswith("# 方法说明")
    e = Api.guide("en-GB")
    for name in ("user_guide", "methods"):
        heads = lambda t: len(re.findall(r"^## ", t, flags=re.M))  # noqa: E731
        assert heads(g[name]) == heads(e[name]), f"{name}: the translation has a different number of sections"
    assert Api.guide("xx-NONE")["user_guide"].startswith("# User guide")
    assert Api.guide("../etc")["user_guide"].startswith("# User guide")
