# Limitations and non-claims

**Diagnostic phase only. No fix is implemented. KDA validation remains BLOCKED and
`READY_FOR_KDA_VALIDATION` is never emitted.**

## Non-claims

- This phase does **not** implement, tune, or validate any fix. No coefficient was tuned, no arm or
  seed added, no architecture, slot count, or dimension changed.
- It does **not** show BindingSlots is solved, nor that any persistence intervention works, nor that
  routing decay is cured.
- It does **not** demonstrate natural-language transfer, production readiness, or KDA readiness. It
  **cannot** unblock KDA and does not attempt to.
- Linear-probe results describe *linear* decodability. A probe failure is reported as **low linear
  decodability, not** proof that the information is absent (it may be present non-linearly).
- Oracle interventions establish *where in the read/value path* usable information is or is not
  recoverable under a controlled bypass; they are **counterfactual localizations**, not a claim about
  what the trained network actually does end-to-end.

## Limitations

- **Single-trajectory reads on a small frozen cohort** (12 runs; 3 seeds per arm). The mechanistic
  split is a localization on these exemplars, not a population estimate.
- **Bounded synthetic protocol** (the frozen needle/binding/supersession/source/multihop tasks over
  the enterprise-prose corpus), 160/256-token contexts, ~2M-parameter CPU-fp32 model. Findings are
  about this protocol.
- **Collapsed-baseline ablations are non-informative.** Where ordinary retrieval is already 0
  (e.g. H2 seed 23 at 1200), terminal slots-off / randomized-address ablations collapse nothing and
  are explicitly labeled `NON_INFORMATIVE`; only the oracle bypasses and probes are used as evidence.
- **Diagnosis is per-seed and may be `*_NOT_LOCALIZED`.** The rules deliberately do not force every
  seed into a mechanism; a seed whose controlled tests do not support one unique boundary is reported
  as `VALUE_PATH_NOT_LOCALIZED` / `QUALITY_INTERFERENCE_NOT_LOCALIZED`.
- **R0 has no persistence or teacher auxiliary.** A quality failure on plain R0 therefore cannot be a
  persistence/teacher gradient conflict and is reported as `QUALITY_INTERFERENCE_NOT_LOCALIZED` — an
  honest null, not evidence against the conflict hypothesis for O1R/H2.
- **Gradient alignment is measured at fixed diagnostic batches and checkpoints (900/1200).** It
  characterizes the local gradient geometry there, not the full optimization trajectory.

## What would (and would not) follow

A localized value-path boundary or a localized gradient conflict **motivates** a specific, narrowly
scoped next intervention (named in the findings), but implementing or validating it is **out of scope
for this phase** and for this PR. KDA remains blocked regardless of outcome.
