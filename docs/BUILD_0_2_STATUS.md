# Build 0.2 Status Report

**Project:** International Tax Network Lab
**Release:** 0.2.0 (project plan v2.1, Phase 0 and Phase 1, with the first part of Phase 2)
**Date:** 20 October 2026
**Status:** core contracts, data layer, views, run records, offline interface and Windows executable implemented and tested. The three published-method engines remain at `interface` status by design.

## 1. Pre-build logical evaluation (plan s 10.1, gate 1)

The Phase 1 design was checked against Build 0.1 and plan v2.1 before implementation. Issues found during the build were added with their fixes.

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | Streamlit cannot be packaged into a reliable single-file executable, re-runs the whole script on each interaction (the cause of Appendix B, B4) and is not needed once the plan's local-server interface exists. Keeping it until Phase 2 exit, as the plan said, would mean maintaining two interfaces over a changing API. | Serious | Retired in 0.2, earlier than planned. The local server and browser interface replace it. Recorded as a deviation (s 4). |
| 2 | The plan's stack included pandas and NumPy. They add tens of megabytes to the executable, and pandas formatting varies between versions, which was the root of the unstable hashes in Build 0.1 (B1). | Serious | Core uses plain Python tables plus NetworkX. Canonical serialisation is implemented directly (plan s 7.2). pandas is an optional notebook extra. The Windows executable is about 11 MB. |
| 3 | A local server reachable from the browser can be driven by any website the user visits (cross-site requests) or reached through DNS rebinding. | Serious | Bound to 127.0.0.1 only; `Host` header checked; every state-changing request needs a per-session token in a custom header (which cross-origin pages cannot send without a preflight the server never approves); JSON content type required; no CORS headers; Content Security Policy on the page; static paths confined to the bundled folder. |
| 4 | Port collision with the JAF Rule Bench (which uses 8765). | Moderate | Default port 8766 with automatic fallback. |
| 5 | Plotly.js must work offline; loading it from a CDN would break the offline and no-network guarantees. | Moderate | Plotly.js 4.1.1 (MIT) bundled in `web/vendor`. Its built-in colour scales do not include Plasma, so a Plasma-like ramp is defined explicitly (found in testing). |
| 6 | Network layout: NetworkX layouts need NumPy and SciPy, which issue 2 removes. | Moderate | Deterministic layout without numerical libraries: jurisdictions on a circle, their entities on small rings. Reciprocal edges are offset so that both remain visible (found in testing). |
| 7 | Language switching must not require code changes, and validation messages are produced on the server. | Moderate | All interface text in `web/locales/*.json` with a fallback chain and text direction; the server returns issue codes and parameters that the interface translates. Tests fail on any missing key. |
| 8 | Dataset identity: should the name be part of the hash? | Minor | No. The id is a content address over canonical tables; the name is metadata. Two imports of identical content share one id. |
| 9 | Interrupted writes (console window closed during a run). | Moderate | Datasets and runs are assembled in a temporary folder and renamed into place; temporary folders older than an hour are removed at start-up; listing ignores them. |
| 10 | Rejected POST requests left their body unread on a kept-alive connection, corrupting the next request; a negative `Content-Length` could block a server thread (found in review). | Serious | The body is read (bounded) before any check; invalid lengths close the connection. Regression tests added. |
| 11 | Engine outputs were returned to the interface as text, so numeric columns sorted and aligned as strings (found in testing). | Moderate | The API converts stored numeric strings back to numbers for display; stored files are unchanged. |
| 12 | `Object.assign` on chart layouts replaced whole axis objects, so dark-mode grid colours were lost (found in testing). | Minor | Axis, legend and font settings are merged. |
| 13 | Hidden form fields reappeared because `.field { display: flex }` overrode the `hidden` attribute (found in testing). | Minor | `[hidden] { display: none !important }`. |
| 14 | Click handlers accumulated on the network chart when the view changed, causing an error when an earlier view's handler ran (found in testing). | Moderate | One listener per chart, dispatching to the latest drawing's handler. |

No fatal issue remained open when implementation began.

## 2. What 0.2 contains

