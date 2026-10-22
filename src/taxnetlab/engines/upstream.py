"""Running one engine inside another (declared derived inputs, plan v2.4, A33).

Outputs are deterministic for a content-addressed dataset, an engine version and parameters, so a small
cache is safe; live previews would otherwise repeat the same upstream computation on every change.
The provenance entry records what was run, so that the dependent result can cite it.
"""

from __future__ import annotations

from typing import Any

from taxnetlab.canonical import canonical_json, sha256_text
from taxnetlab.datasets import Dataset
from taxnetlab.engines.base import OK

CACHE_SIZE = 24
_CACHE: dict[str, Any] = {}


class UpstreamError(Exception):
    """An engine needed as an input could not run; the message says why."""


def run_upstream(dataset: Dataset, engine_id: str, params: dict[str, Any], purpose: str = "this analysis"):
    from taxnetlab.engines import get_engine  # imported here: the registry imports the dependent engines

    engine = get_engine(engine_id)
    key = canonical_json([dataset.dataset_id, engine_id, engine.spec.version, params])
    if key in _CACHE:
        return _CACHE[key]
    resolved, report = engine.resolve_parameters(params)
    if report.ok:
        report.extend(engine.validate(dataset, resolved))
    if not report.ok:
        raise UpstreamError(f"{engine_id} cannot run for {purpose}: " + "; ".join(i.message for i in report.errors))
    result = engine.run(dataset, resolved)
    if result.outcome != OK:
        raise UpstreamError(f"{engine_id} returned '{result.outcome}': " + "; ".join(result.warnings))
    value = (result.outputs, {"engine_id": engine_id, "version": engine.spec.version, "status": engine.spec.status,
                              "parameters": resolved, "outputs_sha256": sha256_text(canonical_json(result.outputs))})
    if len(_CACHE) >= CACHE_SIZE:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = value
    return value
