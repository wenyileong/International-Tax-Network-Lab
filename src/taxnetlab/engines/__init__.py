"""Engine registry. Status is held here and travels with every result (plan v2.1, s 3)."""

from __future__ import annotations

from taxnetlab.engines.base import Engine, EngineResult, EngineSpec, SpecificationNotValidatedError
from taxnetlab.engines.demo import LinkSummaryEngine
from taxnetlab.engines.placeholders import ConduitsSinksEngine, ScalableTdaEngine, TaxRoutingEngine

_ENGINES: dict[str, Engine] = {}


def register(engine: Engine) -> None:
    eid = engine.spec.engine_id
    if eid in _ENGINES:
        raise ValueError(f"engine {eid} already registered")
    _ENGINES[eid] = engine


for _engine in (LinkSummaryEngine(), ConduitsSinksEngine(), TaxRoutingEngine(), ScalableTdaEngine()):
    register(_engine)


def get_engine(engine_id: str) -> Engine:
    try:
        return _ENGINES[engine_id]
    except KeyError:
        raise KeyError(f"unknown engine '{engine_id}'") from None


def list_engines() -> list[EngineSpec]:
    return [e.spec for e in _ENGINES.values()]


__all__ = ["Engine", "EngineResult", "EngineSpec", "SpecificationNotValidatedError", "get_engine", "list_engines",
           "register"]
