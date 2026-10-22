# Specification: optimal tax routing (van 't Riet and Lejour)

**Engine:** `vtrl2018.tax_routing`, reproduction variant. **Specification version:** 0.1 (draft).
**Status of this document:** *draft*. The text of the source was obtained through automated PDF extraction, which garbled some formulas. The equations below are therefore reconstructions, each marked with its basis. Until the author has checked them against the source (s 10), the engine may reach `implemented` but not `verified` (project plan v2.2, s 0.0 item 5).

## 1. Source

* **Used:** Maarten van 't Riet and Arjan Lejour, 'Optimal Tax Routing: Network Analysis of FDI Diversion' (CPB Discussion Paper 349, CPB Netherlands Bureau for Economic Policy Analysis 2017) <https://www.cpb.nl/system/files/cpbmedia/omnidownload/CPB-Discussion-Paper-349-Optimal-tax-routing-Network-analysis-of-FDI-diversion.pdf>. Page numbers below refer to this version.
* **Authoritative version (not yet compared):** Maarten van 't Riet and Arjan Lejour, 'Optimal Tax Routing: Network Analysis of FDI Diversion' (2018) 25 International Tax and Public Finance 1321. Any difference between the versions must be logged here before the engine is promoted.
* **Other version:** Tilburg University CentER Discussion Paper 2017-022.

The source is a working paper of a government economic policy bureau. The journal version is peer reviewed.

## 2. Scope and assumptions of the source

| # | Assumption | Page |
|---|---|---|
| A1 | Only dividends are modelled; interest and royalties are excluded. | 8, 19 |
| A2 | Investment and profit decisions are given; repatriation is full and immediate (no deferral). | 8 |
| A3 | Conditions for dividend participation exemptions are assumed to be satisfied. | 8 |
| A4 | Statutory rates are used (including local taxes), not effective rates. | 11 |
| A5 | The case of no relief at all is ignored. | 8 |
| A6 | 108 jurisdictions, year 2013; tax data from the EY Worldwide Corporate Tax Guide 2013, supplemented by the OECD Tax Database, KPMG, Deloitte and Loyens & Loeff. | 11 to 12 |
| A7 | Averages across pairs are weighted by "double GDP" as a proxy for bilateral flows. | 13, 17 |

## 3. Notation

For an ordered pair of jurisdictions (S, P), where S pays a dividend and P receives it:

* t_S, t_P: statutory corporate income tax (CIT) rates of S and P;
* w_SP: dividend withholding tax levied by S on dividends paid to P: the treaty rate where a treaty applies, otherwise S's general rate (interpretation I11);
* r_P(S) ∈ {exemption, credit, deduction}: the relief method P applies to dividends from S;
* d_SP: the *tax distance* from S to P, that is, the additional tax on repatriation beyond the host's CIT, as a share of pre-tax profit net of host CIT;
* t^e_SP: the combined effective rate on profit earned in S and repatriated to P.

## 4. Direct route (p 8)

The tax distance depends on P's relief method:

| Relief | Tax distance | Basis |
|---|---|---|
| Exemption | d_SP = w_SP | Stated (p 8). |
| Deduction | d_SP = 1 − (1 − w_SP)(1 − t_P) | Stated (p 8). |
| Credit | d_SP = max{ w_SP, (t_P − t_S) / (1 − t_S) } | Stated (p 8); extraction partly garbled, consistent with the identity below. |

Identity (stated, p 8): t^e_SP = 1 − (1 − t_S)(1 − d_SP).

For the credit case this gives t^e_SP = max{ t_P, 1 − (1 − t_S)(1 − w_SP) }: total tax is the home rate if that is higher, otherwise the foreign taxes (CIT and withholding) with excess credits not refunded. The extracted text of this expression was garbled; the form here is *derived* from the stated d_SP and the identity (interpretation I1).

The host CIT is always paid and is therefore excluded from d_SP, so that it is not counted twice (p 9).

## 5. Indirect routes (pp 8 to 9)

For a route 1 → 2 → … → n, with 1 the host and n the final home:

    d(1,n) = 1 − Π_{k=1}^{n−1} (1 − d(k, k+1))                          (R1, stated, p 9)
    t^e(1,n) = 1 − (1 − t_1)(1 − d(1,n))

The order of the bilateral distances does not matter (p 9), which is what allows a standard shortest-path algorithm.

**Conduit CIT (p 9).** A conduit's own CIT matters only when the next parent applies the credit method. In that case the source does not use the conduit's statutory rate (which would overstate the credit) or zero (which would understate it), but the *world average corporate income tax*, excluding the conduit itself. Hence, for a leg k → k+1 with k ≥ 2:

    d(k, k+1) is computed as in s 4, with t_S replaced by t̄_(−k) where P = k+1 applies credit,

and for the first leg (k = 1) the host's statutory CIT t_1 is used. Withholding taxes on earlier legs are "always taken into account and credited where required" (p 9); a footnote notes that a direct credit covers only withholding tax and that the paper ignores the indirect credit for underlying CIT (fn 7). The weighting of the world average is not stated (I2).

Because t̄_(−k) does not depend on the earlier part of the route, every leg's distance depends only on the leg itself and on whether it is the first leg. Route taxation is therefore separable and a shortest-path search is correct.

## 6. Shortest routes (pp 10, 17 to 18)

* **Algorithm:** Floyd-Warshall over all pairs (p 10). The engine uses Dijkstra's algorithm from each host on the transformed weights −ln(1 − d), which finds the same optimum (I5), with the host excluded as an intermediate country so that routes are simple (I4).
* **Penalty:** "a small penalty for each additional intermediate country on a route" (p 18), to prefer fewer conduits where taxes are equal. The value is not stated (I5).
* **Near-optimal set:** "a half percent on top of the combined effective range of the strictly shortest paths" (p 18). Routes within this range are treated as shortest for the centrality measure BTWNS; STRCT uses only the strictly shortest routes. Whether the range applies to t^e or d is not stated (I6).
* Average multiplicity reported: about 5.5 shortest routes per pair with the penalty, 91 with the half-percent range (p 18).

