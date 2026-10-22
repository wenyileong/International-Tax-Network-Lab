"""Published-method engines still at ``interface`` status (tax routing: ``vtrl2018.py``; conduits and sinks:
``gb2017.py``).

Each raises :class:`SpecificationNotValidatedError` until its primary-source specification has been
transcribed and verified (plan v2.1, s 3 and s 9). They are registered so that the interface can show
their status, boundary and next step.
"""

from __future__ import annotations

from taxnetlab.engines.base import REPRODUCTION, Engine, EngineSpec


class ScalableTdaEngine(Engine):
    spec = EngineSpec(
        engine_id="us10417262.tda",
        display_name="Scalable topological data analysis (US 10,417,262 B2)",
        track=REPRODUCTION, variant="reproduction", version="0.0.0", status="interface",
        spec_ref="not yet specified (plan s 9.3)",
        purpose="Topological structure of a declared feature matrix and its stability.",
        boundary="Blocked by the IP gate (docs/IP_GATE_US10417262.md): no TDA code is distributed until the author "
                 "records a decision.",
        next_step="Author's decision on the IP gate options; check the patent's maintenance-fee status.",
        input_schema=("feature matrix (Phase 6)",),
    )
