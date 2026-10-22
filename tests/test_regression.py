"""Approved outputs are reproduced exactly at default parameters (plan s 6.3, "nothing changes")."""

import json

from regression.snapshots import APPROVED, compute


def test_outputs_match_approved_snapshots():
    approved = json.loads(APPROVED.read_text(encoding="utf-8"))
    current = compute()
    diffs = [f"{d}/{e}/{t}" for d in approved for e in approved[d] if e != "dataset_id"
             for t in approved[d][e] if current[d][e].get(t) != approved[d][e][t]]
    assert not diffs, diffs
    assert {d: approved[d]["dataset_id"] for d in approved} == {d: current[d]["dataset_id"] for d in current}
