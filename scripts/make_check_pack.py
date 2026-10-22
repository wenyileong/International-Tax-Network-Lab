"""Build docs/verification/AUTHOR_CHECK_PACK.md from the specifications.

The pack lists every interpretive choice and open question of each draft specification, with blank columns
for the author's outcome, so that nothing is transcribed by hand. Run from the repository root:

    python scripts/make_check_pack.py

A test checks that the committed pack matches what this script produces, so the pack cannot drift from
the specifications.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "verification" / "AUTHOR_CHECK_PACK.md"

SPECS = [
    ("vtrl2018.tax_routing", "docs/specs/vtrl2018_tax_routing.md",
     "CPB Discussion Paper 349 (pp 7 to 10 and 13 to 18) and the journal version, (2018) 25 International Tax and Public Finance 1321"),
    ("gb2017.conduits_sinks", "docs/specs/gb2017_conduits_sinks.md",
     "Garcia-Bernardo, Fichtner, Takes and Heemskerk, (2017) 7 Scientific Reports 6246, Methods, Eqs 1 to 5"),
    ("ph.vietoris_rips", "docs/specs/ph_vietoris_rips.md",
     "the peer-reviewed sources in s 9 of the specification (standard definitions)"),
    ("eligibility (rule layer)", "docs/specs/eligibility.md", "plan s 5.2; the treaty provisions coded in the data"),
    ("compare.models", "docs/specs/compare_models.md", "plan s 6.3 and s 8"),
]

HEADER = """# Author check pack

**Purpose:** the checks that stand between each engine and `verified` status (plan v2.5, s 3.1 and s 13). An engine built on a specification is promoted only after the author has checked the specification against its source and recorded the outcome in `docs/verification/records/<engine>.md` (a test enforces this).
**Generated** by `scripts/make_check_pack.py` from the specifications; do not edit the item lists by hand. Mark the outcome of each item here (or in a copy), then complete the sign-off in the engine's record file.

**How to use.** For each item: read the cited part of the source; mark the outcome as *confirmed*, *corrected* (state the correction) or *open*. A corrected item changes the specification first, then the code, then the fixtures, in that order; the approved-output snapshots (`tests/regression/approved.json`) are regenerated only with the change documented in the changelog.

"""


def items(text: str) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    interp = [(m.group(1), m.group(2).strip()) for m in re.finditer(r"^\| (I\d+|D\d+) \| (.+?) \|", text, re.M)]
    open_q: list[str] = []
    m = re.search(r"^## \d+\. Open questions[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if m:
        open_q = [q.strip() for q in re.findall(r"^\d+\. (.+)$", m.group(1), re.M)]
    sections = re.findall(r"^## (\d+\. .+)$", text, re.M)
    return interp, open_q, sections


def build() -> str:
    parts = [HEADER]
    for engine, path, source in SPECS:
        text = (ROOT / path).read_text(encoding="utf-8")
        version = re.search(r"\*\*Specification version:\*\* ([^\n.]+(?:\.\d+)?)", text)
        interp, open_q, sections = items(text)
        parts.append(f"## {engine}\n\n**Specification:** `{path}`" + (f" (version {version.group(1).strip()})" if version else "")
                     + f"\n**Check against:** {source}.\n")
        if interp:
            parts.append("\n### Interpretations and constraints\n\n| # | Item | Outcome | Note |\n|---|---|---|---|")
            parts.extend(f"| {k} | {v} | | |" for k, v in interp)
        if open_q:
            parts.append("\n### Open questions\n\n| # | Question | Outcome | Note |\n|---|---|---|---|")
            parts.extend(f"| Q{i} | {q} | | |" for i, q in enumerate(open_q, 1))
        parts.append("\n### Sections to read through\n\n" + "\n".join(f"- [ ] {s}" for s in sections) + "\n")
    return "\n".join(parts).rstrip() + "\n"


RECORD = """# Verification record: {engine}

Complete this record when the specification has been checked against its source (see `docs/verification/AUTHOR_CHECK_PACK.md`). The engine's status may be raised to `verified` only when every field below is filled and the outcome is *confirmed* or *corrected* (a test enforces this).

**Specification:** `{path}`
**Checked by:**
**Date (YYYY-MM-DD):**
**Source versions consulted:**
**Outcome (confirmed, corrected or not yet checked):** not yet checked
**Items corrected (with the commit that changed the specification):**
**Items still open:**
"""
RECORD_ENGINES = {"vtrl2018.tax_routing", "gb2017.conduits_sinks", "ph.vietoris_rips", "compare.models"}


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    for engine, path, _ in SPECS:
        if engine in RECORD_ENGINES:
            rec = OUT.parent / "records" / f"{engine}.md"
            if not rec.exists():  # never overwrite a record the author has started
                rec.parent.mkdir(parents=True, exist_ok=True)
                rec.write_text(RECORD.format(engine=engine, path=path), encoding="utf-8")
                print(f"wrote {rec.relative_to(ROOT)}")
    sys.exit(0)
