# Implementation Specification

## Purpose
A local-first academic workbench for inspecting and comparing international-taxation networks. The interface and data layer are shared; model engines remain separate.

## User workflow
1. State research question.
2. Load and inspect dataset.
3. Record source, access date, licence/terms, transformations and limitations.
4. Select a model/version and explicit parameters.
5. Run tests and validation checks.
6. Inspect graph, tables and intermediate calculations.
7. Export figures, tables and a run manifest.
8. Preserve code revision and dataset hashes.

## Data contracts
**Jurisdictions:** stable ID, display name, fictional flag; contextual fields such as GDP require units, year and source.
**Companies:** stable company ID, reported name, jurisdiction ID, entity type.
**Ownership:** shareholder ID, investee ID, reported ownership percentage, observation date, source ID; financial values require valuation basis/year. Ownership, control and economic entitlement are distinct concepts.
**Tax edges:** source/target jurisdiction, tax treatment, income type, tax base, period, conditions, rule status and source ID. A scalar edge rate is only a prototype convenience; actual tax treatment may depend on payer/recipient, beneficial ownership, treaty eligibility, exemptions and credits.

## Model boundaries
**Tax routing:** inputs are versioned tax rules, payment type, entity attributes, route constraints and scenario assumptions. Outputs should include feasible routes, stage-level treatment, total effective burden and explanations. Validate hand-computed routes and edge cases. Do not assume a tax objective is additive without proving it.
**Conduits/sinks:** inputs are ownership chains, ownership/control semantics, financial weights, denominators and period. Outputs must follow the selected paper's measures. Do not replace them with generic betweenness centrality.
**TDA:** document features, preprocessing, lens, metric, cover, clustering and graph construction. Report memberships, parameters, sensitivity and stability. A generic Mapper baseline is distinct from a patent-specific implementation.

## Provenance
Record question, UTC timestamp, data table hashes, source identifiers/access dates, model/version, parameters, assumptions, software versions, warnings, validation status and output paths. Hashes detect changes but do not prove source authenticity or correctness.

## Visualisation
Label edge direction; provide legends; let users inspect underlying rows; distinguish observed, inferred and exploratory relationships; preserve units/time periods; avoid causal or legal implications from visual proximity.

## Release gates
Before calling a method reproduced: archive primary specification; map equations/steps; implement transparent reference version; create hand-calculated fixtures; test edge cases; compare published outputs where compatible; document discrepancies.

## Lawful data access
Review licences, terms, database rights, redistribution limits, privacy duties and automated-access rules. Prefer official sources and documented APIs. Respect rate limits and access controls. Keep source data distinct from derived outputs.
