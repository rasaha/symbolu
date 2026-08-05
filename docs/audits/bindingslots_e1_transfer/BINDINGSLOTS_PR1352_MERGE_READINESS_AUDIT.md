# PR #1352 (E1 independent confirmation) — merge-readiness audit

**Decision: `MERGE_READY`.** Merged via the repository's merge-commit method (`cc66c0b0`).

## Live ground truth (Git + GitHub)
- Default advanced to `7d578d69` (DilChat #1347 merged separately); PR #1352 behind but its files are a
  disjoint tree → `mergeable_state: clean`. Head `f2f2e6ba`; 21 files; 5 commits; **0 review threads**;
  **CI 9/9 success**. Diff entirely under `experiments/bindingslots_e1_confirmation/`, its docs, and its
  CI workflow. PR #1351 merged and reachable from default.

## Mechanical evidence audit (21/21 checks pass)
Verdict recomputed from committed per-seed evidence == `E1_INDEPENDENTLY_CONFIRMED`, co-emitting
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `KDA_VALIDATION_BLOCKED`,
`E1_FOLLOW_ON_RESEARCH_ELIGIBLE`. Verified: final seeds 5140–5144 fresh and unused before lock; C1
reused with no retuning (recipe == frozen); gates == the 17 frozen PR #1351 gates; task/evaluator/leakage
suite/seeds independently rebuilt; 5/5 pass (required 4/5); E1 ≫ B0 (min improvement ≥ 0.5, mean 0.909);
no-match a separate hard gate (passing independently); determinism byte-identical; leakage suite
all_pass (no exact overlap, no answer-in-key, no opaque id, unseen eval identities, lexical-overlap at
chance, no external-table import); seeds disjoint from every prior seed; worst-seed G1 0.987 ≥ floor;
artifact hashes 8/8 match; frozen `abc.json` `b31989a3…` unchanged; torch-free tests 10/10.

## Merge
Documentation + evidence only, faithful, internally consistent, CI green, no threads — nothing required
correction. Merged; commit reachable from default; local default synchronized; tree clean; no unrelated
files.
