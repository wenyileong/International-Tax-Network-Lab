# Note: importing data from the A-share Company Intelligence scraper

**Status:** superseded on 12 November 2026 by release 1.0.0rc2, which imports releases with the Research Suite's own converter (option 2 below, implemented once, in the suite, and vendored into the Lab); see the Research Suite page, `taxnetlab import-ashare` and `docs/SUITE_INTEGRATION.md`. The note is kept as the original assessment. **Date:** 23 October 2026. Based on a reading of `wenyileong/ashare-company-intelligence` v2.0.4.

## What the scraper holds that this software can use

| Scraper data | Lab table | Notes |
|---|---|---|
| Listed companies; organisations register (shareholders, subsidiaries, controllers) | `entities` | Natural persons excluded or pseudonymised (`release --pseudonymise`), as the lab requires. |
| Top ten shareholders (`ownership_pct`) | `ownership` (holder to listed company) | Top ten only, so chains are partial. |
| Subsidiaries and associates (`direct_pct`, `indirect_pct`, `total_pct`, `registered_place`, `principal_place`, `jurisdiction_class`) | `ownership` (listed company to subsidiary), `entities.jurisdiction_id` | Use direct stakes only; the lab derives indirect ownership itself, so nothing is counted twice. Only subsidiaries the company reports. |
| Controlling shareholder, actual controller, control chain | `ownership` (control relations) | Relation type `control`. |
| Revenue (consolidated, listed companies); revenue of major subsidiaries | `entity_financials` | Consolidated figures are flagged by the lab (double counting); subsidiary revenue preferred where reported. |
| Source of each row (CNINFO disclosures; licence class) | `sources` | Public disclosures as `public_attribution`; the scraper's licensed rows stay out unless their terms allow. |

## What a converter must do

1. Map place names (Chinese or English, for example 开曼, British Virgin Islands, Hong Kong) to ISO 3166-1 alpha-3 codes (CYM, VGB, HKG), building on the scraper's `places.py`; unrecognised places are flagged, never guessed.
2. Exclude natural persons.
3. Take direct stakes only; carry dates as `valid_from`.
4. Record provenance and licence classes.

## Scope and limits

The data cover Chinese listed groups and what they disclose, not the global ownership network. They suit questions about how A-share groups hold foreign assets (for example red-chip and VIE structures through Hong Kong, Cayman or the British Virgin Islands). They do not support a replication of Garcia-Bernardo and others (2017), whose GDP-relative measures need global coverage. Tax rates and treaties are not in the scraper; the tax-routing engine still needs China's treaty network coded with the legal coding template.

## Options

1. Manual: export the scraper's subsidiary and shareholder tables to CSV and import them with a column mapping (country codes and natural persons prepared in a spreadsheet first).
2. Built-in converter (preferred for a paper): an importer that reads the scraper's release snapshot (SQLite) and writes a validated lab dataset, with the code lookup, exclusions and provenance automated and tested.

Also noted: GitHub reported `ashare-company-intelligence` as a public repository on 23 October 2026, although the plan recorded was to keep it private for now.
