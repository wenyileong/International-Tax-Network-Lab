# Specification: conduits and sinks (Garcia-Bernardo and others)

**Engine:** `gb2017.conduits_sinks`, reproduction variant. **Specification version:** 0.1 (draft).
**Status of this document:** *draft*. The source text was obtained through automated PDF extraction; the equations of the Methods section (Eqs 1 to 5) were garbled, especially the GDP normalisation terms. The formulas below are reconstructions from the extracted symbols and the surrounding prose, each marked with its basis. Until the author has checked them against the published article (s 9), the engine may reach `implemented` but not `verified` (plan v2.2, s 0.0 item 5).

## 1. Source

* Javier Garcia-Bernardo, Jan Fichtner, Frank W Takes and Eelke M Heemskerk, 'Uncovering Offshore Financial Centers: Conduits and Sinks in the Global Corporate Ownership Network' (2017) 7 Scientific Reports 6246, doi:10.1038/s41598-017-06322-9 (peer reviewed; open access). Text consulted through the Leiden University repository copy <https://scholarlypublications.universiteitleiden.nl/access/item%3A2941974/view> and a second copy for the equations. Preprint: arXiv:1703.03016.
* References below are to the Methods subsections of the article ("Data extraction and quality assessment", "Ownership network", "Company level chains", "Multiplicative ownership", "Aggregating at the country level", "Sink Offshore Financial Centers", "Conduit Offshore Financial Centers") and to the Supplementary Information.

## 2. Data in the source

Orbis (Bureau van Dijk), extracted November 2015: 98,255,206 companies and 71,201,304 ownership relations; operating revenue, country and ownership percentages (direct and total). Isle of Man, Jersey and Guernsey are kept separate from the United Kingdom. Private wealth (natural persons) is excluded. Consolidated revenues are deconsolidated by subtracting subsidiaries' revenue along ownership paths. Ownership stakes are normalised for missing shareholders following Vitali and others. Replication is Tier B (plan s 7.3): Orbis is licensed.

## 3. Firm-level chains ("Company level chains", "Multiplicative ownership")

* **Direction:** firms are nodes; value flows from an owned firm to its owners. A chain starts at a firm and follows ownership upwards: C1 (owned) → C2 (owner of C1) → C3 (owner of C2) → …
* **Multiplicative ownership:** MO(C1|…|Ck) = Π w(C_i → C_(i+1)), where w is the (normalised) share of C_i held by C_(i+1).
* **Threshold:** a chain is extended while MO ≥ 0.001 (stated; robustness to the threshold reported in the Supplementary Information).
* **Cycles:** chains returning to a firm already in the chain are discarded (stated).
* **Value:** V(C1|…|Ck) = R(C1) · MO(C1|…|Ck), where R(C1) is the (deconsolidated) operating revenue of the first, owned firm (stated).

## 4. Country chains ("Aggregating at the country level")

1. Each firm takes its country; adjacent firms in the same country are merged (stated).
2. Chains are split into chunks of length 2, 3, …, |chain| (stated); among chunks sharing the same country sequence, owner and upstream companies, only the chunk with the maximum value is kept, to avoid double counting (stated; reconstruction of the grouping key in I3).
3. Chunks with the same country sequence are summed into a country chain value V_g (stated). G2 and G3 are the sets of country chains with two and three countries (stated).
4. In a country chain g = g[0] | g[1] | … , g[0] is the country of the owned firm, where value originates, and the last element is the country where value ends (stated in prose).

## 5. Sink centrality (Eq 1)

Prose (stated): "the difference of value entering and leaving the country", relative to total value, normalised by GDP; a sink-OFC is a country where the value staying is ten times higher than its GDP would imply.

Reconstruction (I4):

    S_c = [ Σ_{g∈G2: g[1]=c} V_g − Σ_{g∈G2: g[0]=c} V_g ] / Σ_{g∈G2} V_g    ÷    [ GDP_c / Σ_k GDP_k ]

Sink-OFC: S_c > 10 (stated threshold, with robustness in the Supplementary Information). The reconstruction reads "normalised by GDP" as comparing a country's share of value with its share of world GDP, which is the reading under which a threshold of 10 means "ten times higher than expected".

## 6. Conduit centralities (Eqs 2 and 3)

Prose (stated): inward conduit centrality "measures the value of chains flowing from a sink-OFC, into the conduit, out to another country"; outward conduit centrality "measures the value of chains flowing from any country, into the conduit, out to a sink-OFC"; both are normalised by GDP; a conduit-OFC has both above 1.

