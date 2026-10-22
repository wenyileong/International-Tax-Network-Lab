"""Tri-state eligibility for treaty benefits (plan v2.4, s 5.2; specification docs/specs/eligibility.md).

Each treaty rate (payer, recipient, period) may carry conditions in ``tax_treaty_conditions``. Mechanical
conditions are evaluated against scenario facts (holding fraction, holding period, the recipient's corporate
income tax rate). Judgement-based or unmodelled conditions (beneficial ownership, the principal purpose
test, limitation on benefits) are ``indeterminate`` unless the run states an assumption for them. The
software never resolves a judgement-based condition by default.

Result per treaty: ``eligible`` (every condition met), ``ineligible`` (a condition fails) or
``indeterminate`` (none fails and at least one is unresolved). A treaty without conditions is eligible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taxnetlab.schema import ASSUMPTION_CONDITIONS

ELIGIBLE, INELIGIBLE, INDETERMINATE = "eligible", "ineligible", "indeterminate"
ASSUMPTION_VALUES = ("unresolved", "met", "not_met")
MODES = ("assume_eligible", "strict", "contingent")


@dataclass(frozen=True)
class Facts:
    """Scenario facts and assumptions recorded with the run."""
    holding_fraction: float = 1.0
    holding_days: int = 365
    assumptions: dict[str, str] = field(default_factory=dict)  # condition -> unresolved | met | not_met

    def assumption(self, condition: str) -> str:
        return self.assumptions.get(condition, "unresolved")


@dataclass
class Outcome:
    status: str
    failed: list[str] = field(default_factory=list)       # conditions not met
    unresolved: list[str] = field(default_factory=list)   # conditions needing an assumption
    unverified: int = 0


def evaluate(conditions: list[dict[str, Any]], facts: Facts, recipient_cit: float) -> Outcome:
    out = Outcome(ELIGIBLE)
    for c in sorted(conditions, key=lambda r: r["condition"]):
        kind, thr = c["condition"], c.get("threshold")
        if not c["verified"] and c["rule_status"] != "synthetic_assumption":
            out.unverified += 1
        if kind == "min_holding":
            ok = facts.holding_fraction >= thr
        elif kind == "min_holding_days":
            ok = facts.holding_days >= thr
        elif kind == "subject_to_tax":
            ok = recipient_cit > (thr or 0.0)
        elif kind in ASSUMPTION_CONDITIONS:
            a = facts.assumption(kind)
            if a == "unresolved":
                out.unresolved.append(kind)
                continue
            ok = a == "met"
        else:  # pragma: no cover - schema choices prevent this
            raise ValueError(f"unknown condition {kind}")
        if not ok:
            out.failed.append(kind)
    if out.failed:
        out.status = INELIGIBLE
    elif out.unresolved:
        out.status = INDETERMINATE
    return out


def evaluate_treaties(dataset, period: str, facts: Facts, cit: dict[str, float],
                      treaties: dict[tuple[str, str], float]) -> dict[tuple[str, str], Outcome]:
    """Outcome for every treaty rate in force for the period (after scenario overrides)."""
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in dataset.tables["tax_treaty_conditions"]:
        if row["period"] == period:
            by_pair.setdefault((row["payer_jurisdiction"], row["recipient_jurisdiction"]), []).append(row)
    return {pair: evaluate(by_pair.get(pair, []), facts, cit.get(pair[1], 0.0)) for pair in treaties}
