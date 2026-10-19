"""The three published-method engines, at ``interface`` status.

Each raises :class:`SpecificationNotValidatedError` until its primary-source specification has been
transcribed and verified (plan v2.1, s 3 and s 9). They are registered so that the interface can show
their status, boundary and next step.
"""

from __future__ import annotations

from taxnetlab.engines.base import REPRODUCTION, Engine, EngineSpec


class ConduitsSinksEngine(Engine):
    spec = EngineSpec(
        engine_id="gb2017.conduits_sinks",
        display_name="Conduits and sinks (Garcia-Bernardo and others, 2017)",
        track=REPRODUCTION, variant="reproduction", version="0.0.0", status="interface",
        spec_ref="not yet specified (plan s 9.1)",
        purpose="Characterise jurisdictions as destinations or intermediaries in cross-border ownership chains.",
        boundary="Generic betweenness centrality is not this measure. Consumes the value-flow view.",
        next_step="Archive the paper; transcribe chain construction, value allocation, measures and thresholds.",
        input_schema=("entities", "ownership", "jurisdiction_attributes"),
    )


class TaxRoutingEngine(Engine):
    spec = EngineSpec(
        engine_id="vtrl2018.tax_routing",
        display_name="Optimal tax routing (van 't Riet and Lejour, 2018)",
        track=REPRODUCTION, variant="reproduction", version="0.0.0", status="interface",
        spec_ref="not yet specified (plan s 9.2)",
        purpose="Routes for repatriated dividends that minimise tax under the paper's assumptions.",
        boundary="Generic shortest paths are not this method; separability of the tax objective must be established first.",
        next_step="Transcribe tax formulas, relief methods and route optimisation; build the directional relief layer.",
        input_schema=("jurisdictions", "tax rules (Phase 5)"),
    )


class ScalableTdaEngine(Engine):
    spec = EngineSpec(
        engine_id="us10417262.tda",
        display_name="Scalable topological data analysis (US 10,417,262 B2)",
        track=REPRODUCTION, variant="reproduction", version="0.0.0", status="interface",
        spec_ref="not yet specified (plan s 9.3)",
        purpose="Topological structure of a declared feature matrix and its stability.",
        boundary="Blocked by the IP gate: no TDA code is distributed until the claims are assessed.",
        next_step="Obtain the granted claims and file history; complete the IP gate.",
        input_schema=("feature matrix (Phase 6)",),
    )
