# Author check pack

**Purpose:** the checks that stand between each engine and `verified` status (plan v2.6, s 3.1 and s 13). An engine built on a specification is promoted only after the author has checked the specification against its source and recorded the outcome in `docs/verification/records/<engine>.md` (a test enforces this).
**Generated** by `scripts/make_check_pack.py` from the specifications; do not edit the item lists by hand. Mark the outcome of each item here (or in a copy), then complete the sign-off in the engine's record file.

**How to use.** For each item: read the cited part of the source; mark the outcome as *confirmed*, *corrected* (state the correction) or *open*. A corrected item changes the specification first, then the code, then the fixtures, in that order; the approved-output snapshots (`tests/regression/approved.json`) are regenerated only with the change documented in the changelog.


## vtrl2018.tax_routing

**Specification:** `docs/specs/vtrl2018_tax_routing.md` (version 0.1)
**Check against:** CPB Discussion Paper 349 (pp 7 to 10 and 13 to 18) and the journal version, (2018) 25 International Tax and Public Finance 1321.


### Interpretations and constraints

| # | Item | Outcome | Note |
|---|---|---|---|
| I1 | Credit-case t^e derived from stated d and identity. | | |
| I2 | World average CIT excluding the conduit: weighting not stated. | | |
| I3 | First leg uses the host's statutory CIT; later legs use t̄_(−k) only where the receiving parent applies credit. | | |
| I4 | Routes are simple; the host is never an intermediate; domestic pairs (S = P) are not defined and are omitted. | | |
| I5 | Penalty applied per intermediate country in log-retention units (≈ percentage points for small taxes); Dijkstra on −ln(1 − d) + μ per intermediate. | | |
| I6 | Near-optimal range applied to the penalised combined effective rate. | | |
| I7 | Strictly shortest routes: equal penalised cost within 1e-12. | | |
| I8 | ω_SP = GDP_S · GDP_P, normalised so that the weights sum to 100 over the pairs with a route (centrality then reads as a percentage). Annex C2 of the source, which defines the weights, has not been consulted. | | |
| I9 | OCCUR uses the same weights as BTWNS. | | |
| I10 | SHOP measured on t^e. | | |
| I11 | Without a treaty rate, S's general dividend withholding rate applies. | | |
| I12 | Relief method set per receiving jurisdiction, with optional directional overrides for particular payer countries. | | |
| I13 | Legs with d ≥ 1 cannot carry income and are excluded; rates must lie in [0, 1). | | |
| I14 | Enumeration of the near-optimal set is bounded (computational bounds, not in the source): by a maximum number of intermediate countries (raised automatically to the length of the cheapest route), by a maximum number of routes per pair, and by an overall route budget after which remaining pairs use only their strictly cheapest routes. Every bound that binds is reported per pair (`enumeration_capped`) and in the run warnings. The cheapest route itself is never bounded. | | |

### Open questions

| # | Question | Outcome | Note |
|---|---|---|---|
| Q1 | Confirm the three d_SP formulas and the credit-case t^e on p 8 (extraction garbled the credit case). | | |
| Q2 | Confirm the conduit rule on p 9: world average *excluding the conduit*, applied only where the next parent gives credit; and its weighting (I2). | | |
| Q3 | Penalty value (p 18) and whether the half-percent range is on t^e or d (I5, I6). | | |
| Q4 | Double-GDP weights: product form and normalisation (annex C2) (I8). | | |
| Q5 | Whether OCCUR is weighted (I9); whether SHOP is on t^e or d (I10). | | |
| Q6 | Whether relief methods vary by partner country in the data (I12). | | |
| Q7 | Differences between the discussion paper and the journal version. | | |

### Sections to read through

- [ ] 1. Source
- [ ] 2. Scope and assumptions of the source
- [ ] 3. Notation
- [ ] 4. Direct route (p 8)
- [ ] 5. Indirect routes (pp 8 to 9)
- [ ] 6. Shortest routes (pp 10, 17 to 18)
- [ ] 7. Indicators
- [ ] 8. Interpretive choices (engine defaults; adjustable where marked)
- [ ] 9. Scenario variables (live exploration and pinned runs)
- [ ] 10. Open questions for the author's check
- [ ] 11. Benchmarks for later replication (expectation register, plan s 7.5)
- [ ] 12. Feasibility
- [ ] 13. Verification

## gb2017.conduits_sinks

**Specification:** `docs/specs/gb2017_conduits_sinks.md` (version 0.1)
**Check against:** Garcia-Bernardo, Fichtner, Takes and Heemskerk, (2017) 7 Scientific Reports 6246, Methods, Eqs 1 to 5.


### Interpretations and constraints

