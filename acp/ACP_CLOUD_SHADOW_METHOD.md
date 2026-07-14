# ACP Cloud Shadow Method (V2 §9, §12)

How the cloud shadow benchmark runs and measures. Code:
`robotics_reliability_bench/acp_cloud/{corpus.py,run_cloud_bench.py}`. Results:
`robotics_reliability_bench/results/acp_cloud_results.json`.

## Corpus (19 scenarios, provenance-labelled)

| scenario | provenance | exercises | expected |
|---|---|---|---|
| `healthy_rollout` | REPOSITORY_MANIFEST | demo-app scale on ready cluster | PROCEED |
| `insufficient_capacity` | AUTHORED | mutate deployment with 0 available | HELD_BY_ACP |
| `stale_state` | AUTHORED | freshness > 30 s | HELD_BY_ACP |
| `invalid_manifest` | AUTHORED | ROLLOUT with no rollback ref | HELD_BY_ACP |
| `excessive_replica_increase` | REPOSITORY_SCENARIO | 3→90 over real SafetyBounds | HELD_BY_ACP |
| `excessive_blast_radius` | AUTHORED | DELETE of 8 replicas | HELD_BY_ACP |
| `missing_rollback` | AUTHORED | CONFIG_UPDATE, no rollback | HELD_BY_ACP |
| `dependency_unhealthy` | AUTHORED | dependency down | HELD_BY_ACP |
| `active_freeze_window` | REPOSITORY_SCENARIO | real BlackoutWindow active | HELD_BY_ACP |
| `safe_constrained_rollout` | REPOSITORY_MANIFEST | rollout, rollback, surge 1 | PROCEED |
| `destructive_delete_small` | AUTHORED | DELETE 2→0, gate escalates | PENDING_AUTHORIZATION |
| `modified_manifest_after_eval` | SYNTHETIC_UNIT | digest mutated at commit | PROCEED + revalidation reject |
| `state_drift` | SYNTHETIC_UNIT | resourceVersion drifts at commit | PROCEED + revalidation reject |
| `all_strategies_unsafe` | SYNTHETIC_UNIT | no admissible candidate | HELD_BY_ACP |
| **`ag_allows_acp_holds`** | REPOSITORY_SCENARIO | **authorized but not ready (30 s < 120 s)** | **HELD_BY_ACP** |
| **`ag_denies_acp_safe`** | REPOSITORY_SCENARIO | **safe but gate DENY** | **BLOCKED_BY_AUTHORIZATION** |
| `missing_state` | SYNTHETIC_UNIT | no snapshot | HELD_BY_ACP |
| `state_binding_mismatch` | SYNTHETIC_UNIT | candidate on stale version | HELD_BY_ACP |
| `ncc_controller_scale` | REPOSITORY_MANIFEST | real ncc-controller 1→1 | PROCEED |

All 16 required §9 scenarios are present, including the two decisive boundary
cases. Times are fixed constants (no wall clock) so the corpus is fully
deterministic.

## Measures (§12)

**Cloud shadow:** decision distribution (`ActionDecision`), recommendation
distribution (`CloudRecommendation`), fail-closed count, and the invariant
"every fail-closed evidence ⇒ HOLD".

**ActionGate × ACP composition:** combined-outcome distribution
(`PROCEED / HELD_BY_ACP / PENDING_AUTHORIZATION / BLOCKED_BY_AUTHORIZATION`),
ACP-decisive count (`HELD_BY_ACP`), authorization-blocked count, both-layers-
proceed count.

**Determinism:** the whole corpus is run twice; the deterministic content
signature (decision, recommendation, combined, validity, reason codes,
revalidation — latency excluded) is compared for byte-identity. Sink `seen` /
`dropped` reported.

**Latency:** lazy imports of the real `cloud_controller` modules are warmed up
first, then `perf_counter` wraps each `observe`; mean / p95 / max reported.

**Correctness:** each scenario's `(permissive, combined)` is compared to the
value **preregistered** in `corpus.py`; 0 mismatches required.

**Commit revalidation:** for `state_drift` and `modified_manifest_after_eval`,
`commit_revalidate` is called with the drifted world / mutated candidate;
`still_valid=False` is required for both.

## Zero-impact guarantees

The harness constructs cloud envelopes and calls the shadow adapter only; it
imports no Kubernetes client, contacts no cluster, and mutates no state. The
`cloud_controller` loggers are silenced (their policy-denial warnings are
expected corpus outcomes, not errors). No production module imports the cloud
adapter.
