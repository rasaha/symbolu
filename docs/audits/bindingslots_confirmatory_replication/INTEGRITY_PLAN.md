# Integrity plan

## Frozen-artifact protection

- `experiments/phase_lc/results/abc.json` sha256 `b31989a3…` is recorded **before** and **after**
  training in the run manifest and must be unchanged.
- 15 frozen source/config hashes are pinned in `frozen_cr1_config.json` and re-verified by
  `verify_confirmatory_prereg.py` (27 checks) before every run and in CI.
- The existing `scripts/verify_historical_artifact_protection.py` (8 checks) and `scripts/verify_lab.py`
  (81 checks) continue to guard the merged evidence; both must stay green.

## No-forbidden-architecture

`verify_confirmatory_prereg.py` scans the confirmatory harness for `Phase` / `KDA` / `MLA` /
`quadratic_attention` markers. The AST/import boundary tests under
`hybrid_llm_vnext_lab/tests/boundaries/` continue to enforce absence in the graph. Parameter count
(2 000 104 slot / 2 000 392 A+) and architecture signature `6e8672bd…` are asserted.

## Preregistration-before-results

The preregistration commit is pushed **before** any result artifact exists. CI asserts the
preregistration files are present and their hashes match, and that `results/` never predates the
preregistration commit recorded in `results/manifest.json`.

## Evidence completeness

Every conclusion is traceable to a committed curated artifact: per-seed
`results/seeds/<arm>_seed<n>.json` (trajectory, routing, ablations, ppl, params, config hash, code
commit, environment) and the aggregate `results/aggregate_result.json`. Raw per-step traces follow
the merged raw-trace policy (checksums committed; bulk traces may live outside Git) — the curated
evidence alone suffices to reconstruct the verdict.
