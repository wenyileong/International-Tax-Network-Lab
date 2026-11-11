# Research Suite integration

**Release:** 1.0.0rc2 (12 November 2026). **Suite core vendored:** `rscore` 0.4.0, commit recorded in `src/rscore/VENDORED.json`.

## How the Lab fits into the suite

The Research Suite (`Research-Suite-Core`, ResearchSuite.exe) already converts releases of A-share Company Intelligence into a shared SQLite store and exports the Lab's tables. A second converter in the Lab would sooner or later disagree with the suite's on which rows are kept, so the Lab does not have one. It carries an unmodified copy of the suite's core and calls it:

| Step | Who does it | Where |
|---|---|---|
| Read a release (`manifest.json`, `csv/`) | Lab | `taxnetlab.suite.SuiteBridge.inspect_release` |
| Convert (exclusions, rejections, place registry, review) | suite core | `rscore.services.run_import` |
| Record jurisdiction choices; re-import | suite core | `rscore.services.save_overrides`, project folder `jurisdiction_overrides.csv` |
| Export the Lab's tables | suite core | `rscore.services.export_lab` (`<project>_files/lab_exports/`) |
| Import as a dataset with provenance | Lab | `SuiteBridge.import_export_folder`, `Api.import_csv(metadata=...)` |

Projects are the suite's own files, so a project made in the Lab opens in ResearchSuite.exe and the reverse. The Lab lists projects from three places: its workspace folder `suite_projects`, projects opened before, and the suite launcher's `recent_projects` (read only, from `%APPDATA%\ResearchSuite\launcher.json`). This matches the suite's Phase 2 rule that tools read the shared store but do not change its schema.

### Updating the vendored core

```text
python scripts/sync_rscore.py ..\Research-Suite-Core
python -m pytest tests/test_ashare_import.py
```

The script copies the listed files and writes their SHA-256 and the source commit to `VENDORED.json`. A test fails if any vendored file is edited by hand, and another if the importer gains a rejection reason the interface has no label for.

### One adjustment on hand-over

A suite export carries the whole jurisdiction registry (about 250 rows). By default the Lab leaves out jurisdictions that no row refers to (keeping parents of those it keeps) and records the number left out, because persistent homology and the matrix treat each jurisdiction as an observation. The option is on the Research Suite page and `trim_jurisdictions` in the API.

## Proposed changes on the suite side

These are proposals for Research-Suite-Core; nothing in the suite has been changed.

1. **Find the Lab through the registry.** The installer now writes `HKCU\Software\InternationalTaxNetworkLab\InstallDir` (and `Version`). The launcher's tool detection looks only at `%LOCALAPPDATA%\Programs\International Tax Network Lab\taxnetlab.exe`; reading the registry value first would find a Lab installed elsewhere.
2. **Open the Lab on the current project.** `launch()` passes no arguments. Passing `--import "<project.sqlite>"` (or the latest Lab export folder) would open the Lab on the Research Suite page with that project selected; `--import "<release folder>"` opens it on a release, read but not imported.
3. **Pass the language.** `--language zh-Hans` (or `en-GB`) makes the Lab follow the suite's choice. Without it, the Lab already uses the suite's `language` setting when the user has not chosen one in the Lab.
4. **Export manifest.** A small `export.json` beside the exported CSV files (project, release, settings, core version) would let the Lab record provenance for an export folder moved away from its project; today the Lab reconstructs it from the project folder layout.
5. **Translate importer notes.** The reasons and statuses have Chinese labels, but the free-text notes of an import report are English only; message codes with parameters would let both programs translate them.
