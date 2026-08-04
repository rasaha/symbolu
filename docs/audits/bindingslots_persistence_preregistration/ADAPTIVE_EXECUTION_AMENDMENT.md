# Adaptive execution amendment

> **PROTOCOL AMENDMENT BEFORE TRAINING · NO TRAINING HAD STARTED AT AMENDMENT TIME · SCIENTIFIC GATES
> UNCHANGED · EXECUTION ORDER AND FUTILITY ONLY**

Amends the merged PR #1331 persistence preregistration (merge commit
`78be653642c3ec7adc385572c75c411cc0ce4fe0`). It replaces the full up-front 30-run matrix with a
**fixed sequential decision tree** plus **mathematically valid futility stopping**, to find the first
clearly successful persistence intervention without running scientifically unnecessary later arms.
This is **not** adaptive tuning. Machine-readable plan: `experiments/bindingslots_persistence/adaptive_execution_plan.json`;
deterministic controller: `adaptive_plan.py` (planning only, never trains).

## What is unchanged (every scientific definition)

Seeds 23–27; same-seed A+ requirement; O1 objective; O1R coefficient 0.01 / steps 601–1200; H1
parameter group / 0.1× / 600–900; H2 step-600 teacher + target; checkpoints 0/60/120/300/600/700/900/1200;
quality, distance, formation, routing thresholds; slots-off + randomized-address ablations;
`CLEAN_STABLE`; advancement `clean_stable ≥ 4/5`; "candidate must beat R0". Their sha256 are pinned in
the plan and verified (`verify_amendment.py`: 34 checks, 0 failures).

## What changed (order + futility + omission only)

**Reference block (always, no futility):** A+ × 23–27, then R0 × 23–27 = 10 mandatory runs (A+ precedes
R0 because the causal threshold is same-seed; every candidate must beat the *complete* R0).

**Candidate order (fixed):** O1R → H1 → H2, each on seeds 23–27 in order.

**Futility:** stop an arm immediately after its **second** non-`CLEAN_STABLE` seed — with two failures,
`clean_stable ≥ 4/5` is impossible. Remaining seeds get `ARM_FUTILITY_REACHED`.

**Success:** an arm succeeds **only after all five of its seeds complete** and `clean_stable ≥ 4/5`
**and** `> R0`. Success is never declared from four completed seeds with the fifth unrun.

**First success selects and stops:** later candidates and the O1 diagnostic are skipped
(`EARLIER_CANDIDATE_SELECTED` / `DIAGNOSTIC_NOT_REQUIRED`).

**O1 diagnostic branch:** runs only if O1R **and** H1 **and** H2 all fail; it is **not selectable** and
must not rescue a failed intervention.

## No within-seed early stopping

Every seed used for classification runs through **step 1200**. No seed is stopped for good step-600
routing, needle 1.0, early prob > 0.50, a promising intermediate checkpoint, or apparent
non-recovery. The controller only ever consumes whole-seed outcomes, so intra-seed early stopping is
impossible by construction.

## Run-count bounds

| path | runs |
|---|---|
| best case (O1R passes 5/5) | **15** (A+ 5 + R0 5 + O1R 5) |
| O1R futile → H1 passes | 17 |
| all fail (each futile after 2) → O1 diagnostic | 21 |
| worst case | **30** |

Savings come only from omitting unnecessary later runs — never from weakening the evidence a
successful candidate must produce.

## Statistical honesty

Deterministic decision tree, not outcome-driven tuning; arm order and seeds fixed before training; the
futility boundary follows directly from the 4/5 requirement. **An unrun arm is `NOT_EVALUATED`, never
failed or inferior.** Selecting O1R first does **not** prove it superior to unrun H1/H2 — only that
O1R passed the frozen advancement gate and later testing was unnecessary for this decision. Do not
compare a selected arm against unrun arms as though they failed.

## Boundary

Training the resulting plan still requires a **separate explicit authorization**
(`TRAINING_AUTHORIZATION_GATE.md`). This amendment adds no runnable training path; KDA validation
remains **BLOCKED**.
