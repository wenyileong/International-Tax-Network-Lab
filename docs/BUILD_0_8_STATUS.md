# Build 0.8 Status Report

**Project:** International Tax Network Lab
**Release:** 0.8.0 (Phase 8: comparison, sensitivity and outputs; project plan v2.6)
**Date:** 22 October 2026
**Status:** sensitivity sweeps with robustness shares, self-contained run reports, export packages by reproducibility tier with reproduction from a package, and publication-style figure export. The plan's Phase 8 exit gate (a Tier B package reproduced on a second Windows machine with the same licensed inputs) needs licensed data and a second machine; the software path is tested end to end with Tier C and Tier B packages between workspaces.

## 1. Pre-build logical evaluation

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | A sweep could hide failed draws by ranking what was left (plan s 6.3). | Serious | Draws that cannot run are listed with the reason, counted and excluded; never treated as zero. |
| 2 | Licensed data must never leave the workspace in an export (plan s 11, security). | Fatal if unaddressed | Tier from the sources' licence classes; tier B packages hold no data tables and no outputs unless the researcher confirms the licence permits it; tested. |
| 3 | A package altered after export could be "reproduced" against altered data. | Serious | Manifest of SHA-256 hashes for every file; reproduction refuses an altered package; tested. |
| 4 | Reports could carry script or unescaped text from research questions or data. | Moderate | Static HTML, every value escaped, no external resources; tested with markup in the research question. |
| 5 | Publication figures must not drop the watermarks that mark unverified methods or synthetic data. | Moderate | Publication export restyles the chart (white, serif, black ink) and keeps every annotation. |
| 6 | The Runs page note still said the published-method engines could not run (stale since 0.3; found in the browser test). | Minor | Rewritten. |
| 7 | The run view drew bar charts of long tables (one row per draw), which are meaningless (found in the browser test). | Minor | Charts only for one row per jurisdiction. |

## 2. What 0.8 adds

* **`sensitivity.sweep`** (`docs/specs/sensitivity.md`): every combination of a parameter grid for any method engine (up to 200 draws); rank range and median, share in the top k, robust top-k membership at a stated share, shares classified as sink or conduit.
* **Run reports** (`/api/runs/<id>/report.html`, `taxnetlab export --report`): question, method and status, data and sources, parameters, assumptions, warnings, trace, every output with its hash, environment, replay instructions, software citation.
* **Export packages** (`/api/runs/<id>/package.zip`, `taxnetlab export`) by tier A, B or C, byte-identical on each export; **reproduction** from a package in another workspace (`taxnetlab reproduce`, Runs page).
* **Publication figures**: a chart button that exports SVG with a white background and serif type.

## 3. Tests

253 tests on Python 3.12; self-test extended to export and reproduction in a second workspace and to the report; browser smoke test of every page in both reading modes and both colour schemes, and a sweep run through the background job.
