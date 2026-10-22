# User guide

International Tax Network Lab is a research workbench for international tax and corporate ownership networks. It runs published methods faithfully, records exactly how every result was produced, and lets you replay, compare, report and export results. It gives no tax or legal advice, and a jurisdiction's position in a network is not evidence of avoidance, misconduct or illegality.

## 1. Starting

**Windows.** Run the installer (no administrator rights needed) or the portable `taxnetlab.exe`. A console window opens and shows the local address; the interface opens in your browser. Close the console window, or press **Quit**, to stop. Nothing is sent over the network: the server listens on `127.0.0.1` only.

**From source.** Python 3.11 or newer: `pip install -e .` then `python -m taxnetlab`.

**Workspace.** Your datasets, runs, expectations, reports and logs are kept in a workspace folder: `Documents\TaxNetLab` on Windows, `~/TaxNetLab` elsewhere. Choose another with `--workspace DIR` or the `TAXNETLAB_WORKSPACE` environment variable. The software never writes inside its own installation folder.

On first launch a small synthetic world is created so that every page has something to show. Synthetic data are fictional throughout and are marked as such on every chart and export.

## 2. Reading modes and languages

The top bar switches between **Plain English** (default) and **Technical** wording. Every chart has guidance on how to read it, open in Plain English and folded away in Technical mode. Interface text comes from locale files; English (UK) is complete, and other languages can be added without changing the code (`docs/TRANSLATING.md`).

## 3. Data

A dataset is a set of tables (CSV files with a header row; columns are matched by name, in any order). Required: `sources`, `jurisdictions`, `entities`, `ownership`. Optional: jurisdiction attributes (GDP), the tax-rule tables, revenue, treaty conditions and the verification log. The **Data** page shows each table with its column definitions and a validation report.

Conventions: rates and shares are fractions (0.25 is 25 per cent); real jurisdictions use ISO 3166-1 alpha-3 codes and fictional ones the `FIC_` prefix; ownership is stored holder to held; natural persons are excluded; nothing is repaired or imputed silently; synthetic records may never refer to a real jurisdiction.

Datasets are **content-addressed**: the identifier is a hash of the tables, so the same content always has the same identifier, and any change makes a new dataset. Old datasets stay readable.

**Adding data.**
* *Synthetic generator* (Data page or `taxnetlab generate`).
* *CSV import*, one file per table. For files exported from a database with its own column names, give a **column mapping**, for example `{"ownership": {"holder_id": "Shareholder BvD ID", "source_id": "=ORBIS_2025"}}` (`=value` sets a constant).
* *Legal coding templates*: the illustrative template (fictional, complete) shows the format; the real-sample template lists the jurisdictions you choose with every legal field blank and `verified` set to false. Fill in the legal fields from the sources, then import the ZIP. The data dictionary in each template explains every column and its coding layer (liability, collection, observation).
* *Verification log* (`rule_verifications`): who checked which legal row, when, against which source and with what outcome.

Unverified legal rows can be used, but every result that relies on them is flagged.

## 4. The analysis pages

* **Network**, **Matrix**: the ownership network in ownership or value-flow direction, and a jurisdiction-by-jurisdiction matrix.
* **Tax routes** (van 't Riet and Lejour): the cheapest route for dividends from a host to a home jurisdiction, the treaty-shopping gain, and conduit rankings. Move a tax rate or a treaty and everything recomputes. **Treaty conditions** can be applied: holding thresholds are checked against facts you set, and the beneficial ownership, principal purpose and limitation-on-benefits tests stay undecided unless you record an assumption. *Strict* withholds undecided benefits; *contingent* keeps them and flags the routes that rely on them.
* **Conduits and sinks** (Garcia-Bernardo and others): where corporate value ends up relative to the size of the economy, and through which jurisdictions it passes.
* **Topology** (persistent homology): clusters and loops among jurisdictions across all scales, and which jurisdictions the structure depends on.
* **Compare**: the methods' measures side by side; a rank is shown only where every reading of the source agrees.

Live results on these pages are **exploratory previews**: they are not stored and carry an "exploratory" mark. **Save as run** records the exact state as a run.

## 5. Runs

A **run** is one engine on one dataset with one set of parameters. Its record is immutable and holds the parameters and assumptions, the data identifiers, warnings, the calculation trace, the hash of every output and the software environment. On the **Runs** page:

* **Execute** runs in the background with progress; **Cancel** stops it and stores nothing.
* **Replay** re-executes a run and compares every output hash.
* **Report (HTML)** is a self-contained report suitable for archiving with a paper.
* **Export package** writes a ZIP by reproducibility tier: A (public data: everything), B (licensed data: no data tables, outputs only if the licence permits), C (synthetic: everything, labelled synthetic). Another researcher reproduces it with **Reproduce** or `taxnetlab reproduce`.
* A run is marked **stale** when the engine's version or status has changed since.

**Sensitivity sweeps** (`sensitivity.sweep`) run a method over a grid of parameter values and report how stable each jurisdiction's rank and classification are.

## 6. Status of methods

Every engine carries a status, shown on every result: *interface* (registered, cannot run), *specified*, *implemented* (passes every test against its specification), *verified* (the specification has been checked against the source by the author, with a completed record in `docs/verification/records`), *replicated* or *replicated with discrepancies* (published results matched on real data under a frozen expectation). Results from engines below *verified* carry an "unverified method" mark.

The engine for the patented topological method (US 10,417,262 B2) stays at interface status pending the IP decision; persistent homology is a separate, published method.

## 7. Replicating a published result

1. Write an expectation entry (drafts are in `docs/expectations`): the published results, the statistic, the tolerance and the decision rule.
2. **Freeze** it (Runs page or `taxnetlab expect freeze FILE --by NAME`). A frozen entry cannot be changed; a correction is a new entry that supersedes it.
3. Import the real data, run the engine with the parameters the entry requires, and **check** the run against the entry. A run made before the entry was frozen is refused.

## 8. Command line

```text
taxnetlab [serve] [--workspace DIR] [--port N] [--no-browser]
taxnetlab generate --seed 42
taxnetlab datasets
taxnetlab import FILE.zip|FOLDER [--name TEXT] [--mapping MAP.json]
taxnetlab template illustrative|real-sample [--jurisdictions NLD,LUX]
taxnetlab run SPEC.json
taxnetlab replay RUN_ID
taxnetlab export RUN_ID [--include-outputs] [--report FILE.html]
taxnetlab reproduce PACKAGE.zip
taxnetlab expect list | freeze FILE --by NAME | check ENTRY_ID --run RUN_ID
taxnetlab selftest
taxnetlab version
```

## 9. Troubleshooting

* *The browser did not open*: open the address shown in the console window.
* *Windows SmartScreen warns*: the executable is not code-signed; compare its SHA-256 with `SHA256SUMS.txt` from the release, then choose More info, Run anyway.
* *A run is slow*: large tax-routing worlds enumerate many near-optimal routes; the bounds (`max_intermediates`, `max_routes_per_pair`, `route_budget`) are reported when they bind. Run it from the Runs page, where it runs in the background.
* *Something went wrong*: details are written to the log file in the workspace (`logs/taxnetlab.log`).

## 10. Privacy

Everything stays on your computer. There is no telemetry and no network access at run time. Licensed data are never written to export packages beyond what you confirm the licence permits.
