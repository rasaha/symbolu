# PR #1355 (T4 error-structure analysis) — audit and merge record

**Decision: `MERGE_READY`.** Merged via merge-commit `e4a9d327` (2-parent; reachable from and now the
default tip; local default synchronized; tree clean).

## Verified (Git + GitHub + committed artifacts + independent replay + hashes + tests + CI) — 19/19
- PR contains only the T4 error-structure analysis (spec, implementation, evidence, tests, CI step) and
  its audit record; **no new training**.
- **Deterministic replay byte-identical:** the committed `param_hash_report` matches `per_seed.json`
  `e1_param_sha256` for all 5 seeds, and an **independent replay of seed 6140 reproduced the exact param
  hash**.
- The classification categories + conclusion rule were committed **before** any aggregate was read;
  conclusion reconstructs mechanically as **`T4_ERROR_ANALYSIS_INCONCLUSIVE`**.
- Counts exact: **750** total T4 queries; **294** end-to-end failures; **77.9%** `NULL_OR_ABSTAIN`;
  **17.0%** right-entity/wrong-older; **5.1%** wrong-entity; **0%** invalid/other.
- Supplementary null-excluded addressing analysis is explicitly separated from the frozen conclusion;
  null-excluded failures split **~50/50** (0.506 older / 0.494 wrong-entity); **abstention ≈ 30.5%** of
  all T4; **at-step control recovers the target ≈ 92%**.
- **T5 outside the conclusion**; no model/seed/gate/prior-evidence/verdict changed; prior temporal
  artifact hashes match; frozen `abc.json` `b31989a3…` unchanged; merged verdict
  `E1_TEMPORAL_TRANSFER_PARTIAL` preserved; no `…_VALIDATED`/`…_CONFIRMED`/`…_ELIGIBLE` emitted; CI 9/9
  green; 0 unresolved review threads; claims bounded.

Documentation + evidence only, faithful, CI green, no threads — nothing required correction. Merged.
