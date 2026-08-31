# PR #1349 — independent merge-readiness audit

**Decision: `MERGE_READY_AFTER_SCOPED_CORRECTIONS`** (sole scoped change: this audit report added as
documentation; no evidence, seed, cohort, arm, threshold, timing record, metric, classification,
result, or verdict touched).

## 1. Live ground truth (checked directly from Git + GitHub)

| item | value |
|---|---|
| authoritative default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| default tip | `2e159f17` (== PR base; branch not behind, not diverged) |
| PR base / head | `2e159f17` / `2813fc58` |
| PR state | open, draft, not merged; `mergeable_state: clean` |
| commits / files | 7 commits (prescribed order) / 26 files |
| scope | all under `experiments/bindingslots_v100_reference/**`, its `docs/audits/**`, and its CI workflow; no out-of-scope files, no `_progress`/logs/db/binaries |
| reviews / unresolved threads | none / none |
| CI | **9/9 success** (v100-integrity ×2, pipeline-ci ×2, invariance-audit ×2, terminology, API-stability, Safety-case+SBOM) |
| #1346 / #1348 | both merged and reachable from default (`6a9ad7ed`, `2e159f17`) |

## 2. Mechanical verdict reconstruction (recomputed from committed raw per-seed evidence)

Recomputing `aggregate → gates → verdict` from `per_arm_results.json` + `isolation_tests.json`
reproduces the committed verdict **exactly**:
**`ALWAYS_VERIFY_RELIABILITY_VERIFIED_OPERATIONAL_COST_UNRESOLVED`**, co-emitting
`KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE`, `BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`KDA_VALIDATION_BLOCKED`; **17/17 hard gates pass**; the forbidden
`ALWAYS_VERIFY_OPERATIONALLY_QUALIFIED` is not emitted.

All committed claims verified (seeds 28–32; n=600): M0 = 0.208 and **byte-identical to the merged
baseline** per seed; T0 = 1.000; F0 = 0.842 (recall 0.80, precision 0.964, **95** confidently-wrong
missed); V100 = 1.000 (agreements **125**, corrections **475**, incorrect verified **0**, incorrect
corrections **0**, abstentions **0**); all **475** disagreements detected and corrected; **exactly one
table read per query** (600 total); provenance 1.000; cross-session/tenant leakage 0;
stale/expired/deleted/incorrect-version returns 0; table-unavailable + injected read/write failures fail
closed; cleanup leaves 0 live rows; model params unchanged; **0 eval optimizer steps**; deterministic
replay + trajectory reproduction succeeded.

## 3. Latency interpretation

Confirmed from `timing_characterization.json`: V100 query p50 ≈ **15.85 ms** (neural inference ≈ 15.78 ms,
**99.5%** of the path) vs T0 p50 ≈ **0.023 ms** → V100 ≈ **688×** the table-only path. Timing is flagged
characterization-only, no ceiling approved, and the note explicitly forbids substituting the isolated
~0.006 ms read for end-to-end latency. The reports do **not** imply a latency optimization, table-read
avoidance, lookup improvement over T0, production/enterprise latency, operational qualification, routing
repair, confidence⇒correctness, or KDA unblock — every such phrase occurs only in explicit non-claim
context.

## 4. Independent checks

- Torch-free semantics/lifecycle/verdict tests: **17/17 pass**.
- Torch-backed invariance tests (no param change, zero optimizer steps, byte-identical M0, exactly one
  read/query): **4/4 pass**.
- Artifact-hash manifest: **8/8 match, 0 mismatches**.
- Frozen `abc.json` `b31989a3…` **unchanged**.
- Terminology / API-stability / invariance / Safety-case CI: green.

## 5. Decision and merge

Nothing in the raw evidence, seeds, cohort, arm definitions, thresholds, timing records, metrics,
classifications, results, or verdict required change. The sole scoped change is this audit report
(documentation). Merge is explicitly authorized for `MERGE_READY(_AFTER_SCOPED_CORRECTIONS)`; merged via
the repository's established merge-commit method.
