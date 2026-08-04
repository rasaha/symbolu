# Implementation decisions — functional-routing development

## 1. Focused scope (user-directed)

The originating prompt specified a 7-arm two-stage matrix (~35–45 runs, ~10–15 h). Given compute
reality, this session runs the **focused Stage-1 screen**: **A+, R0, O1, O2, H3** on seeds 18–22
(~25 runs). The **O3, H1, H2, O1R, C1** arms and the **Stage-2 development holdout** are documented
but **deferred**. No frozen threshold is changed by narrowing scope.

## 2. Runtime function-swap, not file edits

Each arm runs the frozen `stabilize.run_arm` loop with **at most one** `interventions.py` function
swapped **in memory** (O1/O2 → `alignment_loss`; H3 → `curriculum_batch`; R0/A+ unswapped). The
`interventions.py` / `stabilize.py` files on disk are never edited; their sha256 are pinned and
verified by `verify_fr_prereg.py`, and the swap is restored after every run (tested). This makes the
intervention the *only* difference between arms — architecture, optimizer, λ-schedule, evaluation, and
the frozen causal ablations are the identical frozen code path — and preserves paired data order for
R0/O1/O2 (identical RNG consumption; they diverge only via the auxiliary gradient during steps ≤ 600).

## 3. A+ included

The frozen `forming()` and causal-collapse thresholds are defined relative to A+, so A+ is trained on
seeds 18–22 (cheap window-only control) even though R0 is the superiority comparator. This applies the
frozen per-seed rules unchanged.

## 4. Branch

Environment git discipline binds this session to `claude/bindingslots-confirmatory-replication-d117c1`.
This phase therefore extends that branch (and PR #1324) in a **separate directory**
(`experiments/bindingslots_functional_routing/`) rather than a new branch. Documented so reviewers know
PR #1324 now carries both the confirmatory result and this follow-up development.

## 5. PR #1324 unmerged (not a blocker)

R0 is recovered from the merged PR #1319; the motivation is reconstructed from #1324's committed
evidence. No merge is forced to satisfy a literal prerequisite.

## 6. Honesty on compute

If the ~25-run Stage-1 matrix cannot complete, the classifier emits
`FUNCTIONAL_ROUTING_RESOURCE_BLOCKED`. No numbers are fabricated; the verdict comes only from real,
committed per-seed data.

## 7. Metric note

The address-specific metrics (correct-slot prob/rank/margin) are the frozen diagnostics fields
`read_prob_on_highest_write_slot` / `rank_of_highest_write_slot_under_read` / `address_logit_margin`
at d96 — already computed by the frozen harness, so no new evaluation code enters the training path.
