# International Tax Network Lab
## Project Plan and Technical Roadmap

**Document version:** 2.5 (supersedes 2.4, 2.3, 2.2, 2.1, 2.0 and 1.0)
**Project baseline:** Build 0.1
**Date:** 22 October 2026
**Target:** a full research software product (release 1.0), delivered as a Windows executable (`.exe`), developed through verifiable intermediate releases.

---

## 0. Revision history

### 0.0000 Changes in version 2.5 (release 0.6)

1. **Rule layer completed for the reproduction tables (s 5.2).** Table `tax_treaty_conditions` (minimum holding, holding period, subject-to-tax, beneficial ownership, principal purpose test, limitation on benefits) and tri-state eligibility (`docs/specs/eligibility.md`). The tax routing engine evaluates conditions only when asked (`eligibility` = `strict` or `contingent`); its default reproduces the source, confirmed by the approved-output snapshots.
2. **Coding templates delivered (s 5.4)** as ZIP archives of CSV files with a data dictionary assigning every column to a coding layer, rather than a workbook (A38): an illustrative template and a real-sample template; header-based import; round-trip test.
3. **Model comparison brought forward from Phase 8 (s 8, s 6.3)** for the documented readings of each source (`docs/specs/compare_models.md`): agreement rule, robustness shares, rank correlations, no combined score. Sensitivity sweeps beyond the documented readings remain in Phase 8 (A39).
4. **Promotion gate (s 3.1).** `docs/verification/AUTHOR_CHECK_PACK.md`, generated from the specifications, and one record per engine; a test refuses `verified` status without a completed record.
5. **Regression snapshots (s 6.1, 6.3)** of approved outputs, checked on every platform and Python version in CI; floating-point sums use exact summation so that hashes agree across interpreter versions (A36).
6. **Sequence (s 10.3):** release 0.7 is the author's checks and promotions, the IP decision and the start of Phase 7 (expectation register, first real-data importer, a legal-row verification log, A37).

### 0.000 Changes in version 2.4 (release 0.5)

1. **Alternative topological methods recorded (new s 9.4).** The methods that could serve the goals of the patented pipeline (a summary of the shape of a feature space and its stability) without reciting the elements of claim 1 of US 10,417,262 B2 are compared in s 9.4: persistent homology, Ball Mapper, exact Reeb graphs and contour trees, network-native methods, UMAP with HDBSCAN, and a Mapper restricted to lenses not computed by matrix-vector multiplication. They are also recorded as option (f) in `docs/IP_GATE_US10417262.md`.
2. **The patent method is kept.** The engine `us10417262.tda` stays registered at `interface` status behind the unchanged IP gate (s 9.3); its specification and any Mapper-type code remain blocked until the author records a decision. The alternatives are additional engines, not replacements.
3. **Persistent homology engine (new).** `ph.vietoris_rips`, specified in `docs/specs/ph_vietoris_rips.md` (v0.1) and built in release 0.5 at `implemented`. Its design constraints (D1 to D5 of the specification) keep it free of a lens, a cover, clustering within cover elements and a graph of clusters. It is included in the executable; before any public distribution the author confirms the reasoning in s 9.4 and the patent landscape search (s 9.4, item 4) is completed.
4. **FeatureMatrix implemented (s 5.2).** A FeatureMatrix may now be derived inside a run from engine outputs computed with recorded engine identifiers, versions and parameters, as well as from a cited run record (A33).
5. **Sequence revised (s 10.3).** Release 0.5 is the alternative topological method and the Topology page; the items previously planned for 0.5 (author checks, IP decision, remaining rule layer, model comparison page) move to 0.6.

### 0.00 Changes in version 2.3 (release 0.4)

1. **Conduits and sinks specified and implemented.** `docs/specs/gb2017_conduits_sinks.md` (v0.1, draft) from the open-access article; engine `gb2017.conduits_sinks` at `implemented` (s 9.1).
2. **IP gate research completed; decision open.** `docs/IP_GATE_US10417262.md` records the claim structure (23 claims; independent claims 1, 12 and 23 recite lens, metric and resolution selection, mapping by matrix-vector multiplication, cover, clustering and a node-and-edge visualisation). The plan's earlier assumption that a generic Mapper baseline lies outside the patent is not safe. The TDA engine stays at `interface` and out of the executable until the author records a decision (s 9.3).
3. **Reading modes delivered** (s 8): Plain English and Technical, with chart guidance in both registers.
4. **New data table:** `entity_financials` (operating revenue per entity and period), introduced with the generation-2 hashing rule so that existing dataset ids are unchanged.

### 0.0 Changes in version 2.2

