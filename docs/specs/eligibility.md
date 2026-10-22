# Specification: tri-state eligibility for treaty benefits

**Code:** `src/taxnetlab/eligibility.py`; used by `vtrl2018.tax_routing` (parameters `eligibility`, `holding_fraction`, `holding_days`, `assume_beneficial_ownership`, `assume_ppt`, `assume_lob`).
**Specification version:** 0.1 (22 October 2026). **Plan reference:** v2.4, s 5.2 (rule layer) and s 6.3 ("nothing changes").
**Variant:** extension. The reproduction of van 't Riet and Lejour assumes that every treaty benefit applies (source assumptions A1 to A5); the default mode keeps that assumption, and the approved-output snapshots confirm that its outputs are unchanged.

## 1. Data

Table `tax_treaty_conditions` (schema generation 2: datasets without it keep their identifiers). One row per condition on the treaty rate for a directional pair and period in `tax_treaty_dividends`.

| Condition | Kind | Threshold | Met when |
|---|---|---|---|
| `min_holding` | mechanical | fraction, required | the holding fraction is at least the threshold |
| `min_holding_days` | mechanical | days, required | the holding period is at least the threshold |
| `subject_to_tax` | mechanical | fraction, optional (default 0) | the recipient's corporate income tax rate (after scenario overrides) exceeds the threshold |
| `beneficial_ownership` | judgement | none | only by an explicit assumption |
| `ppt` (principal purpose test, including through the Multilateral Instrument) | judgement | none | only by an explicit assumption |
| `lob` (limitation on benefits) | factual, not modelled | none | only by an explicit assumption |

Every row carries `rule_status`, `verified`, `source_id`, an optional `pinpoint` and a note. Validation: a threshold is required for the two holding conditions; fractions must be below 1; a threshold on an assumption condition is ignored with a warning; a condition for a pair and period without a treaty rate has no effect and is warned about; synthetic rows may not refer to real jurisdictions.

## 2. Scenario facts and assumptions

Facts: `holding_fraction` (default 1, a wholly owned subsidiary) and `holding_days` (default 365). Assumptions for `beneficial_ownership`, `ppt` and `lob`: `unresolved` (default), `met` or `not_met`. The software never resolves a judgement-based condition by default; every fact and assumption is a run parameter and is recorded with the run.

## 3. Evaluation

For each treaty rate in force for the period: if any condition fails, the treaty is **ineligible**; otherwise, if any condition is unresolved, **indeterminate**; otherwise **eligible**. A treaty with no conditions is eligible. Treaty rates added by a scenario override carry no conditions.

Modes (`eligibility`):

| Mode | Ineligible | Indeterminate | Withholding basis reported on legs |
|---|---|---|---|
| `assume_eligible` (default; the source) | not evaluated | not evaluated | `treaty`, `general` |
| `strict` | general rate | general rate | `general_ineligible`, `general_indeterminate` |
| `contingent` | general rate | treaty rate, flagged | `general_ineligible`, `treaty_contingent` |

In `contingent` mode the summary reports the number of pairs whose cheapest route relies on an indeterminate treaty, and lists the treaties with the conditions that would have to be met. Routes are otherwise computed exactly as in the reproduction (shortest paths on the modified rates).

## 4. Properties (tested)

1. *Nothing changes:* in `assume_eligible` mode the outputs equal those of the same dataset without conditions; in `strict` mode with every fact and assumption satisfied they equal the reproduction's pairs, legs and centralities.
2. *Monotonicity:* withdrawing treaty benefits never lowers the cheapest combined effective rate where treaty rates do not exceed general rates (assume ≤ contingent ≤ strict).
3. *Precedence:* a failing condition makes a treaty ineligible even when another condition is unresolved.

## 5. Limits

Conditions are evaluated per treaty, not per route: one set of scenario facts applies to every holding in the route. Domestic participation conditions on relief, anti-hybrid rules, controlled foreign company rules and Pillar Two are outside this layer (plan s 10.2, Phase 10).
