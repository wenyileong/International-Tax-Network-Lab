# International Tax Network Lab

A local-first research workbench for analysing international tax and corporate ownership networks. It is built to implement published methods faithfully and keep them separate, to record exactly how every result was produced, and to let a researcher inspect, compare and export results to a standard fit for peer-reviewed work.

**Release 0.4.** Core contracts, data layer, network views, run records with replay, a minimalist offline interface and a Windows executable (0.2), plus the **optimal tax routing engine** of van 't Riet and Lejour with **live exploration**: move a tax rate or a treaty and watch the cheapest routes, treaty-shopping gains and conduit rankings recompute. Release 0.4 adds the **conduits and sinks engine** of Garcia-Bernardo and others with its own live page, and **Plain English and Technical reading modes**. Both method engines are at *implemented* status: they pass every test against their specifications and become *verified* once those specifications have been checked against the source papers. The topological method (US Patent 10,417,262 B2) stays at *interface* status pending the author's decision on the IP gate (`docs/IP_GATE_US10417262.md`). See `docs/PROJECT_PLAN_v2_3.md` and `docs/BUILD_0_4_STATUS.md`.

> The data shipped with the software are synthetic. Every jurisdiction, company, value and rate is fictional. The software gives no tax or legal advice, and network position, centrality or clustering is not evidence of avoidance, misconduct or illegality.

## Using the Windows executable

1. Download `taxnetlab.exe` and `SHA256SUMS.txt` from the latest GitHub Release, or from the `taxnetlab-windows-x64` artefact of the latest successful **CI** workflow run.
2. Optionally check the file: `certutil -hashfile taxnetlab.exe SHA256` should print the value in `SHA256SUMS.txt`.
3. Double-click `taxnetlab.exe`. A console window opens and shows the local address; the interface opens in your default browser. The executable is unsigned, so Windows SmartScreen may ask you to confirm (More info, then Run anyway).
4. Close the console window, or press **Quit** in the interface, to stop.

No installation, Python or administrator rights are needed, and nothing is sent over the network. The server listens on `127.0.0.1` only, from port 8766 (the JAF Rule Bench uses 8765, so both can run together).

Your work is kept in a **workspace** folder: `Documents\TaxNetLab` on Windows (`~/TaxNetLab` elsewhere). Use `taxnetlab.exe serve --workspace D:\path\to\folder` or the `TAXNETLAB_WORKSPACE` environment variable to choose another.

Command-line use of the same executable:

```text
taxnetlab.exe                       start the interface (same as "serve")
taxnetlab.exe generate --seed 42    create a synthetic dataset
taxnetlab.exe datasets              list datasets
taxnetlab.exe run spec.json         execute a run specification
taxnetlab.exe replay RUN_ID         re-execute a stored run and compare hashes
taxnetlab.exe selftest              end-to-end check in a temporary workspace
taxnetlab.exe version               version, build and environment details
```

A run specification is a small JSON file:

```json
{"engine_id": "demo.link_summary", "dataset_id": "d4ee06ae7a4282d4",
 "parameters": {"relation_type": "equity"}, "research_question": "..."}
```

## The interface

| Page | What it shows |
|---|---|
| Overview | Size and composition of the dataset, ownership-fraction distribution, validation report. |
| Network | Ownership (holder → held), value-flow (held → holder) or jurisdiction-aggregated views. Edge colour and width show the size of each relation; node colour shows the jurisdiction. Click a node for its records. |
| Matrix | Holder-jurisdiction by held-jurisdiction heatmap under a stated aggregation rule. |
| Tax routes | Live explorer for the optimal tax routing model: choose a host and a home jurisdiction, change corporate tax, withholding, relief and treaty rates with sliders, and see the cheapest route, its legs, the treaty-shopping gain for every pair and conduit centrality update at once. Sweeps plot a route's tax across a rate's range. Live results are exploratory previews; "Save as run" records the state, including every change, as a replayable run. |
| Conduits and sinks | Live explorer for Garcia-Bernardo and others: move the ownership, sink and conduit thresholds and see which jurisdictions are sinks (where value ends, relative to GDP) and conduits (through which it passes), on a conduit map, a sink-centrality chart and a flow diagram of three-country chains. |
| Data | Table viewer and CSV download, validation report, synthetic generator and CSV import. |
| Runs | Execute an engine, inspect outputs, calculation trace and full record, replay, download. |
| Methods | Every registered engine with its status, boundary and next step. |
| About | Version, build, source commit, lock-file hash, workspace. |

