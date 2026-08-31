# Component & Deployment Inventory (M1)

*The real frozen ActionGate (the subject of Gap 0), the pilot runtime it plugs into, and the deployment
surface a bounded customer shadow pilot requires. All consumed read-only.*

## The real frozen ActionGate

- **Location:** `cyber_security/action_gate_reference/action_gate_ref/gate.py` (package `action_gate_ref`;
  version tag used by the existing control-plane adapter: `action_gate_ref_v1`).
- **API:** `gate.evaluate(envelope: dict, signed_policy: dict, *, evidence=None, approvals=None, now: str,
  used_nonces=(), algorithm_id='sha-256', identity_profile='v1') -> dict`.
- **Output shape:** `{outcome, dispositive_rules, applied_constraints, action_hash, policy_hash,
  state_trace, terminal, reason, hash_algorithm_id}`.
- **Outcome vocabulary (6):** `ALLOW`, `ALLOW_WITH_CONSTRAINTS`, `DENY`, `ESCALATE_TO_HUMAN`,
  `REQUEST_MORE_EVIDENCE`, `SIMULATE_AND_RETRY`.
- **Reason codes:** `dispositive_rules` (e.g. `R1`) + a `state_trace` through the decision state machine:
  `RECEIVED → VALIDATED → INVARIANT_CHECK → SIMULATION_CHECK → CONSEQUENCE_CHECK → APPROVAL_CHECK →
  FINAL_DECISION → AUDIT_LOGGED`.
- **Policy inputs:** a **signed policy**, **evidence** (backup, signed-artifact, simulation), **approvals**
  (e.g. dual-control), **attestation** on the envelope, cryptographic **action/policy hashes**, nonces,
  and an identity profile. This is a cryptographic decision engine, not a heuristic.
- **Canonical operations (10):** `IAM_GRANT_ADMIN, DEPLOY, DB_DELETE, NET_EXPOSE, SECRET_READ,
  MONITORING_DISABLE, DB_MUTATION, KEY_ROTATE, CLOUD_SPEND_INCREASE, EXTERNAL_COMMS`.
- **Failure mode:** raises `GateError` on malformed envelope/policy → the pilot adapter must fail closed.
- **Observed full-evidence + dual-approval outcomes:** ALLOW (IAM_GRANT_ADMIN, KEY_ROTATE),
  ALLOW_WITH_CONSTRAINTS (SECRET_READ), SIMULATE_AND_RETRY (DEPLOY, DB_MUTATION), ESCALATE_TO_HUMAN
  (DB_DELETE), DENY (NET_EXPOSE, MONITORING_DISABLE, CLOUD_SPEND_INCREASE, EXTERNAL_COMMS).

### Contrast with the GIP shadow mapping (the Gap-0 limitation)

The pilot's `action_shadow_v1` mapped `{required_authority, reversibility, risk}` to
`PERMIT/CONSTRAIN/BLOCK/ESCALATE`. It **cannot express**: signed policy, evidence sufficiency, approvals,
attestation, simulation, `REQUEST_MORE_EVIDENCE`, `SIMULATE_AND_RETRY`, or applied constraints. The
differential study (M3) measures where the shadow and the real gate disagree, and whether any
disagreement is *unsafe* (shadow blocks, real permits).

## Pilot runtime consumed read-only

`governed_inference_pilot` (frozen `ab237af`): orchestrator, adapters, `gip_corpus_v1`, audit
(`gip_audit_v1`), replay, dispositions/reconciliation, contracts (`gip_contracts_v1`). The readiness
track imports these but modifies none.

## Deployment surface a bounded shadow pilot requires

| Surface | Status entering this track | Owner in this track |
|---|---|---|
| Non-enforcing pilot API | not built | M-API |
| Authn/authz boundary | not evaluated | M-Security |
| Tenant isolation | schema field only | M-Security |
| Data classification / permitted-use | not built | M-Data |
| Redaction / minimization | partial (audit redaction) | M-Data |
| Secrets / encryption interfaces | not built | M-Data |
| Retention / deletion / export | not built | M-Data |
| Secure artifact intake | not built | M-Intake |
| Observability | audit trace only | M-Ops |
| Incident response | not built | M-Ops |
| Kill switches (pilot + tenant) | not built | M-Ops |
| Deployment packaging | none (shadow) | M-Deploy |
| Rollback / recovery | none | M-Deploy |
| Tenant-scoped human review | simulated only | M-Review |
| Load / concurrency | not measured | M-Load |

Every surface is implemented as a **non-enforcing, shadow-only** control: the pilot API returns `WOULD_*`
dispositions, never enforces, and never executes an action.
