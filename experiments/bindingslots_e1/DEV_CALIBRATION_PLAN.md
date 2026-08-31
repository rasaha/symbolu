# E1 bounded development-calibration plan (committed before selection)

This plan is committed and pushed **before** the mechanical configuration-selection run. It fixes the
candidate set, seeds, budgets, and selection rule so the single frozen E1 configuration cannot be
adapted after observing development results. Machine-readable twin: `dev_calibration_plan.json`.

**Transparency:** an earlier *exploratory* sweep (3 configurations) was run before this discipline was
imposed and informed the candidate set below. That premature run also produced a reserved evaluation on
seeds 2028–2032; those seeds are therefore **burned** and are **not** the final cohort. The final cohort
uses fresh, previously-unevaluated seeds (below). This plan + the fresh cohort restore preregistration
discipline; the selection is executed mechanically under the committed rule.

## Non-reserved development seeds
`DEV_SEEDS = [500, 501, 502]`. Selection score is computed on the primary dev seed **500**; the chosen
configuration is then verified to pass all frozen gates on all three dev seeds. **Reserved final pool and
reserved seeds are never read during calibration.**

## Candidate configurations (exact; no expansion after observing results)
Each candidate = `(steps, tau, train_no_match_frac)`:
- **C1** = (1200, 0.07, 0.30)
- **C2** = (1800, 0.05, 0.30)
- **C3** = (1800, 0.05, 0.40)
- **C4** = (1500, 0.05, 0.40)

Fixed across all candidates: `D=64`, `BATCH=48`, `LR=1e-3`, 1500 train episodes (seed 7), 32 keys/episode,
learned-null-key no-match, cosine score, hard top-1 read.

## Bounds
- **Maximum candidate configurations:** 4.
- **Maximum development runs:** ≤ 40 model trainings (4 candidates × selection + 3-seed verification of
  the winner, each an E1 and a B0 training).
- **Maximum steps per run:** 1800. **Maximum wall-clock per run:** 120 s.
- **Total development compute budget:** ≤ 30 minutes wall-clock.

## Selection rule (mechanical; frozen; no reserved data)
On dev seed 500, for each candidate: train E1 + B0 on the fixed train episodes; evaluate on the dev-pool
splits; require `determinism_ok` and leakage-suite `all_pass`. Compute
`score = mean(addressing over {G1,G2,G3,G4,G5,G7}) − max(0, nomatch_false_accept − 0.30)`.
Select `argmax(score)`; tie-break by **lower** `nomatch_false_accept`, then **fewer** steps. The winner
is frozen as `config.SELECTED`; `run_dev_selection.py` asserts the rule's winner equals the frozen
`SELECTED` and records the full candidate scores in `results/selection_result.json`.

## After selection
The frozen configuration is unchanged for the rest of the experiment. Gates (see `GATE_RATIONALE.md`)
are frozen independently of the reserved cohort. The reserved go/no-go runs once on the fresh seeds
`[3140, 3141, 3142, 3143, 3144]` and is never repeated to improve the result.
