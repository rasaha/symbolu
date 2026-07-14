# ACP V2.1 — Results & Verdicts (live ActionGate + ACP composition, Kubernetes)

**Run:** deterministic integrated shadow benchmark, 18 Kubernetes scenarios.
Machine-readable: `robotics_reliability_bench/results/acp_k8s_integrated_results.json`.
Preregistration: `ACP_V2_1_PREREGISTRATION.md` (committed `a1fec91`, **before**
this run). **Shadow-only. Neither ActionGate nor ACP authoritative. No cluster
mutated. No token minted. Zero authoritative behaviour change.**

The frozen ACP V1 core is **hash-identical** (`8f8660e293308cf94c983a26a2ae69c9`);
ActionGate is **unmodified** (only invoked).

---

## 1. Headline

| metric | value |
|---|---|
| scenarios | 18 (REPO_FIXTURE 1 · AUTHORED 13 · SYNTHETIC 4) |
| real ActionGate outcomes | ALLOW 13 · DENY 2 · SIMULATE_AND_RETRY 1 · ESCALATE_TO_HUMAN 1 |
| composition classes produced | **all 8** |
| both pass | 3 · authorization-only block 1 · operational-only hold 7 · both block 1 · identity mismatch 1 |
| corpus expectations met | **18 / 18** (0 class mismatches, 0 commit mismatches) |
| §11 invariants (13) | **all pass** |
| determinism | rerun **100 %** · ActionGate action-hash **deterministic** · sink dropped **0** |
| contradictory-ownership errors / duplicated constraints | **0 / 0** |
| authoritative behaviour changes / cluster mutations | **0 / 0** |
| latency (full integrated eval) | mean **2.5 ms** · p95 **3.2 ms** · max **3.6 ms** |

## 2. The stack answers two questions independently, on one bound action

Every scenario runs the **real** ActionGate engine and the **real** ACP adapter on
the **same** identity-bound Kubernetes operation. Representative rows:

- `authorized_healthy_scale` — real ALLOW + ACP PROCEED → `AUTHORIZED_AND_OPERATIONALLY_SAFE`.
- `unauthorized_but_safe` — real DENY (namespace out of ActionGate scope) + ACP
  safe → `BLOCKED_BY_AUTHORIZATION` (ACP cannot override).
- `authorized_readiness_cooldown` — real ALLOW + real `ReadinessChecker` blocks
  (action 30 s ago < 120 s) → `HELD_BY_OPERATIONAL_SAFETY` (ActionGate had no way
  to catch this).
- `blocked_by_both` — real DENY + ACP freeze hold → `BLOCKED_BY_BOTH`.
- `ag_requests_evidence_acp_passes` — real SIMULATE_AND_RETRY (missing dry-run)
  while ACP is safe → `REQUEST_MORE_EVIDENCE`.
- `ag_passes_acp_requests_fresh` — real ALLOW while ACP state is stale →
  `REQUEST_FRESH_OPERATIONAL_STATE`.
- `composition_identity_mismatch` — ACP bound to a divergent patch digest →
  `COMPOSITION_IDENTITY_MISMATCH` (fail closed).

## 3. Safety invariants (all 13 proven — §11)

I1 ActionGate denial never overridden · I2 ACP never grants authorization · I3
approval/evidence not reused after action modified (commit patch mutation →
ActionGate rejects) · I4 ACP evidence cannot transfer to another candidate/state
(frozen revalidator rejects) · I5 both layers bind the same operation (mismatch
fails closed) · I6 stale resourceVersion invalidates the composed result · I7
modified patch invalidates **both** prior evaluations · I8 missing evidence fails
closed in the owning layer · I9 no duplicate ownership of approval/replay/nonce
(source-scanned) · I10 no duplicate ownership of operational readiness · I11 all
deterministic · I12 no authoritative behaviour change · I13 no shadow path mutates
the cluster (no k8s client imported). `test_integrated.py` (27 tests, pytest +
unittest) proves these plus all 8 classes; 112 ACP tests + V2 bench still green.

