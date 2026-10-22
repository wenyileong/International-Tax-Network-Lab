# Release 1.0.0rc1 Status Report

**Project:** International Tax Network Lab
**Release:** 1.0.0rc1, release candidate for 1.0 (Phase 9, software part; project plan v2.6)
**Date:** 23 October 2026

## 1. Conditions for 1.0 (plan s 1.4)

| Condition | State | What remains |
|---|---|---|
| At least two of the three method engines at `verified` | Three method engines at `implemented`, each passing every test against its specification; check pack and records ready; the promotion gate is enforced by a test. | **Author:** check the specifications against the sources and complete the records in `docs/verification/records`. |
| At least one engine `replicated` or `replicated_with_discrepancies` | Expectation register, replication reports and a draft entry for Garcia-Bernardo and others (2017) in place; column mapping for database exports; reference benchmarks at the source's scale. | **Author:** check and freeze the expectation; obtain the real (licensed) data; run and check. |
| The data layer imports, validates, versions and documents real datasets | Done: header-based CSV and ZIP import with column mapping; validation with ISO registry; content-addressed versions; sources and licence classes; verification log; coding templates with a data dictionary. | Coding of a first real sample (author). |
| Every result can be replayed from its run record | Done: replay, stale marking, approved-output snapshots identical on Windows and Linux and on Python 3.11 and 3.12; export packages reproduced in another workspace. | None in software. |
| Executable and installer install and run on physical Windows 10 and 11 and pass the smoke test (s 11.1) | Executable and per-user installer built by CI, installed without administrator rights, self-tested (including that nothing is written inside the installation folder) and uninstalled on a Windows runner. | **Author:** the physical smoke test on Windows 10 and 11. |
| User and method documentation complete | Done: user guide (in the interface and `docs/USER_GUIDE.md`), method notes, glossary, specifications, generated API reference, release checklist. | Review by the author. |
| Citable: licence, `CITATION.cff`, archived release with a DOI | `CITATION.cff` and `.zenodo.json` ready. | **Author:** choose the licence; tag the release; archive on Zenodo; add the DOI. |

## 2. Non-functional requirements (plan s 11)

| Requirement | State |
|---|---|
| Executable without Python, administrator rights or internet; portable and installer; binds to 127.0.0.1; free port; never writes inside its folder | Met; the last checked in CI after installation. |
| Interactive views within two seconds on a reference dataset; long runs in the background with progress and cancellation | Met for the synthetic reference worlds; background jobs with cancellation. |
| Scale | Tax routing at 108 jurisdictions about 6 s; conduits and sinks at 50,000 entities about 6 s; persistent homology at 108 jurisdictions about 7 s (build machine). |
| Reliability | Run records written atomically; cancelled runs store nothing; parallel background runs give identical results (tested). |
| Portability | Windows executable; library and CLI tested on Windows and Linux. |
| Security and privacy | Local only; no telemetry; session token on POST; host-header check; content security policy; tier B packages withhold licensed data. |
| Maintainability | Coverage 91 per cent, reported in CI; specifications versioned with the code; build manifest in every executable. |
| Accessibility | WCAG AA contrast for text in both themes (tested); skip link; labelled charts with CSV data; both reading modes complete. |

## 3. Pre-build evaluation and findings

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | A version called 1.0 would claim conditions only the author can satisfy (A44). | Serious | Release candidate; `RELEASING.md` lists the remaining conditions. |
| 2 | The upstream-engine cache was shared by parallel background runs without a lock. | Serious | Lock added; a test runs eight comparison, sweep and topology jobs at once and checks identical results. |
| 3 | The smoke test's display-theme step had no control (A43). | Moderate | Theme selector. |
| 4 | An installer that needed administrator rights or wrote into its folder would breach s 11. | Moderate | Per-user Inno Setup installer; CI checks the folder is unchanged after the self-test. |
| 5 | Documentation could drift from the code. | Moderate | API reference generated from the code, the user guide copy and the check pack compared by tests. |

## 4. Tests

261 tests on Python 3.12 (246 plus 15 optional differential tests on 3.11), coverage 91 per cent; self-test of 30 checks; browser smoke test of every page in both reading modes and both themes.
