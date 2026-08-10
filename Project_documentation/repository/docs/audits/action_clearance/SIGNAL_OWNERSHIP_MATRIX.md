# ACP Signal-Ownership Matrix

For each input the ACP discipline consumes, the authoritative source and whether ACP **owns**, **fetches**,
**receives**, or merely **evaluates** it. The design principle: **ACP evaluates trusted signals; it must not
become the source of truth for unrelated operational systems.**

| Signal | Expected authoritative source | Live source in this repo | ACP relationship | Status |
|---|---|---|---|---|
| Authorization validity | ActionGate / authorization store | `AuthorizationVerdict` token passed to `compose()`; DA `AuthorizationOutcome` | **Receives** (opaque token) | Correct |
| Policy version | Policy service | `constraint_set_version` / `policy_refs` on the request | **Evaluates** (drift check) | Correct |
| Actor status / identity | Identity provider | **none wired** — no actor/principal field in the core | Missing | **Gap** |
| Active incident | Incident system | **none** — `acp_db` has a `migration_active` flag only | Missing | **Gap** |
| Change freeze | Change-management system | `freeze_active` flag (cloud), `change_freeze_active` (console) | **Receives** (flag) | Partial |
| Environment / runtime state | Deployment/runtime system | real `cloud_controller` `ReadinessChecker`; console `cluster_health` | **Evaluates** (via adapter) | Correct |
| Prior consumption | Idempotency / execution ledger | **none** — no consumption ledger | Missing | **Gap** |
| Action identity | Prepared action envelope | `CanonicalActionCandidate.identity` / manifest digest | **Evaluates** (binding) | Correct |
| Target state | Execution provider / target adapter | `resource_version`, `generation`, `observed_row_version` | **Evaluates** (via adapter) | Correct |
| Credential validity | Secrets / identity | **none** — explicitly disclaimed (`authorization.py:6-7`) | Missing | **Gap** |
| Required checks / rollback | CI / deployment | `ROLLBACK_AVAILABLE` (cloud/acp_db) | **Evaluates** | Correct |
| Rate / budget / blast radius | Policy / SLO system | real `SafetyBounds`/`PolicyEngine`; console `error_budget` | **Evaluates** (via adapter) | Correct |
| Temporal expiry | Clock (injected) | `expiry_time_s`, `freshness_s`, `seconds_since_last_action` | **Evaluates** (injected time) | Correct |

## Reading

- Where ACP is doing the right thing (**evaluate/receive** trusted signals), the pattern is clean: the
  robotics/cloud/DB adapters inject already-fetched signals (readiness, safety bounds, freeze flag,
  resource_version) and ACP evaluates a neutral hard-filter over them. It does **not** poll Kubernetes, call
  an incident API, or fetch credentials — correct separation.
- The **gaps** (actor identity, credentials, incidents, prior-consumption) are all signals that a *governance*
  ACP would need to *receive* (not own). They are absent because the robotics core delegates identity/RBAC to
  ActionGate and has no execution ledger. A governance ACP product must define **receive** contracts for
  these — and must resist the temptation to *own* them (e.g. do not build an incident client or an
  idempotency ledger inside ACP; those belong to the incident system and the execution ledger respectively —
  see `STATE_AND_PERSISTENCE.md`).

## Anti-pattern to avoid

Do **not** centralize every pre-execution check into ACP. Target-specific validation (a K8s readiness probe,
a DB replication check, a trajectory validator) legitimately lives in the **execution provider / target
adapter**; ACP evaluates the *neutral clearance policy* over the signals those adapters surface. The live
code already respects this — `cloud/constraints.py` and `acp_db/safety.py` call real target modules and hand
ACP a `ConstraintResult`, rather than embedding target logic in the core.
