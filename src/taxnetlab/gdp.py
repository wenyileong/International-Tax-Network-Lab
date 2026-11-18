"""GDP for a period: one rule for every engine.

The value recorded for the period itself; otherwise the latest value recorded for an earlier period. A value
for a later period is never used, because it would let information from after the period shape the result.
Before release 1.0.0rc3 the routing and conduit engines fell back to the latest value of any period, while the
topology features used this rule, so the same dataset could be normalised by different GDP figures on
different pages.
"""

from __future__ import annotations

from taxnetlab.datasets import Dataset


def gdp_with_periods(dataset: Dataset, period: str | None) -> dict[str, tuple[float, str]]:
    """Jurisdiction -> (GDP, period it was recorded for). Periods compare as text (for example '2025')."""
    best: dict[str, tuple[float, str]] = {}
    for a in dataset.tables["jurisdiction_attributes"]:
        if str(a["attribute"]).lower() != "gdp" or a["value"] is None:
            continue
        per = a["period"]
        if period is not None and per > period:
            continue
        cur = best.get(a["jurisdiction_id"])
        if cur is None or per > cur[1]:
            best[a["jurisdiction_id"]] = (a["value"], per)
    return best


def gdp_for(dataset: Dataset, period: str | None) -> dict[str, float]:
    return {j: v for j, (v, _) in gdp_with_periods(dataset, period).items()}


def substitution_warning(dataset: Dataset, period: str | None, used: set[str] | list[str]) -> str | None:
    """A warning naming the jurisdictions whose GDP is taken from an earlier period, or None."""
    older = sorted(f"{j} ({p})" for j, (_, p) in gdp_with_periods(dataset, period).items() if j in set(used) and p != period)
    if not older:
        return None
    return (f"GDP for period {period} is not recorded for {len(older)} jurisdiction(s); the latest earlier value is "
            f"used: {', '.join(older[:15])}" + (" ..." if len(older) > 15 else ""))
