# Method Reconstruction Register

This is a verification checklist, not a claim that the methods have already been independently reproduced.

## A. Optimal tax routing: van 't Riet and Lejour
Verify exact node/edge definitions; income type and tax base; domestic/treaty withholding rules; participation exemptions and double-tax relief; stage-by-stage and total tax formulas; route feasibility and termination; assumptions required for additive path optimisation; data dates/coverage and reported benchmarks.
Tests: hand-computed direct route; multi-stage route; nontrivial route comparison; missing/ineligible treaty; invalid rate boundaries; published benchmark where comparable data exist.

## B. Garcia-Bernardo et al.: conduits and sinks
Verify exact paper/version; edge direction; ownership-chain construction; chain length and inclusion rules; multiple owners and indirect holdings; financial-value allocation and duplicate counting; exact sink/conduit measures and normalisation; dataset and period; classification thresholds.
Tests: hand-worked network; disconnected nodes/cycles; missing ownership; repeated chains; missing/zero denominator; published results only where data/definitions are comparable.

## C. US Patent 10,417,262 B2: scalable TDA
Verify independent/dependent claims; disclosed computational steps; lens/projection; cover and overlap; clustering; graph construction; claimed scalability/memory optimisation; examples and benchmarks; differences between generic Mapper and patent-specific implementation.
Tests: toy point cloud; deterministic repeat; parameter sensitivity; inspectable node memberships; memory/runtime benchmarks; matched comparison with baseline Mapper.

## Cross-model integration
Do not combine scores by default. Shared jurisdiction identifiers do not make model measures commensurable. Preserve each method's unit of analysis, definitions, period and uncertainty.
