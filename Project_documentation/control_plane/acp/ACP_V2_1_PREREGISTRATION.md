# ACP V2.1 — Preregistration (live ActionGate + ACP composition for Kubernetes)

**Committed BEFORE the final integrated shadow run.** Frozen below: the operation
path, the environment, the corpus, the policies, the operational constraints, the
identity mapping, the composition rules, the thresholds, the stale limits, the
latency criteria, the verdict rules, the success criteria, and the exclusions.
Deviations are appended post-hoc, never edited in place.

**Standing constraints (V2.1):** shadow-only; neither ActionGate nor ACP is
authoritative; **no real execution** through the shadow stack; **no cluster
mutation** (no live/kind/k3d cluster is available — see §2); the frozen ACP V1
core is unchanged (hash-verified); ActionGate is unchanged (only invoked); no
VC-brief change; no platform claim beyond the measured Kubernetes composition;
do not recommend production enforcement.

---

## 1. Selected Kubernetes path (frozen)

**Deployment scale / rollout / delete** on the real `action_gateway_k8s`
integration-fixture Deployment `web` / `gw-web` in namespace `protected`
(`replicas: 1`; `scripts/cluster_fixtures.sh:44-62`, `demos/scenarios.py:79-91`).
Mapped to ActionGate operation `DEPLOY` (scale/rollout via `kubernetes.apply`) or
`DB_DELETE` (delete), per `action_gateway_k8s/mapping.py`.

The current authoritative execution path (the real `K8sGateway` /
`cloud_controller` actuator) is **unchanged**; this study only *observes*.

## 2. Environment (frozen) + exclusions

A live, kind, or k3d cluster is **infeasible** in this environment: no
`kubectl` / `kind` / `k3d` / `minikube` / `kubernetes` client is installed, and
the cluster provisioners (`action_gateway_k8s/scripts/cluster_up.sh`,
`deploy/local-shadow/bring_up.sh`) require network-gated binary/image downloads.
Therefore, per the milestone's fallback order (§1: "repository-native fake API
server only if a real local cluster is infeasible"), and because **no fake API
server exists** in the repo, we run:

- the **real frozen ActionGate engine** (`action_gate_ref.gate.evaluate` +
  `action_gateway_k8s.policy`) — stdlib-only, offline, real authorization;
- the **real ACP cloud adapter** (frozen ACP core + real `cloud_controller`
  readiness/policy/safety) — offline, real operational safety;

on **reproducible Deployment state modelled from the real integration fixture**.
`resourceVersion`, `availableReplicas`, readiness, freeze windows, and dependency
health have no offline source and are **authored**, labelled
`AUTHORED_DETERMINISTIC`. **Exclusions:** no live cluster; no server-side dry-run;
no real `availableReplicas`; no token minting/redemption; no broker capability; no
cluster mutation. These are environment limits, reported honestly, not defects.

## 3. Policies (frozen)

- **ActionGate:** the real signed Kubernetes bundle
  `action_gateway_k8s.policy.build_bundle(allowed_namespaces=("protected",))`
  signed via `action_gate_ref.policy.sign_policy` (rules `K8S_DEPLOY`,
  `K8S_DELETE`; real deterministic admission checks). Signing is the reference
  HMAC stand-in (not production crypto) — a documented ActionGate limitation, not
  ours.
- **ACP:** the real `cloud_controller` defaults — `ReadinessConfig`
  (min_plasticity 0.3, min_time_since_action 120 s), `DeploymentPolicy`
  (min 1 / max 100), `SafetyConfig` (+50 % / −25 %, min_replicas 1).

## 4. Operational constraints (frozen)

The ACP cloud hard-constraint set from V2 (`ACP_CLOUD_CONSTRAINTS.md`), unchanged:
`STATE_FRESH`, `TARGET_BOUND`, `READINESS_OK`, `REPLICA_WITHIN_LIMIT`,
`BLAST_RADIUS_WITHIN_BOUND`, `MIN_AVAILABILITY_PRESERVED`, `NO_ACTIVE_FREEZE`,
`DEPENDENCY_HEALTHY`, `CAPACITY_SUFFICIENT`, `ROLLBACK_AVAILABLE`. Stale limit:
`freshness_s ≤ 30 s` (fail closed).

