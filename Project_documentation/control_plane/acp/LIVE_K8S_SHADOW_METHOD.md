# Live K8s Shadow Method (V2.1 §7, §8)

How the integrated ActionGate + ACP shadow benchmark runs and measures, and what
is real vs reproduced. Code:
`robotics_reliability_bench/acp_k8s_integrated/{harness,run_integrated_bench}.py`.
Results: `robotics_reliability_bench/results/acp_k8s_integrated_results.json`.

## What is real

- **ActionGate is the real frozen engine.** Every verdict comes from
  `action_gate_ref.gate.evaluate` over a real 24-field envelope
  (schema-validated), the real signed Kubernetes policy bundle
  (`action_gateway_k8s.policy` + `action_gate_ref.policy.sign_policy`), real
  `kubernetes_admission` / `simulation` / `rollback_attestation` evidence, real
  approvals, a real `action_hash`, and real dispositive rules. No synthetic
  verdict is ever supplied. Different outcomes come from **real inputs**: an
  out-of-scope namespace or non-compliant manifest makes the real deterministic
  admission check withhold evidence → real `DENY`; a missing dry-run simulation →
  real `SIMULATE_AND_RETRY`; a delete without approval → real `ESCALATE_TO_HUMAN`.
- **ACP is the real frozen core + real `cloud_controller`.** Readiness, policy
  bounds, and safety bounds are computed by the actual
  `ReadinessChecker` / `PolicyEngine` / `SafetyBounds`.
- **The hashing/binding is real.** `manifest_digest` and `current_state_hash` use
  the real ActionGate domain-digest conventions, so the cross-layer binding is
  byte-exact.

## What is reproduced (and honestly labelled)

A live / kind / k3d cluster is **infeasible** here: no `kubectl` / `kind` / `k3d` /
`minikube` / `kubernetes` client, and the provisioners need network-gated
downloads; **no repository fake API server exists**. So the Deployment *state* is
modelled from the real `action_gateway_k8s` fixture (`web` / `gw-web`, ns
`protected`, `replicas: 1`) with `resourceVersion`, `availableReplicas`,
readiness, freeze, and dependency health **authored** (`AUTHORED_DETERMINISTIC`).
This is exactly the milestone's stated fallback when a real local cluster is
infeasible, reported as an environment limit — not a live-cluster claim.

## Feed & flow (per scenario, deterministic)

```
KubernetesOperation
   -> run_actiongate(...)          # REAL ActionGate outcome + action_hash
   -> CloudShadowAdapter.observe   # REAL ACP recommendation + evidence validity
   -> bind(...)                    # identity binding (fail-closed)
   -> compose(...)                 # 8-class composition
   -> commit_revalidate(...)       # optional drift check (both layers)
   -> IntegratedRecord             # bounded sink
```

Fixed clocks throughout (ActionGate `NOW`; ACP `now_s = 0.0`) so every run is
byte-reproducible.

## Commit-time revalidation (§8)

For drift scenarios, immediately before hypothetical execution the harness
rechecks and records **which layer rejects**:

| drift | ActionGate rejects because | ACP rejects because |
|---|---|---|
| resourceVersion change | recomputed `current_state_hash` ≠ bound hash (E_STALE_STATE) | frozen `ReferenceCommitRevalidator`: `world.version` changed |
| manifest/patch mutation | recomputed action-hash input ≠ bound `manifest_digest` | frozen revalidator: candidate identity changed |
| policy-version change | bound `policy_version` ≠ current | (ActionGate-owned; ACP N/A) |

Both layers independently reject resourceVersion drift and patch mutation — the
composed result is invalidated by whichever layer owns the drifted fact.

## Measures (§10)

**ActionGate:** outcome distribution; allow/deny/pending rates; action-hash
determinism. **ACP:** recommendation + validity distribution; evidence-valid rate.
**Composition:** class distribution; both-pass / auth-only-block / op-only-hold /
both-block / identity-mismatch counts; contradictory-ownership errors (0 by
design — disjoint reason spaces); duplicated constraints (0 by design); state-drift
rejections; authoritative-behaviour-change count (0); shadow-error rate; latency
mean/p95/max. **Determinism:** whole corpus run twice; deterministic content
signature compared; action hashes compared.

## Zero-impact guarantees (verified)

The harness makes **no** Kubernetes API call (no client imported — asserted by
test), mints/consumes **no** ActionGate execution token, mutates **no** cluster
(`cluster_mutated` is always `False`), and changes **no** authoritative path
(`authoritative_behavior_change_count = 0`). Every record is `shadow_only`.
Exceptions are contained and surfaced as `SHADOW_ERROR`.

## Rollback & kill-switch (§13.10)

- **Kill switch:** `IntegratedShadowHarness(enabled=False)` (default) — no work,
  returns `None`. Not wired into any production path.
- **Rollback:** delete `robotics_reliability_bench/acp_k8s_integrated/`; nothing in
  production imports it; the frozen ACP core, the ACP V2 cloud adapter, and all
  ActionGate packages are untouched (ActionGate is only *invoked*, never modified).
- **Tested:** OFF ⇒ `None` + no record; exception contained ⇒ `SHADOW_ERROR`;
  bounded sink caps length + counts drops; determinism 100 %.
