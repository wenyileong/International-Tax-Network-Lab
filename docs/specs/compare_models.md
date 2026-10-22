# Specification: model comparison and the agreement rule

**Engine:** `compare.models` (original-model track; it compares methods and adds none of its own).
**Specification version:** 0.1 (22 October 2026). **Plan reference:** v2.4, s 8 (model comparison), s 6.3 (agreement rule; explicit outcome states; "unranked"), s 3.2 (robustness shares).
**Code:** `src/taxnetlab/engines/compare.py`.

## 1. Purpose

To show, jurisdiction by jurisdiction, how the published methods describe the same network, without merging them: each method's measures keep their own names, definitions and units; rankings are declared only where every reading of an ambiguous source agrees; and classifications carry the share of readings under which they hold.

## 2. Readings

A *reading* is one of the documented alternative interpretations of a source (the open interpretations in each specification). Other parameters stay at their defaults.

| Engine | Readings | Interpretations |
|---|---|---|
| `vtrl2018.tax_routing` | 4 | I2 world-average CIT (unweighted, GDP-weighted) × I8 pair weights (GDP product, equal) |
| `gb2017.conduits_sinks` | 4 | I1 missing shareholders (normalised, as reported) × I5 conduit denominator (subset total, all G3) |
| `ph.vietoris_rips` | 1 | defaults (its choices are analytical, not readings of a source) |

The first reading listed is each engine's default. Each run of an engine is made through the declared-input mechanism (plan A33) and listed in the `engines` output with its parameters, status and output hash. An engine that cannot run on the dataset is `unranked`, with the reason, and the count is reported; its measures are omitted, never set to zero.

## 3. Measures (namespaced; definitions in each engine's specification)

`vtrl2018.btwns`, `vtrl2018.occur`, `vtrl2018.shop_as_host` (mean treaty-shopping gain over homes, derived here from `pairs.shop`), `gb2017.sink_centrality`, `gb2017.conduit_in`, `gb2017.conduit_out`, `ph.influence_h1`.

## 4. Ranks and the agreement rule

For each measure and reading, jurisdictions with a defined value are ranked in descending order of value; equal values (after rounding to 12 decimal places) share the lower rank (competition ranking: 1, 2, 2, 4); undefined values are unranked. For each jurisdiction and measure: the rank is **agreed** only if every reading ranks it and all give the same rank; otherwise the cell is a tie, reported with the minimum and maximum rank and the number of readings that ranked it.

## 5. Robustness shares

For the classifications of `gb2017.conduits_sinks` (sink-OFC, conduit-OFC): the number and share of readings under which each jurisdiction is classified; a classification is *robust* when the share is 1.

## 6. Rank correlations

Between every pair of measures, on each measure's default reading, over jurisdictions where both are defined: Spearman's rho (Pearson correlation of average ranks) and Kendall's tau-b (corrected for ties). Undefined (empty) for fewer than three jurisdictions or a constant measure.

## 7. Limits

No combined score is computed (plan s 8). The comparison's status can be no higher than the lowest status of the engines it compares, reported in the summary. Correlations describe agreement between measures on this dataset; they are not tests of either method.

## 8. Tests

Competition ranks; Spearman and Kendall by hand and against SciPy (optional); agreement consistent with the per-reading ranks; readings that do not affect a measure agree; robustness shares; an engine that cannot run is unranked and reported; no combined score column; replay after clearing the upstream cache.