## 5. Identity mapping (frozen)

One `KubernetesOperation` is the single source of truth. Both layers bind to the
same operation via the pair `(manifest_digest, current_state_hash)`, computed with
the **real** ActionGate hashing conventions (`mapping.py:121`, `server.py:75-85`),
plus a shared `operation_digest` and `state_version`. `bind()` re-derives these
from each layer's own artifacts and fails closed
(`COMPOSITION_IDENTITY_MISMATCH`) on any disagreement. The two decision schemas
are **not** merged.

## 6. Composition rules (frozen — 8 classes)

Precedence, non-compensatory, top-down: `COMPOSITION_IDENTITY_MISMATCH` →
`SHADOW_ERROR` → (`DENY` + ACP hard hold) `BLOCKED_BY_BOTH` → `DENY`
`BLOCKED_BY_AUTHORIZATION` → gate-not-final `REQUEST_MORE_EVIDENCE` → (authorized
+ ACP stale/missing) `REQUEST_FRESH_OPERATIONAL_STATE` → (authorized + ACP hard
hold) `HELD_BY_OPERATIONAL_SAFETY` → (authorized + ACP safe)
`AUTHORIZED_AND_OPERATIONALLY_SAFE`. **ActionGate DENY is never overridden; ACP
never grants authorization; ALLOW does not override an ACP hard hold; execution is
hypothetically eligible only when both pass.**

## 7. Corpus (frozen, 18 scenarios)

Provenance-labelled `REPOSITORY_INTEGRATION_FIXTURE` / `AUTHORED_DETERMINISTIC` /
`SYNTHETIC_UNIT` (`LIVE_K8S_SCENARIO_CORPUS.md`). Required members: authorized
healthy scale; unauthorized-but-safe; readiness cooldown; capacity/replica limit;
stale resourceVersion; state drift after eval; modified patch after eval; missing
rollback; active freeze; dependency/readiness failure; both block; AG-requests-
evidence-while-ACP-passes; AG-passes-while-ACP-requests-fresh; identity mismatch;
evaluator exception; no-safe-candidate (+ two delete cases). Each names its
expected composition class.

## 8. Thresholds / stale limits / latency criteria (frozen)

ACP freshness ≤ 30 s. ActionGate evidence freshness per its own `valid_until`.
Latency: mean/p95/max of the full integrated evaluation reported; no repository
budget exists, so latency is descriptive, not a pass/fail gate.

## 9. Verdict rules (frozen)

- **Integrated composition** → `INTEGRATED_STACK_SUPPORTED` iff all §11 invariants
  pass, all 8 classes are produced, and 0 corpus mismatches; `…_WITH_LIMITATIONS`
  if it works but rests on a documented environment concession (e.g. no live
  cluster); `…_NOT_SUPPORTED` if any invariant fails.
- **Live Kubernetes evidence** → `LIVE_K8S_SHADOW_SUPPORTED` iff run against a real
  cluster; `LIVE_K8S_SHADOW_LIMITED` if the real engines run on reproducible
  fixture/authored state without a live cluster; `LIVE_K8S_EVIDENCE_INSUFFICIENT`
  if neither engine is real.
- **Product evidence** → `CONTROL_PLANE_STACK_VALIDATED` /
  `…_PARTIALLY_VALIDATED` / `PLATFORM_CLAIM_PREMATURE`, argued from the evidence.

## 10. Success criteria (frozen)

All 13 §11 invariants pass; all 8 composition classes produced by REAL engines; 0
corpus mismatches; deterministic rerun + deterministic ActionGate action hash; 0
authoritative behaviour changes; 0 cluster mutations; both layers reject state
drift and patch mutation at commit time.

## 11. Exclusions (frozen)

No live cluster; no fake API server (none exists); `availableReplicas`/readiness
authored; ActionGate signing is the HMAC stand-in; latency has no repository
budget; one operation family (Deployment) on one fixture — decision-grade
evidence, not certification; no platform claim beyond this Kubernetes composition.
