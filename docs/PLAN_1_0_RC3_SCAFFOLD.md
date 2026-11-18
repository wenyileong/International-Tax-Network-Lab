# Scaffold plan: release 1.0.0rc3 and after

**Date:** 18 November 2026. **Base:** commit 2aa4a16 (engine and integration fixes from the review of 1.0.0rc2).

This plan lays out every feature suggested after the review, so that later work fits one structure. Each
feature has a home in the code, an interface, a test, and a decision on whether it can be built in this run.
A feature that cannot be built now is scaffolded only: its interface is registered (an engine at `interface`
status, a documented format, or a recorded proposal) so that the interface shows its boundary and next step,
as the Lab already does for the patented method.

## 1. Constraints that decide what can be built now

* **No network.** The workspace cannot reach the World Bank or any other data service (the proxy refuses
  them, and the Lab itself never goes online). No external dataset can be bundled in this run.
* **No other repository is changed.** The A-share scraper and Research-Suite-Core are separate projects;
  the vendored suite core in `src/rscore` is never edited by hand.
* **Legal content needs the author.** Coded tax rules must be verified against primary sources and recorded
  in the verification log by the author; software cannot supply them.
* **Approved results must not move.** Every new option defaults to the current behaviour, so the approved
  regression snapshots (`tests/regression/approved.json`) stay valid.
* **No new runtime dependency.** The Lab depends on networkx alone; new code uses the standard library.

## 2. Features

| # | Feature | Home | Decision |
|---|---|---|---|
| F1 | GDP reference data | `taxnetlab/reference.py`, Data page, `taxnetlab reference` | **Build** the store and the World Bank CSV reader; the data file is downloaded by the user (no network here) |
| F2 | Unconsolidated revenue for A-share groups | scraper (parent-only statements, 母公司报表) then `entity_financials` | **Scaffold**: proposal recorded; needs the scraper and a schema decision |
| F3 | Global minimum tax (Pillar Two) scenario | `engines/vtrl2018.py` parameters | **Build**, default off |
| F4 | Coded real tax rules (core jurisdictions) | coding templates, JAF Rule Bench | **Scaffold**: rule-pack format and route recorded; content is the author's |
| F5 | Change over time | `taxnetlab/timecompare.py`, API, Network page | **Build** (ownership changes between two dates) |
| F6 | Interest and royalty routes | new engine variant and tax tables | **Scaffold**: engine `vtrl2018.income_types` at `interface` status |
| F7 | Robustness to missing ownership data | new engine | **Scaffold**: engine `robustness.ownership` at `interface` status |
| F8 | Methods appendix export | `taxnetlab/methods_text.py`, Runs page, `taxnetlab appendix` | **Build**: Markdown, HTML and Word (.docx) |
| F9 | Compare two runs | `taxnetlab/rundiff.py`, Runs page, `taxnetlab diff` | **Build** |
| F10 | Native "Browse" for folders and files | `taxnetlab/picker.py`, `POST /api/pick` | **Build**; the page keeps the typed path as the fallback |
| F11 | Search by entity name on the Network page | `web/app.js` | **Build** |
| F12 | Progress for A-share imports | `taxnetlab/jobs.py` (generic tasks), Research Suite page | **Build** |
| F13 | Suite-side changes | Research-Suite-Core | **Scaffold**: proposals in `docs/SUITE_INTEGRATION.md` (unchanged) |
| F14 | Code signing; CI minutes | release process | **Author actions**: recorded in `RELEASING.md` |

## 3. Designs

### F1 GDP reference data
* Format read: the World Bank's own CSV download for indicator `NY.GDP.MKTP.CD` (four preamble lines, then
  `Country Name, Country Code, Indicator Name, Indicator Code, 1960, ..., YYYY`). Aggregates (regions, income
  groups) are dropped by keeping only assigned ISO 3166-1 alpha-3 codes from the jurisdiction registry.
* Store: `workspace/reference/<sha12>/` holding the original file, `values.json` and `meta.json` (source,
  indicator, file SHA-256, retrieved date stated by the user, years present, count). Reference sets are
  content-addressed and never edited.
* Use: `Api.complete_from_reference(dataset_id, reference_id, period)` derives a new dataset (through the existing
  `derive_dataset`) with `jurisdiction_attributes` GDP rows for the dataset's real jurisdictions and a `sources` row
  citing the World Bank with the licence class `public_attribution`. Jurisdictions without a value are reported,
  never filled.
