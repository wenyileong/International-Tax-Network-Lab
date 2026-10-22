# Specification: persistent homology of jurisdictions (Vietoris–Rips)

**Engine:** `ph.vietoris_rips` (reproduction track, variant `reproduction`)
**Specification version:** 0.1 (22 October 2026). Status of the engine built on it: `implemented`.
**Plan reference:** project plan v2.4, s 9.4 (alternative topological methods) and s 5.2 (FeatureMatrix).
**Code:** `src/taxnetlab/topology.py` (algorithms), `src/taxnetlab/features.py` (FeatureMatrix), `src/taxnetlab/engines/ph.py` (engine).

Unlike the two earlier specifications, this one is not transcribed from a single paper by automated extraction. It states standard definitions from the peer-reviewed literature listed in s 8, so the equations can be checked against textbook sources. It remains for the author to check before the engine is promoted to `verified` (plan s 3.1).

## 1. Purpose

To describe the shape of a set of jurisdictions in a declared feature space, or in tax-routing cost, at every scale at once: how many clusters there are and when they merge (dimension 0), and whether the jurisdictions surround empty regions, forming loops (dimension 1); to say how long each such feature persists across scales; and to say which jurisdictions the structure depends on. This serves the research purpose of the patented pipeline (plan s 9.3) by a different, published method.

## 2. Design constraints (plan s 9.4, condition 1)

The engine must not contain any of the following, which correspond to elements 1b to 1f of claim 1 of US 10,417,262 B2 (IP note s 2):

| # | Constraint | How it is met |
|---|---|---|
| D1 | No lens or filter function mapping data to a reference space for analysis. | Every computation uses only the distance matrix. |
| D2 | No cover of a reference space, and no resolution or overlap parameters. | The filtration is indexed by scale over the whole space; there are no cover elements. |
| D3 | No clustering within cover elements. | The only grouping is the connected components of the Rips complex at a scale, over the whole space (single linkage). |
| D4 | No graph of clusters joined by shared members. A display projection, if any, is never read by the computation. | Outputs are diagrams, barcodes, Betti curves and influence scores. The two-dimensional projection (s 6) is written to the output for drawing only; a test checks that every other output is unchanged when the projection is altered. |
| D5 | No procedure taken from the patent's description (for example lens evaluation by matrix-vector products feeding a cover). | The algorithms are those of s 4 and s 5 and their published sources. |

These constraints are part of the specification: a change that breaches one is a change of method and needs the IP gate (plan s 9.3).

## 3. Inputs

### 3.1 Feature matrix (`input = features`)

Observation unit: jurisdiction, for one period (default: the latest period with tax rules). Features are chosen from the catalogue below by identifier, in a comma-separated list.

| Identifier | Definition | Unit |
|---|---|---|
| `cit` | `tax_domestic.cit_rate` | share |
| `dividend_wht` | `tax_domestic.dividend_wht_rate` | share |
| `mean_applicable_wht` | mean over every other jurisdiction with tax rules of the treaty rate where there is one, otherwise the general rate | share |
| `treaty_count` | treaty rows with the jurisdiction as payer | count |
| `log_gdp` | ln of GDP for the period, or the latest earlier period | ln(currency) |
| `outward_links` | current equity relations held by its entities in entities elsewhere | count |
| `inward_links` | current equity relations held in its entities by entities elsewhere | count |
| `vtrl_btwns` | conduit betweenness, `vtrl2018.tax_routing`, default parameters | percent |
| `vtrl_mean_shop` | mean treaty-shopping gain as host, `vtrl2018.tax_routing` | share |
| `gb_sink_centrality` | sink centrality, `gb2017.conduits_sinks`, default parameters | ratio |
| `gb_conduit_out` | conduit centrality towards sinks, `gb2017.conduits_sinks` | ratio |

Default: `cit, dividend_wht, mean_applicable_wht, treaty_count, log_gdp, outward_links, inward_links`.

*Derived features (A33).* Features from another engine are computed inside the run with that engine's default parameters for the period; the engine identifier, version, status, resolved parameters and the hash of its outputs are recorded. A warning names any such engine below `verified`.

