# Specification: demonstration engine `demo.link_summary` (v1)

**Track:** demonstration. **Status:** verified. **Engine version:** 0.2.0.

This engine exists to exercise the engine interface, run records and replay (project plan v2.1, Phase 1). It is not a research method. It does not implement or approximate the Garcia-Bernardo and others conduit and sink measures, the van 't Riet and Lejour routing model or any other published measure, and its outputs must not be read as indicators of conduit, sink or routing behaviour.

## 1. Inputs

* `entities` (for each entity's jurisdiction) and `ownership` (direct relations, holder → held).
* Parameters: `as_of` (ISO date or empty; empty selects relations without `valid_to`) and `relation_type` (default `equity`).

## 2. Link counts

For each jurisdiction *j*, over the selected relations *r* from holder *h(r)* to held *d(r)*:

* `outbound_links(j)` = number of *r* with jur(h) = *j* and jur(d) ≠ *j*;
* `inbound_links(j)` = number of *r* with jur(d) = *j* and jur(h) ≠ *j*;
* `domestic_links(j)` = number of *r* with jur(h) = jur(d) = *j*.

Parallel relations (for example two share classes between the same pair) count separately.

## 3. Values

* `outbound_value(j)` = sum of `value_amount` over the outbound relations of *j* with a reported value;
* `inbound_value(j)` likewise for inbound relations;
* `net_outbound_value(j)` = `outbound_value(j)` − `inbound_value(j)`.

Relations without a reported value are counted as links but not summed; the run record states how many. Values in more than one currency block the run.

## 4. Identities (tested)

* Σ outbound_links = Σ inbound_links; Σ outbound_value = Σ inbound_value.
* Σ (outbound_links + domestic_links) = number of selected relations.
* Relabelling entity and relation identifiers does not change any output; multiplying every value by *k* multiplies value outputs by *k* and leaves link counts unchanged.

## 5. Hand-calculated fixture

The Build 0.1 network (`taxnetlab.synthetic.build_0_1_fixture`) gives, for `FIC_A`: outbound 2, inbound 0, domestic 1, outbound value 160.0; for `FIC_D`: inbound value 95.0, outbound value 32.0; for `FIC_E`: net outbound value −32.0. See `tests/test_engines.py::test_hand_calculated_fixture`.
