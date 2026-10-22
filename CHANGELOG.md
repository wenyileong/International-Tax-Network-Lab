# Changelog

## 0.3.0 (22 October 2026)

Plan v2.2: tax routing, method first. See `docs/BUILD_0_3_STATUS.md`.

* Phase 3 specification for van 't Riet and Lejour (`docs/specs/vtrl2018_tax_routing.md`, draft).
* Tax rule tables: domestic rates and relief, directional treaty withholding, directional relief.
* Optimal tax routing engine (`vtrl2018.tax_routing`, implemented): cheapest routes, treaty-shopping gain, conduit centralities, scenario overrides.
* Live exploration: engine-generic preview API and the Tax routes page with sliders, sweeps and "Save as run".
* Existing dataset ids and workspaces are unchanged.

## 0.2.0 (20 October 2026)

Phase 0 and Phase 1 of the project plan (v2.1). See `docs/BUILD_0_2_STATUS.md`.

* New core: typed schemas, integrity checks, content-addressed datasets, canonical hashing, graph views, engine interface with status ladders, immutable run records with replay, service layer, CLI.
* New offline interface served by a local server bound to 127.0.0.1, replacing the Streamlit shell.
* Windows executable (`taxnetlab.exe`) built and self-tested by CI.
* Language infrastructure: locale files with fallback and text direction; English (UK) complete.
* Fixed every Build 0.1 defect listed in Appendix B of the plan.

## 0.1.0

Initial scaffold (tagged `v0.1.0`, unmodified).
