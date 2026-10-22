# Build 0.3 Status Report

**Project:** International Tax Network Lab
**Release:** 0.3.0 (project plan v2.2, s 10.3: tax routing, method first)
**Date:** 22 October 2026
**Status:** the optimal tax routing engine (van 't Riet and Lejour) is at `implemented` with every test passing; promotion to `verified` awaits the author's check of the specification against the source (plan v2.2, s 0.0 item 5). Live exploration is in place for this engine.

## 1. Phase 3 for the routing method

* Source obtained: CPB Discussion Paper 349 (2017), open access. The journal version (2018) 25 International Tax and Public Finance 1321 has not yet been compared.
* Specification `docs/specs/vtrl2018_tax_routing.md` v0.1 (draft): direct and indirect route formulas with page references; the conduit world-average rule (which makes route taxation separable); shortest routes, penalty and the half-percent range; the treaty-shopping and betweenness indicators; 14 interpretive choices (I1 to I14); 7 open questions; benchmarks for later replication; feasibility (Tier B: the source's tax data come from commercial guides).
* The text was obtained by automated PDF extraction, which garbled parts of the credit-relief formulas. The credit-case effective rate is therefore *derived* from the stated tax distance and identity (I1), and is listed as open question 1.

## 2. Pre-build logical evaluation (plan s 10.1)

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | Adding the tax tables would have changed the content hash, and so the id, of every existing dataset, making stored workspaces fail their integrity check on load. | Fatal | Tables introduced after schema generation 1 enter the hash only when they have rows. Existing ids are unchanged (regression test with the 0.2 fixture id). |
| 2 | Live previews compute results that are not run records, contrary to "no result without a run record". | Serious | Plan A29: previews are exploratory, watermarked, not stored, and citable only after "Save as run", which records every scenario override. |
| 3 | The plan expected credit relief to make route taxation path-dependent, which would invalidate a shortest-path search. | Serious | Resolved from the source: the conduit world-average assumption keeps each leg independent of the path. A brute-force differential test confirms the search. |
| 4 | Near-optimal route enumeration grows combinatorially; in a world where every tax is zero, a 26-jurisdiction preview could run for minutes and block the interface. | Serious | Three reported bounds (I14): intermediates (raised to the cheapest route's length), routes per pair, and an overall route budget. The worst case measured fell from minutes to about 4 seconds; the cheapest routes never depend on the bounds (tested). |
| 5 | An automated transcription is not a reviewed specification. | Serious | Plan A32: the engine stays `implemented`; results carry the "unverified method" watermark. |
| 6 | Scenario overrides must be replayable. | Moderate | Overrides are an engine parameter, validated (kinds, jurisdictions, ranges, unknown fields) and recorded in run records; replay tested. |
| 7 | Live controls must not be hard-coded to one method. | Moderate | The preview endpoint and caching are engine-generic; the route explorer is the first page built on them. |
| 8 | Concurrent previews from fast slider movement. | Moderate | Client debounce and sequence numbers discard superseded responses; thread-safe server-side caches keyed by engine version, dataset id and canonical parameters. |
| 9 | The engine's validation resolves an empty period to the latest one; replay must use the resolved value. | Minor | The resolved period is stored in the run's parameters (tested). |
| 10 | Real legal rows that are unverified must be visible in results. | Moderate | Validation warning per row; the engine reports how many unverified rows it used. Synthetic assumptions are exempt. |

## 3. What 0.3 adds

* **Tax rule tables** (schema generation 2): `tax_domestic` (CIT, general dividend withholding, relief method), `tax_treaty_dividends` (directional treaty withholding) and `tax_relief_overrides` (directional relief, plan A23). Integrity rules as for other tables, including the ban on synthetic assumptions about real jurisdictions.
* **Engine `vtrl2018.tax_routing`** (reproduction track, `implemented`): direct and cheapest routes for every ordered pair, leg-by-leg calculation trace, treaty-shopping gain, BTWNS, STRCT, OCCUR and UNWTD centralities, and weighted summary measures comparable with the source's Table 4.
* **Scenario overrides:** CIT, general withholding and relief method of any jurisdiction; treaty rate for any ordered pair (including adding or removing a treaty); relief for a particular partner.
* **Live preview API** (`POST /api/engines/<id>/preview`): runs an engine without storing anything, with caching.
* **Tax routes page:** host and home selectors; sliders for CIT, withholding and treaty rates; relief selectors; model settings; a route map coloured by CIT and sized by GDP, with each leg's tax distance; direct-versus-cheapest decomposition; leg table; treaty-shopping heatmap (click a cell to open that pair); conduit centrality chart; sensitivity sweeps (25-point line charts showing the conduits used); "Save as run".
* Synthetic worlds now include fictional tax rules, with one jurisdiction given conduit-like features so that there are routes to explore.
* Self-test extended to preview, pin and replay a tax routing run.

## 4. Tests and verification

* `pytest`: 86 tests. New for the engine: each relief formula on hand-calculated numbers; a worked indirect route through a conduit using the world-average rule; the half-percent range and betweenness; GDP-scaling invariance; the penalty choosing the direct route when every route is tax-free; scenario overrides, one-sided relief, and add-then-remove restoring the base results; override validation; missing tax data, unknown periods and missing GDP; a **brute-force differential test** (Hypothesis, 30 random worlds) comparing the cheapest route and the near-optimal and strict route counts with enumeration of every simple route; a property test that raising any withholding rate never lowers any route's tax; run records and replay; the route budget; and dataset-id stability for 0.2 workspaces.
* Browser tests: the route explorer in light, dark and phone-width layouts with no script errors; slider changes recompute; treaty toggling; sweeps; heatmap selection; saving a run and opening it on the Runs page.
* Performance: synthetic worlds of 6, 12 and 26 jurisdictions compute in about 2 ms, 20 ms and 1.1 s.

These tests verify the implementation against the specification. They cannot verify the specification against the source; that is the author check in s 5.

## 5. Next steps

1. **Author check** of the specification (open questions 1 to 7) against CPB Discussion Paper 349 and the journal version; if the fixtures still pass, change the engine's status to `verified` (one line in `engines/vtrl2018.py`).
2. Physical Windows smoke test of the CI-built executable.
3. Release 0.4: Phase 3 for Garcia-Bernardo and others and the patent IP gate.