| # | Item | Outcome | Note |
|---|---|---|---|
| I1 | Ownership weights: direct equity fractions, normalised so that the known shareholders of each firm sum to one ("missing shareholders"). | | |
| I2 | Chains are every simple upward path from each firm with MO ≥ threshold (each distinct path once). | | |
| I3 | Double-counting rule: among firm paths from the same first firm to the same last firm with the same country sequence, keep the maximum value. | | |
| I4 | Sink centrality compares value share with GDP share (s 5). | | |
| I5 | Conduit denominators (s 6). | | |
| I6 | Entropy definitions and natural logarithm (s 7). | | |
| I7 | GDP: the dataset's `gdp` attribute for the period, otherwise the latest earlier period (never a later one; a substitution is reported as a warning; since 1.0.0rc3, previously the latest period of any year); GDP is required for every jurisdiction that appears in G2 or G3. | | |
| I8 | Revenue: the `operating_revenue` of the owned firm for the period, from `entity_financials`. Consolidated figures are flagged; deconsolidation is a data-preparation step outside the engine. Firms without revenue contribute no value. | | |
| I9 | A conduit with an empty denominator (no sink-bound or sink-originating chains) has no conduit centrality (reported as empty, never as 0). | | |
| I10 | Thresholds as stated: sink 10, conduit 1, adjustable for sensitivity. | | |
| I11 | Chain length bound for computation: none beyond the ownership threshold, but an overall chain budget stops enumeration and is reported. | | |

### Open questions

| # | Question | Outcome | Note |
|---|---|---|---|
| Q1 | Eq 1: the exact GDP term (I4). | | |
| Q2 | Eqs 2 and 3: the denominators and GDP terms (I5); the middle-position index. | | |
| Q3 | Eqs 4 and 5: index sets and normalisation (I6). | | |
| Q4 | The chunking and double-counting rule (I3), including whether chunks are prefixes from the owned firm. | | |
| Q5 | Missing-shareholder normalisation in Vitali and others (I1). | | |
| Q6 | Which GDP year is used. | | |

### Sections to read through

- [ ] 1. Source
- [ ] 2. Data in the source
- [ ] 3. Firm-level chains ("Company level chains", "Multiplicative ownership")
- [ ] 4. Country chains ("Aggregating at the country level")
- [ ] 5. Sink centrality (Eq 1)
- [ ] 6. Conduit centralities (Eqs 2 and 3)
- [ ] 7. Entropy (Eqs 4 and 5)
- [ ] 8. Interpretive choices
- [ ] 9. Open questions for the author's check
- [ ] 10. Benchmarks (expectation register)
- [ ] 11. Feasibility

## ph.vietoris_rips

**Specification:** `docs/specs/ph_vietoris_rips.md` (version 0.1)
**Check against:** the peer-reviewed sources in s 9 of the specification (standard definitions).


### Interpretations and constraints

| # | Item | Outcome | Note |
|---|---|---|---|
| D1 | No lens or filter function mapping data to a reference space for analysis. | | |
| D2 | No cover of a reference space, and no resolution or overlap parameters. | | |
| D3 | No clustering within cover elements. | | |
| D4 | No graph of clusters joined by shared members. A display projection, if any, is never read by the computation. | | |
| D5 | No procedure taken from the patent's description (for example lens evaluation by matrix-vector products feeding a cover). | | |

### Sections to read through

- [ ] 1. Purpose
- [ ] 2. Design constraints (plan s 9.4, condition 1)
- [ ] 3. Inputs
- [ ] 4. Persistence
- [ ] 5. Summaries and stability
- [ ] 6. Display projection (D4)
- [ ] 7. Outputs
- [ ] 8. Tests (acceptance for `implemented`)
- [ ] 9. Sources

## eligibility (rule layer)

**Specification:** `docs/specs/eligibility.md` (version 0.1)
**Check against:** plan s 5.2; the treaty provisions coded in the data.


### Sections to read through

- [ ] 1. Data
- [ ] 2. Scenario facts and assumptions
- [ ] 3. Evaluation
- [ ] 4. Properties (tested)
- [ ] 5. Limits

## compare.models

**Specification:** `docs/specs/compare_models.md` (version 0.1)
**Check against:** plan s 6.3 and s 8.


### Sections to read through

- [ ] 1. Purpose
- [ ] 2. Readings
- [ ] 3. Measures (namespaced; definitions in each engine's specification)
- [ ] 4. Ranks and the agreement rule
- [ ] 5. Robustness shares
- [ ] 6. Rank correlations
- [ ] 7. Limits
- [ ] 8. Tests

## sensitivity.sweep

**Specification:** `docs/specs/sensitivity.md` (version 0.1)
**Check against:** plan s 3.2 and s 6.3.


### Sections to read through

- [ ] 1. Inputs
- [ ] 2. Computation
- [ ] 3. Outputs
- [ ] 4. Limits
- [ ] 5. Tests
