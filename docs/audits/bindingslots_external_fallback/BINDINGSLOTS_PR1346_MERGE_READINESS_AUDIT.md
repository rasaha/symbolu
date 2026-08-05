# PR #1346 — independent merge-readiness audit

**Decision: `MERGE_READY_AFTER_SCOPED_CORRECTIONS`** (only scoped change: this audit report added as
documentation; no evidence/verdict/threshold/arm/metric touched).

## 1. Live ground truth (checked directly from Git + GitHub)

| item | value |
|---|---|
| authoritative default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| default tip | `6e4ba3e8` (== PR base; branch not behind) |
| PR base / head | `6e4ba3e8` / `93ce2f8d` |
| local branch / head | `claude/bindingslots-external-ephemeral-fallback` / `93ce2f8d` (synced with origin) |
| working tree | clean |
| PR state | open, draft, not merged |
| mergeability | mergeable; base == default tip (clean 3-way, no conflict) |
| CI | **9/9 success** (pipeline-ci, invariance-audit, fallback-integrity, terminology, API-stability, Safety-case+SBOM) |
| reviews / unresolved threads | none / none |
| #1344 / #1345 | both merged and reachable from default (`05dcee8e`, `6e4ba3e8`) |
| diff scope | 26 files, all under `experiments/bindingslots_external_fallback`, its docs, and its CI workflow; no out-of-scope files, no `_progress`/logs/db/binaries |

## 2. Mechanical verdict reconstruction (from committed evidence)

Verdict on default-committable evidence: **`EXTERNAL_TABLE_RELIABILITY_VERIFIED_HYBRID_TRIGGER_FAILED`**
co-emitting **`BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`** and **`KDA_VALIDATION_BLOCKED`**. All 19
committed claims verified:

- M0/T0/F1 completed on frozen seeds 28–32; T0 = 1.000; F1 ≈ 0.842; recall ≈ 0.80; precision ≈ 0.964;
  **95** confidently-wrong reads missed (`fn`); incorrect-fallback rate = 0; cross-session leakage = 0;
  cross-tenant leakage = 0; expired never returned; deleted never returned; provenance = 1.000; p95
  read latency ≈ 0.006 ms; fallback-disabled byte-identical gate true; no model weight/gradient change;
  deterministic reproductions matched committed B0; gate `all_pass` = False (hybrid failed as expected).
- Report does **not** imply routing repaired / confidence = correctness / hybrid qualified / table as a
  system of record / KDA unblocked — the only occurrences of such phrases are in explicit *non-claim*
  (negation) contexts.

## 3. Audit checks

- Torch-free adapter/lifecycle/isolation/trigger tests: **15/15 pass**.
- Torch-backed tests (no-param-change, fallback-disabled == M0, table-only + provenance): **4/4 pass**.
- Artifact-manifest hash verification: **8/8 match, 0 mismatches**.
- Frozen `abc.json` `b31989a3…` **unchanged**; storage guard against tensors/gradients/labels present.
- Terminology / API-stability / safety CI: green.

## 4. Decision and merge

Nothing in the raw evidence, seeds, cohort, calibration cohort, thresholds, trigger behavior, arm
definitions, metrics, results, or verdict required change. The sole scoped change is this audit report
(documentation). Merge is explicitly authorized for `MERGE_READY(_AFTER_SCOPED_CORRECTIONS)`; merged
via the repository's established merge-commit method. Merge confirmation is recorded in the phase's
integrity trail and this PR's merged state.
