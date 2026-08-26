# Expiry & Idempotency

## Expiry
- `expiry = injected_now + expiry_seconds` when the decision carries `expiry_seconds`
  and a clock is provided; otherwise expiry is `None` (missing stays missing).
- The clock is **injectable** (`ActionGateProvider(..., clock=…)`), so the same clock
  yields deterministic expiry; timezone is preserved.
- Zero and negative durations follow the live semantics: `now + 0` and `now + (−n)`
  (an already-expired instant); ActionGate does not special-case them.

### Enforcement owner
Two different things are meant by "expiry", and ActionGate's role differs for each.

**The expiry ActionGate emits on its own decision** — it emits, it does not enforce.
Classification: **`PROVIDER_EMITS_EXPIRY`**. Whether dispatch is blocked after that
instant is a **framework / execution-layer** responsibility. ActionGate provides no
temporal replay protection.

**The expiry of the upstream authorization the request rides on** — ActionGate
**does** honour this, as of the `authorization_expired` change. The neutral request
carries the flag, the control-plane adapter computes it, and ActionGate returns
`EXPIRED` without consulting policy. Previously ActionGate discarded the flag and
had no native outcome able to express expiry, so an action riding an expired CER was
authorized. Classification for this second sense: **`PROVIDER_HONOURS_UPSTREAM_EXPIRY`**.

### The boundary instant
`now >= expires_at` is expired — the instant an authorization expires, it is expired,
not valid for that tick. `ugence_actiongate_provider.vnext.is_expired` states the rule
once, and the control-plane adapter applies it. This previously read
`expires_at < now`, which disagreed by one instant with Action Clearance
(`evaluation_time >= expires_at`), leaving a window in which one layer would authorize
what the other had already retired.

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
