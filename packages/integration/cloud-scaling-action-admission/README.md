# Ugence Cloud Scaling Action Admission

**Cloud Scaling Phase 5C — the `ActionGatePort` for capacity actions.**
Distribution `ugence-cloud-scaling-action-admission` · namespace
`ugence_cloud_scaling_action_admission` · version **0.1.0**.

> **An authorization is admission, not execution.**
> This package decides whether a presented capacity action is the action a signed
> envelope was issued for, and stops there. 5X credentials and an execution reservation
> are still required before anything runs; every outcome reports `executable` as a
> permanently-`False` property.

Ratified by `docs/architecture/ADR_CLOUD_SCALING_PHASE5C_ACTION_ADMISSION_SCOPING.md`
(D-2 mapping, D-4 posture). Risk Authority 0.8.0's `ActionAdmissionSeam` (D-1, D-3, D-5)
is the kernel half.

---

## What it composes

| Input | From | Role |
|---|---|---|
| `RiskAuthorizationEnvelope` with the five 5B-4 bindings | Risk Authority 0.6.0+, `cloud-scaling-envelope-issuance` | what was issued, loaded from the store by the kernel |
| `ExecutionTargetScope` and the candidate digest | Phase 5A, presented by the caller | what the caller says it is about to do |
| `ActionAdmissionSeam` | Risk Authority 0.8.0 | one clock read, kernel verification, derived id, replay, persistence |

## The fixed D-2 mapping

`capacity_action_to_canonical(envelope, target_scope)` writes exactly:

| `CanonicalAction` field | Value |
|---|---|
| `tenant_id` | the envelope's |
| `actor_id` | `envelope.subject` |
| `model_id` | `envelope.model_id` |
| `action_type` | `target_scope.action_type` (one of `no_change`, `scale_up`, `scale_down`, `coordinated`) |
| `target_id` | `target_scope.digest()` |
| `purpose` | `cloud_scaling.capacity_action` |
| data classes, destination, money | empty |

Magnitude is bounded by the target scope's own ceilings and by the envelope's
`cloud-scaling.execution-target-scope` binding, never by the generic scope. Widening the 4C
scope was rejected by the ADR.

## The gate

`CapacityActionGate` is built per act with the presented artifacts and declares
`is_production_authoritative = True`. The kernel has already verified signature, window,
tenant and session, revocation and epoch before it runs (D-4), so it checks only that the
action is the issued one: the target-scope binding equals the re-derived digest and the
action's `target_id`; the candidate binding equals the presented digest; the action type is
canonical and equals the scope's; actor and model equal the envelope's and the runtime
identity; the purpose is the capacity purpose inside the envelope scope; no data, destination
or money; the magnitude ceilings hold; the required conditions are satisfied. It answers
`AUTHORIZED` or `DENIED` and nothing else.

## The act

```python
root = CloudScalingActionAdmission.production(app=app, clock=clock)
out = root.admit(CapacityAdmissionRequest(
    tenant_id=..., envelope_id=..., target_scope=scope, candidate_digest=..., session_id=...))
out.admitted     # True iff the verdict is AUTHORIZED
out.replayed     # True iff the stored verdict for this triple was returned
out.executable   # always False
```

Re-admitting the same triple returns the stored verdict as `REPLAYED` and emits nothing, so
the authorization ref downstream (Action Clearance, the execution ledger, RA-8) stays stable.

## What it does not do

Read a clock; verify a signature, window, revocation or epoch; accept a caller-supplied
instant, action, binding or decision; hold a key; broker a credential (5X); reserve or
dispatch execution (5D); call a cloud provider. Asserted over the AST and the dependency
manifest in `tests/test_import_boundary.py` and `tests/test_time_authority.py`.

## Run the suite

```
python -m pytest packages/integration/cloud-scaling-action-admission
```

The suite drives the genuine chain through the 5B-4 fixtures: a real Risk Authority
decision, a real issued bounds policy, a minted attestation, an issued envelope, then
admission of the matching capacity action, its replay, and refusals for a wider magnitude,
a different target scope, a different action type and a forged binding.
