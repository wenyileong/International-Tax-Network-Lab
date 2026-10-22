"""Promotion gate (plan s 3.1): an engine reaches 'verified' only with a completed verification record, and
the author check pack stays in step with the specifications."""

import datetime as dt
import importlib.util
import re
from pathlib import Path

from taxnetlab.engines import list_engines
from taxnetlab.engines.base import VERIFIED_OR_ABOVE

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "docs" / "verification" / "records"


def _field(text, name):
    m = re.search(rf"^\*\*{re.escape(name)}:\*\*[ \t]*(.*)$", text, re.M)
    return (m.group(1).strip() if m else "")


def test_verified_engines_have_completed_records():
    for spec in list_engines():
        if spec.track == "demonstration":
            continue
        rec = RECORDS / f"{spec.engine_id}.md"
        if spec.status in VERIFIED_OR_ABOVE:
            assert rec.exists(), f"{spec.engine_id} is {spec.status} without a verification record"
            text = rec.read_text(encoding="utf-8")
            assert _field(text, "Checked by"), spec.engine_id
            dt.date.fromisoformat(_field(text, "Date (YYYY-MM-DD)"))
            assert _field(text, "Source versions consulted"), spec.engine_id
            assert _field(text, "Outcome (confirmed, corrected or not yet checked)") in ("confirmed", "corrected")
        elif spec.status == "implemented":
            assert rec.exists(), f"{spec.engine_id}: record template missing; run scripts/make_check_pack.py"


def test_check_pack_matches_specifications():
    path = ROOT / "scripts" / "make_check_pack.py"
    spec = importlib.util.spec_from_file_location("make_check_pack", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert (ROOT / "docs" / "verification" / "AUTHOR_CHECK_PACK.md").read_text(encoding="utf-8") == mod.build()
