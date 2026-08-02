# Ugence Action Clearance (v0.1 core)

**Deterministic, domain-neutral, stateless.** Given an already-authorized exact
action and a bundle of trusted current-state signals, Action Clearance decides
whether that action remains operationally **CLEAR** immediately before execution.

> Action Clearance may preserve, narrow, hold, escalate, or block an existing
> authorization. It may never create authority, broaden authorization, replace
> ActionGate, dispatch execution, or own authoritative one-time consumption.

- Statuses: `CLEAR · HOLD · BLOCK · ESCALATE` (precedence `BLOCK > ESCALATE > HOLD > CLEAR`).
- No persistence, no execution, no reservation, no network, no credentials, no
  domain adapters. `evaluate_clearance(request, policy) -> ClearanceResult` is a
  pure function of its inputs (caller-supplied `evaluation_time`; no clock read).

See `docs/` for the public API, authority boundary, trusted-signal model, policy
model, determinism/fingerprinting, status/reason codes, persistence/execution
boundary, acceptance coverage, limitations, and next phases. Run the offline demo:
`python examples/clearance_demo.py`.
