# Expiry & Idempotency

## Expiry
- `expiry = injected_now + expiry_seconds` when the decision carries `expiry_seconds`
  and a clock is provided; otherwise expiry is `None` (missing stays missing).
- The clock is **injectable** (`ActionGateProvider(..., clock=…)`), so the same clock
  yields deterministic expiry; timezone is preserved.
- Zero and negative durations follow the live semantics: `now + 0` and `now + (−n)`
  (an already-expired instant); ActionGate does not special-case them.

### Enforcement owner
ActionGate **emits** expiry; it does **not** enforce it. Classification:
**`PROVIDER_EMITS_EXPIRY`**. Whether dispatch is blocked after expiry is a
**framework / execution-layer** responsibility (the control-plane adapter carries an
`authorization_expired` signal and an `EXPIRED` kernel outcome). ActionGate itself
provides no temporal replay protection.

## Idempotency & replay
- The neutral request's `idempotency_key` is **preserved** through request mapping.
- Repeated identical requests (same clock, same policy) are **deterministic**: same
  outcome and same fingerprint.
- No package operation causes duplicate provider registration.

### Replay classification
**`IDEMPOTENCY_KEY_PRESERVED` + `DETERMINISTIC_REPEAT_ONLY`.** ActionGate has **no
durable replay protection**: no durable nonce/token store, no consumption tracking,
no cross-process replay detection, no atomic single-use enforcement. A `single_use`
constraint being emitted is **not** proof that ActionGate consumes or enforces it.
