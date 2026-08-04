# BindingSlots Confirmatory Replication — Pre-registration

**Status:** PRE-REGISTERED. Committed and pushed **before** any confirmatory model training.
No hyperparameter, schedule, architecture, task, optimizer, threshold, classifier, gate, seed, or
verdict-mapping change is permitted after training begins.

## Scientific question

Does the merged, frozen **CR1** intervention (curriculum + temporary write-read alignment)
reproducibly increase **causally slot-dependent** retrieval-circuit formation on **five independent
fresh seeds**, without architecture changes, schedule changes, task changes, or post-hoc tuning?

## Prerequisites (verified live)

- PR **#1300** merged (`5f0cbe45`) — `PARTIALLY_STABLE` (3/5) → `NOT_READY_FOR_KDA_VALIDATION`.
- PR **#1319** merged (`ba665e42`) — `PROVISIONALLY_STABILIZED` (CR1 4/5, seed-9 retention failure)
  → `NOT_READY_FOR_KDA_VALIDATION`.
- Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` @ `ba665e42`.

## Frozen intervention

**CR1** = frozen curriculum (boundaries 300/700/1200; final 500 steps original ABC_MIX) + frozen
temporary write-read alignment (λ 0.10 → 0 by step 600; label-free; **no inference-time op or
parameter**). The full frozen configuration — architecture, optimizer, schedules, gates, and the
sha256 of every frozen source file — is pinned in [`frozen_cr1_config.json`](./frozen_cr1_config.json).

## Fresh seeds

**13, 14, 15, 16, 17** — the next five integers after the highest previously-used BindingSlots
training seed (12). Outcome-independent. Independence proof in
[`fresh_seeds.json`](./fresh_seeds.json).

## Arms

`A+` (window-only parameter/architecture control), `B0` (unscaffolded S baseline), `CR1`
(intervention) — all trained fresh on the five seeds for the exact 1200-step budget. `A+` is part of
the frozen Stage B matrix and is the reference against which the frozen classifier defines
formation, margin, causal-collapse, and quality; including it applies the merged classifier
unchanged and does not alter the primary decision rule.

## Primary confirmatory criterion

`REPLICATED_SLOT_FORMATION_STABILIZATION` **iff all** of:

1. CR1 forms on **≥ 4/5** fresh seeds;
2. CR1 formation count **> B0** formation count;
3. CR1 wins vs A+ at d96 on **≥ 4/5** paired seeds;
4. mean(CR1 − A+) at d96 **≥ 0.080**; median **≥ 0.050**;
5. **every** forming seed collapses under **slots-off**;
6. **every** forming seed collapses under **randomized addressing**;
7. quality (perplexity) gate passes;
8. distance gate passes (d16 / d220);
9. integrity passes; and
10. **no protocol deviation**.

Otherwise `CONFIRMATORY_REPLICATION_FAILED` (or an `INVALID` verdict when a valid scientific
verdict cannot be produced). Thresholds are inherited byte-identically from the merged Stage B
classifier — see [`classifier.json`](./classifier.json).

## Discipline

- **3/5 is not "nearly replicated."** A higher mean with < 4/5 formed does not pass.
- **One causally-unclean forming seed fails the whole replication.** Causal results are never
  averaged across seeds.
- **No best-checkpoint selection.** The classifier uses only the step-1200 evaluation.
- `PROVISIONALLY_STABILIZED` is not a valid confirmatory verdict.
- `READY_FOR_KDA_VALIDATION` is never emitted directly from this experiment; the most a pass yields
  is `ELIGIBLE_FOR_NEXT_VALIDATION_LADDER`.

## No tuning

No change is made to improve seed retention (no slower decay, residual alignment, alignment floor,
retention loss, EMA, teacher, checkpoint selection, extended training, early stopping,
restart-from-best, seed-specific schedules, curriculum extension, different optimizer/lr/init,
orthogonal reinit, gradient surgery, slot/window dropout, or additional auxiliary loss). No Phase,
KDA, MLA, quadratic attention, N×N state, or new inference-time op/param is introduced.

## Environment note

The merged Stage B run used a different torch build; this run uses **torch 2.2.2+cu121, CPU, fp32,
threads=4**. The frozen protocol pins the optimizer/lr/betas/schedule, **not** the torch build, and
the fresh seeds are new — so exact numerical reproduction of seeds 8–12 is neither required nor
expected. The torch-build delta is recorded as a documented environment factor.

## Retention diagnostics (explanatory only)

Per-seed trajectory is categorized as one of `NEVER_FORMED`, `FORMED_AND_RETAINED`,
`FORMED_THEN_COLLAPSED`, `LATE_FORMATION`, `TRANSIENT_RECOVERY`, `OTHER_PREDEFINED`. These never
override the formation classifier. Prior seed 9 showed a post-scaffold retention failure; this phase
**observes** retention but does not change CR1 to solve it.