* Tests: a fixture file in the World Bank layout; aggregates dropped; values and periods kept exactly; the
  derived dataset passes the GDP check of conduits and sinks; re-import gives the same reference id.

### F3 Global minimum tax scenario (labelled extension of van 't Riet and Lejour)
* Parameters: `minimum_tax_rate` (0 to 0.5; default 0 = off) and `substance_carve_out` (0 to 1; default 0).
* Model: a qualified domestic minimum top-up tax in every jurisdiction. Tax borne on the underlying profit in
  jurisdiction j becomes `t_j' = t_j + max(0, m - t_j)(1 - c)`. It replaces the statutory rate where the model
  uses tax already borne: the source's profit tax (t_S) and the world average used for conduits under credit
  relief. Where a jurisdiction taxes a dividend it receives (credit and deduction), its statutory rate stays,
  because dividends between group members are excluded from the minimum tax base. Withholding taxes are unchanged.
* The scenario is recorded in every result's assumptions and labelled an extension of the source model.
* Tests: the brute-force oracle with t_S and the world average replaced; off by default (approved snapshots
  unchanged); at m = 0.15 and c = 0 no route has t^e below 0.15; carve-out of 1 equals off.

### F5 Change over time
* `timecompare.ownership_changes(dataset, date_a, date_b)` lists relations present at only one date, and stakes
  that changed, using the same `valid_from`/`valid_to` rule as the Network page (end date inclusive).
* Jurisdiction summary: relations and cross-border relations gained and lost per jurisdiction.
* Surfaces: `GET /api/datasets/{id}/changes?from=&to=`, a card on the Network page, `taxnetlab changes`.

### F8 Methods appendix
* `methods_text.appendix(record, outputs, locale)` writes prose from the run record alone: data (name, hash,
  sources and licence classes), method (engine, version, status, specification), parameters and readings,
  assumptions, warnings, and how to reproduce; plus a citation of the software and of each source in OSCOLA form.
* Outputs: Markdown, HTML (static, no script) and Word (.docx written with the standard library; paragraphs
  and tables only). Output tables appear as Word tables, first 40 rows, with their hashes.
* Tests: every parameter and warning appears; the .docx opens as a valid ZIP with `word/document.xml`; no em dash.

### F9 Compare two runs
* `rundiff.diff(record_a, record_b, outputs_a, outputs_b)`: engine and version, dataset, parameter differences,
  assumption and warning differences, and per output table the rows added, removed and changed, keyed by the
  engine's declared output keys.
* Tests: identical runs give no differences; a changed parameter shows exactly that parameter and the changed rows.

### F10 Native file dialogs
* `POST /api/pick {kind: folder | sqlite | zip}` opens a Tk dialog in a worker thread and returns the chosen
  path, `null` when cancelled, or `{"available": false}` when Tk cannot be used (no display, or not bundled).
* Only on 127.0.0.1 with the session token, as every route. Tests cover the unavailable path and the response shape.

### F12 Progress for imports
* `JobManager.submit_task(kind, fn)` runs any callable with the existing tracker, progress and cancellation;
  `POST /api/suite/import_job` returns a job id, and the page polls `GET /api/jobs/{id}` as runs do.
  The suite importer's own progress callback feeds the tracker.

### F2, F4, F6, F7 (scaffold only)
* **F2** needs the scraper to extract parent-company statements, and a schema decision: `entity_financials` has one
  row per entity and period, so consolidated and parent-only figures cannot both be stored today. Proposal: a
  `consolidation` value per row and a primary key that includes it (a schema change with `added_in` rules), and a
  gb2017 parameter `revenue_basis`.
* **F4** uses the existing real-sample coding template as the rule-pack format; the route from JAF Rule Bench is an
  export in that format. The content is coded and verified by the author.
* **F6** `vtrl2018.income_types`: interest and royalty withholding, treaty rates and relief per income type; needs a
  written specification and new tax tables.
* **F7** `robustness.ownership`: repeated runs with relations thinned or stakes perturbed under a recorded seed,
  reporting how often each finding holds; needs a written specification.

## 4. Test of the plan before implementation
1. Scaffold first: the two interface engines and the new modules with their signatures. The full suite, the
   API documentation check, the self-test and the approved snapshots must all pass with the scaffold in place.
2. Tests for each feature to be built are written against the scaffold's interfaces before the code; they are
   expected to fail until the feature is implemented, and must pass afterwards.
3. Brute-force oracles (`tests/test_engine_oracles.py`) are extended for F3.
4. Browser smoke test in both languages; release as 1.0.0rc3.
