# Authority Boundary

## The chain (with authoritative owners)

```text
Authorized actor + Decision Authority
        ↓ binding DecisionRecord
ContextEnvelopeRecord (CER)
        ↓ governance context
ActionGate
        ↓ exact-action authorization (ActionGovernanceResult)
Action Clearance
        ↓ immediate execution clearance (ClearanceResult)
Execution provider + execution/idempotency ledger
        ↓ dispatch, observation, reconciliation, authoritative consumption
```

## Boundary definitions

### Decision Authority — *who may decide, validly recorded?*

Owns: actor authority; binding-decision validation; `DecisionRecord`; segregation of duties; override
and supersession semantics. (Types in `ugence_decision_authority`: `DecisionRecord`, `AuthorityType`,
`EffectiveStatus`, `OverrideRecord`.)

Does **not** own: live execution readiness.

### ActionGate — *is THIS exact action authorized?*

Owns: exact-action authorization; policy constraints; requested-parameter validation; the authorization
result; authorization expiry and obligations where currently defined. (Type in
`ugence_governance_contracts`: `ActionGovernanceResult` with `outcome ∈ {AUTHORIZED,
AUTHORIZED_WITH_CONSTRAINTS, DENIED, INDETERMINATE, EXPIRED}`, `constraints`, `obligations`, `expiry`,
`authority_basis`, `reason_codes`, `fingerprint`.)

Does **not** own: current-target or operational-state evaluation.

### Action Clearance — *is the already-authorized action clear to execute NOW?*

Owns: deterministic evaluation of trusted current-state signals; immediate executability of an existing
authorization; a short-lived clearance result; fail-closed handling of stale, missing, conflicting, or
untrusted signals; narrowing, holding, escalation, or blocking.

Does **not** own: original decision authority; creation of authorization; broadening permissions;
provider routing; workflow state; execution dispatch; external-system source-of-truth state; the
authoritative one-time-use ledger.

### Execution provider + execution ledger — *do it exactly once, observe, reconcile.*

Own: atomic one-time dispatch protection; idempotency reservation; execution; observation;
reconciliation; authoritative consumption state. (Today: `ugence_governance_contracts.contracts.execution`
+ Decision-Authority `execution/` and `repositories/execution_repository.py`.)

## Resolving the audit's authority ambiguity

The audit's R1 MIGRATION_BLOCKER: robotics V1 *mints* a `ControlAuthorization` grant (an
authorization engine), while the cloud/console framing never authorizes. **This design resolves the
ambiguity in favor of clear-only.** Action Clearance:

- never mints an authorization grant,
- never converts a `DENIED` / `INDETERMINATE` / `EXPIRED` ActionGate outcome into an executable result,
- consumes an existing authorization and only ever preserves/narrows/holds/escalates/blocks it.

The robotics grant-minting semantics are therefore **not reused** (see
[`EXISTING_IMPLEMENTATION_DISPOSITION.md`](EXISTING_IMPLEMENTATION_DISPOSITION.md)). The live cloud
composition already enforces the property Action Clearance adopts: an ActionGate `DENY` is never
overridden; a permissive clearance mints nothing; proceed requires both layers.

## Prohibited responsibility transfers

Action Clearance must **not** silently become any of:

| Forbidden role | Why it is forbidden |
|---|---|
| Original decision maker | Decision Authority owns the binding decision |
| Action-authorization engine | ActionGate owns authorization; this is the R1 resolution |
| Execution provider | the execution provider dispatches; the core never actuates |
| Workflow orchestrator | the Workflow Service assembles requests and persists receipts |
| Provider router | Model Selection / GPF resolve providers |
| Repo/target-specific policy engine | target checks live in adapters; the core is neutral |
| Incident-management system | the incident system owns incident state; the core receives a signal |
| Identity provider | identity owns actor status; the core receives a signal |
| Idempotency / consumption ledger | the execution ledger owns one-time use |
| Retry / reconciliation engine | downstream execution owns retry and reconciliation |
| Durable workflow engine | the core persists nothing |

Each transfer is re-checked structurally: the core has no client of any external system, no persistence
surface, no dispatch surface, and no path from a denial to an executable result.