*Missing values.* An observation lacking any selected feature is excluded and listed with the features it lacks; nothing is imputed.

*Scaling.* `zscore` (default: subtract the mean, divide by the population standard deviation), `minmax` (to [0, 1]) or `none`. A feature without variation is scaled to 0 and named in a warning.

*Metric.* `euclidean` (default), `manhattan` or `chebyshev` between scaled rows.

*Hash.* The matrix has a SHA-256 hash of its canonical form (unit, period, scaling, features, provenance and raw values), reported in the summary.

### 3.2 Network-native distance (`input = routing_cost`)

For jurisdictions S and P with tax rules, c(S, P) = -ln(1 - d*(S, P)), where d*(S, P) is the tax distance of the cheapest route from S to P under `vtrl2018.tax_routing` with default parameters (its spec s 5). Because route tax distances compose as 1 - prod(1 - d), c is additive along routes. c is directional; the distance is max(c(S, P), c(P, S)) (default) or their mean. A missing or unbounded cost is an input error.

## 4. Persistence

### 4.1 Filtration

For a distance matrix D on n points, the Vietoris–Rips complex at scale e, VR(e), contains every vertex, every edge {i, j} with D(i, j) <= e, and every triangle whose three edges are in VR(e). The value of a simplex is the scale at which it enters: 0 for a vertex, D(i, j) for an edge, the longest edge for a triangle. Simplices are ordered by value, then by dimension, then by a fixed tie-break (edges by vertex indices; triangles by their edge positions in descending order). The diagram does not depend on the tie-break.

### 4.2 Dimension 0

Edges are processed in order with a union-find structure. An edge joining two components kills one of them: the bar [0, D(i, j)). All vertices are born at 0, so the elder rule is applied with ties broken by the smallest vertex index (the component whose smallest vertex is larger dies). Components left at the end are essential bars [0, infinity). Bars of zero length (duplicate points) are counted, not listed. Each bar lists the members of the dying (or surviving) component.

### 4.3 Dimension 1

Persistence pairs (edge, triangle) are computed over Z/2 by persistent cohomology with clearing: the coboundary columns of the edges not paired in dimension 0 are reduced in reverse filtration order, the pivot being the earliest triangle (de Silva, Morozov and Vejdemo-Johansson 2011; Bauer 2021). This gives the same pairs as reduction of the triangle boundary matrix (Edelsbrunner, Letscher and Zomorodian 2002; Zomorodian and Carlsson 2005), which the code also implements as an independent check. A pair gives the bar [value of edge, value of triangle); zero-length bars are dropped. An edge left unpaired gives an essential bar; this happens only when the filtration is truncated (s 4.5), because the complete complex has no loops.

### 4.4 Representative cycles

For a bar born at edge {a, b}, the engine reports a cycle born with it: the edge plus a path with the fewest edges from b to a through earlier edges. It represents a class born at that scale; it is not necessarily the shortest representative, and it is described as "a representative cycle".

### 4.5 Truncation and budget

`max_scale` truncates the filtration (0 means none). The number of triangles is bounded by `simplex_budget`: if the complete complex would exceed it, the filtration is truncated just below the first edge value at which it would, so that every triangle up to the effective maximum scale is present and the pairs are exact there. Classes alive at the truncation scale are reported as essential, and the truncation is stated in the warnings and summary.

## 5. Summaries and stability

### 5.1 Betti curves

b_k(e) = the number of bars [b, d) in dimension k with b <= e < d, evaluated at every critical value. b_0(e) is the number of clusters at scale e; b_1(e) the number of independent loops.

### 5.2 Bottleneck distance and stability

The bottleneck distance between two diagrams is the smallest e for which there is a matching of their points, each point matched to a point of the other diagram within e in L-infinity distance or to the diagonal at a cost of half its persistence, with essential classes matched among themselves by birth (the distance is infinite, reported empty, if their numbers differ). The threshold is found by binary search over the candidate values; feasibility at a threshold uses the Mendelsohn–Dulmage theorem (a matching covering every point of A too persistent for the diagonal, and one covering every such point of B). If two distance matrices on the same points differ by at most delta in every entry, the diagrams in each dimension are within delta in bottleneck distance (Cohen-Steiner, Edelsbrunner and Harer 2007; for Rips filtrations Chazal, de Silva and Oudot 2014). This is a tested property.

