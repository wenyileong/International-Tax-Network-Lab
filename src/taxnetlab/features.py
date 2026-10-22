"""FeatureMatrix: a declared matrix of observations by features (plan v2.4, s 5.2).

Observation unit: jurisdiction for one period. Every feature has a definition, a unit and a derivation;
features computed from another engine's outputs record that engine's identifier, version and resolved
parameters (a declared derived dataset, A33). No value is imputed: an observation lacking a selected
feature is excluded and listed with the features it lacks.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from taxnetlab.canonical import canonical_json, sha256_text
from taxnetlab.datasets import Dataset
from taxnetlab.views import _active


@dataclass(frozen=True)
class FeatureDef:
    feature_id: str
    label: str
    unit: str
    derivation: str
    engine: str | None = None  # engine whose outputs the feature uses


CATALOGUE: dict[str, FeatureDef] = {f.feature_id: f for f in (
    FeatureDef("cit", "Corporate income tax rate", "share", "tax_domestic.cit_rate for the period"),
    FeatureDef("dividend_wht", "General dividend withholding rate", "share",
               "tax_domestic.dividend_wht_rate for the period"),
    FeatureDef("mean_applicable_wht", "Mean withholding on dividends paid to each other jurisdiction", "share",
               "mean over every other jurisdiction with tax rules of the treaty rate where one exists, otherwise "
               "the general rate"),
    FeatureDef("treaty_count", "Treaty partners (as payer)", "count",
               "rows of tax_treaty_dividends with the jurisdiction as payer, for the period"),
    FeatureDef("log_gdp", "GDP (natural logarithm)", "ln(currency units)",
               "ln of jurisdiction_attributes gdp (the period, or the latest earlier period)"),
    FeatureDef("outward_links", "Cross-border holdings by its entities", "count",
               "current equity relations held by entities in the jurisdiction in entities elsewhere"),
    FeatureDef("inward_links", "Cross-border holdings in its entities", "count",
               "current equity relations held in entities in the jurisdiction by entities elsewhere"),
    FeatureDef("vtrl_btwns", "Conduit betweenness on cheapest tax routes", "percent",
               "vtrl2018.tax_routing centrality.btwns, default parameters", "vtrl2018.tax_routing"),
    FeatureDef("vtrl_mean_shop", "Mean treaty-shopping gain as host", "share",
               "vtrl2018.tax_routing mean of pairs.shop over homes, default parameters", "vtrl2018.tax_routing"),
    FeatureDef("gb_sink_centrality", "Sink centrality", "ratio",
               "gb2017.conduits_sinks jurisdictions.sink_centrality, default parameters", "gb2017.conduits_sinks"),
    FeatureDef("gb_conduit_out", "Conduit centrality towards sinks", "ratio",
               "gb2017.conduits_sinks jurisdictions.conduit_out, default parameters (undefined without a sink)",
               "gb2017.conduits_sinks"),
)}

DEFAULT_FEATURES = "cit,dividend_wht,mean_applicable_wht,treaty_count,log_gdp,outward_links,inward_links"
SCALINGS = ("zscore", "minmax", "none")


@dataclass
class FeatureMatrix:
    unit: str
    period: str
    features: list[FeatureDef]
    raw: dict[str, dict[str, float | None]]          # observation -> feature -> value (None if missing)
    scaling: str
    scaled: dict[str, list[float]] = field(default_factory=dict)  # included observation -> scaled vector
    excluded: dict[str, list[str]] = field(default_factory=dict)  # observation -> missing features
    constant: list[str] = field(default_factory=list)            # features with no variation
    provenance: list[dict[str, Any]] = field(default_factory=list)

    @property
    def observations(self) -> list[str]:
        return sorted(self.scaled)

    @property
    def matrix_sha256(self) -> str:
        body = {"unit": self.unit, "period": self.period, "scaling": self.scaling,
                "features": [f.feature_id for f in self.features], "provenance": self.provenance,
                "rows": {o: [self.raw[o][f.feature_id] for f in self.features] for o in sorted(self.raw)}}
        return sha256_text(canonical_json(body))


def parse_features(text: str | None) -> tuple[list[str], list[str]]:
    """Feature ids in the order given, and any unknown ids."""
    ids = [s.strip() for s in (text or DEFAULT_FEATURES).split(",") if s.strip()]
    seen: list[str] = []
    for i in ids:
        if i not in seen:
            seen.append(i)
    return seen, [i for i in seen if i not in CATALOGUE]


def build(dataset: Dataset, period: str, feature_ids: list[str], scaling: str,
          engine_runner: Callable[[str, dict[str, Any]], tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]]
          ) -> FeatureMatrix:
    """Build the matrix. ``engine_runner(engine_id, params)`` returns (outputs, provenance entry)."""
    defs = [CATALOGUE[f] for f in feature_ids]
    observations = sorted(j["jurisdiction_id"] for j in dataset.tables["jurisdictions"])
    columns: dict[str, dict[str, float | None]] = {}
    provenance: list[dict[str, Any]] = []
    cache: dict[str, dict[str, list[dict[str, Any]]]] = {}

    def outputs(engine_id: str) -> dict[str, list[dict[str, Any]]]:
        if engine_id not in cache:
            out, prov = engine_runner(engine_id, {"period": period})
            cache[engine_id] = out
            provenance.append(prov)
        return cache[engine_id]

    dom = {r["jurisdiction_id"]: r for r in dataset.tables["tax_domestic"] if r["period"] == period}
    treaty = {(r["payer_jurisdiction"], r["recipient_jurisdiction"]): r["dividend_wht_rate"]
              for r in dataset.tables["tax_treaty_dividends"] if r["period"] == period}
    for f in defs:
        col: dict[str, float | None] = {}
        fid = f.feature_id
        if fid == "cit":
            col = {j: dom[j]["cit_rate"] for j in dom}
        elif fid == "dividend_wht":
            col = {j: dom[j]["dividend_wht_rate"] for j in dom}
        elif fid == "mean_applicable_wht":
            for j in dom:
                others = [k for k in dom if k != j]
                if others:
                    col[j] = math.fsum(treaty.get((j, k), dom[j]["dividend_wht_rate"]) for k in others) / len(others)
        elif fid == "treaty_count":
            counts: dict[str, float] = defaultdict(float)
            for (payer, _), _r in treaty.items():
                counts[payer] += 1
            col = {j: counts.get(j, 0.0) for j in dom}
        elif fid == "log_gdp":
            for j, v in _gdp(dataset, period).items():
                if v > 0:
                    col[j] = math.log(v)
        elif fid in ("outward_links", "inward_links"):
            where = {e["entity_id"]: e["jurisdiction_id"] for e in dataset.tables["entities"]}
            counts = {j: 0.0 for j in observations}
            for o in dataset.tables["ownership"]:
                if o["relation_type"] != "equity" or not _active(o, None):
                    continue
                a, b = where.get(o["holder_id"]), where.get(o["held_id"])
                if a is None or b is None or a == b:
                    continue
                counts[a if fid == "outward_links" else b] += 1
            col = counts
        elif fid == "vtrl_btwns":
            col = {r["jurisdiction_id"]: r["btwns"] for r in outputs("vtrl2018.tax_routing")["centrality"]}
        elif fid == "vtrl_mean_shop":
            acc: dict[str, list[float]] = defaultdict(list)
            for r in outputs("vtrl2018.tax_routing")["pairs"]:
                acc[r["host"]].append(r["shop"])
            col = {j: math.fsum(v) / len(v) for j, v in acc.items() if v}
        elif fid == "gb_sink_centrality":
            col = {r["jurisdiction_id"]: r["sink_centrality"] for r in outputs("gb2017.conduits_sinks")["jurisdictions"]}
        elif fid == "gb_conduit_out":
            col = {r["jurisdiction_id"]: r["conduit_out"] for r in outputs("gb2017.conduits_sinks")["jurisdictions"]}
        columns[fid] = {j: (None if col.get(j) is None else float(col[j])) for j in observations}

    raw = {j: {f.feature_id: columns[f.feature_id][j] for f in defs} for j in observations}
    fm = FeatureMatrix("jurisdiction", period, defs, raw, scaling, provenance=provenance)
    included = []
    for j in observations:
        missing = [f.feature_id for f in defs if raw[j][f.feature_id] is None]
        if missing:
            fm.excluded[j] = missing
        else:
            included.append(j)
    scaled_cols: dict[str, dict[str, float]] = {}
    for f in defs:
        vals = [raw[j][f.feature_id] for j in included]
        lo, hi = (min(vals), max(vals)) if vals else (0.0, 0.0)
        if vals and hi == lo and scaling != "none":
            fm.constant.append(f.feature_id)
        if scaling == "zscore" and vals:
            mean = math.fsum(vals) / len(vals)
            sd = math.sqrt(math.fsum((v - mean) ** 2 for v in vals) / len(vals))
            scaled_cols[f.feature_id] = {j: ((raw[j][f.feature_id] - mean) / sd if sd > 0 else 0.0) for j in included}
        elif scaling == "minmax" and vals:
            scaled_cols[f.feature_id] = {j: ((raw[j][f.feature_id] - lo) / (hi - lo) if hi > lo else 0.0)
                                         for j in included}
        else:
            scaled_cols[f.feature_id] = {j: raw[j][f.feature_id] for j in included}
    fm.scaled = {j: [scaled_cols[f.feature_id][j] for f in defs] for j in included}
    return fm


def _gdp(dataset: Dataset, period: str) -> dict[str, float]:
    best: dict[str, tuple[str, float]] = {}
    for a in dataset.tables["jurisdiction_attributes"]:
        if a["attribute"].lower() != "gdp" or a["period"] > period:
            continue
        cur = best.get(a["jurisdiction_id"])
        if cur is None or a["period"] > cur[0]:
            best[a["jurisdiction_id"]] = (a["period"], a["value"])
    return {j: v for j, (_, v) in best.items()}


def distance(u: list[float], v: list[float], metric: str) -> float:
    if metric == "euclidean":
        return math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(u, v)))
    if metric == "manhattan":
        return math.fsum(abs(a - b) for a, b in zip(u, v))
    if metric == "chebyshev":
        return max((abs(a - b) for a, b in zip(u, v)), default=0.0)
    raise ValueError(f"unknown metric {metric}")


METRICS = ("euclidean", "manhattan", "chebyshev")
