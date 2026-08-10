# ACP Duplication & Adjacent-Logic Disposition

Clearance-like logic found **outside** the robotics core, classified. The goal is **not** to centralize
every pre-execution check: target-specific validation may legitimately remain in the execution provider
while ACP evaluates neutral clearance policy.

| # | Location | What it does | Classification | Disposition |
|---|---|---|---|---|
| 1 | `cer_v0_3/acp_db/safety.py:36-93` | Full DB operational-safety evaluator: freeze / migration(incident) / state-binding / state-version(expiry) / freshness / rollback HARD checks | **ACP_CORE_LOGIC** (re-expressed per domain) | Would consolidate onto a neutral clearance kernel; reuses frozen `compose()` correctly today |
| 2 | `ugence_console_api/.../operational_safety.py:33-60` | CLEAR/HOLD over freeze / cluster health / error budget, fail-closed on missing | **ACP_CORE_LOGIC** (separate reimpl) | Duplicates the discipline with no shared code; consolidation candidate |
| 3 | `robotics_reliability_bench/acp_k8s_integrated/harness.py:249-294` | Reimplements ActionGate-side commit-time drift/staleness/**duplicate-dispatch** rejection (resourceVersion→state-hash, patch→action-hash, policy-version) | **UPSTREAM_AUTHORIZATION_LOGIC** (bench copy) | Bench-only reproduction for offline determinism; not product; leave in bench |
| 4 | `acp_k8s_integrated/actiongate_runner.py:96-128` | Byte-for-byte reproductions of `K8sStateOracle.state_hash` and manifest-digest conventions | **DUPLICATE_LOGIC** (hashing) | Bench-only; leave, but note as a fragility if conventions drift |
| 5 | `robotics_reliability_bench/acp_shadow/bcvf_replica.py:28-70` | Faithful copy of the 3 production BCVF *selection* call sites | **WORKFLOW_COORDINATION** (shadowed runtime) | Deliberate; the "current runtime" side being shadowed; leave |
| 6 | `decision_governance/actions/control_plane.py:94-95` | CER `expires_at < now` → `AuthorizationOutcome.EXPIRED` | **DOWNSTREAM_EXECUTION_SAFETY** (governance-chain freshness) | Owned by Decision Authority; the canonical governance-chain clearance seam; do NOT move into ACP |
| 7 | `packages/governance-provider-framework/.../reference/action.py:64` + `adapters/action_to_control_plane.py:91` | `authorization_expired` → `EXPIRED` mapping | **DOWNSTREAM_EXECUTION_SAFETY** | Reference/adapter; leave |
| 8 | `cloud/constraints.py` (readiness/blast-radius/freeze/rollback via real `cloud_controller`) | Target-specific K8s validation surfaced as `ConstraintResult` | **TARGET_SPECIFIC_VALIDATION** | **Legitimate local check** — stays in the target adapter |
| 9 | `safety_adapters/trajectory_adapter.py` (physical validation via real validator) | Robot trajectory validation surfaced as `ConstraintResult` | **TARGET_SPECIFIC_VALIDATION** | Legitimate; stays in the robotics adapter |
| 10 | `control_plane/` + `control_plane_shadow/` governance invariants | selection-within-eligible, executed==selected, stale-eligibility | **LEGITIMATE_LOCAL_CHECK** (Model Selection, UNRELATED) | Not ACP; leave |

## Reading

- **True duplicated *clearance* logic** (freshness / freeze / state-binding / expiry) exists in **three
  independent expressions**: robotics `authorization.py`+`cloud/constraints.py`, `acp_db/safety.py`, and the
  console `operational_safety.py`. These are the consolidation targets *if* the product is ever built —
  onto a single neutral clearance kernel.
- **Target-specific validation** (K8s readiness, trajectory validation, DB replication) is correctly local
  to the adapters and must **not** be pulled into an ACP core.
- **Governance-chain freshness** (`EXPIRED`) is correctly owned by Decision Authority + the provider
  framework and must **not** be pulled into ACP either — doing so would move durable governance-chain
  responsibility across a forbidden boundary (`STATE_AND_PERSISTENCE.md`).
- **Bench reproductions** (ActionGate hashing/drift) are offline-determinism copies; acceptable in benches,
  but they are a maintenance hazard if the real conventions change.

## Disposition summary

No duplication requires action in this audit (it is documentation-only). The duplication is **recorded as a
consolidation prerequisite**: a governance ACP package would unify the three clearance expressions (#1, #2,
and the robotics core) behind one kernel, while explicitly **leaving** target-specific validation (#8, #9)
in adapters and **leaving** governance-chain freshness (#6, #7) in Decision Authority/GPF.