## 7. Indicators

**Treaty shopping (p 15).** The difference between the direct-route rate and the shortest-route rate; "a positive difference means that there exists a detour with a tax gain". The engine reports SHOP_SP = t^e_direct − t^e_best (I10).

**Betweenness centrality (pp 17 to 18).** For jurisdiction c, over ordered pairs (S, P) with c ∉ {S, P}:

    BTWNS_c = Σ_(S,P) ω_SP · σ_SP(c) / σ_SP                              (stated in words, p 17)

where σ_SP is the number of routes in the near-optimal set for (S, P), σ_SP(c) the number of those passing through c, and ω_SP the "double GDP" weight (I8). Variants (p 18): STRCT (strictly shortest routes only), OCCUR (1 if c lies on any route in the set, else 0, summed over pairs; weighting not stated, I9), UNWTD (ω_SP = 1).

## 8. Interpretive choices (engine defaults; adjustable where marked)

| # | Choice | Default | Parameter |
|---|---|---|---|
| I1 | Credit-case t^e derived from stated d and identity. | as s 4 | none |
| I2 | World average CIT excluding the conduit: weighting not stated. | unweighted mean over jurisdictions in the network | `world_average` (`unweighted`, `gdp`) |
| I3 | First leg uses the host's statutory CIT; later legs use t̄_(−k) only where the receiving parent applies credit. | as s 5 | none |
| I4 | Routes are simple; the host is never an intermediate; domestic pairs (S = P) are not defined and are omitted. | as stated | none |
| I5 | Penalty applied per intermediate country in log-retention units (≈ percentage points for small taxes); Dijkstra on −ln(1 − d) + μ per intermediate. | μ = 0.0001 | `penalty` |
| I6 | Near-optimal range applied to the penalised combined effective rate. | 0.005 | `tolerance` |
| I7 | Strictly shortest routes: equal penalised cost within 1e-12. | as stated | none |
| I8 | ω_SP = GDP_S · GDP_P, normalised so that the weights sum to 100 over the pairs with a route (centrality then reads as a percentage). Annex C2 of the source, which defines the weights, has not been consulted. | as stated | `centrality_weights` (`gdp_product`, `unweighted`) |
| I9 | OCCUR uses the same weights as BTWNS. | as stated | none |
| I10 | SHOP measured on t^e. | as stated | none |
| I11 | Without a treaty rate, S's general dividend withholding rate applies. | as stated | none |
| I12 | Relief method set per receiving jurisdiction, with optional directional overrides for particular payer countries. | as stated | data |
| I13 | Legs with d ≥ 1 cannot carry income and are excluded; rates must lie in [0, 1). | as stated | none |
| I14 | Enumeration of the near-optimal set is bounded (computational bounds, not in the source): by a maximum number of intermediate countries (raised automatically to the length of the cheapest route), by a maximum number of routes per pair, and by an overall route budget after which remaining pairs use only their strictly cheapest routes. Every bound that binds is reported per pair (`enumeration_capped`) and in the run warnings. The cheapest route itself is never bounded. | 3; 20,000; 300,000 | `max_intermediates`, `max_routes_per_pair`, `route_budget` |

## 9. Scenario variables (live exploration and pinned runs)

The engine accepts scenario overrides that change inputs without editing the dataset, and records them in the run: a jurisdiction's CIT rate, its general dividend withholding rate, its relief method, and the treaty withholding rate for an ordered pair (including removing a treaty). Overrides are scenario assumptions in the sense of plan s 7.1.

## 10. Open questions for the author's check

1. Confirm the three d_SP formulas and the credit-case t^e on p 8 (extraction garbled the credit case).
2. Confirm the conduit rule on p 9: world average *excluding the conduit*, applied only where the next parent gives credit; and its weighting (I2).
3. Penalty value (p 18) and whether the half-percent range is on t^e or d (I5, I6).
4. Double-GDP weights: product form and normalisation (annex C2) (I8).
5. Whether OCCUR is weighted (I9); whether SHOP is on t^e or d (I10).
6. Whether relief methods vary by partner country in the data (I12).
7. Differences between the discussion paper and the journal version.

## 11. Benchmarks for later replication (expectation register, plan s 7.5)

From the source (108 jurisdictions, 2013, double-GDP weighted): average tax on repatriated dividends, direct versus shortest route: withholding 7.7% → 2.1%; home CIT 4.4% → 3.7%; total double tax 11.8% → 5.8%; host CIT 29.2% (Table 4, p 15). An indirect route is cheaper for 67% of pairs (pp 14, 17). Top BTWNS: United Kingdom 12.2; Luxembourg 7.7; Estonia 6.7; Netherlands 6.6; Hungary 6.1 (Table 5, p 17).

## 12. Feasibility

The tax data come from commercial guides, so full replication is Tier B (plan s 7.3). A public alternative is a source-backed subset: CIT rates and some withholding rates from the OECD Tax Database, and treaty dividend rates from treaty texts, for a small group of jurisdictions. The engine is jurisdiction-level and computes quickly (108 jurisdictions are well within the live-exploration budget for the strictly shortest routes; the near-optimal enumeration is bounded by I14).

## 13. Verification

Hand-calculated fixtures, a brute-force differential test against enumeration of every simple route, property tests and metamorphic tests are in `tests/test_vtrl2018.py`. The worked example in the fixture `taxnetlab.fixtures.vtrl_fixture()` is documented in that test file.
