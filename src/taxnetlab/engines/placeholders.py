"""Published-method engines still at ``interface`` status (tax routing: ``vtrl2018.py``; conduits and sinks:
``gb2017.py``).

Each raises :class:`SpecificationNotValidatedError` until its primary-source specification has been
transcribed and verified (plan v2.1, s 3 and s 9). They are registered so that the interface can show
their status, boundary and next step.
"""

from __future__ import annotations

from taxnetlab.engines.base import ORIGINAL, REPRODUCTION, Engine, EngineSpec


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


class IncomeTypesRoutingEngine(Engine):
    """Scaffold (plan docs/PLAN_1_0_RC3_SCAFFOLD.md, F6)."""

    spec = EngineSpec(
        engine_id="vtrl2018.income_types",
        display_name="Tax routes for interest and royalties (extension of van 't Riet and Lejour)",
        track=ORIGINAL, variant="extension", version="0.0.0", status="interface",
        spec_ref="not yet specified (docs/PLAN_1_0_RC3_SCAFFOLD.md, F6)",
        purpose="Cheapest routes for interest and royalty payments, with withholding, treaty rates and relief per "
                "income type, alongside the dividend routes of vtrl2018.tax_routing.",
        boundary="Not runnable: needs a written specification and tax tables for interest and royalties.",
        next_step="Write the specification (income-type tables, relief rules, how the routes combine with dividends).",
        input_schema=("tax_domestic", "tax_treaty_interest (proposed)", "tax_treaty_royalties (proposed)"),
    )


class OwnershipRobustnessEngine(Engine):
    """Scaffold (plan docs/PLAN_1_0_RC3_SCAFFOLD.md, F7)."""

    spec = EngineSpec(
        engine_id="robustness.ownership",
        display_name="Robustness to missing ownership data",
        track=ORIGINAL, variant="perturbation", version="0.0.0", status="interface",
        spec_ref="not yet specified (docs/PLAN_1_0_RC3_SCAFFOLD.md, F7)",
        purpose="Reruns a method with relations thinned or stakes perturbed under a recorded seed, and reports how "
                "often each finding holds.",
        boundary="Not runnable: the perturbation scheme (what is thinned, by how much, how draws are summarised) "
                 "needs a written specification.",
        next_step="Write the specification; then implement on the sensitivity sweep's draw machinery.",
        input_schema=("as the perturbed engine",),
    )
