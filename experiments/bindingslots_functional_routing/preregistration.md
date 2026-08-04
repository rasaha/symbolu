# BindingSlots Functional Routing & Retention — Pre-registration (focused Stage-1 screen)

**Status:** PRE-REGISTERED, committed and pushed **before** any training. No objective, schedule,
threshold, classifier, seed, or verdict-mapping change after training begins.

## Scope

Focused variant chosen for this session: a **Stage-1 screen** of **R0, O1, O2, H3** (plus the frozen
**A+** control) on **five fresh seeds (18–22)**. Stage-2 holdout, the O3/H1/H2/O1R/C1 arms, and
independent confirmation are **documented but deferred** to a follow-up phase — no frozen threshold
changes.

## Question

Can a bounded **training-only** intervention make retrieval depend on the **specific slot that
stored the value** *and* preserve that routing after scaffold withdrawal — without changing the
inference architecture, task, model size, optimizer family, evaluation protocol, or the frozen causal
gates?

## Motivation (PR #1324)

`CONFIRMATORY_REPLICATION_FAILED` (CR1 3/5). Two failures: **retention** (seeds 13/14 collapsed with
aggregate overlap ~0.70 retained but needle → 0) and **purity** (seed 16: needle 1.0 yet
randomized-address 0.45, read-prob on written slot 0.21, rank ~14). Working hypothesis: *aggregate
write-read overlap dissociates from retrieval through the specific stored slot* — to be **tested**,
not assumed.

## Arms

| arm | change | mechanism |
|---|---|---|
| A+ | frozen window-only control | `stabilize.run_arm('A+')`, unswapped |
| R0 | frozen CR1 (comparator) | `stabilize.run_arm('CR1')`, unswapped |
| O1 | `L = −log(r[q,s*]+1e-6)` | swap `interventions.alignment_loss` |
| O2 | `L = max(0, 3.0 − (z[q,s*] − max_{j≠s*} z[q,j]))` | swap `interventions.alignment_loss` |
| H3 | original-mixture 0→1 across steps 600–900 | swap `interventions.curriculum_batch` |

`s*(f) = argmax_j stop_gradient(w[f,j])` (lowest index on ties). O1/O2 use the **R0 λ schedule**
(0.10→0 by step 600). Each arm runs the **frozen `stabilize.run_arm` loop** with **at most one**
in-memory function swap — the `interventions.py` / `stabilize.py` files on disk are never edited and
their sha256 are verified.

## Metrics (new; aggregate overlap kept as diagnostic only)

Correct-slot probability ≥ 0.50, correct-slot rank ≤ 5, address-logit margin ≥ 3.0 — from the frozen
diagnostics routing block at d96. These are development diagnostics grounded in the known clean
(15/17) vs impure (16) trajectories; they **do not replace** the frozen causal gates.

## Stage-1 full single-arm gate

Causally-clean stable formers ≥ 4/5 **and** paired wins vs R0 ≥ 4/5 **and** every final former
passes slots-off **and** randomized-address **and** formed-then-collapsed ≤ 1/5 **and**
routing-unclean final formers = 0 **and** quality **and** distance pass. Winner by clean-stable
count → wins-vs-R0 → fewer collapses → fixed tie-break O1, O2, H3, R0.

## Discipline

No answer-label / evaluator / frozen-randomized-address signal in training (verified). No
best-checkpoint selection, no outcome-based seed replacement, no threshold changes. No Phase / KDA /
MLA / quadratic / N×N / new arch / new inference op. Even on selection, readiness never exceeds
`KDA_VALIDATION_BLOCKED_PENDING_INDEPENDENT_CONFIRMATION`; `READY_FOR_KDA_VALIDATION` is never
emitted.
