# Build 0.7 Status Report

**Project:** International Tax Network Lab
**Release:** 0.7.0 (Phase 7, software part; project plan v2.6)
**Date:** 22 October 2026
**Status:** the software needed to work with real data and to replicate published results is in place: verification log for legal rows, jurisdiction registry, expectation register with replication reports, column mapping for database exports, a faster routing engine with stated reference benchmarks, and background runs with progress and cancellation. Replication itself needs real (in part licensed) data and the author's frozen expectations, so no engine is `replicated` yet.

## 1. Pre-build logical evaluation

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | The near-optimal route enumeration grew so fast that 60 jurisdictions took 35 s and 108 (the source's sample) was impractical. | Serious | Index-based leg costs and successors pre-sorted by cost plus an admissible bound, so the search stops scanning as soon as no candidate can fit; routes counted, not stored. 108 jurisdictions now take about 6 s. Identical outputs confirmed by the approved snapshots and the existing brute-force differential test. |
| 2 | A replication could be judged against expectations written after seeing the results (plan s 7.5). | Serious | Frozen entries are hashed and immutable; corrections are new entries that supersede; a check is refused when the run started before the entry was frozen, when its parameters differ from those the entry requires, or when the run record has been modified. Reports are stored once and never rewritten. |
| 3 | Legal rows had no verifier and date (A37); adding columns would change dataset identifiers. | Moderate | `rule_verifications` table under the generation-2 rule; rows must refer to existing legal rows; inconsistent flags are warned about. |
| 4 | Real exports (for example Orbis) do not use the schema's column names. | Moderate | Column mapping per table, including constants; unmapped or absent columns are errors; the mapping is kept in the dataset's metadata. A mapped file gives the same dataset identifier as the same content imported directly (tested). |
| 5 | Long runs blocked the interface with no way to stop them (plan s 11). | Moderate | Background jobs with progress and cooperative cancellation; a cancelled run stores nothing. |
| 6 | Real jurisdiction codes were checked for form only. | Minor | ISO 3166-1 alpha-3 registry bundled; unassigned codes are warned about (not rejected, since some sources use user-assigned codes); the real-sample template names each jurisdiction. |
| 7 | Comparing `started_utc` with millisecond precision and a frozen time without it as text gave the wrong order (found in testing). | Serious | Times are parsed before comparison; frozen times carry milliseconds. |

## 2. Reference benchmarks (scripts/benchmark.py, Linux build machine, Python 3.12)

| Engine | Reference size | Time |
|---|---|---|
| Tax routing | 108 jurisdictions, 40 per cent treaty density | about 6 s |
| Conduits and sinks | 60 jurisdictions, 50,000 entities | about 6 s |
| Persistent homology | routing cost, 108 jurisdictions | about 7 s |
| Model comparison | 20 jurisdictions, nine engine runs | under 1 s |

`tests/test_performance.py` holds generous budgets so that an algorithmic regression fails CI.

## 3. Draft expectation entry

`docs/expectations/gb2017-ofc-classification.draft.json`: the 24 sink-OFCs (Table 1) and five conduit-OFCs (p 6) of Garcia-Bernardo and others (2017), transcribed from the open-access version through automated extraction and converted to alpha-3 codes. It is a draft: the author checks it against the published table and freezes it before any run on real data.

## 4. Tests

239 tests on Python 3.12 (224 plus 15 optional differential tests skipped on Python 3.11), including new tests for jobs and cancellation, the expectation register and replication verdicts, column mapping, the verification log, the registry and performance budgets; self-test extended to a background job.