* **Domain and data layer** (`schema.py`, `datasets.py`, `canonical.py`): typed table schemas with header-based column matching; cross-table integrity checks (referential integrity, ISO and `FIC_` identifier rules, no natural persons, direct relations only, parallel relations kept and reported, equity over 100%, ownership cycles, currency and period checks, and a block on attributing synthetic data to real jurisdictions); content-addressed datasets with canonical CSV and SHA-256 hashes; atomic storage with tamper detection.
* **Synthetic data** (`synthetic.py`): a seeded generator (the seed changes the data) and the Build 0.1 fixture converted to fractions. All amounts use ISO 4217 code `XTS` (reserved for testing).
* **Views** (`views.py`): ownership (holder → held), value flow (held → holder) and jurisdiction aggregation (count, fraction sum, value sum), with as-of filtering, exclusion lists and a refusal to add different currencies.
* **Engines** (`engines/`): the engine interface and status ladders of plan s 3 and s 4.2; outcome states; a demonstration engine (`demo.link_summary`, specification in `docs/specs/`); the three published-method engines at `interface` status.
* **Runs** (`runs.py`): immutable run records with their own content hash, output hashes, dataset hashes, parameters, validation report, calculation trace, environment and build details; replay; stale flags when an engine's version or status changes.
* **Service layer, server and CLI** (`api.py`, `server.py`, `cli.py`).
* **Interface** (`web/`): Overview, Network, Matrix, Data (viewer, validation, generator, CSV import), Runs, Methods, About. Minimalist layout, colourful charts, light and dark themes, phone-width layout, chart export as PNG, SVG and CSV, watermarks for synthetic data and demonstration or unverified engines, language menu.
* **Packaging and CI**: PyInstaller specification; build manifest (version, commit, dirty flag, lock-file hash, build time) embedded in the executable and written into run records; hash-locked build environment; GitHub Actions running the tests on Windows and Linux (Python 3.11 and 3.12), building `taxnetlab.exe` on a Windows runner, self-testing the built executable and publishing it as an artefact, and as a release asset for `v*` tags.

## 3. Tests and verification

* `pytest`: 72 tests covering schema parsing, every integrity rule, canonical hashing (including the B1 regression), storage and tamper detection, generator determinism, direction conventions, parallel relations, as-of filtering, aggregation rules, the engine registry and ladders, parameter validation, a hand-calculated fixture, property-based identity tests (Hypothesis), metamorphic scaling and relabelling tests, run records, replay, tampering, blocked runs storing nothing, stale flags, server protections (host check, token, content type, CORS, path traversal, keep-alive safety, invalid lengths) and language coverage. All pass on Python 3.11 and 3.12 (Linux, locally); CI runs the same suite on Windows.
* `taxnetlab selftest`: end-to-end check (starter dataset, validation, run, replay, blocked engine, server pages, offline Plotly, locales, token enforcement) in a temporary workspace whose path contains spaces and non-ASCII characters. Passes from source and from a frozen Linux build; CI runs it on the Windows executable.
* Browser tests (headless Chromium): every page in light and dark themes and at phone width with no script errors; network node selection; CSV import of a valid and an invalid dataset; synthetic generation; language switching including a right-to-left test locale, remembered after reload; Quit stops the server.

These checks establish the tested behaviours only. They do not validate any published method, which no engine in this release implements.

## 4. Deviations from plan v2.1

1. Streamlit retired at 0.2 rather than at Phase 2 exit (issue 1).
2. pandas and NumPy dropped from the core (issue 2); plan s 4.5 should be read accordingly.
3. Two Phase 2 items arrived early: CSV import with validation and the seeded generator.
4. The workspace location is a default folder (with an override) rather than chosen on first launch; a folder chooser needs a native dialogue and is deferred.

## 5. Appendix B (Build 0.1 defects): closure

| # | Status |
|---|---|
| B1 hashing over literal `\n` | Fixed: canonical CSV; test compares with the hash of the stored file. |
| B2 synthetic flag from label | Fixed: derived from the sources table. |
| B3 seed without effect | Fixed: seeded generator. |
| B4 manifest per rerun; interface state as parameter | Fixed: runs only on explicit execution; parameters limited to engine parameters (tested). |
| B5 parallel edges overwritten | Fixed: `MultiDiGraph`; parallel relations reported, not merged. |
| B6 missing entities | Fixed: referential integrity blocks import. |
| B7 optional value read unconditionally | Fixed: optional with warnings; never imputed. |
| B8 no arrowheads | Fixed: arrowheads and direction in the legend note. |
| B9 percentages | Fixed: fractions throughout. |
| B10 thin direction test | Fixed: forward and reverse edges tested for both views. |
| B11 no Git, caches, no lock | Fixed: Git with the 0.1 baseline tagged `v0.1.0`; caches ignored; hash-locked build environment. |
| B12 fragile `locals()` | Removed with the Streamlit shell. |

## 6. Known limitations

1. No published method is implemented; the next substantive work is Phase 3 desk research (source archiving, specifications, feasibility, the IP gate).
2. The executable is unsigned; Windows SmartScreen may warn (plan s 11.2). Checksums are published.
3. CI tests the executable on a Windows runner. The physical-machine smoke test of plan s 11.1 remains a manual release step.
4. Long runs execute synchronously; background jobs with progress and cancellation are needed before real-data engines (Phase 7).
5. Datasets are stored as CSV and re-validated on load; DuckDB and Parquet storage are deferred until data sizes require them.
6. The software licence is undecided (Phase 0 open item).
7. Plain English and Technical reading modes (plan s 8) are not yet implemented; the language infrastructure is in place.

## 7. Next steps

1. Decide the licence (plan s 4.6).
2. Run the physical Windows smoke test on the CI-built executable.
3. Phase 3: archive the three sources, write versioned specifications and complete the replication-feasibility notes and the IP gate.
