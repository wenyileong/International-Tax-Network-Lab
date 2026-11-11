# Release 1.0.0rc2 Status Report

**Project:** International Tax Network Lab
**Release:** 1.0.0rc2, second release candidate for 1.0 (project plan v2.6; Research Suite integration)
**Date:** 12 November 2026

## 1. What this release adds

| Request | Delivered |
|---|---|
| An A-share converter | Research Suite page and `taxnetlab import-ashare`: a release is read, imported into a suite project with the suite's own converter (vendored `rscore` 0.4.0, unmodified, pinned to a commit), reviewed, re-imported with the saved jurisdiction choices, and brought into the Lab as a dataset with provenance. `taxnetlab suite list / review / choose / reimport / bring` on the command line. |
| A Chinese translation | Simplified Chinese (`zh-Hans`): every interface string (983, checked for parity and placeholders by a test), the user guide and the method notes. Terms follow the suite's own translation (研究工具套件, 数据发布, 通道与汇点). |
| A custom icon | Indigo rounded square with a four-jurisdiction network and the cheapest route in green, in the family of the Research Suite icon; `.ico` for the executable, installer and uninstaller entry; SVG favicon and top-bar logo; drawn by `packaging/icon/make_icon.py`. |
| Features for seamless use in the suite | Projects shared with ResearchSuite.exe in both directions; its recent projects and language read from its settings; `--import PATH` and `--language TAG` hand-over; installer registry key; a completion template and derived datasets for the GDP and tax rules a release lacks; provenance on the Overview page; proposals for the suite side in `docs/SUITE_INTEGRATION.md`. |

## 2. Pre-build evaluation and findings

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | A converter written for the Lab would duplicate the suite's and, sooner or later, keep different rows from the same release. | Serious | No second converter: the suite core is vendored unmodified; tests fail if a vendored file is edited or if the importer gains a rejection reason without an interface label. |
| 2 | A suite export carries the whole jurisdiction registry (about 250 rows); persistent homology and the matrix would treat 240 empty jurisdictions as observations. | Serious | Unused registry jurisdictions are left out on hand-over by default (parents kept); the number is recorded in the dataset's provenance; the option can be turned off. |
| 3 | Releases have no GDP or tax rules, so conduits and sinks, tax routes and default persistent homology are blocked. | Moderate | Dataset completion (template for the dataset's own jurisdictions; derived dataset); persistent homology now runs without a period when only link features are chosen, and its message says so. |
| 4 | The start-up hand-over writes a path chosen outside the interface into the page. | Moderate | Written as HTML-escaped JSON in a `meta` element (no inline script; the content security policy is unchanged); a test injects quotes and angle brackets. |
| 5 | The interface accepts file paths for releases and projects. | Moderate | Accepted only with the session token on 127.0.0.1, as before; projects must be `.sqlite` or `.db` files; new projects are created only in the workspace; file-system errors are reported as user errors. |
| 6 | A Windows checkout with automatic line-ending conversion would fail the vendored-hash test. | Minor | Hashes compared on LF-normalised bytes. |
| 7 | Tests could read the developer's own ResearchSuite.exe settings. | Minor | Settings location redirected for every test. |
| 8 | Path fields rendered several hundred pixels tall (found in the browser smoke test). | Minor | Fixed. |
| 9 | The free-text notes of an import report are English only, also in the Chinese interface. | Minor | Open; proposed to the suite (message codes), `docs/SUITE_INTEGRATION.md` item 5. |

## 3. Tests

* Python 3.12: 274 passed. Python 3.11: 259 passed, 15 skipped (optional topology libraries not installed).
* New: `tests/test_ashare_import.py` (vendored copy unedited; reason codes; release inspection; import, review, choices, re-import, hand-over and provenance; natural persons absent from the Lab; existing projects and subsets; suite recent projects and language; trimming; dataset completion; persistent homology without a period; command line; start-up hand-over and escaping); Simplified Chinese parity and guide sections; every new route answers.
* `taxnetlab selftest` now imports the demonstration release with the bundled core, applies a choice, brings the project into the Lab, and checks the Chinese strings, the Chinese guide and the icon over HTTP; in CI this runs on the built executable and after installation.
* Browser smoke test in English and Simplified Chinese: read, import, review, save and import again, bring into the Lab, then every page; no script errors and no error messages.

## 4. Conditions for 1.0

Unchanged from `docs/BUILD_1_0_RC1_STATUS.md`: verification records, a replication on real data, the physical Windows test, the licence and a DOI remain the author's. The A-share route gives a first source of real, public data for the network pages and topology; it does not support a replication of Garcia-Bernardo and others (2017), which needs global coverage.
