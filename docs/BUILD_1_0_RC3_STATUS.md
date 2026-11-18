# Release 1.0.0rc3 Status Report

**Project:** International Tax Network Lab
**Release:** 1.0.0rc3, third release candidate for 1.0
**Date:** 18 November 2026
**Plan:** `docs/PLAN_1_0_RC3_SCAFFOLD.md`

## 1. How the release was built

1. The corrections from the review of 1.0.0rc2 were committed first (commit 2aa4a16).
2. Every suggested feature was planned in one scaffold (`docs/PLAN_1_0_RC3_SCAFFOLD.md`), with its home in the code, its
   interface, its test, and a decision to build it now or scaffold it only.
3. The scaffold (two engines at `interface` status and five module interfaces) was tested against the existing code:
   the full suite, the API documentation check, the self-test and the approved regression snapshots all passed.
4. The tests for every feature to be built were written against the scaffold before any feature code and run to
   confirm that they failed. One test passed without the feature (an unknown parameter is ignored, and the synthetic
   world had no route below the floor); it was strengthened to require the parameter and a binding floor.
5. The features were implemented until those tests passed, then checked in the browser in both languages.

## 2. Built

| # | Feature | Where |
|---|---|---|
| F1 | GDP reference data from the World Bank's own CSV file | Data page; `taxnetlab.reference`; `/api/reference` |
| F3 | Global minimum tax scenario in tax routes (off by default) | Routes page; `minimum_tax_rate`, `substance_carve_out` |
| F5 | Ownership change between two dates | Network page; `/api/datasets/{id}/changes` |
| F8 | Methods appendix in Word, Markdown and HTML | Runs page; `/api/runs/{id}/appendix.docx` |
| F9 | Comparison of two runs | Runs page; `/api/runs/{id}/diff` |
| F10 | System file and folder dialogs | Research Suite page; `/api/pick` |
| F11 | Search by entity or jurisdiction name | Network page |
| F12 | A-share import in the background with a stage indicator | Research Suite page; `/api/suite/import_job` |

## 3. Scaffolded only, and why

| # | Feature | What is in place | What it waits for |
|---|---|---|---|
| F2 | Unconsolidated revenue for A-share groups | proposal in the plan | the scraper (parent-company statements) and a schema decision |
| F4 | Coded real tax rules | rule-pack format (the real-sample template) | the author's coding and verification |
| F6 | Interest and royalty routes | engine `vtrl2018.income_types` (interface) | a written specification and tax tables |
| F7 | Robustness to missing ownership data | engine `robustness.ownership` (interface) | a written specification |
| F13 | Suite-side changes | proposals in `docs/SUITE_INTEGRATION.md` | work in Research-Suite-Core |
| F14 | Code signing; CI minutes | `RELEASING.md` | a certificate; the Actions allowance |

No GDP data are bundled: the World Bank's service is not reachable from the build environment, and the Lab never
goes online. The researcher downloads the file once.

## 4. Decisions in the minimum tax scenario

The scenario models a qualified domestic minimum top-up tax in every jurisdiction: tax borne on profit becomes
`t + max(0, m - t)(1 - c)`. It replaces the statutory rate where the source model uses tax already borne (the source's
profit tax and the world average used for conduits under credit relief). Where a jurisdiction taxes a dividend it
receives, its statutory rate stays, because dividends between group members are outside the minimum tax base, and
withholding taxes are unchanged. Consequently the scenario raises every route's combined rate to at least the minimum
but leaves part of the treaty-shopping gain (the withholding saved) in place. Income inclusion and undertaxed-profits
rules are not modelled. The scenario is an extension, labelled as such in every result.

## 5. Defects found while building

| Defect | Severity | Resolution |
|---|---|---|
| A language chosen while the page was still starting was shown in the menu but not applied | Minor | Handler attached before the first language file loads; the last choice wins |
| The author check pack was stale after the specification change in the review commit | Minor | Regenerated |
| `submit` of a background import could be cancelled after writing began | Moderate (prevented) | Cancelling is allowed only before anything is written |

## 6. Tests

* Python 3.12: 298 passed. Python 3.11: 283 passed, 15 skipped (optional libraries).
* `tests/test_rc3_features.py` (10 tests) and `tests/test_engine_oracles.py` (7 tests, brute-force references).
* The self-test now runs the minimum tax scenario, a run comparison and a Word appendix; in CI it runs on the
  built executable and after installation.
* Browser test in English and Simplified Chinese: import with the stage indicator, Browse (hidden where no dialog
  can open), bring into the Lab, add the World Bank file and complete GDP, find an entity, change between dates,
  minimum tax control, two runs compared and the Word appendix downloaded; every page opened without errors.
* The Word appendix was opened in LibreOffice and converted to PDF to check headings, tables, lists and Chinese text.
