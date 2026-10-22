# Method notes

These notes explain each method in plain terms. The specifications in `docs/specs` give the definitions, interpretations and tests; the Compare page shows the measures side by side.

## Optimal tax routing (van 't Riet and Lejour)

**Question.** When a company's profits are paid as dividends from the country where they are earned (the host) to the country of the ultimate parent (the home), how much tax is lost on the way, and can routing them through other countries reduce it?

**How.** Each step from one country to another costs withholding tax and, depending on how the receiving country relieves foreign dividends (exemption, credit or deduction), some home-country tax. The cheapest route is found with a shortest-path search. The treaty-shopping gain is the saving of the cheapest route over the direct one. Conduit centrality measures how often a country lies on near-cheapest routes, weighted by the economic size of the two ends.

**Limits.** Dividends only; statutory rates; treaty benefits assumed available unless you apply treaty conditions (an extension). Anti-abuse rules are judgement-based and are never decided by the software.

## Conduits and sinks (Garcia-Bernardo and others)

**Question.** Where does corporate value end up, relative to the size of each economy, and through which countries does it pass on the way?

**How.** Value flows up ownership chains from each owned company, weighted by its revenue and by the share held at each step. Chains are summarised by the sequence of countries. A *sink* attracts much more value than its GDP would suggest; a *conduit* carries value into and out of sinks out of proportion to its size.

**Limits.** Results depend on the coverage of the ownership data. Some equations of the source were read from an automated transcription and await the author's check.

## Persistent homology

**Question.** Do jurisdictions, placed by their tax and network characteristics or by tax-routing cost, form robust groups or surround gaps (loops), and which jurisdictions does that structure depend on?

**How.** Jurisdictions are joined when they are within a distance of each other; as the distance grows, groups merge and loops appear and fill in. Features that last over a wide range of distances are robust. The bottleneck distance measures how much the picture changes when a jurisdiction is left out.

**Limits.** The shape describes the chosen features and distance, not conduct. The two-dimensional picture is a projection for display only.

## Model comparison and sensitivity

**Comparison** places the measures side by side, runs each paper under its documented alternative readings, and shows a rank only where all readings agree. **Sensitivity sweeps** vary parameters over a grid and report how often each finding holds. Neither combines measures into a score.
