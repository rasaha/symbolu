# Live K8s Scenario Corpus (V2.1 §6)

18 deterministic scenarios. Code:
`robotics_reliability_bench/acp_k8s_integrated/corpus.py`. Base Deployment state
is the **real** `action_gateway_k8s` fixture (`web` / `gw-web`, ns `protected`,
`replicas: 1`); the discriminating operational variable is authored where no
offline source exists. Provenance:
`REPOSITORY_INTEGRATION_FIXTURE` 1 · `AUTHORED_DETERMINISTIC` 13 ·
`SYNTHETIC_UNIT` 4. No local-cluster data is called production customer evidence.

| # | scenario | provenance | real ActionGate | ACP | expected composition class |
|---|---|---|---|---|---|
| 1 | authorized_healthy_scale | REPO_FIXTURE | ALLOW | PROCEED | `AUTHORIZED_AND_OPERATIONALLY_SAFE` |
| 2 | unauthorized_but_safe | AUTHORED | DENY (ns) | safe | `BLOCKED_BY_AUTHORIZATION` |
| 3 | authorized_readiness_cooldown | AUTHORED | ALLOW | HOLD | `HELD_BY_OPERATIONAL_SAFETY` |
| 4 | authorized_excessive_replicas | AUTHORED | ALLOW | HOLD | `HELD_BY_OPERATIONAL_SAFETY` |
| 5 | stale_operational_state | AUTHORED | ALLOW | stale | `REQUEST_FRESH_OPERATIONAL_STATE` |
| 6 | state_drift_after_eval | SYNTHETIC | ALLOW | PROCEED | `AUTHORIZED_…SAFE` + commit reject (both) |
| 7 | modified_patch_after_eval | SYNTHETIC | ALLOW | PROCEED | `AUTHORIZED_…SAFE` + commit reject (both) |
| 8 | rollout_missing_rollback | AUTHORED | ALLOW | HOLD | `HELD_BY_OPERATIONAL_SAFETY` |
| 9 | active_freeze_window | AUTHORED | ALLOW | HOLD | `HELD_BY_OPERATIONAL_SAFETY` |
| 10 | dependency_unhealthy | AUTHORED | ALLOW | HOLD | `HELD_BY_OPERATIONAL_SAFETY` |
| 11 | blocked_by_both | AUTHORED | DENY (ns) | HOLD (freeze) | `BLOCKED_BY_BOTH` |
| 12 | ag_requests_evidence_acp_passes | AUTHORED | SIMULATE_AND_RETRY | safe | `REQUEST_MORE_EVIDENCE` |
| 13 | ag_passes_acp_requests_fresh | AUTHORED | ALLOW | stale | `REQUEST_FRESH_OPERATIONAL_STATE` |
| 14 | composition_identity_mismatch | SYNTHETIC | ALLOW | (divergent patch) | `COMPOSITION_IDENTITY_MISMATCH` |
| 15 | evaluator_exception | SYNTHETIC | — | — | `SHADOW_ERROR` |
| 16 | no_safe_rollout_candidate | AUTHORED | ALLOW | HOLD (freeze+cooldown+no-rollback) | `HELD_BY_OPERATIONAL_SAFETY` |
| 17 | authorized_delete_safe | AUTHORED | ALLOW (approved) | HOLD (delete→0 min-avail) | `HELD_BY_OPERATIONAL_SAFETY` |
| 18 | delete_escalates_to_human | AUTHORED | ESCALATE_TO_HUMAN | — | `REQUEST_MORE_EVIDENCE` |

All 8 composition classes are exercised. The two required cross-layer cases —
**ActionGate requests evidence while ACP passes** (#12) and **ActionGate passes
while ACP requests fresh state** (#13) — prove the layers ask for different things
from their own domains. #6/#7 exercise commit-time drift (both layers reject).
#14 proves identity binding fails closed. #15 proves exception containment.

Base fixture facts (real): `web`/`gw-web`, ns `protected`, `replicas: 1`,
restricted-PSS pod spec (`cluster_fixtures.sh:44-62`, `scenarios.py:79-91`).
Authored fields (labelled): `resource_version` (e.g. `1001`), `available_replicas`,
`readiness_plasticity`, `seconds_since_last_action`, `freeze_active`,
`dependency_healthy` — none has an offline repository source.