1. **Live exploration (new s 8.1).** Engine parameters and scenario variables (for example a country's corporate income tax rate or a treaty withholding rate) can be changed with sliders and switches, and the charts recompute as they move, in the manner of interactive controls in a live script. Live results are *previews*: they are labelled exploratory, are not run records, and become citable only when pinned as a run.
2. **Engine order decided (s 10.3).** The tax routing engine (van 't Riet and Lejour) is built first, because it is the most legally intuitive, is cheap to compute at jurisdiction level, and does not depend on the feasibility questions that affect the other two methods (Orbis licensing; the patent). Phase 3 now proceeds method by method: each engine's specification precedes that engine, rather than all three specifications preceding any engine.
3. **Separability resolved from the source (s 9.2).** The paper makes route taxation separable by assumption (a conduit's creditable corporate tax is the world average), which justifies an ordinary shortest-path search. The engine follows the paper; the path-dependent alternative becomes a possible extension.
4. **Scenario overrides are run parameters (s 7.1).** Changes made with live controls are recorded in the run record when a state is pinned, so every pinned result can be replayed.
5. **Specification status (s 3.1).** A specification transcribed with automated text extraction is `specified (draft)` until the author has checked the equations against the source document. An engine built on a draft specification can reach `implemented`, not `verified`.

### 0.1 Changes in version 2.1

1. **Executable delivery.** The software must be delivered as a Windows executable that runs without a Python installation. Every release from 0.2 onwards ships one (sections 1.3, 1.4, 4.4, 10 and 11).
2. **Interface architecture decided now, not at Phase 6.** Delivering an executable from 0.2 makes the Streamlit-or-alternative question urgent. Version 2.1 adopts the pattern proven in the JAF Rule Bench: one executable starts a local server bound to `127.0.0.1` and opens an offline interface in the default browser (section 4.4).
3. **Directional treaty relief.** Version 2.0 keyed treaty rules on the jurisdiction pair, which misstates one-sided relief such as unilateral credits. Relief is now coded by direction (section 5.2).
4. **Shared legal coding layer with the JAF Rule Bench** (liability, collection and observation layers; coding template with verification flags) and shared run-record format (sections 4.6 and 5.4).
5. **Second status track for original models**, so that a model of the author's own (such as JAF) can be hosted or linked without being described as a reproduction (section 3.2).
6. **Pre-build logical evaluation** becomes a formal gate in every phase (section 10.1).
7. **New test classes:** "nothing changes" equivalence tests for extensions, accounting-identity tests and explicit failure states (section 6).
8. **Expectation register** before replication on real data (section 7.5).
9. **Two reading modes** (Plain English and Technical) and universal chart export (section 8).
10. **Python 3.12** for alignment with the JAF Rule Bench.

### 0.2 Changes in version 2.0 (from 1.0)

Retained in full: product definition; status ladder; core contracts before engines; data and licence feasibility before engine work; IP gate for the patent; separate ownership and value-flow views; namespaced measures; FeatureMatrix for TDA; tax-rule layer with tri-state eligibility; reproducibility tiers. Appendix A lists every flaw found in 1.0 and Appendix B the Build 0.1 code defects.

---

## 1. Product definition

### 1.1 Purpose

A local-first research workbench for analysing international tax and corporate ownership networks. It implements published methods faithfully, keeps them separate, records how every result was produced, and lets a researcher inspect, compare and export results to a standard fit for peer-reviewed publication.

### 1.2 Intended users

- **Primary:** academic researchers in international tax law, public finance and corporate networks, with either a legal (qualitative) or a quantitative background.
- **Secondary:** policy analysts and doctoral researchers reproducing or extending the literature.
- **Not intended:** taxpayers or advisers seeking planning advice. The software does not give tax advice and its outputs are not compliance conclusions.

### 1.3 Delivery form

| Component | Role |
|---|---|
| **Windows executable (`.exe`)** | **The primary deliverable.** A self-contained build that runs on Windows 10 and 11 (x64) without Python, administrator rights or network access. It starts the local application server and opens the interface in the default browser (section 4.4). Shipped with every release from 0.2; at 1.0, also offered as an installer. |
| `taxnetlab` Python library | The product core. All domain logic, engines, validation and provenance. Usable directly from notebooks, and bundled inside the executable. |
| Command-line interface | Headless, scriptable runs from a run specification file and replay of past runs. Available from the library and as a second entry point in the executable (`taxnetlab.exe run ...`). |
| Project workspace | A self-contained folder per research project (data catalogue, datasets, runs, exports), chosen by the user and kept outside the executable's own folder. |
| Documentation | User guide, method notes per engine, data dictionary, API reference; the guide is also built into the interface. |

macOS packaging is a post-1.0 aim (section 1.5). Linux users run the library and CLI from source.

### 1.4 What "1.0" means

Release 1.0 is reached when all of the following hold:
- at least two of the three engines are at `verified`, and at least one is at `replicated` or `replicated_with_discrepancies` (section 3);
- the data layer imports, validates, versions and documents real datasets;
- every result can be replayed from its run record in a compatible environment;
- **the Windows executable and installer install and run on a physical Windows 10 and Windows 11 machine without developer tooling, and pass the release smoke test (section 11.1);**
- user and method documentation are complete;
- the software is citable (licence, `CITATION.cff`, archived release with a DOI).

### 1.5 Out of scope until after 1.0

- macOS application bundle.
- Hosted or multi-user service. The architecture must not preclude it (section 4), but it is not built.
- Commercial licensing of the software.
- Extensions beyond the published methods (for example other income types or Pillar Two), except as clearly labelled extension variants after the reproduction variant of an engine is verified.
- Any patent-specific implementation that has not cleared the IP gate (section 9.3).
- Automated conclusions about avoidance, misconduct or illegality.

---

## 2. Governing principles

Retained from version 1.0: methodological fidelity, transparency, reproducibility, provenance, local-first operation, synthetic-first development, lawful data access, no unsupported inference, and a transparent baseline before optimisation.

Added in 2.0:

- **Reproduction versus extension.** Each engine has a *reproduction variant* that follows the source exactly (including its simplifications and period) and may later have *extension variants*. An extension is never displayed as the published method.
- **Status is enforced in code, not by hiding.** Status is held in the engine registry and travels with every result (section 3).
- **Explicit conventions over implicit ones.** Units, edge direction, time semantics and identifier schemes are declared in schemas and checked at load time.
- **No silent loss.** Duplicate edges, missing nodes, unparseable values and dropped records produce visible warnings and are listed in the run record.

Added in 2.1:

- **Offline by default.** The executable makes no network connections at run time. Any future data download is an explicit, user-initiated action recorded in the source registry.
- **Invented law is never attributed to real states.** Illustrative and test data use fictional jurisdictions only. Templates for real jurisdictions ship with every legal field blank and marked unverified (section 5.4).
- **Logical evaluation before building.** No phase begins implementation while a flaw rated fatal in its pre-build evaluation remains open (section 10.1).

---

## 3. Status ladders

### 3.1 Reproduction track (published methods)

Every engine variant that implements a published method carries exactly one status. Claims in the interface, exports and documentation use only these terms.

| Status | Meaning | Required evidence |
|---|---|---|
| `interface` | Placeholder only. Calling it raises `SpecificationNotValidatedError`. | None. |
| `specified` | A versioned specification exists, with page, equation, table and appendix references to an archived source version. | Spec document reviewed; open questions listed. |
| `implemented` | Reference implementation exists and follows the specification step by step. | Code traceable to spec sections. |
| `verified` | Implementation matches hand-calculated fixtures and passes edge-case, property, identity and metamorphic tests. | Test suite green; fixtures documented with workings. |
| `replicated` | Reproduces the source's published results on the same or equivalent data within a stated tolerance. | Replication report. |
| `replicated_with_discrepancies` | As above, with remaining differences explained or listed as unexplained. | Replication report with discrepancy log. |

### 3.2 Original-model track (new in 2.1)

A model of the author's own (for example a future link to the JAF Rule Bench) has no published result to replicate, so the reproduction track does not fit it. It uses:

| Status | Meaning | Required evidence |
|---|---|---|
| `interface`, `specified`, `implemented`, `verified` | As in 3.1, with the specification being the author's own versioned model document. | As in 3.1. |
| `robust` | Reported findings (rankings, signs, directions) hold across a stratified sensitivity sweep at a stated threshold. | Sweep report with robustness shares; non-converged draws counted. |
| `empirically_tested` | Frozen predictions have been compared with observed data under a pre-specified design. | Expectation register entry (section 7.5) and test report. |

Original models are labelled as such on every page and export, and are never shown under a heading that implies a published method.

### 3.3 Rules common to both tracks

- Results from engines below `verified` are watermarked "unverified" in the interface and every export, and the status is written into the run record.
- `replicated` and `empirically_tested` require real data, so no phase before real-data integration may require them.
- A performance implementation inherits status only by passing differential tests against the reference implementation on the full fixture suite.

---

## 4. Architecture

### 4.1 Layers

1. **Domain layer:** typed schemas for every entity (section 5), conventions and validators.
2. **Data layer:** importers, column mapping, coding templates, source registry, dataset versioning, storage (DuckDB catalogue over Parquet files).
3. **Engine layer:** independent engines behind one interface (section 4.2).
4. **Run layer:** run specification, execution, immutable run records, replay.
5. **Service layer:** a single Python API (`taxnetlab.api`), exposed to the interface through a local HTTP API bound to `127.0.0.1`. The CLI and notebooks call the Python API directly. No front end calls engines directly.
6. **Presentation layer:** browser-based offline interface served by the executable; CLI; notebooks.

### 4.2 Engine interface (to be fixed before any engine is written)

Each engine variant declares:
- `engine_id`, `track` (`reproduction` or `original`), `variant` (`reproduction`, `baseline` or a named extension), `version`, `status`;
- `spec_ref`: identifier and version of its specification document;
- `input_schema`: which domain entities and views it consumes;
- `parameter_schema`: typed parameters with defaults, units and permitted ranges;
- `validate(inputs, params) -> ValidationReport`: errors that block and warnings that do not;
- `run(inputs, params) -> EngineResult`: outputs as typed tables, a calculation trace, warnings, assumptions and an explicit outcome state (section 6.3);
- `measures`: namespaced output measure names (for example `gb2017.sink_measure`, `vtrl2018.conduit_centrality`), each with definition text, numerator, denominator, unit and source reference.

`EngineResult` replaces the current `ModelResult`.

### 4.3 Reference and performance implementations

Each engine first gets a reference implementation written for readability (pure Python, NetworkX, small data). Real datasets in this field are large (the Garcia-Bernardo study is reported to have used tens of millions of firms and ownership links). A performance implementation (sparse matrices, igraph or DuckDB queries) is added in the real-data phase and must pass differential tests against the reference implementation.

### 4.4 Executable and interface architecture (decided in 2.1)

**Decision.** The application is delivered as a single Windows executable built with PyInstaller. On launch it:
1. starts a local HTTP server bound to `127.0.0.1` only, on the first free port from a configured default (falling back automatically, and showing the port in the console window);
2. opens the interface in the user's default browser;
3. serves a static, offline front end (HTML, CSS and JavaScript bundled inside the executable, with no content from external servers);
4. shuts down cleanly when the console window is closed or the interface's "Quit" control is used, finishing or cancelling any running job and never leaving a partial run record.

**Why.** This is the pattern already built and tested in the JAF Rule Bench. It avoids desktop GUI toolkits that are missing from embeddable Python builds, keeps all logic in the library, and lets the same front end later sit over a hosted service without change.

**Streamlit.** Build 0.1's Streamlit shell is retained only as a developer prototype until Phase 2 exit, then retired. Streamlit is not packaged into the executable.

**Front end.** A lightweight, dependency-pinned JavaScript front end that reads JSON from the local API. Plotly.js is bundled for interactive charts so that figures match those produced in notebooks. Long-running runs execute as background jobs with progress reporting and cancellation through the API.

**Two entry points.** `taxnetlab.exe` (interface) and `taxnetlab.exe run <spec>` / `taxnetlab.exe replay <run_id>` (headless), so that the executable alone can reproduce a run.

**Build pipeline.** Executables are built by continuous integration on a Windows runner (not under Wine), from the locked environment, and each build records its own hash and the lock-file hash in an embedded build manifest shown in the interface's "About" panel and written into every run record.

### 4.5 Technology stack

Python 3.12 (aligned with the JAF Rule Bench); pandas, moving to Polars where profiling justifies it; NumPy and SciPy; pydantic for configuration and run specifications; pandera or equivalent for table schemas; openpyxl for coding templates; NetworkX for reference implementations; SciPy sparse or igraph for performance implementations; DuckDB and Parquet for storage; a minimal local HTTP framework for the service layer; Plotly (Python and bundled Plotly.js); pytest with Hypothesis; PyInstaller for the executable; `uv` (or pip-tools) for the lock file; Git with continuous integration on Windows and Linux.

### 4.6 Relationship with the JAF Rule Bench (new in 2.1)

The two tools answer different questions. The Network Lab reproduces published methods; the JAF Rule Bench implements the author's own model of situs rules for digital assets. They remain **separate products**. They share:

| Shared element | Form | When |
|---|---|---|
| Run-record format | One documented JSON schema for run manifests (parameters, code version, seed, data and output hashes, build manifest). | Adopted in Phase 1; JAF aligned at its next release. |
| Jurisdiction and treaty registry | Common identifiers, territory mapping, treaty identity, entry-into-force and MLI modification fields. | Phase 5. |
| Legal coding layer | Liability, collection and observation layers; directional relief; verification flags; OSCOLA source fields (section 5.4). | Phase 5. |
| Coding-template conventions | Workbook layout, header-based column lookup, optional-column handling, validation messages. | Phase 2. |
| Interface conventions | Reading modes, guide and glossary, chart export, palette. | Phases 2 and 9. |
| Packaging pattern | Executable with local server and offline browser interface. | Phase 1. |

**Extraction rule.** Shared code is first duplicated deliberately behind the same schema. It is extracted into a common package only once both tools use identical code for the same purpose, to avoid coupling the release cycles of two single-developer projects prematurely.

**Terminology.** JAF's "conduit switching" is a third distinct use of "conduit" (alongside the Garcia-Bernardo and van 't Riet and Lejour measures). Any shared vocabulary uses namespaced terms.

**Licensing.** The JAF Rule Bench is under PolyForm Noncommercial 1.0.0 (code) and CC BY-NC 4.0 (documents). The Network Lab licence is chosen in Phase 0 (section 10). As sole author, the developer can license shared code under both projects' terms. PolyForm Noncommercial is not an OSI-approved open-source licence; if submission to a venue such as the Journal of Open Source Software is contemplated, its current licence policy must be checked before the licence is fixed.

---

## 5. Data model

### 5.1 Global conventions

- **Units.** Shares, rates and percentages are stored as fractions in [0, 1]. Build 0.1 stores ownership in 0 to 100 and rates in 0 to 1; this must be unified.
- **Money.** Amount, ISO 4217 currency, valuation basis and reference date are stored together. No implicit currency.
- **Identifiers.** Real jurisdictions use ISO 3166-1 alpha-3 codes with a documented mapping for non-sovereign territories (for example Crown Dependencies and overseas territories). Fictional jurisdictions use a reserved `FIC_` prefix so they can never collide with real codes.
- **Time.** Every fact carries *valid time* (the period it was true in the world) and *recorded time* (when it entered the workspace). Engines take an "as of" date and select facts accordingly.
- **Natural persons.** Individual shareholders are excluded at import or replaced by a pseudonymous category (for example "individual, jurisdiction X"), to limit data-protection exposure under the UK GDPR, the GDPR and the Malaysian Personal Data Protection Act 2010.

### 5.2 Entities

**Jurisdiction:** `jurisdiction_id`, `display_name`, `iso3` (nullable for fictional), `fictional`, `parent_jurisdiction_id` (for territories).

**JurisdictionAttribute:** a time series of contextual values (for example GDP), with `attribute`, `value`, `unit`, `currency`, `period`, `source_id`. GDP is an input dependency where a method normalises by economic size.

**Entity:** `entity_id`, `reported_name`, `jurisdiction_id`, `entity_type` with `entity_type_rule`, `is_natural_person` (must be false after import processing), source and valid-time fields.

**OwnershipRelation:** `relation_id`, `holder_id`, `held_id`, `relation_type` (`equity`, `voting`, `control`, `economic_interest`), `share_class` (nullable), `fraction` (nullable, never imputed silently), `direct` (true; indirect holdings are derived), `valid_from`, `valid_to`, `source_id`. Several relations between the same pair are permitted and kept distinct.

**Graph views (derived, never stored as truth):** `ownership_view` (holder to held); `value_flow_view` (held to holder, where value travels towards the ultimate owner); `jurisdiction_aggregate_view` (entities collapsed under a declared aggregation rule). Each view records the transformation that produced it, and every figure legend states which view is shown.

**Tax rules.** Tax treatment is represented as rules evaluated for a situation, not as a property of a jurisdiction pair:
- *DomesticRule:* jurisdiction, tax (for example corporate income tax, outbound dividend withholding), rate or schedule, relief method for inbound income (`exemption`, `credit`, `deduction`, `none`) with conditions (minimum holding, holding period, subject-to-tax tests), valid period, source.
- *TreatyRule:* treaty identifier, contracting jurisdictions, article, income type, the reduced rate the **source** state may levy, conditions (holding threshold, holding period, beneficial ownership, limitation on benefits), principal purpose test applicability (including through the Multilateral Instrument), entry into force and effective dates per jurisdiction, source.
- *ReliefRule (directional, new in 2.1):* `relieving_jurisdiction`, `taxing_jurisdiction`, income type, relief method, relief rate or cap, `applies_both_ways` (default false), legal basis (`treaty`, `domestic_unilateral`, `regional`), valid period, source. Pairs and directions not coded fall back to the relieving jurisdiction's domestic rule, never to a global default silently; any fallback is listed in the run record.
- *Multilateral or regional rule:* for example the EU Parent-Subsidiary Directive, with membership and conditions.
- *Rule status:* `source_backed`, `derived`, `synthetic_assumption`.

**Eligibility is tri-state:** `eligible`, `ineligible`, `indeterminate`. Mechanical conditions are evaluated. Judgement-based conditions (the principal purpose test, contested beneficial ownership) evaluate to `indeterminate` and are resolved only by an explicit scenario assumption recorded in the run. The software never resolves a judgement-based condition by default.

**FeatureMatrix (for TDA):** `matrix_id`, observation unit (for example jurisdiction-year), feature definitions (name, unit, source or derivation), rows and missing-value policy. If a feature is another engine's output, the matrix is a *declared derived dataset*: it either cites that run record or, from 2.4, is derived inside the run from engine outputs computed with recorded engine identifiers, versions and parameters (A33). The matrix carries its own content hash, and no missing value is imputed: an observation lacking a selected feature is excluded and listed.

**Source:** identifier, title, custodian, URL or API, retrieval date, licence and terms, permitted uses, redistribution restrictions, coverage, limitations, transformations, and `licence_class` (`public`, `public_attribution`, `licensed_no_redistribution`, `synthetic`). For legal sources, an OSCOLA citation field and a pinpoint field.

**Dataset and DatasetVersion:** a named collection of tables with a content hash computed by canonical serialisation (section 7.2). Any change produces a new version; old versions remain readable.

### 5.3 Data quality checks

Required columns and types; unique identifiers; referential integrity (blocking); units and ranges per convention; duplicate and parallel relations reported, not merged; cycles reported; natural-person records after import (blocking); facts outside the "as of" date excluded and listed; source coverage and observation periods; contradictory records and unresolved entity matches; unverified legal rows and legal rows without a source (warnings, shown on every result that relies on them).

### 5.4 Legal coding layer and coding template (new in 2.1)

Adapted from the JAF Rule Bench's three-layer template, so that legal coding is done once and in one format.

**Three layers per rule entry:**
- *Liability:* who is liable, on what connecting factor, at what rate, with what relief.
- *Collection:* how tax is collected (self-assessment, withholding by a payer or intermediary), since withholding changes what is actually collected.
- *Observation:* how the taxing state learns of the income or holding (domestic reporting, automatic exchange such as the CRS, or none), by counterparty state and year. For the corporate-dividend methods this layer is optional; it is carried so that the shared schema serves both tools.

**Every legal row carries:** valid period, OSCOLA source and pinpoint, `verified` (yes or no), verifier note and date. Unverified rows can be used in runs but every dependent result displays a warning and the run record lists them.

**Template workbook rules:**
- two templates: an **illustrative template** using fictional jurisdictions only, and a **real-sample template** listing candidate jurisdictions with every legal field blank and `verified` set to no;
- columns are located by header, never by position;
- optional columns that are absent produce warnings and documented defaults, so older templates still load; mandatory columns that are absent block the import;
- validation catches missing fields, out-of-range values, duplicate codes, unknown jurisdiction or treaty codes, and directional relief rows whose two jurisdictions are identical;
- a round-trip test guarantees that a template written and read back is identical.

---

## 6. Validation framework

### 6.1 Generic harness (built in Phase 2, independent of any method)

- fixture format: a small network plus expected outputs plus a written derivation;
- tolerance-aware comparison of result tables;
- property-based tests (relabelling identifiers does not change results; adding an isolated node does not change other nodes' results);
- metamorphic tests (scaling all monetary values changes outputs only as the specification predicts);
- **accounting-identity tests** (new): decompositions sum to one; revenue or value allocated across claimants sums to the total; flows into and out of an intermediate node balance where the specification says they must;
- differential testing between reference and performance implementations;
- regression snapshots of approved outputs;
- a replication report template.

### 6.2 Method fixtures (built in each engine's phase)

Hand-calculated fixtures belong to the engine phase, after the specification exists.

### 6.3 Equivalence and failure-state tests (new in 2.1)

- **"Nothing changes" tests.** Every extension variant must reproduce its reproduction variant exactly (to machine precision, or within a stated tolerance where solvers differ) when the extension's added parameters are set to neutral values. Every later release must reproduce the approved outputs of the earlier release on the regression fixtures unless the change is documented as intended.
- **Explicit outcome states.** Engines return one of `ok`, `no_solution_found`, `not_converged`, `corner_solution` or `invalid_input`, never a plausible-looking number in place of a failure. Rankings or comparisons involving a non-`ok` result are reported as "unranked", and the count of such cases is shown.
- **Agreement rule for comparisons.** Where an engine offers alternative solution concepts or readings of an ambiguous specification, a ranking is declared only where all readings agree; otherwise the result is shown as a tie with the readings side by side.

---

## 7. Provenance and reproducibility

### 7.1 Definition of a run

A run is the execution of one engine variant on one set of dataset versions with one parameter set. A run record is immutable once written and contains: run identifier; research question; UTC start and end time; engine, track, variant, version, status and specification reference; dataset version hashes and source identifiers; views and transformations used; parameters and scenario assumptions (including every resolution of an `indeterminate` eligibility and every relief fallback); unverified legal rows relied on; validation report; outcome state; warnings; output table hashes and paths; software version, Git commit and whether the working tree was modified; lock-file hash; **executable build hash (when run from the executable)**; Python and platform versions.

Interface state (for example which jurisdiction is highlighted) is not a model parameter and is not recorded as one.

### 7.2 Hashing

Hashes are computed over a canonical serialisation: rows sorted by primary key, columns in schema order, fixed numeric formatting, UTF-8, `\n` line endings. Hashes detect change; they do not establish that data are authentic or correct.

### 7.3 Reproducibility tiers

| Tier | Data | What is exported |
|---|---|---|
| A | Public, redistributable | Full package: data, run records, code version, environment lock, executable build reference. |
| B | Licensed, not redistributable | Run records, extraction query or specification, dataset hashes, code version, environment lock, executable build reference, and derived outputs only to the extent the licence permits. Reproducible by another licensee. |
| C | Synthetic | Full package, labelled synthetic in every file. |

The acceptance criterion is: "another researcher with lawful access to the same inputs can reproduce the analysis from the exported package".

### 7.4 Replay and stale results

`taxnetlab replay <run_id>` (from the library or the executable) re-executes a run from its record and reports whether outputs match the stored hashes. On start-up, stored results produced by an engine version whose output schema has changed are marked stale (not deleted); datasets and coded rules are kept, and the user is invited to re-run.

### 7.5 Expectation register (new in 2.1)

Before any engine is run on real data for replication or testing, the researcher records, dated and hashed: the published results to be matched, the tolerance, the comparison statistic and the decision rule for `replicated` versus `replicated_with_discrepancies`. For original models, model outputs (checked against the sensitivity sweep at a stated threshold before freezing) are kept separate from observable hypotheses, which are not frozen until their data sources and design are specified. Entries cannot be edited after freezing; corrections are new, linked entries.

---

## 8. User-facing feature plan

Pages: Workspace, Data manager (including coding templates), Network explorer, Tax route simulator, Conduit and sink analysis, Topological explorer, Model comparison, Run history, Reproducibility and exports, Guide.

- **All pages:** engine status and track shown beside every result; "unverified" watermark below `verified`; synthetic watermark on synthetic outputs; warnings for unverified legal rows relied on.
- **Reading modes (new in 2.1):** a header switch between **Plain English** (default on first opening) and **Technical**. Plain English mode uses descriptive page names, an open guidance box on every chart (what it shows, how to read it, why it matters), and settings grouped by question with the symbol shown beside each plain name. Technical mode shows model terms, symbols and the technical description. Every setting carries a "?" explanation in both registers. Legal analogies are used only where accurate.
- **Guide and glossary:** every engine, measure and status defined in plain English with the technical definition beneath; the same content serves as the Technical-mode glossary.
- **Chart export:** every chart exports as PNG, SVG and CSV, with the run identifier and status watermark embedded.
- **Colour:** saturated, clearly separated hues tested for common colour-vision deficiencies; ink colour chosen per hue; on-chart colour keys where shading direction depends on the display theme; each jurisdiction keeps one colour across charts.
- **Network explorer:** arrowheads and the view name (ownership or value-flow) in the legend.
- **Tax route simulator:** reproduction variant limited to the source's scope (repatriated dividends); extensions labelled; routes with `indeterminate` eligibility shown separately with the assumption required.
- **Conduit and sink analysis:** namespaced measures; a separate, labelled exploratory panel for generic centralities.
- **Topological explorer:** select a declared FeatureMatrix and show its provenance. From 0.5, the Topology page (persistent homology): persistence diagram, barcode, Betti curves, a scale slider showing the Rips graph and the clusters at that scale, loops traced on a display projection, and the influence of each observation on the diagram.
- **Model comparison:** namespaced measures with definitions side by side; agreement rule and robustness shares (section 6.3); no combined score by default.
- **Run history:** list, filter, compare and replay runs; stale results marked.

### 8.1 Live exploration (new in 2.2)

- **Controls generated from the engine.** Each engine declares its parameters and the scenario variables it accepts (s 4.2); the interface builds sliders, switches and selectors from those declarations, so no method-specific control is hard-coded.
- **Recompute on change.** Results update shortly after a control stops moving; superseded requests are discarded; recent results are cached so that returning to an earlier setting is immediate.
- **Previews are not runs.** A preview executes the same engine code as a run but stores nothing. Every live chart carries an "exploratory" mark together with the engine's status. This reconciles live exploration with the rule that no result exists without a run record (s 11): a preview is not a result until pinned.
- **Pinning.** "Save as run" turns the current state, including every scenario override, into an ordinary immutable run record that can be replayed.
- **Sweeps.** Choosing one or two parameters produces a line chart or heatmap of a chosen output across a grid of values (the interactive form of the sensitivity analysis in Phase 8).
- **Scale.** Live exploration is designed for jurisdiction-level data and synthetic worlds. Entity-level data at Orbis scale are explored through runs, not previews.

---

## 9. Engine-specific plans

### 9.1 Conduits and sinks: Garcia-Bernardo and others

**Source:** Javier Garcia-Bernardo, Jan Fichtner, Frank W Takes and Eelke M Heemskerk, 'Uncovering Offshore Financial Centers: Conduits and Sinks in the Global Corporate Ownership Network' (2017) 7 Scientific Reports 6246 (preprint arXiv:1703.03016).

**Known constraints (to be confirmed against the archived text):**
- Data are from Orbis (Bureau van Dijk, now part of Moody's), a licensed database, reportedly about 98 million firms and 71 million ownership links. Redistribution is not permitted, so replication is Tier B.
- Value is described as moving *towards* sinks, so the engine consumes `value_flow_view`, not `ownership_view`.
- The CORPNET group publishes results online (ofcmeter.org). Whether published jurisdiction-level results, code or a data availability statement can serve as a replication target must be checked.

**Specification (2.3):** `docs/specs/gb2017_conduits_sinks.md` v0.1 (draft): Orbis November 2015 vintage; chains extended while multiplicative ownership is at least 0.001, cycles discarded; chain value = revenue of the owned firm times multiplicative ownership; country chains with adjacent repeats merged; sink centrality on two-country chains and conduit centralities on three-country chains, each relative to GDP share; thresholds 10 (sink) and 1 (conduit). The GDP terms and conduit denominators are reconstructions pending the author's check.

**Reconstruction tasks:** exact version; chain construction and direction; length and inclusion rules; multiple owners; value allocation and double counting; exact measures with numerators, denominators and normalisation; classification thresholds; coverage and period; the Orbis vintage and extraction rules used.

**Fixtures:** hand-worked chains and weights; disconnected components; cycles (cross-holding); parallel relations (two share classes between the same pair); missing ownership values; missing or zero denominators; a fixture where ownership and value-flow direction give visibly different answers; identity tests on value allocation.

### 9.2 Optimal tax routing: van 't Riet and Lejour

**Source:** Maarten van 't Riet and Arjan Lejour, 'Optimal Tax Routing: Network Analysis of FDI Diversion' (2018) 25 International Tax and Public Finance 1321. Earlier versions: CPB Discussion Paper 349 (2017) and Tilburg University discussion paper 2017-022. Differences between versions are logged; the journal version is authoritative.

**Specification:** `docs/specs/vtrl2018_tax_routing.md` (v0.1, draft), transcribed from CPB Discussion Paper 349 with page references, interpretive choices and open questions.

**Known constraints:** scope is repatriated dividends; the model includes corporate income tax, dividend withholding taxes, double tax treaties and relief methods (exemption, credit, deduction), and computes routes that minimise tax; it derives a betweenness centrality for conduit countries and a treaty-shopping indicator, namespaced as `vtrl2018.*`. The paper uses 108 jurisdictions in 2013 with tax data from commercial tax guides (EY Worldwide Corporate Tax Guide 2013, supplemented by OECD, KPMG, Deloitte and Loyens & Loeff), so full replication is Tier B; a source-backed public subset is the alternative.

**Separability (resolved in 2.2).** The paper composes taxes along a route multiplicatively, d(1,n) = 1 − Π(1 − d(k,k+1)), and makes each leg independent of the path by assuming that, where the next parent gives credit relief, the conduit's creditable corporate tax is the world average (excluding the conduit) rather than tax actually paid. Under that assumption an ordinary shortest-path search is correct. A path-dependent credit model would be an extension variant, tested against the reproduction variant with "nothing changes" tests where the two coincide.

**Relief direction.** The engine uses directional `ReliefRule` entries (section 5.2): relief is granted by the receiving state for tax levied earlier in the route. A fixture with one-sided (unilateral) relief is required.

**Rule layer dependency:** this engine requires the tax-rule and legal coding entities in sections 5.2 and 5.4, built in the same phase.

### 9.3 Scalable topological data analysis: US Patent 10,417,262 B2

**Bibliographic details (from Google Patents, to be confirmed against USPTO records):** 'Scalable topological data analysis', inventor Ryan H Lewis, original assignee Ayasdi AI LLC (current assignee listed as Ayasdi Inc and SymphonyAI Sensa LLC), priority date 1 July 2016, filed 30 June 2017, granted 17 September 2019, listed as active, anticipated expiry 30 June 2037. No foreign family members were shown.

**Technical point.** The disclosure centres on applying the lens function by matrix-vector multiplication, followed by cover generation, clustering within cover elements and graph construction. Related Ayasdi patents on landmark point selection (US 10,216,828; US 11,397,753; US 12,032,602) are different documents and must not be conflated with this one.

**IP gate (blocking).** Before any TDA code, including the baseline Mapper, is distributed, **which includes inclusion in the executable**:
1. obtain the granted claims and prosecution history; prepare the claim chart as a research document;
2. assess whether the baseline pipeline (lens, cover, clustering, nerve graph), following the published Mapper method of Singh, Mémoli and Carlsson (2007), falls within any independent claim;
3. confirm legal status (maintenance fees, assignments, disclaimers) from USPTO records;
4. consider territoriality: a US patent with no foreign counterparts affects making, using, selling and offering in the United States, including distribution of the executable to US users; the US experimental-use defence is very narrow (*Madey v Duke University* 307 F 3d 1351 (Fed Cir 2002));
5. record the decision: (a) include the baseline in the executable; (b) include the baseline but keep patent-specific procedures in a separate, non-distributed research module; or (c) rely on an existing open-source Mapper library as an optional dependency excluded from the executable.

The claim chart and assessment are research documents, not a freedom-to-operate opinion.

**Status (2.3):** research completed in `docs/IP_GATE_US10417262.md`; the decision is the author's and is recorded in that document. Until then the TDA engine stays at `interface`.

**Status (2.4):** unchanged. The patent-method engine `us10417262.tda` stays registered at `interface` and out of the executable. The gate in this section governs the patented pipeline and every Mapper-type method (lens, cover, clustering within cover elements, graph of clusters). Methods without those elements are assessed under s 9.4.

**Remaining tasks:** specification of preprocessing, lens, metric, cover, overlap, clustering and graph construction; membership preservation; benchmarks; against a declared FeatureMatrix.

### 9.4 Alternative topological methods (new in 2.4)

**Purpose.** The patented pipeline is one way of summarising the shape of a high-dimensional feature space. The research questions for this project (do jurisdictions form clusters, loops or flares in tax-attribute space; which jurisdictions shape that structure; is it stable) can be served by other published methods. Under the all-elements rule, a method that lacks any element of an independent claim does not infringe that claim literally, and the doctrine of equivalents is applied element by element, not to the invention as a whole (*Warner-Jenkinson Co v Hilton Davis Chemical Co* 520 US 17 (1997)). If an element was narrowed by amendment during prosecution, equivalents for that element are presumptively barred (*Festo Corp v Shoketsu Kinzoku Kogyo Kabushiki Co* 535 US 722 (2002)); this matters only for alternatives that keep most of the claimed steps, and turns on the file wrapper, which has not yet been read. The comparison below is a research document for the author, not a freedom-to-operate opinion.

| Method | Principal sources | Elements of claim 1 (IP note s 2) | Other IP and licences | Decision in the plan |
|---|---|---|---|---|
| **Persistent homology** (Vietoris–Rips filtration of a distance matrix; barcodes and diagrams; bottleneck stability) | Edelsbrunner, Letscher and Zomorodian (2002); Zomorodian and Carlsson (2005); Cohen-Steiner, Edelsbrunner and Harer (2007); Chazal, de Silva and Oudot (2014) | No lens (1b, 1c), no cover (1d), no clustering within cover elements (1e), no graph of clusters (1f). Shares only 1a and the use of a metric. | Mature open-source implementations (Ripser, MIT licence; GUDHI, MIT licence). No blocking patent identified; landscape search outstanding (item 4). | **Built in 0.5** (`ph.vietoris_rips`), strongest option. |
| **Network-native persistent homology** (filtrations of a weighted network, for example tax-routing cost between jurisdictions) | Horak, Maletić and Rajković (2009); Petri and others (2014) | As persistent homology; the input is a network distance, not a feature matrix. | As above. | **Built in 0.5** as the `routing_cost` input of the same engine. |
| **Ball Mapper** (cover by balls around a landmark net; graph of balls that share points) | Dłotko (2019), arXiv preprint, not peer reviewed so far as is known | No lens (1b, 1c), but a cover (by balls), membership and a graph joining overlapping cover elements remain; 1d and 1f arguably present, 1e in substance (each ball is one node). Equivalence argument for the missing lens is plausible. | Landmark selection is the subject of other Ayasdi patents (US 10,216,828; US 11,397,753; US 12,032,602), which must be read before any landmark method is used. | **Deferred** until the landmark patents have been read; candidate second alternative. |
| **Exact Reeb graphs and contour trees** | Carr, Snoeyink and Axen (2003); Biasotti and others (2008) | Uses a scalar function (lens-like) but no cover or clustering; needs a simplicial or manifold domain. | None identified. | **Not planned**: jurisdiction data are not samples of a manifold; the scalar function reintroduces a lens choice. |
| **UMAP with HDBSCAN** (embedding plus density clustering) | McInnes, Healy and Melville (2018), arXiv preprint with a peer-reviewed software paper; Campello, Moulavi and Sander (2013) | No cover and no graph of clusters; the embedding is a projection used for display and clustering. | BSD licences. | **Not planned** for 0.5: stochastic (seed dependent), no stability guarantee comparable to persistence; possible later as a comparison method. |
| **Mapper with lenses not computed by matrix-vector multiplication** (option (e)) | Singh, Mémoli and Carlsson (2007) | Keeps 1b and 1d to 1f; avoids 1c only if "matrix-vector multiplication" is construed narrowly; the closest to equivalence and the most exposed to a Festo analysis. | Patent in force in the United States. | **Not planned** (weakest). |

**Conditions for the alternatives.**
1. *Design constraints are part of the specification.* Each alternative's specification lists the claim elements it must not contain (for persistent homology, constraints D1 to D5 in `docs/specs/ph_vietoris_rips.md`), and tests check the constraints that can be checked in code (for example, that results do not depend on a display projection).
2. *Display projections are display only.* Where a page shows observations in two dimensions (classical multidimensional scaling), the projection is never used to build a cover, clusters or a graph, and is labelled approximate.
3. *Status track.* The alternatives are reproductions of published mathematical methods applied to the project's declared feature matrices; they carry the reproduction ladder. Promotion to `verified` needs the author's check of the specification and the differential tests against an independent implementation.
4. *Before public distribution:* (a) the author confirms the reasoning in this section; (b) a landscape search of the Ayasdi and SymphonyAI portfolios and of persistence-related US patents is completed and recorded in the IP note; (c) the patent's maintenance-fee status is checked (IP note s 1). Until then the executable is distributed only privately.

---

## 10. Development phases and release gates

### 10.1 Gates that apply to every phase (new in 2.1)

1. **Pre-build logical evaluation.** Before implementation begins, the phase's design is checked against the current build and recorded in a table (issue, severity: fatal, serious, moderate or minor; resolution). Implementation does not start while a fatal issue is open. Issues found during the build are added to the same table with the fix and the result after the fix.
2. **Executable deliverable.** From Phase 1 onwards, every release ships a Windows executable built by continuous integration on a Windows runner.
3. **Physical Windows smoke test.** Each release executable is launched and exercised on a physical Windows machine (not only under Wine or in CI) using the smoke test in section 11.1. The result is recorded in the release notes.
4. **Regression.** All earlier acceptance tests still pass, including the "nothing changes" tests (section 6.3).

### 10.2 Phases

Each phase maps to one minor release. Phases 3 and 4 can overlap once Phase 2 is complete.

| Phase | Release | Content | Exit gate |
|---|---|---|---|
| 0 | 0.1.x | **Repository hardening.** Initialise Git and tag the Build 0.1 baseline; choose a software licence (section 4.6); add a lock file, continuous integration on Windows and Linux, `CITATION.cff`; remove caches from the distributed tree; fix the Appendix B defects. | Clean repository; CI green on both platforms; Appendix B closed. |
| 1 | 0.2 | **Core contracts and first executable.** Domain schemas and conventions; engine interface (4.2); status ladders enforced in the registry (3); run specification, immutable run record (shared schema, 4.6), run store, canonical hashing, replay; CLI `run` and `replay`; local service layer and minimal offline browser interface (4.4); PyInstaller build in CI. A trivial demonstration engine, clearly marked as a demonstration, proves the pipeline end to end. | **`taxnetlab.exe` launches on a physical Windows machine without Python, opens the interface, executes a demonstration run, and replays it with identical output hashes; the same run gives identical hashes from the CLI and a notebook.** |
| 2 | 0.3 | **Data layer, coding templates and validation harness.** Project workspace; CSV, Parquet and coding-template import with column mapping and preview; validation reports; source registry; dataset versioning; seeded synthetic generator; graph views with direction; generic validation harness (6.1) and outcome states (6.3); Network explorer, Data manager and Guide pages with both reading modes and chart export. Streamlit prototype retired. | A synthetic dataset can be generated, imported, validated, versioned and used in a replayable run from the executable; the harness detects deliberately planted errors (mutation check); template round-trip test passes. |
| 3 | 0.4 | **Source specifications and feasibility (desk research, all three methods).** Archive exact source versions; versioned specifications with page and equation references; replication-feasibility assessment (data, licence, cost, scale); IP gate (9.3). Confirm engine order. | All three engines at `specified` or formally deferred; replication tier recorded; IP decision recorded. |
| 4 | 0.5 | **Conduit and sink engine** (provisional first engine, confirmed at Phase 3 exit): reference implementation, method fixtures, conduit/sink page. | Engine at `verified`; page available in the executable. |
| 5 | 0.6 | **Tax rule layer, legal coding layer and tax routing engine:** rule entities including directional relief, tri-state eligibility, scenario assumptions, three-layer coding (5.4) with illustrative and blank real-sample templates, shared jurisdiction and treaty registry, reference implementation, separability and one-sided relief fixtures, route simulator page. | Engine at `verified`; every displayed route traceable to rules and calculation steps. |
| 6 | 0.7 | **Baseline TDA** (only as permitted by the IP decision, including whether it may be included in the executable): FeatureMatrix, Mapper pipeline, membership inspection, sensitivity. | Engine at `verified`, or formally deferred with the IP decision recorded. |
| 7 | 0.8 | **Real data and scale.** Expectation register entries frozen first (7.5); source-specific importers; entity resolution where needed; jurisdiction identifier validation; performance implementations with differential tests; replication against published results. | At least one engine at `replicated` or `replicated_with_discrepancies`; every dataset has provenance, permitted use and quality limitations recorded; the executable handles the reference dataset within the performance budget. |
| 8 | 0.9 | **Comparison, sensitivity and outputs.** Model comparison page with agreement rule; sensitivity analysis with robustness shares; publication-quality figures and tables; research-run reports; export packages by reproducibility tier. | Export package for a Tier B run reproduces the run on a second Windows machine using the executable and the same licensed inputs. |
| 9 | 1.0 | **Productisation.** Windows installer (per-user, no administrator rights) alongside the portable executable; code signing (section 11.2); user guide, method notes, API reference; error handling and logging; performance budgets met; accessibility review; release process and archived DOI. | Section 1.4 criteria met. |
| 10 | post-1.0 | Extension variants (other income types, Pillar Two, controlled foreign company rules); patent-specific procedures if cleared; macOS bundle; optional hosted service; optional link to original models such as the JAF Rule Bench under the original-model track. | Each extension specified and verified separately, with "nothing changes" tests. |

### 10.3 Revised sequence (2.2)

The table in 10.2 is kept for reference. From 0.3 the order is:

| Release | Content | Exit gate |
|---|---|---|
| 0.3 | **Tax routing, method first.** Phase 3 for van 't Riet and Lejour (specification, feasibility); the tax-rule tables needed by the reproduction variant (domestic rates and relief method, directional treaty withholding, directional relief overrides); the reference engine; live route explorer with scenario overrides and pinning. | Engine at `implemented` with every hand-calculated fixture, a brute-force differential test and property tests passing; promotion to `verified` once the author has checked the specification against the source. |
| 0.4 | Phase 3 for Garcia-Bernardo and others and for the patent (IP gate); conduit and sink engine; reading modes. **Delivered** (engine at `implemented`; IP decision open). | As 10.2, Phases 3 and 4. |
| 0.5 | **Alternative topological method (2.4).** Alternatives recorded (s 9.4); specification and engine for persistent homology with the FeatureMatrix and a network-native input; Topology page with live exploration; the patent-method engine kept at `interface`. | Engine at `implemented` with hand-calculated fixtures, an independent rank-based check of Betti numbers, the stability property and (where installed) a differential test against Ripser passing; design constraints tested. |
| 0.6 | Remaining Phase 5 rule layer (tri-state eligibility, treaty conditions, coding templates); model comparison page for the documented readings; author check pack and promotion gate; regression snapshots. **Delivered** (2.5). | Eligibility and comparison engines `implemented` with "nothing changes" and agreement-rule tests; template round trip; snapshots stable across platforms. |
| 0.7 | Author checks and promotions to `verified`; IP decision; Phase 7 start: expectation register entries, a legal-row verification log (A37), the first real-data importer. | Engines `verified` with records; IP decision recorded. |
| 0.7 onwards | As 10.2, Phases 7 to 9. | As 10.2. |

**Why this order.** Contracts and the first executable (Phase 1) come before engines so that three engines do not produce three designs and packaging problems surface early, not at 1.0. Specification and feasibility for all three methods (Phase 3) precede engine work because data licensing or the patent may change which engine is worth building first. Replication sits with real data (Phase 7), so earlier gates require only `verified`.

---

## 11. Non-functional requirements for 1.0

- **Executable:** runs on Windows 10 and 11 (x64) without Python, administrator rights or internet access; portable folder build plus per-user installer; starts to a usable interface within a stated time on a reference machine; binds only to `127.0.0.1`; chooses a free port automatically; stores workspaces only where the user chooses; never writes inside its own installation folder.
- **Performance:** interactive views respond within two seconds on a reference dataset of a stated size; long runs execute in the background with progress and cancellation.
- **Scale:** performance implementations handle a jurisdiction-level network of all reporting jurisdictions and an entity-level network of a stated size (fixed at Phase 3).
- **Reliability:** no run produces a result without a run record; interrupted runs leave no partial records; closing the console window shuts the server down cleanly.
- **Portability:** Windows executable; library and CLI on Windows, macOS and Linux.
- **Security and privacy:** workspaces local; no telemetry; no network access at run time; licensed data never written to exports beyond licence terms; natural-person data excluded.
- **Maintainability:** test coverage reported; every engine's specification versioned alongside its code; build manifest embedded in every executable.
- **Accessibility:** colour choices legible for common colour-vision deficiencies; figures provide data tables; both reading modes complete.

### 11.1 Release smoke test (physical Windows machine)

1. Launch the portable executable from a folder path containing spaces and non-ASCII characters.
2. Confirm the interface opens and the "About" panel shows the build hash.
3. Create a workspace; download, complete and upload the illustrative coding template; import a synthetic dataset.
4. Execute a run on every engine at `verified` or above; export a chart (PNG, SVG, CSV) and an export package.
5. Replay the run from the interface and from `taxnetlab.exe replay`; confirm identical hashes.
6. Switch reading modes and display themes; confirm no script errors.
7. Close the console window; confirm no orphan process and no partial run record.

### 11.2 Code signing

Unsigned PyInstaller executables commonly trigger Windows SmartScreen warnings and occasional antivirus false positives. Before 1.0, decide whether to obtain a code-signing certificate (cost and identity verification apply). Until then, each release publishes SHA-256 checksums of the executable and installer.

---

## 12. Risk register

| Risk | Effect | Mitigation |
|---|---|---|
| Orbis or tax database access unavailable or unaffordable | `replicated` unreachable for that engine | Phase 3 feasibility; replicate against published aggregates; partial replication on a public subset; document as Tier B or not replicable. |
| Patent claims read on baseline Mapper | TDA cannot be shipped in the executable | IP gate; options (a) to (c) in 9.3; defer TDA after 1.0 if required (1.0 needs only two engines). |
| Tax rule data collection is labour-intensive | Routing engine delayed | Small, source-backed subset first; shared coding layer with JAF so that coding is done once. |
| Source papers ambiguous on key steps | Implementation choices mistaken for the method | Log interpretive choices as open questions; test alternative readings under the agreement rule; contact authors if necessary. |
| Executable blocked or flagged by Windows security | Users cannot run the software | Physical Windows smoke test each release; published checksums; code-signing decision (11.2); avoid packing tricks known to trigger false positives. |
| Packaging tested only in emulation | Defects reach users | CI build on a Windows runner and physical smoke test as release gates (10.1). |
| Bundled scientific libraries inflate executable size or break in the frozen build | Slow start; missing-module errors | Size and start-up budget tracked per release; frozen-build test suite run in CI against the executable itself. |
| Coupling with the JAF Rule Bench | One tool's release blocks the other | Shared schemas first; code extracted only under the extraction rule (4.6). |
| Scope creep into extensions | Delays verified core | Extensions post-1.0 unless a reproduction variant is verified first. |
| Single developer | Bus factor; self-review | Specification reviews and replication reports read by an independent reviewer before status changes. |
| Outputs read as legal conclusions | Reputational and legal risk | Watermarks; no-advice notice; `indeterminate` eligibility never auto-resolved; unverified legal rows flagged. |

---

## 13. Immediate next actions

1. Author checks of `docs/specs/vtrl2018_tax_routing.md` (CPB Discussion Paper 349, pp 7 to 10 and 13 to 18, and the journal version) and `docs/specs/gb2017_conduits_sinks.md` (Methods, Eqs 1 to 5); resolve the open questions; promote each engine to `verified` if its fixtures still pass.
1a. Author's decision on the IP gate (`docs/IP_GATE_US10417262.md` s 5), after checking the patent's maintenance-fee record.
0. Work through `docs/verification/AUTHOR_CHECK_PACK.md` and complete the records in `docs/verification/records/`.
1b. Author check of `docs/specs/ph_vietoris_rips.md` and of the reasoning in s 9.4; landscape search before any public distribution (s 9.4, item 4); read the landmark patents before Ball Mapper is considered.
2. Choose the licence (s 4.6); create the `v0.1.0` and `v0.3.0` tags (tag pushes are not available from the build session).
3. Physical Windows smoke test of the CI-built executable (s 11.1).
4. Release 0.7 (s 10.3).
5. Obtain the JAF Rule Bench 1.0 read-me and specification so that the shared formats match the current JAF build.

---

## Appendix A: Flaw register

### A.1 Flaws in version 1.0 (resolved in 2.0)

| # | Location in v1.0 | Flaw | Resolution |
|---|---|---|---|
| A1 | s 2, out of scope | Excludes distribution, while the goal is full software; no definition of done. | s 1. |
| A2 | Phase 2 exit gate | Requires method fixtures before any method is specified. | s 6; fixtures move to engine phases. |
| A3 | Phases 3 to 6 | Require comparison with published results before real data are integrated. | Status ladder; `replicated` only in Phase 7. |
| A4 | s 3 to 7 | No engine interface, run object or schema layer before engines are built. | Phase 1. |
| A5 | s 6.1, 6.2 | Licensed data dependencies not identified; replication feasibility not assessed. | Phase 3; s 9.1, 9.2. |
| A6 | s 6.3, Phase 5 | Patent assumed not to cover a baseline Mapper without reading the claims. | IP gate, s 9.3. |
| A7 | s 4.1, 6.2 | Ownership and value-flow direction treated as one convention. | Derived views, s 5.2. |
| A8 | s 5, 6 | "Conduit" used by both methods for different measures. | Namespaced measures, s 4.2. |
| A9 | s 4.1, 6.3 | No data entity for TDA input. | FeatureMatrix, s 5.2. |
| A10 | s 4.1 | Tax treatment cannot depend on entity attributes; judgement-based anti-abuse rules not representable. | Rule layer and tri-state eligibility, s 5.2. |
| A11 | s 5 Page D | Simulator offers income types beyond the paper's scope without labelling them as extensions. | Reproduction and extension variants. |
| A12 | s 6.1 | Separability of the tax objective not tied to an algorithm choice or test. | s 9.2. |
| A13 | s 4.3 | "Run" undefined; manifest regenerated on every interface refresh. | s 7.1. |
| A14 | s 4.3 | Hash stability assumed across environments. | s 7.2. |
| A15 | Phase 8, s 8 | Full reconstruction by another researcher incompatible with licensed data. | s 7.3. |
| A16 | s 3.1, Phase 7 | NetworkX cannot handle the scale of the source datasets. | s 4.3. |
| A17 | s 3.3, Phase 3 | Hiding unverified engines from the interface does not prevent notebook use. | Status enforced in registry, s 3. |
| A18 | s 4.1 | Inconsistent units; no currency, identifier or valid-time conventions. | s 5.1. |
| A19 | s 4.1 | Parallel relations between the same pair would be merged. | s 5.2; Appendix B. |
| A20 | s 3.1 | Python 3.10 floor at end of life; build tested only on 3.13. | Python 3.12; CI matrix. |
| A21 | s 9 | Next actions skip the shared contracts the first engine depends on. | s 13. |
| A22 | Throughout | No software licence, citation file or release archiving. | Phases 0 and 9. |

### A.2 Flaws in version 2.0 (resolved in 2.1)

| # | Location in v2.0 | Flaw | Resolution in 2.1 |
|---|---|---|---|
| A23 | s 5.2 TreatyRule | Relief keyed on the jurisdiction pair misstates one-sided relief (unilateral credits) and does not say which state grants relief. | Directional `ReliefRule`, s 5.2; fixture in s 9.2. |
| A24 | s 1.3, 4.4 | Interface framework left open until Phase 6, so packaging risk would surface late; no commitment to an executable. | Executable architecture decided, s 4.4; executable from Phase 1. |
| A25 | s 3 | Only a reproduction track; an original model could not be represented without misdescribing it. | Original-model track, s 3.2. |
| A26 | s 6 | No test that extensions leave the reproduction variant unchanged; engines could return numbers in place of failures. | s 6.3. |
| A27 | s 7 | No freezing of expected results before replication, leaving room for post hoc tolerance choices. | Expectation register, s 7.5. |
| A28 | s 1.4, 11 | Installation criterion did not require testing on a physical Windows machine. | Gates in s 10.1; smoke test s 11.1. |

---

### A.3 Issues in version 2.1 (resolved in 2.2)

| # | Location in v2.1 | Issue | Resolution in 2.2 |
|---|---|---|---|
| A29 | s 11 (reliability), s 8 | "No run produces a result without a run record" conflicts with live exploration, which computes many states that are never recorded. | Previews are defined as non-results: labelled exploratory, not exportable as results, and citable only after pinning (s 8.1). |
| A30 | s 10.2, Phase 3 | Requiring all three specifications before any engine delays an engine whose feasibility is independent of the others. | Method-by-method Phase 3 (s 10.3); the reason for the original rule (licensing and the patent could reorder engines) does not affect the routing engine. |
| A31 | s 9.2 | Separability was framed as an open technical question although the source answers it by assumption. | Resolved from the source (s 9.2); path-dependent credit is an extension. |
| A32 | s 3.1 | "Specified" did not distinguish a reviewed specification from an automated transcription. | Draft specifications cap the engine at `implemented` (s 0.0, item 5). |

### A.4 Issues in version 2.3 (resolved in 2.4)

| # | Location in v2.3 | Issue | Resolution in 2.4 |
|---|---|---|---|
| A33 | s 5.2 FeatureMatrix | A matrix built from engine outputs had to cite an earlier run record, so a live preview could never use one, and a run would depend on another run having been made first. | In-run derivation with recorded engine identifiers, versions, parameters and the matrix hash; the outputs are deterministic, so replay reproduces them. |
| A34 | s 9.3, s 10.2 Phase 6 | Topological analysis was tied to one patented pipeline, so the whole method family depended on a single IP decision. | Alternatives assessed (s 9.4); the patent engine kept behind its gate; persistent homology built under stated design constraints. |
| A35 | s 9.3 | The gate's scope ("any TDA code") would also block methods that recite none of the claimed elements. | Scope clarified: the gate governs the patented pipeline and Mapper-type methods; other methods go through s 9.4. |

### A.5 Issues in version 2.4 (resolved in 2.5)

| # | Location in v2.4 | Issue | Resolution in 2.5 |
|---|---|---|---|
| A36 | s 7.2 | Python 3.12 changed the built-in `sum` of floats (compensated summation), so a run gave different output hashes under Python 3.11 and 3.12 (found by the new snapshots for the as-reported ownership reading). | Exact summation (`math.fsum`) in every engine; snapshots checked on both versions and both platforms in CI. |
| A37 | s 5.4 | Every legal row should carry a verifier note and date, but adding columns to existing tables would change every dataset identifier. | Interim: the `note` column; a separate verification log table (schema generation 2, so identifiers are unchanged) is planned for 0.7. |
| A38 | s 5.4 | A template *workbook* needs a spreadsheet library in the executable. | ZIP of CSV files with a data dictionary and read-me; spreadsheets open CSV directly; import from the ZIP or the CSV files. |
| A39 | s 10.2 Phase 8 | The comparison page waited for the sensitivity framework, although the agreement rule needs only the documented readings. | Comparison over the documented readings in 0.6; general sensitivity sweeps stay in Phase 8. |

---

## Appendix B: Build 0.1 code defects

Found by reading the Build 0.1 source. The test suite does not detect any of them.

| # | File | Defect | Fix |
|---|---|---|---|
| B1 | `provenance.py` | `lineterminator="\\n"` writes a literal backslash and `n` instead of a newline, so the hashed text is a single line rather than CSV; hashes will not match a hash of the downloaded file. | Canonical serialisation (s 7.2); test against an independently computed hash. |
| B2 | `provenance.py` | `synthetic` is inferred from the string label, not from the data. | Derive from the source `licence_class` and `fictional` flags. |
| B3 | `app.py`, `synthetic.py` | The seed is editable and recorded but has no effect. | Implement the seeded generator, or record `seed: null` until then. |
| B4 | `app.py` | A new manifest is generated on every Streamlit rerun; interface state is recorded as a model parameter. | Runs created only by explicit execution (s 7.1). |
| B5 | `graph_utils.py` | `nx.DiGraph` keeps only one edge per pair, silently overwriting parallel relations. | Multigraph or explicit aggregation with a warning. |
| B6 | `graph_utils.py` | An ownership row naming a missing entity creates an attribute-less node; the figure then raises `KeyError`. | Referential-integrity check before graph construction. |
| B7 | `graph_utils.py` | `capital_value_usd_mn` read unconditionally though optional. | Optional field handling with warnings. |
| B8 | `graph_utils.py` | No arrowheads, so direction cannot be read; `ownership` argument unused. | Arrowheads and view label. |
| B9 | `synthetic.py` | Ownership in 0 to 100, rates in 0 to 1. | Fractions throughout. |
| B10 | `tests/` | The direction check is a single `has_edge` assertion. | Test that the reverse edge is absent and that the value-flow view reverses it. |
| B11 | Repository | No Git history; caches in the distributed folder; no lock file. | Phase 0. |
| B12 | `app.py` | `"choice" in locals()` depends on tab execution order. | Superseded by the 2.1 interface; in the interim use `st.session_state`. |

---

## Appendix C: JAF Rule Bench assessment (basis for the 2.1 changes)

Assessed from the JAF build plan covering versions 0.1 to 0.4. A 1.0 build exists and may already address some points.

**Adopted from JAF:** pre-build logical evaluation with severities; "nothing changes" equivalence tests (JAF test 13); accounting-identity tests (JAF tests 7 and 12); explicit failure states and "unranked" reporting; agreement rule across solution concepts; separation of frozen model outputs from draft observable hypotheses; illustrative-versus-real template integrity rule; header-based template columns and tolerant optional columns (JAF tests 18 and 23); directional treaty relief; three-layer legal coding; reading modes, guide, chart export and palette; executable with local server and offline browser interface.

**Not adopted:** merging the tools or hosting JAF as an engine before 1.0 (different research object, own-model status, separate licence and release cycle); Wine-only testing of executables (replaced by physical Windows testing).

**Lessons recorded:** JAF flaw 10 (a numerator including revenue that the denominator excluded) shows why every measure in this plan declares its numerator and denominator (s 4.2).
