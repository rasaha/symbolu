# Confirmatory replication — limitations & interpretation boundaries

These bounds hold **regardless of outcome**.

## What a PASS would support

Only: *frozen CR1 reproducibly improved causally slot-dependent circuit formation on the frozen
synthetic retrieval protocol across an independent five-seed confirmation set.*

## What a PASS would NOT prove

- general language-model benefit
- natural-language transfer
- production readiness
- architecture-wide stabilization
- long-horizon retention
- different slot-count transfer
- different sequence-length transfer
- different model-scale transfer
- KDA superiority
- inference-speed benefit
- memory-efficiency benefit

## What a FAIL means

The original 4/5 holdout result did **not** independently replicate under the frozen protocol. It is
**not** reframed as success because some seeds formed transiently.

## Standing limitations

- **Synthetic protocol only.** One retrieval task family (needle/ABC_MIX), one architecture (2 M
  params, 32 slots, seq 160), one distance suite (d16/d96/d220).
- **Small sample.** Five seeds; the confirmatory verdict is a reliability count, not an effect-size
  estimate. Forming-seed needle saturates near 1.0, so margin size is not the headline.
- **Retention is observed, not solved.** The merged seed 9 showed a post-scaffold retention failure;
  this phase does not modify CR1 to address it. Any retention category is an explanatory diagnostic
  and never overrides the formation classifier. Mechanistic statements are phrased conservatively
  (e.g. "consistent with retention instability after scaffold removal"); architectural bistability is
  **not** claimed as conclusively established from a few trajectories.
- **Environment delta.** A different torch build than the merged run; the frozen protocol pins the
  optimizer/schedule, not the torch build, and the seeds are new, so exact seed-8–12 reproduction is
  neither expected nor required.
- **Selection history.** CR1 was chosen over multiple Stage A arms on a development set; this single
  confirmatory replication reduces but does not eliminate that selection-bias concern.

## Scope guardrails (unchanged)

No Phase, KDA, MLA, quadratic attention, N×N state, or new inference-time op/param is introduced. A
successful confirmatory replication permits **designing** the next validation ladder; it does not
itself prove readiness for full KDA integration, and `READY_FOR_KDA_VALIDATION` is never emitted from
this experiment.
