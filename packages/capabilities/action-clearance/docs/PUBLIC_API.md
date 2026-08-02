# Action Clearance — Public API

> Machine-readable: `public_api.json` (with API fingerprint). Curated in
> `ugence_action_clearance.api` and re-exported from the package root.

## Evaluator

```python
from ugence_action_clearance import ActionClearanceEvaluator, evaluate_clearance
result = ActionClearanceEvaluator().evaluate(request, policy)   # -> ClearanceResult
result = evaluate_clearance(request, policy)                    # module-level convenience
```

The evaluator is **stateless** and a **pure function** of `(request, policy)`. It
reads no clock (`request.evaluation_time` is caller-supplied), performs no network
call, persists nothing, and dispatches nothing.

## Types

| Symbol | Role |
|---|---|
| `ClearanceRequest`, `ClearancePolicyContext` | immutable request + resolved policy reference |
| `ClearancePolicy` | resolved immutable policy projection |
| `ClearanceResult` | deterministic output; `result_id = "acr_" + result_fingerprint` |
| `ClearanceReceiptBody` | neutral immutable receipt **body** (not persisted here) |
| `ClearanceStatus` | `CLEAR · HOLD · BLOCK · ESCALATE` |
| `ClearanceReasonCode` | curated CORE_NEUTRAL reason catalog |
| `AuthorizationContext`, `AuthorizedActionIdentity` | authorization projection + exact action identity |
| `TrustedSignal`, `SignalProvenance`, `SignalBundle` | trusted current-state signals |
| `SignalType`, `SignalStatus`, `SignalTrustLevel`, `ConsumptionStatus` | signal vocabularies |
| `EffectiveConstraint`, `ConstraintKind`, `ClearanceObligation` | narrowing algebra |
| `ActionClearanceError`, `ValidationError`, `FingerprintError`, `UnsupportedVersionError` | typed exceptions |

Internal canonicalization/fingerprint helpers and private policy implementation
details are intentionally **not** exported.
