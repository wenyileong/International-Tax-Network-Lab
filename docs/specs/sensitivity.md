# Specification: sensitivity sweeps and robustness shares

**Engine:** `sensitivity.sweep` (original-model track). **Specification version:** 0.1 (22 October 2026).
**Plan reference:** v2.5, s 3.2 (status `robust`: findings hold across a sensitivity sweep at a stated threshold, with robustness shares and non-converged draws counted), s 6.3 (outcome states), Phase 8.
**Code:** `src/taxnetlab/engines/sensitivity.py`.

## 1. Inputs

* `engine`: the method engine to sweep (`vtrl2018.tax_routing`, `gb2017.conduits_sinks`, `ph.vietoris_rips`).
* `grid`: `name=v1|v2|...; other=a|b`. Every combination is one *draw* (at most 200). Every value must be valid for the swept engine; the period cannot be swept. Other parameters stay at the engine's defaults.
* `measure`: a namespaced measure of that engine, as on the Compare page (`docs/specs/compare_models.md` s 3).
* `top_k` and `robust_share`.

## 2. Computation

For each draw the engine runs through the declared-input mechanism (plan A33). A draw whose engine cannot run, or returns an outcome other than `ok`, is *excluded*: listed with the reason and counted, never treated as zero. In each included draw jurisdictions are ranked by the measure (descending; ties share the lower rank; undefined values unranked).

For each jurisdiction: the number of draws in which it is ranked; minimum, maximum and median rank; the share of included draws in which its rank is at most `top_k` (ties at the boundary are inside the top group); for the conduits and sinks engine, the shares of draws in which it is classified as a sink-OFC and as a conduit-OFC. A top-k membership is **robust** when its share is at least `robust_share`.

## 3. Outputs

`draws` (parameters as JSON, outcome, reason), `values` (value and rank per draw and jurisdiction), `robustness`, `summary`.

## 4. Limits

The grid is exhaustive, not stratified random sampling; with many parameters the author chooses the values. A sweep says how sensitive a method's outputs are to its parameters on this dataset; it does not test the method.

## 5. Tests

Draw count equals the grid size; excluded draws counted; robustness shares computed from the per-draw ranks; a one-value grid gives shares of 0 or 1 equal to the base run; invalid grids refused.
