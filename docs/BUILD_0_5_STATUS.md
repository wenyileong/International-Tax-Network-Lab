# Build 0.5 Status Report

**Project:** International Tax Network Lab
**Release:** 0.5.0 (project plan v2.4, s 10.3)
**Date:** 22 October 2026
**Status:** alternative topological methods recorded in the plan and the IP note, with the patent-method engine kept at `interface` behind its gate; persistent homology engine (`ph.vietoris_rips`) at `implemented` with every test passing; Topology page with live exploration.

## 1. Plan and IP note

* **Plan v2.4** (`docs/PROJECT_PLAN_v2_4.md`): new s 9.4 compares persistent homology, network-native persistent homology, Ball Mapper, exact Reeb graphs and contour trees, UMAP with HDBSCAN and a Mapper restricted to lenses not computed by matrix-vector multiplication, element by element against claim 1, with other IP, licences and a decision for each. Conditions for the alternatives (design constraints in the specification, display-only projections, status track, steps before public distribution). Section 10.3 revised: 0.5 is the alternative method; author checks, the IP decision, the rest of the rule layer and the model comparison page move to 0.6. Issues A33 to A35 added to Appendix A.
* **IP note** (`docs/IP_GATE_US10417262.md`): option (f) and a new s 5A with the element-by-element table and three open steps (landscape search including the landmark patents; reading the prosecution history; the author's confirmation). The patent-method engine `us10417262.tda` is unchanged: registered, at `interface`, blocked in the interface, the API and the CLI, and out of the executable.

## 2. Pre-build logical evaluation (plan s 10.1)

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | The plan's FeatureMatrix had to cite an earlier run record when a feature came from another engine, so a live preview could never use one (A33). | Serious | In-run derivation: the upstream engine's identifier, version, status, resolved parameters and output hash are recorded; outputs are deterministic, so replay holds. Tested. |
| 2 | A display projection could be read as a lens, reintroducing a claimed element. | Serious | Constraint D4: the projection is written for drawing only; a test replaces it and checks that every other output is unchanged. |
| 3 | No numerical library is bundled (dependency policy), and a naive boundary reduction is slow in pure Python (3.5 s for 100 points). | Serious | Persistent cohomology with clearing (0.5 s for 100 points, 1.8 s for 150); the homology reduction kept as an independent cross-check. |
| 4 | An essential class has an infinite death, which JSON (strict, `allow_nan=False`) and the canonical CSV cannot carry as a number. | Serious | Death stored as empty with `essential = true`; charts draw essential classes at the top of the diagram. |
| 5 | Unbounded triangle counts on large inputs. | Moderate | Triangle budget: the filtration is truncated just below the first scale at which the budget would be exceeded, so pairs are exact up to the effective scale; reported. Tested. |
| 6 | Leave-one-out influence repeats the computation once per observation. | Moderate | Bounded by `influence_limit` (default 40) and reported when skipped; the bottleneck distance uses the Mendelsohn–Dulmage reduction to two one-sided matchings. |
| 7 | Missing feature values (for example conduit centrality when there is no sink). | Moderate | Observations are excluded and listed, never imputed; a feature without variation is scaled to 0 and named. |
| 8 | Upstream engines would be recomputed on every slider movement of the routing-cost input. | Minor | Small cache keyed on dataset id, engine version and parameters (content-addressed, so safe). |
| 9 | The starter dataset has six jurisdictions, too few for loops. | Minor | The page offers to generate a 20-jurisdiction synthetic world. |
| 10 | Changing the input kept a view scale from a different distance scale (found in browser testing). | Minor | The view scale resets when the inputs that define distances change. |
| 11 | The projection caption overlapped the watermark at phone width (found in browser testing). | Minor | Caption moved under the axis. |

## 3. What 0.5 adds

* **Engine `ph.vietoris_rips`** (reproduction track, `implemented`; spec `docs/specs/ph_vietoris_rips.md` v0.1): Vietoris–Rips persistence in dimensions 0 and 1 from a declared feature matrix (eleven features, including features derived from the two method engines) or from the symmetrised cost of the cheapest tax route; representative cycles; Betti curves; leave-one-out influence by bottleneck distance; outputs `points`, `features`, `distances`, `diagram`, `betti`, `influence`, `summary`.
* **FeatureMatrix** (`src/taxnetlab/features.py`): declared features with units and derivations, provenance, a content hash and the no-imputation rule.
* **Topology page:** a scale slider that changes the view without recomputing (Rips graph and clusters at that scale on a display projection, with its stress); persistence diagram with the alive region shaded; barcode; Betti curves; influence chart; click a loop to trace it on the map; feature, scaling, metric and input controls that recompute live; "Save as run"; guidance in both reading modes.

## 4. Tests and verification

* `pytest`: 178 tests on Python 3.12 (169 plus 9 optional differential tests skipped where Ripser and GUDHI are not installed, as in CI). New: hand fixtures (square, triangle, hexagon, separated pairs, duplicates); Betti numbers at every critical scale against ranks of boundary matrices over Z/2; cohomology against homology with tied distances; bottleneck distance against brute force; the stability theorem as a property test; differential tests against Ripser 0.6.15 and GUDHI 3.13.0 (run locally, all passing); D4; exclusion without imputation; derived-feature provenance; previews, pinning and replay; the design-constraint checks; the feature list shared by the interface and the engine.
* Self-test extended to the persistent homology preview and a pinned, replayed run.
* Browser tests (Chromium): Topology page in light, dark and phone-width layouts and in both reading modes; generating a world; selecting a loop; moving the scale; switching to routing cost; no script errors.

These tests verify the implementation against the specification and an independent implementation; the specification itself awaits the author's check.

## 5. Next steps (release 0.6)

1. Author checks of the three specifications; promotion to `verified`.
2. IP decision for the patent method; the three steps in IP note s 5A before any public distribution of the executable.
3. Remaining rule layer (eligibility, coding template); model comparison page.
4. Physical Windows smoke test; licence decision; version tags.
