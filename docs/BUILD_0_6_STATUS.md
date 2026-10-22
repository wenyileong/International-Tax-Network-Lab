# Build 0.6 Status Report

**Project:** International Tax Network Lab
**Release:** 0.6.0 (project plan v2.5, s 10.3)
**Date:** 22 October 2026
**Status:** rule layer (treaty conditions and tri-state eligibility) and legal coding templates delivered; model comparison engine and page at `implemented`; author check pack and promotion gate in place; approved-output snapshots guard every earlier result. The method engines remain at `implemented` pending the author's checks; the patent-method engine remains at `interface`.

## 1. Pre-build logical evaluation (plan s 10.1)

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | Adding conditions to the routing engine could silently change the reproduction's outputs and stored runs. | Fatal if unaddressed | Approved-output snapshots taken **before** any change (`tests/regression/approved.json`); the default mode (`assume_eligible`) never reads the conditions; no new output table or column (summary rows and new withholding-basis values appear only in the extension modes); "nothing changes" tests with neutral facts. |
| 2 | Adding condition columns to the treaty table would change every dataset identifier. | Fatal if unaddressed | Separate table `tax_treaty_conditions` under the generation-2 hashing rule; snapshot datasets reproduced exactly. |
| 3 | Judgement-based conditions (principal purpose test, beneficial ownership) must never be resolved by default (plan s 5.2). | Serious | Assumptions default to `unresolved`; `strict` withholds such benefits, `contingent` grants them and flags every dependent pair; each assumption is a recorded run parameter. |
| 4 | The agreement rule needs the alternative readings of each source to be explicit. | Serious | Readings taken from the specifications' interpretation tables (vtrl2018 I2, I8; gb2017 I1, I5) and listed with their parameters in every comparison result. |
| 5 | A comparison could be read as a combined ranking. | Serious | No combined score; each measure keeps its namespace and definition; status of the comparison bounded by the lowest status compared. |
| 6 | Changing the synthetic generator would change every synthetic dataset for a seed. | Moderate | Conditions drawn from a separate random stream; every other table for a seed is unchanged (checked by the snapshots, which strip the new table). |
| 7 | A spreadsheet workbook would add a dependency to the executable (A38). | Moderate | ZIP of CSV files with a data dictionary; header-based import; guarded against oversized archives. |
| 8 | Status promotion relied on discipline alone. | Moderate | Verification records and a test that blocks `verified` without a completed record. |

**Found during the build**

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 9 | The Tax routes page failed to open after the treaty-condition controls were added (a control was used before its helper was defined); caught by the browser test, not by the Python suite. | Fatal | Fixed; every page is opened in both reading modes and both colour schemes in the browser test before release. |
| 10 | Output hashes differed between Python 3.11 and 3.12 for one reading of the conduits engine, because Python 3.12 changed floating-point `sum` (A36). | Serious | Exact summation (`math.fsum`) in all engines; snapshots now identical on both versions; CI runs them on Windows and Linux. |
| 11 | The Data page did not list `entity_financials` (since 0.4) or the new table. | Moderate | Listed; a test ties the page's table list to the schema. |
| 12 | Upstream caching could make a replay reuse a cached result instead of recomputing. | Moderate | Replay test clears the cache first; the cache is keyed on the content-addressed dataset, engine version and parameters. |
| 13 | Integer thresholds in templates were written as `365` but read back as `365.0`, breaking the round trip. | Minor | Thresholds written as floats; round-trip test passes byte for byte. |

## 2. What 0.6 adds

* **Treaty conditions and eligibility** (`docs/specs/eligibility.md`): new table; evaluator; routing-engine modes `assume_eligible` (default, the source), `strict` and `contingent`; scenario facts (holding size and period) and assumptions (beneficial ownership, principal purpose test, limitation on benefits); a "relies on an assumption" flag on the Tax routes page; synthetic worlds now carry fictional conditions.
* **Legal coding templates** (`src/taxnetlab/coding.py`): illustrative and real-sample templates with a three-layer data dictionary; import from the Data page, the API or `taxnetlab import`; `taxnetlab template`.
* **Model comparison** (`compare.models`, `docs/specs/compare_models.md`) and the **Compare** page: agreement grid, robustness shares of sink and conduit classifications, rank-correlation matrix, one measure under each reading, definitions side by side.
* **Author check pack** (`docs/verification/AUTHOR_CHECK_PACK.md`, generated from the specifications) and **verification records** for each engine.
* **Regression snapshots** of approved outputs for every engine on five datasets.

## 3. Tests and verification

* `pytest`: 217 tests on Python 3.12 (202 plus 15 optional differential tests skipped where Ripser, GUDHI and SciPy are not installed, as on Python 3.11 in CI). New: eligibility evaluator and engine modes, monotonicity of withdrawn benefits, "nothing changes" with neutral facts; template round trip, real-sample blanks, ZIP guards, API, CLI and server import; comparison ranks, agreement consistency, robustness shares, unranked engines, Spearman and Kendall by hand and against SciPy; promotion gate; check-pack freshness; approved snapshots.
* Self-test extended to the comparison, treaty-condition routing and template import.
* Browser tests (Chromium, light and dark): Compare, Tax routes in each eligibility mode, template import on the Data page, every page in both reading modes, phone width; no script errors.

## 4. For the author

1. Work through the check pack and complete the four records; then the engines can be promoted.
2. IP decision and the steps in IP note s 5A.
3. Code a first real sample with the real-sample template (it lists candidate jurisdictions with blank legal fields).
4. Physical Windows smoke test; licence decision; version tags.