## 4. Commit-time revalidation (§8)

For `state_drift_after_eval` (resourceVersion change) and
`modified_patch_after_eval` (patch mutation), the harness rechecks immediately
before hypothetical execution and records which layer rejects. **Both** layers
reject **both** drifts: ActionGate via recomputed `current_state_hash` /
action-hash input; ACP via the frozen `ReferenceCommitRevalidator`. The composed
result is invalidated by whichever layer owns the drifted fact.

## 5. Limitations (binding)

- **No live cluster.** A live/kind/k3d cluster is infeasible offline (no
  kubectl/kind/k3d/k8s-client; network-gated binaries; no repository fake API
  server). The **engines are real**, but Deployment state is modelled from the
  real `action_gateway_k8s` fixture with resourceVersion/availability/readiness
  **authored** (`AUTHORED_DETERMINISTIC`). This bounds the *live-Kubernetes*
  verdict, not the composition result.
- **ActionGate signing is the HMAC stand-in** (a documented ActionGate limitation,
  not introduced here). No real key custody.
- **One operation family, one fixture Deployment.** Decision-grade evidence, not
  certification. `REPOSITORY_INTEGRATION_FIXTURE` provenance is thin (1 base
  Deployment; operational perturbations are authored).
- **`availableReplicas` / readiness are authored** — the repo has no offline
  source (the control-plane-only cluster never schedules pods; readiness comes
  from Prometheus, unavailable offline).
- **Latency has no repository budget** — reported descriptively.

## 6. Verdicts (§12)

### Integrated composition → **`INTEGRATED_STACK_SUPPORTED`**
All 13 §11 invariants pass; all 8 composition classes are produced by **real**
engines; 0 corpus mismatches; deterministic rerun + deterministic ActionGate
action hash; 0 authoritative behaviour changes; 0 cluster mutations; both layers
reject state drift and patch mutation at commit time; identity binding fails closed
on divergence; ownership is clean (0 contradictory-ownership errors, 0 duplicated
constraints, source-scanned no-duplicate-ownership). The complete Ugence governance
stack **can** independently evaluate authorization and operational safety for the
same exact Kubernetes action with clean ownership, deterministic composition, and
zero behavioural impact — which is precisely the milestone question, answered yes.

### Live Kubernetes evidence → **`LIVE_K8S_SHADOW_LIMITED`**
The **real** ActionGate and **real** ACP engines run end-to-end on **reproducible**
Kubernetes state modelled from the real integration fixture — but **not against a
live cluster** (infeasible offline; documented). resourceVersion/availability/
readiness are authored. So the composition and binding are proven on real engines;
the *live-cluster* evidence is limited, not full. Hence `LIVE_K8S_SHADOW_LIMITED`,
not `LIVE_K8S_SHADOW_SUPPORTED`.

### Product evidence → **`CONTROL_PLANE_STACK_PARTIALLY_VALIDATED`**
The two-layer composition is architecturally validated on real engines with clean
ownership and strong invariants — a genuine, positive result. But it rests on one
operation family, one fixture Deployment, authored operational state, and no live
cluster or real ActionGate crypto. That is real partial validation, not a full
platform claim. **`PLATFORM_CLAIM_PREMATURE` remains the honest ceiling** until a
live cluster and a second operation surface are added — so the verdict is
`CONTROL_PLANE_STACK_PARTIALLY_VALIDATED`, and **no production enforcement is
recommended.**

## 7. Next step (if pursued)

(1) Run the identical harness against a real control-plane cluster
(`action_gateway_k8s/scripts/cluster_up.sh`, one network-enabled bootstrap) to
lift the live verdict from `LIMITED` toward `SUPPORTED` — real resourceVersion,
real TOCTOU, real dry-run simulation. (2) Add a second operation surface (e.g.
Service/HPA) and real `availableReplicas` from the full `deploy/local-shadow`
stack. (3) Integrate real ActionGate key custody. Then re-run and re-evaluate the
product verdict.
