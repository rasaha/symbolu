# Agent Runtime — Governance Integration

The runtime integrates with governance through a **neutral boundary it owns**. The
boundary lets the runtime ask an external governance implementation whether a
consequential transition may proceed. The runtime obeys the answer; it never authors
policy, binds a decision, or creates authority.

Machine-readable form:
[`../artifacts/agent_runtime_governance_contract.json`](../artifacts/agent_runtime_governance_contract.json).

## The contract

```python
class GovernanceHook(Protocol):
    def evaluate(self,
                 proposal: TransitionProposal,
                 evaluation_time: float) -> GovernanceEvaluation: ...
```

- `TransitionProposal` is an **immutable** description of the *exact* intended provider
  invocation — workflow/instance/task ids, provider id, operation, canonicalized
  arguments, idempotency key, correlation — plus a deterministic `fingerprint` over
  those fields. It carries **no** credentials and **no** policy.
- `evaluation_time` is **caller-controlled**: the runtime passes its injected clock
  value so the runtime (not the hook) owns the logical clock and determinism.
- `GovernanceEvaluation` returns only what the runtime needs: `disposition`,
  `proposal_fingerprint`, `reason_codes`, `evaluation_reference`,
  `authorization_reference`, `clearance_reference`, `valid_until`, `required_resolution`,
  `correlation_reference`.

## Exact-action binding (P0)

A `CLEAR` result permits execution **only** when it is provably about the exact
proposal. Immediately before invoking a provider the runtime checks, and fails closed
(provider not called, task/workflow `FAILED`) on any of:

| Reason code | Condition |
| --- | --- |
| `GOVERNANCE_CLEAR_MISSING_EVALUATION` | no evaluation returned |
| `GOVERNANCE_NOT_CLEAR` | disposition is not CLEAR |
| `GOVERNANCE_CLEAR_MISSING_FINGERPRINT` | evaluation carries no `proposal_fingerprint` |
| `GOVERNANCE_CLEAR_FINGERPRINT_MISMATCH` | fingerprint ≠ the proposal's |
| `GOVERNANCE_PROPOSAL_TAMPERED` | the proposal changed after it was built |
| `GOVERNANCE_CLEAR_MISSING_REFERENCE` | no binding reference (evaluation/authorization/clearance) |
| `GOVERNANCE_CLEAR_EXPIRED` | `valid_until` is past at the execution check |
| `GOVERNANCE_CLEAR_CORRELATION_MISMATCH` | correlation reference inconsistent |
| `PROPOSAL_INVOCATION_MISMATCH` | the built invocation re-fingerprints to a different value |

The runtime **mints none** of these references; governance produces them. The runtime
proves the permission it consumes applies to the invocation it makes — without importing
any concrete governance implementation.

## Disposition vocabulary (preserved, not invented)

The established outcomes `CLEAR / HOLD / BLOCK / ESCALATE` are preserved by value at
the boundary. The runtime maps them to coordination behavior and **never broadens**
them:

| Disposition | Runtime directive | Effect |
| --- | --- | --- |
| `CLEAR` | CONTINUE | run the provider |
| `HOLD` | WAIT | task/workflow `WAITING`; no authority created |
| `BLOCK` | STOP | do not execute; task/workflow `FAILED` |
| `ESCALATE` | PAUSE | workflow `PAUSED` pending external authority/review |

Fail-closed rule: a missing evaluation, or any unrecognized disposition, resolves to
`STOP` — never `CONTINUE`. `HOLD` and `ESCALATE` are never converted to `CLEAR`.

## What the core does NOT import

The neutral boundary depends on nothing concrete. The core package does **not**
import TAP, Decision Authority, ActionGate, Action Clearance, Code Governance, or
StoryGraph — verified by the import-boundary tests.

## Where concrete governance lives

Concrete Ugence governance adapters (which translate `ExecutionContext` into a TAP /
Decision Authority / ActionGate / Action Clearance / StoryGraph evaluation and back to
a `GovernanceEvaluation`) live **outside** this package — in the application layer or
in an optional integration package (e.g. a future `ugence-agent-runtime-governance`).
They are never required for the core to import. This packaging phase does **not**
create such an adapter package, because a clean application-level adapter can already
implement `GovernanceHook` directly.

## Default hook — fail closed (P0)

The **default** hook is `UnconfiguredGovernanceHook`, which returns `BLOCK` with reason
`GOVERNANCE_NOT_CONFIGURED` for every consequential transition. With no governance
adapter configured, the runtime never treats its own default as permission to execute a
consequential action. Non-consequential tasks (`consequential=False`) do not cross the
boundary and run without a hook.

`AllowAllGovernanceHook` returns `CLEAR` bound to the proposal fingerprint. It is an
**explicit, opt-in, documented-unsafe** testing/simulation helper and is **never** a
default; `NoopGovernanceHook` is retained only as a deprecated alias (emits
`DeprecationWarning`). Production deployments inject a real adapter via
`AgentRuntimeConfig(governance_hook=...)` or `register_governance_hook(config, hook)`.
