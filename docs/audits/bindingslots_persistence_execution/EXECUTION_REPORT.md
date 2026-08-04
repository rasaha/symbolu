# BindingSlots adaptive persistence execution — report

**Primary verdict: `NO_PERSISTENCE_INTERVENTION_SELECTED` · `KDA_VALIDATION_BLOCKED`.**

The authorized adaptive persistence screen ran the merged decision tree on reserved seeds 23–27. No
intervention reached the frozen advancement gate (clean-stable ≥ 4/5 and > R0). All results are
reconstructed mechanically from committed evidence; the planner replay reproduces the run ledger
exactly (`results/aggregate_classification.json`, `replay_reproducible: true`).

## Provenance

| Item | Value |
|---|---|
| Preregistration (PR #1331) merge | `78be653642c3ec7adc385572c75c411cc0ce4fe0` |
| Adaptive amendment (PR #1332) merge | `101951cb8bbccca32b6e3faa371bc675371dca89` |
| Execution branch | `claude/bindingslots-persistence-adaptive-execution` |
| execution_code_commit (A+/R0/O1R/H1) | `5cc392e1` |
| execution_code_commit (H2/O1, after authorized fidelity correction) | `9380bdb1` |
| Runs executed | **24** (max 30; adaptive saved 6 via futility) |
| Frozen `abc.json` | `b31989a3…` unchanged |
| Verifiers | amendment 35/0 · historical 8/0 · lab 81/0 · replay reproducible |

## Adaptive trace (exact order)

A+ ×5 → R0 ×5 → **O1R** (futile after 3) → **H1** (futile after 3) → **H2** (futile after 3) → **O1
diagnostic** ×5 → terminal. See `ADAPTIVE_STOPPING_TRACE.md`.

## Clean-stable counts

| arm | clean-stable | outcome |
|---|---|---|
| R0 (frozen CR1) | **2/5** (seeds 24, 27) | baseline |
| O1R | 1/5 | futile (2 quality-failed) |
| H1 | 1/5 | futile (1 causally-unclean, 1 quality-failed) |
| H2 | 1/5 | futile (1 collapsed, 1 quality-failed) |
| O1 (diagnostic, not selectable) | 1/5 | reference phenotype |

No candidate > R0's 2 clean-stable, and none ≥ 4/5 → **no selection**.

## Two failure families (the scientific result)

Several persistence interventions retained a **strong written-slot preference on the fixed routing
diagnostic** after scaffold withdrawal — O1R/H1/H2 hold correct-slot probability 0.78–0.99 at step
1200 (vs plain O1's decay to 0.17–0.25). This demonstrates that *diagnostic routing decay can be
mitigated*, but it did **not** produce reliable, quality-preserving end-to-end retrieval across the
evaluation distribution — clean-stable retrieval still failed, via **two distinct modes**:

1. **Quality interference** — persistent supervision raises perplexity above the frozen 1.20×A+ gate:
   O1R s24/s25, H1 s25, H2 s25 (and R0 s25). Retrieval is fine; **quality** fails.
2. **Downstream value/readout collapse** — H2 s23: correct-slot prob retained **0.96** at step 1200,
   quality passes, yet needle collapses **1.00 (step 700) → 0.00 (step 1200)**. Addressing retained,
   retrieval lost *downstream*.

Details + the corrected framing (probe-vs-eval dissociation; causal ablations non-informative on
already-collapsed seeds) in `ROUTING_RETENTION_AND_FAILURE_FAMILIES.md`. Per-seed table in
`PER_SEED_RESULTS.md`. Provenance/integrity in `INTEGRITY_AND_PROVENANCE.md`. Non-claims in
`LIMITATIONS_AND_NONCLAIMS.md`.

## Supported claim

Under the frozen synthetic protocol, none of the three preregistered persistence interventions (O1R
standing residual, H1 routing-parameter consolidation, H2 functional teacher) produced reliable,
quality-preserving, causally-clean end-to-end retrieval on the reserved seeds. The interventions
retained address routing; retrieval nonetheless failed via a quality-interference family and a
downstream value/readout family.

## Exact next phase

**Phase-Free BindingSlots Value Integrity, Readout, and Quality-Interference Mechanism Isolation** —
a diagnostic (probe + controlled-bypass) phase to localize *where* usable slot information is lost and
*which* parameter groups drive the quality regression. Not started here; its own preregistered phase.
KDA remains blocked.
