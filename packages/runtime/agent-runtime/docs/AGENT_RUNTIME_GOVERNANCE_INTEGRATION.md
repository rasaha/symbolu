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
                 context: ExecutionContext,
                 proposed_transition: str,
                 evaluation_time: float) -> GovernanceEvaluation: ...
```

- `ExecutionContext` describes the proposed transition (workflow/instance/task ids,
  operation, correlation, arguments). It carries **no** credentials and **no** policy.
- `evaluation_time` is **caller-controlled**: the runtime passes its injected clock
  value so the runtime (not the hook) owns the logical clock and determinism.
- `GovernanceEvaluation` returns only what the runtime needs: `disposition`,
  `reason_codes`, `evaluation_reference`, `valid_until`, `required_resolution`,
  `correlation_reference`.

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

## Default hook

The default `NoopGovernanceHook` returns `CLEAR` for every evaluation. It creates no
authority — it simply expresses "no governance is integrated." Production deployments
inject a real adapter via `AgentRuntimeConfig(governance_hook=...)` or
`register_governance_hook(config, hook)`.
