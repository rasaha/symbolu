# Action Clearance Integration

## Eligibility (upstream authorization required)

Action Clearance is invoked only when the ActionGate shadow result is **eligible**:
`AUTHORIZED` or `AUTHORIZED_WITH_CONSTRAINTS`. For `DENIED` / `INDETERMINATE` /
`EXPIRED` / errored / missing outcomes the product:

- does **not** report CLEAR and does **not** fabricate a `ClearanceResult`;
- records the stage state `NOT_EVALUATED_UPSTREAM_NOT_AUTHORIZED`;
- preserves the ActionGate outcome + reasons;
- keeps execution disabled;
- lets reconstruction distinguish *evaluated* vs *legitimately not evaluated* vs
  *missing unexpectedly*.

## Mapping (ActionGate result + PreparedMergeAction -> canonical inputs)

`ActionClearanceShadowAdapter` binds (via the Action Clearance public API):

| Canonical field | Source |
|---|---|
| `AuthorizationContext.authorization_ref` / `authorization_result_fingerprint` | ActionGate shadow `result_fingerprint` |
| `authorization_outcome` | ActionGate outcome (eligibility-checked) |
| `authorization_expires_at` | PreparedMergeAction expiry (CER expiry) |
| `authorization_constraints` / `authorization_obligations` | ActionGate constraints / obligations |
| `decision_record_ref` / `context_envelope_ref` / `context_envelope_hash` | DecisionRecord id / CER id / CER content hash |
| `AuthorizedActionIdentity.authorized_action_fingerprint` | PreparedMergeAction fingerprint |
| `target_ref` / `operation` / `parameters` | repository / merge method / exact requested parameters (base/head SHA, method, target branch) |
| `evaluation_time` | **caller-supplied** by the Workflow Service |

The adapter imports no Action Clearance internals and never imports Code Governance
models into Action Clearance.

## Stage state machine

```
ACTION_EVALUATED -> CLEARANCE_PENDING -> CLEARANCE_EVALUATED
                 -> INTERVENTION_ASSESSED -> SHADOW_COMPLETE
```

Fail-closed clearance terminals: `CLEARANCE_INPUT_INCOMPLETE`,
`CLEARANCE_INTEGRITY_FAILURE`, `CLEARANCE_EVALUATION_ERROR`. `CLEAR`/`HOLD`/`BLOCK`/
`ESCALATE` are **not** workflow-state names — the canonical `ClearanceStatus` lives on
the evaluation record.
