# PR #1356 (T4 counterfactual diagnostics) — audit and merge record

**Decision: `MERGE_READY`.** Merged via merge-commit `71d52947` (reachable from and now the default tip;
local default synchronized; tree clean).

## Verified (Git + GitHub + committed artifacts + independent replay + hashes + tests + CI) — 14/14
- PR contains only the zero-training D0–D5 counterfactual diagnostics + audit record; no new training.
- **Byte-identical** param hashes for all 5 seeds (committed report matches `per_seed.json`), plus an
  **independent replay of seed 6141** reproducing the exact hash; **D0 reproduces the committed T4
  addressing**.
- Conclusion reconstructs mechanically as **`T4_SHORTFALL_MIXED`** (value-path secondary invariant
  correctly False); components abstention 0.463 / entity 0.218 / latest-ranking 0.320; D4 value-fail 0.
- Preserves `E1_TEMPORAL_TRANSFER_PARTIAL`, `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
  `KDA_VALIDATION_BLOCKED`; emits no `…_VALIDATED`/`…_CONFIRMED`/`…_ELIGIBLE`; T5 outside.
- No model/seed/gate/prediction/verdict changed; prior temporal artifact hashes intact; frozen
  `abc.json` `b31989a3…` unchanged; CI 9/9 green; 0 unresolved review threads; claims bounded.

Documentation + evidence only, faithful, CI green, no threads — nothing required correction. Merged.