A **reading mode** switch in the top bar changes between Plain English (default) and Technical wording; every chart carries guidance on how to read it. Every chart can be downloaded as PNG, SVG or CSV. Charts and exports from synthetic data, demonstration engines or unverified methods carry a visible watermark.

## Data format

A dataset is a set of CSV tables with header rows; columns are matched by name, in any order. Required tables: `sources`, `jurisdictions`, `entities`, `ownership`. Optional: `jurisdiction_attributes` (GDP is used for weights), `illustrative_tax_edges`, and the tax rule tables used by the routing engine: `tax_domestic` (CIT, general dividend withholding, relief method), `tax_treaty_dividends` (directional treaty withholding) and `tax_relief_overrides` (relief for a particular partner); and `entity_financials` (operating revenue per entity and period), which weights ownership chains in the conduits and sinks engine. Legal rows carry `rule_status` and `verified` columns; unverified real-world rows are flagged on every result that uses them. Column definitions are in `src/taxnetlab/schema.py`; the Data page shows them for each table. Conventions:

* shares and rates are fractions in [0, 1]; money is an amount plus an ISO 4217 currency;
* real jurisdictions use ISO 3166-1 alpha-3 codes; fictional ones use the `FIC_` prefix;
* ownership is stored as direct relations, holder → held; indirect holdings are derived, never stored;
* natural persons must be excluded or pseudonymised before import;
* nothing is repaired or imputed silently, and synthetic records may never be attributed to a real jurisdiction.

Datasets are content-addressed: the dataset id is derived from a SHA-256 hash of the canonical form of its tables, so the same content always has the same id.

## Running from source

Python 3.11 or newer.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[test]"
python -m pytest
python -m taxnetlab            # start the interface
```

Notebook users: `pip install -e ".[notebook]"` and open `notebooks/01_research_workbench.ipynb`. The notebook uses the same service layer and workspace as the interface.

## Building the executable

On Windows, the simplest route is to double-click `scripts\build_exe.bat` (Python 3.12 must be installed). It creates a private build environment from the hash-locked requirements, builds `dist\taxnetlab.exe` and runs its self-test.

CI builds `taxnetlab.exe` on a Windows runner from the hash-locked environment in `requirements/windows-build.lock`, runs `taxnetlab.exe selftest` on the result and publishes it as an artefact (and as a Release asset for tags `v*`). To build locally on Windows:

```bat
python -m pip install --require-hashes -r requirements\windows-build.lock
python -m pip install --no-deps -e .
python scripts\write_build_manifest.py requirements\windows-build.lock
pyinstaller --noconfirm --clean packaging\taxnetlab.spec
dist\taxnetlab.exe selftest
```

## Languages

All interface text is loaded from `src/taxnetlab/web/locales/<tag>.json`. English (UK) is complete. To add a language, see `docs/TRANSLATING.md`; the language menu picks up new files automatically, and right-to-left scripts are supported through the locale's `dir` setting.

## Project documents

* `docs/PROJECT_PLAN_v2_3.md`: plan, status ladders, phases and release gates.
* `docs/BUILD_0_4_STATUS.md`, `docs/BUILD_0_3_STATUS.md` and `docs/BUILD_0_2_STATUS.md`: what each release contains, the pre-build logical evaluations and test results.
* `docs/IP_GATE_US10417262.md`: research note on the patent for the author's decision.
* `docs/METHOD_RECONSTRUCTION_REGISTER.md`: verification checklists for the three published methods.
* `docs/specs/`: specifications of implemented engines.
* `CHANGELOG.md`.

## Licence and citation

All rights reserved pending the licence decision recorded in the project plan (s 4.6). See `LICENSE`. Citation metadata is in `CITATION.cff`.

Plotly.js (MIT licence) is bundled in `src/taxnetlab/web/vendor/` so that the interface works offline.

## Acknowledgements

Development of this software was assisted by Claude (Anthropic), an AI model, under the direction of the author, who is responsible for its design decisions and content.