### 5.3 Influence

For each jurisdiction j, the bottleneck distance between the diagram of all jurisdictions and the diagram without j, in each dimension, and the rank by the dimension-1 value. It answers: how much of the loop structure depends on this jurisdiction? Computed only up to `influence_limit` observations, because it repeats the computation once per observation.

## 6. Display projection (D4)

Classical multidimensional scaling of D (double-centred squared distances; top two eigenvectors by power iteration with deflation; deterministic start vectors; sign fixed so the largest component is positive). Used only to draw points; its Kruskal stress-1 is reported (0 exact; above about 0.2 the picture misleads). The page draws the Rips edges and clusters at the chosen scale from D, not from the projection.

## 7. Outputs

| Table | Key | Content |
|---|---|---|
| `points` | jurisdiction | included, missing features, projection x, y |
| `features` | jurisdiction, feature | raw and scaled values |
| `distances` | a, b | the distance matrix (upper triangle) |
| `diagram` | feature id (`H1-0001` is the most persistent loop) | dimension, birth, death, persistence, essential, birth and death simplices, members (H0), representative cycle (H1) |
| `betti` | step | scale, b0, b1 |
| `influence` | jurisdiction | bottleneck H0, bottleneck H1, rank |
| `summary` | measure | counts, matrix hash, truncation, budget, projection stress |

## 8. Tests (acceptance for `implemented`)

1. Hand fixtures: square (one loop [1, sqrt 2)); equilateral triangle (no loop); two separated pairs (H0 death at the gap); hexagon (one loop dying at the long diagonal).
2. Independent check: at every critical scale, Betti numbers from the ranks of the boundary matrices of VR(e) over Z/2 equal the numbers of bars alive.
3. Cohomology and homology algorithms give identical diagrams, including with tied distances.
4. Stability: random perturbations of at most delta move each diagram by at most delta.
5. Bottleneck distance: against brute force over all matchings for small diagrams.
6. Differential: against Ripser and GUDHI when installed (optional test dependencies).
7. D4: altering the projection leaves every other output unchanged; engine outputs identical across repeated runs; replay reproduces hashes.
8. No imputation: an observation lacking a feature is excluded and listed.

## 9. Sources

* Herbert Edelsbrunner, David Letscher and Afra Zomorodian, 'Topological Persistence and Simplification' (2002) 28 Discrete & Computational Geometry 511.
* Afra Zomorodian and Gunnar Carlsson, 'Computing Persistent Homology' (2005) 33 Discrete & Computational Geometry 249.
* David Cohen-Steiner, Herbert Edelsbrunner and John Harer, 'Stability of Persistence Diagrams' (2007) 37 Discrete & Computational Geometry 103.
* Frédéric Chazal, Vin de Silva and Steve Oudot, 'Persistence Stability for Geometric Complexes' (2014) 173 Geometriae Dedicata 193.
* Vin de Silva, Dmitriy Morozov and Mikael Vejdemo-Johansson, 'Dualities in Persistent (Co)homology' (2011) 27 Inverse Problems 124003.
* Ulrich Bauer, 'Ripser: Efficient Computation of Vietoris–Rips Persistence Barcodes' (2021) 5 Journal of Applied and Computational Topology 391.
* Danijela Horak, Slobodan Maletić and Milan Rajković, 'Persistent Homology of Complex Networks' (2009) Journal of Statistical Mechanics: Theory and Experiment P03034.
* N S Mendelsohn and A L Dulmage, 'Some Generalizations of the Problem of Distinct Representatives' (1958) 10 Canadian Journal of Mathematics 230.
* Joseph B Kruskal, 'Multidimensional Scaling by Optimizing Goodness of Fit to a Nonmetric Hypothesis' (1964) 29 Psychometrika 1.
