# Build 0.4 Status Report

**Project:** International Tax Network Lab
**Release:** 0.4.0 (project plan v2.3, s 10.3)
**Date:** 22 October 2026
**Status:** conduits and sinks engine (Garcia-Bernardo and others) at `implemented` with every test passing; IP gate research completed with the decision left to the author; Plain English and Technical reading modes delivered.

## 1. Phase 3 outputs

* **Conduits and sinks:** specification `docs/specs/gb2017_conduits_sinks.md` v0.1 (draft) from the open-access article (Scientific Reports 7, 6246). Chain construction, value weighting, aggregation, thresholds and benchmarks are stated in the source. Equations 1 to 5 were garbled in extraction: the GDP normalisation, the conduit denominators and the entropy definitions are reconstructions (I4 to I6), with the alternative conduit denominator available as a parameter. Six open questions are listed for the author.
* **Patent (IP gate):** `docs/IP_GATE_US10417262.md`. 23 claims; independent claims 1, 12 and 23 recite lens, metric and resolution selection, mapping by matrix-vector multiplication, a cover, clustering and a node-and-edge visualisation. A baseline Mapper with a PCA or centrality lens appears to correspond element by element, subject to claim construction, so the assumption that it lies outside the patent is not safe. The maintenance-fee record decides the planning horizon: the 7.5-year fee falls due on 17 March 2027, and non-payment would end the patent on 17 September 2027. Options (a) to (e) are set out; the decision is the author's. The TDA engine stays at `interface` and out of the executable.

## 2. Pre-build logical evaluation (plan s 10.1)

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | The source's chain value needs the owned firm's revenue, which the data model did not hold. | Serious | New `entity_financials` table (generation 2: existing dataset ids unchanged), with consolidation status and checks. |
| 2 | The conduit denominators could not be read from the source; choosing one silently would pass an interpretation off as the method. | Serious | Default reconstruction plus the alternative as a recorded parameter; both documented (I5) and tested by hand. |
| 3 | Without any sink, conduit centrality has no denominator; returning 0 would look like a finding. | Serious | Reported as empty (null), with a warning (I9); tested. |
| 4 | Firm-level path enumeration can grow quickly in dense ownership networks. | Moderate | Reported chain budget (I11); 1,600 entities compute in about 30 ms; budget behaviour tested. |
| 5 | Parallel relations (share classes) between the same pair and missing shareholders. | Moderate | Fractions summed per holder, then normalised for missing shareholders by default (I1); both tested by hand. |
| 6 | Reading modes must not double the translation burden or break the language infrastructure. | Moderate | Mode variants are optional `.plain` and `.tech` keys falling back to the base key; tests require both variants for every chart guide and forbid orphan variants. |
| 7 | Synthetic worlds had no sink-like structure, so the new page would show nothing to explore. | Minor | The generator places some group parents in a small fictional jurisdiction. Synthetic datasets for a given seed differ from 0.3 (stored datasets are unaffected). |
| 8 | Key naming collision: `mode.plain` read as the plain variant of `mode` (found in testing). | Minor | Renamed to `mode.option_plain` and `mode.option_technical`. |
| 9 | Log-scale scatter could not show undefined or zero centralities, and pinned labels overlapped (found in testing). | Minor | Values at or below 0.01 pinned to the floor with labels dropped and explained in the chart guide. |

## 3. What 0.4 adds

* **Engine `gb2017.conduits_sinks`** (reproduction track, `implemented`): firm-level chains with multiplicative ownership, country chains, sink centrality, inward and outward conduit centralities, entropies, classification; outputs by jurisdiction, country chains and summary.
* **Conduits and sinks page:** live sliders for the ownership threshold (log scale), sink and conduit thresholds, missing-shareholder normalisation and the conduit denominator; a conduit map (outward against inward centrality, log axes, coloured by sink centrality, sized by GDP, with the conduit zone shaded); sink-centrality bars with the threshold; a Sankey diagram of value through three-country chains; full table; "Save as run".
* **Reading modes:** a header switch between Plain English (default) and Technical. Navigation labels, titles and parameter labels change by mode; every chart has guidance, open in Plain English and folded away (as a technical note) in Technical mode. The choice is remembered.

## 4. Tests and verification

* `pytest`: 100 tests. New for this engine: hand-calculated country chains, sink centralities, conduit centralities and entropy; the alternative denominator; the accounting identity (GDP-share-weighted sink centralities sum to zero; value in equals value out); missing-shareholder normalisation; the ownership threshold under both weightings; cycles; parallel relations; metamorphic scaling of revenue and GDP; validation of missing revenue, missing GDP and consolidated figures; the chain budget; property tests on random worlds; run records and replay. Language tests now require both reading-mode variants of every chart guide.
* Self-test extended to the conduits and sinks preview and its balance identity.
* Browser tests: conduits page in light, dark and phone-width layouts; live threshold changes; saving a run; switching reading modes and its persistence; every page in both modes without script errors.

As with the routing engine, these tests verify the implementation against the specification, not the specification against the source.

## 5. Next steps (release 0.5)

1. Author checks of both draft specifications; promotion of both engines to `verified`.
2. Author's IP gate decision, after checking the maintenance-fee record.
3. Remaining rule layer (eligibility, coding template); model comparison page.
4. Physical Windows smoke test; licence decision; tags `v0.1.0` to `v0.4.0`.
