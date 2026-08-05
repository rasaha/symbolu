# E1 protocol lock — frozen protocol (Stage 2)

**Result: `E1_PROTOCOL_LOCKED`.** All load-bearing choices are frozen on non-reserved development
fixtures under the committed `DEV_CALIBRATION_PLAN.md`; the reserved final pool and reserved seeds are
never read in Stage 2. Machine-readable lock: `results/protocol_lock.json` (source hashes, dataset/split
hashes, frozen config + gates, mechanical selection result). Always preserved:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `KDA_VALIDATION_BLOCKED`.

## Frozen task & arms
Shared compositional semantic-matching task (`DESIGN_DECISIONS.md`): identity = pair of entity
primitives; attribute = one primitive; fact → value. Keys use canonical surface forms; queries use
different synonym surface forms + reorder + filler (no verbatim overlap). Disjoint train/dev/final
identity pools (774/181/173).
- **B0** — anonymous soft content-addressed slots (32), own next-value objective, no explicit key, no
  abstention.
- **E1** — explicit-key dual encoder (shared embedding; separate key/query heads; cosine; learned null
  key; **hard top-1** value read; contrastive InfoNCE over episode-local keys + null).

## Bounded selection (committed before selection; see DEV_CALIBRATION_PLAN.md)
Candidate set `{C1,C2,C3,C4}` frozen before the mechanical selection run. `run_dev_selection.py` trains
each on dev seed 500, evaluates dev splits, and applies the frozen rule (max mean held-out addressing −
no-match penalty; tie-break lower false-accept then fewer steps). The winner **must** equal the frozen
`SELECTED` (`results/selection_result.json`). The mechanical rule selected **C1** (mean dev addressing
1.000, no-match false-accept 0.153) over the other candidates; `SELECTED` was updated to the rule's
winner (the pre-filled guess C3 was overridden by the rule — the intended behaviour of a mechanical
selector). Frozen winner: **C1** = `steps=1200, tau=0.07, train_no_match_frac=0.30`, `D=64`, `BATCH=48`,
`LR=1e-3`, 32 keys/episode.

## Frozen numeric gates (rationale: GATE_RATIONALE.md)
Absolute competence bars motivated by the frozen B0 baseline (anonymous slots at chance, ≈0.031
addressing) and a meaningful minimum effect size — **not** thresholds set at observed dev performance.
Generalization min addr: G1/G2/G3/G5 = 0.80, G4 = 0.75. No-match: max false-accept 0.30, min recall
0.70, min precision 0.70, max confident-false-accept 0.20, max valid false-reject 0.15, min availability
0.80. End-to-end: min ordinary retrieval 0.70, **min improvement over B0 0.50**, min oracle value 0.99,
max oracle-to-predicted gap 0.30, min G7-stable addr 0.90. Fresh-seed: 5 seeds, ≥4 pass, worst-seed G1 ≥
0.70. A shortcut, memorizing, weak, collapsed-abstention, or unstable model **fails** these bars.

## Cohort & seeds
Reserved final seeds = **`[3140,3141,3142,3143,3144]`** — fresh, previously-unevaluated, disjoint from
dev (500–502), from V100 seeds (28–32), and from the **burned** set `[2028–2032]` (observed in a
premature non-preregistered run; explicitly **not** the final cohort). Reserved identities drawn from the
FINAL pool only.

## Determinism, compute, futility
CPU fp32, `threads=4`, seeded; repeated dev fixture byte-identical (verified). Max steps/seed 1800; 5
reserved seeds; futility: stop when max possible remaining passes < 4; also stop on determinism failure,
leakage detection, or resource exhaustion; **no selective seed restarts**; no post-evaluation tuning.

## Dev calibration result (non-reserved)
`determinism_ok = True`; leakage `all_pass = True`; selection winner = frozen `SELECTED`; dev seeds pass
all primary gates. Evidence: `results/selection_result.json`, `results/dev_calibration.json`,
`results/determinism.json`, `results/leakage_report.json`.
