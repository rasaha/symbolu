# PR #1353 (transfer preregistration) — audit and merge record

**Decision: `MERGE_READY`.** Merged via merge-commit `780b2b9d` (2-parent; reachable from and now the
default tip; local default synchronized; tree clean).

## Verified (Git + GitHub + diff + CI)
- **Documentation-only:** diff is exactly the two `.md` deliverables under
  `docs/audits/bindingslots_e1_transfer/`; no code, no execution artifacts.
- **Accurately records** the PR #1352 audit + merge (`cc66c0b0`).
- **Structurally different task** proposed (Temporal Event Memory — temporal ordering / updates /
  relations, not new vocabulary/paraphrase).
- **Exact frozen C1 recipe preserved** (steps 1200, τ 0.07, no-match-frac 0.30, learned null key,
  contrastive episode-local matching, hard top-1, ~32 keys, D=64; no architecture/dimension/loss/
  optimizer/capacity change).
- **Within C1's plausible capacity** (density ~32, bounded lengths, bounded integer position tokens, no
  larger tokenizer/LM; structural not linguistic variation).
- **Proposed seeds disjoint** from every prior experiment (train 73; dev 720–722; final 6140–6144).
- **No transfer implementation or execution** existed on the branch.
- **`abc.json` `b31989a3…` unchanged**; earlier evidence untouched; **KDA remains blocked**.
- **CI 7/7 green; 0 unresolved review threads;** not behind default at merge time.

Documentation-only, faithful, CI green, no threads — nothing required correction. Merged.