Reconstruction (I5), with G3^(s1) the chains in G3 whose first country is a sink-OFC and G3^(s3) those whose last country is a sink-OFC:

    C^in_c  = [ Σ_{g∈G3^(s1): g[1]=c} V_g / D^in ]  ÷  [ GDP_c / Σ_k GDP_k ]
    C^out_c = [ Σ_{g∈G3^(s3): g[1]=c} V_g / D^out ] ÷  [ GDP_c / Σ_k GDP_k ]

The denominators D could not be read reliably. Default: D^in = Σ_{g∈G3^(s1)} V_g and D^out = Σ_{g∈G3^(s3)} V_g (each subset's total), so that a value of 1 means the conduit carries a share of sink-bound or sink-originating value equal to its share of world GDP. Alternative (parameter `conduit_denominator = all_g3`): D = Σ_{g∈G3} V_g.

Conduit-OFC: C^in_c > 1 and C^out_c > 1 (stated).

## 7. Entropy (Eqs 4 and 5)

Prose (stated): Shannon entropy is lower for conduits that serve few countries or have skewed distributions. Reconstruction (I6), natural logarithm:

    EC^in_c  = − Σ_i p_i ln p_i,  p_i ∝ Σ_{s∈sinks} V(s | c | i)   (destinations of value arriving from sinks)
    EC^out_c = − Σ_i p_i ln p_i,  p_i ∝ Σ_{s∈sinks} V(i | c | s)   (origins of value sent on to sinks)

## 8. Interpretive choices

| # | Choice | Default | Parameter |
|---|---|---|---|
| I1 | Ownership weights: direct equity fractions, normalised so that the known shareholders of each firm sum to one ("missing shareholders"). | normalise | `normalise_missing_shareholders` |
| I2 | Chains are every simple upward path from each firm with MO ≥ threshold (each distinct path once). | 0.001 | `ownership_threshold` |
| I3 | Double-counting rule: among firm paths from the same first firm to the same last firm with the same country sequence, keep the maximum value. | as stated | none |
| I4 | Sink centrality compares value share with GDP share (s 5). | as stated | none |
| I5 | Conduit denominators (s 6). | `subset_total` | `conduit_denominator` (`subset_total`, `all_g3`) |
| I6 | Entropy definitions and natural logarithm (s 7). | as stated | none |
| I7 | GDP: the dataset's `gdp` attribute for the period, otherwise the latest period; GDP is required for every jurisdiction that appears in G2 or G3. | as stated | none |
| I8 | Revenue: the `operating_revenue` of the owned firm for the period, from `entity_financials`. Consolidated figures are flagged; deconsolidation is a data-preparation step outside the engine. Firms without revenue contribute no value. | as stated | none |
| I9 | A conduit with an empty denominator (no sink-bound or sink-originating chains) has no conduit centrality (reported as empty, never as 0). | as stated | none |
| I10 | Thresholds as stated: sink 10, conduit 1, adjustable for sensitivity. | 10; 1 | `sink_threshold`, `conduit_threshold` |
| I11 | Chain length bound for computation: none beyond the ownership threshold, but an overall chain budget stops enumeration and is reported. | 1,000,000 | `chain_budget` |

## 9. Open questions for the author's check

1. Eq 1: the exact GDP term (I4).
2. Eqs 2 and 3: the denominators and GDP terms (I5); the middle-position index.
3. Eqs 4 and 5: index sets and normalisation (I6).
4. The chunking and double-counting rule (I3), including whether chunks are prefixes from the owned firm.
5. Missing-shareholder normalisation in Vitali and others (I1).
6. Which GDP year is used.

## 10. Benchmarks (expectation register)

Five conduit-OFCs: Netherlands, United Kingdom, Ireland, Singapore and Switzerland; 24 sink-OFCs (stated). 11,404,819 company-level chains; 108,159,506 chunks; 16,448,469 chains after de-duplication; 377,098 country-level chains; 7,172 in G2 and 52,655 in G3 (stated).

## 11. Feasibility

Orbis is licensed and not redistributable, so full replication is Tier B; the published conduit and sink lists can serve as a qualitative replication target. The reference implementation enumerates firm-level paths and is intended for synthetic and modest datasets; Orbis scale needs the performance implementation of plan Phase 7.
