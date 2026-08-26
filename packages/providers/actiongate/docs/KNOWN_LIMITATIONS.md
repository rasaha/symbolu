# Known Limitations

- **ActionGate authorizes; it does not execute.** No dispatch/execute/observe/
  reconcile/compensate surface exists.
- **Authorization does not prove execution.** An AUTHORIZED result is a decision, not
  evidence that anything ran.
- **Constraints may require downstream enforcement.** ActionGate emits constraints
  (e.g. `maximum_amount`, `allowed_region`); enforcing them at runtime is a downstream
  (control-plane / execution-layer) responsibility.
- **Obligations may require downstream fulfilment.** `human_review`, `notification`,
  and `logging` are emitted, not fulfilled, by ActionGate.
- **`single_use` is not durable replay prevention.** ActionGate emits the constraint
  but has no durable nonce store, consumption tracking, or cross-process replay
  detection. Classification: `NO_REPLAY_PROTECTION` (only
  `IDEMPOTENCY_KEY_PRESERVED` + `DETERMINISTIC_REPEAT_ONLY`).
- **The expiry ActionGate emits is not enforced by ActionGate.** Classification
  `PROVIDER_EMITS_EXPIRY`; whether dispatch is blocked after that instant is a
  framework/execution-layer concern. This is *not* true of the upstream
  authorization's expiry, which ActionGate now honours by returning `EXPIRED` —
  see `EXPIRY_AND_IDEMPOTENCY.md`.
- **Policy dimensions are governed only where a policy declares them.** An
  `ActionGatePolicy` that declares no rule for a dimension cannot make that
  dimension dispositive. `ActionGateEngine.governed_dimensions` reports exactly
  which dimensions a configured engine can act on, so an ungoverned dimension is
  observable rather than an assumption; a default-constructed engine governs none.
- **Tenant propagation is intentionally lossy** — the neutral request has no tenant
  field, so native `tenant` is empty. A semantic fix is a separate versioned phase.
- **Unknown outcomes and provider failures become non-authorizing** (INDETERMINATE) —
  by design.
- **Remote mode requires independently secured transport and authentication.**
- **Deterministic policy evaluation is not legal or business correctness.**
- **Packaging verification is not production certification** — `production_certified
  = False`.
