# Changelog

## 0.7.0 (22 October 2026)

See `docs/BUILD_0_7_STATUS.md`.

* Expectation register (freeze, supersede, check) and stored replication reports; draft entry for Garcia-Bernardo and others (2017).
* Verification log for legal rows (`rule_verifications`); ISO 3166-1 alpha-3 registry.
* Column mapping for imports of database exports.
* Background runs with progress and cancellation (Runs page, `/api/jobs`).
* Tax routing about six times faster (108 jurisdictions in about 6 s); reference benchmarks and performance budgets.

## 0.6.0 (22 October 2026)

Plan v2.5. See `docs/BUILD_0_6_STATUS.md`.

* Treaty conditions (`tax_treaty_conditions`) and tri-state eligibility; tax routing modes `strict` and `contingent` (the default still reproduces the source).
* Legal coding templates (illustrative and real-sample) with a three-layer data dictionary; ZIP import; CLI `template` and `import`.
* Model comparison engine (`compare.models`) and Compare page: agreement rule, robustness shares, rank correlations.
* Author check pack and verification records; `verified` status now requires a completed record.
* Approved-output snapshots; exact floating-point summation so that results hash identically under Python 3.11 and 3.12.
* Fixed: the Data page did not list the revenue table.
* Synthetic worlds now include fictional treaty conditions (a new table, so dataset ids for a seed change; other tables are unchanged).

## 0.5.0 (22 October 2026)

Plan v2.4. See `docs/BUILD_0_5_STATUS.md`.

* Alternative topological methods recorded (plan s 9.4; IP note option (f) and s 5A). The patent-method engine stays at `interface` behind the IP gate.
* Persistent homology engine (`ph.vietoris_rips`, implemented) with specification `docs/specs/ph_vietoris_rips.md`; FeatureMatrix with derived features and provenance; network-native routing-cost input.
* Topology page with live exploration.
* Existing dataset ids and workspaces are unchanged.

## 0.4.0 (22 October 2026)

Plan v2.3. See `docs/BUILD_0_4_STATUS.md`.

* Phase 3 specification for Garcia-Bernardo and others (`docs/specs/gb2017_conduits_sinks.md`, draft).
* Conduits and sinks engine (`gb2017.conduits_sinks`, implemented) and a live Conduits and sinks page.
* IP gate research note for US Patent 10,417,262 (`docs/IP_GATE_US10417262.md`); decision open; TDA stays out of the executable.
* Plain English and Technical reading modes with chart guidance.
* New `entity_financials` table. Existing dataset ids unchanged; synthetic datasets for a given seed differ from 0.3.

## 0.3.0 (22 October 2026)

Plan v2.2: tax routing, method first. See `docs/BUILD_0_3_STATUS.md`.

* Phase 3 specification for van 't Riet and Lejour (`docs/specs/vtrl2018_tax_routing.md`, draft).
* Tax rule tables: domestic rates and relief, directional treaty withholding, directional relief.
* Optimal tax routing engine (`vtrl2018.tax_routing`, implemented): cheapest routes, treaty-shopping gain, conduit centralities, scenario overrides.
* Live exploration: engine-generic preview API and the Tax routes page with sliders, sweeps and "Save as run".
* Existing dataset ids and workspaces are unchanged.

## 0.2.0 (20 October 2026)

Phase 0 and Phase 1 of the project plan (v2.1). See `docs/BUILD_0_2_STATUS.md`.

* New core: typed schemas, integrity checks, content-addressed datasets, canonical hashing, graph views, engine interface with status ladders, immutable run records with replay, service layer, CLI.
* New offline interface served by a local server bound to 127.0.0.1, replacing the Streamlit shell.
* Windows executable (`taxnetlab.exe`) built and self-tested by CI.
* Language infrastructure: locale files with fallback and text direction; English (UK) complete.
* Fixed every Build 0.1 defect listed in Appendix B of the plan.

## 0.1.0

Initial scaffold (tagged `v0.1.0`, unmodified).
