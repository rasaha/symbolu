# R1 Security Properties & Limitations

## Properties (tested)
- **No permissiveness added.** The projection cannot produce an ALLOW the gate would not.
  DENY-causing conditions are always `TERMINAL`; `retryability.retryable == False` on DENY.
  Policy metadata cannot upgrade a terminal condition (tested for FORBID + opt-in metadata).
- **Purity / no mutation.** The projection never mutates the envelope, policy, evidence,
  approvals, or decision (tested across all fixtures).
- **Hash/binding invariance.** Remediation is excluded from `action_hash`, `policy_hash`,
  approval/evidence/token digests, and the audit payload. A changed action gets a new
  `action_hash`; prior approvals/evidence/tokens (bound to the old hash) do not carry over —
  R1 changes none of this.
- **Advisory only.** The remediation output contains no signatures, keys, approval/evidence/
  token hashes, or credential authority (tested). It cannot be replayed as evidence, an
  approval, an execution token, or credential authority.
- **Disclosure control.** MINIMAL/STANDARD never reveal exact thresholds (tested: the numbers
  `25000`/`10000` never appear). Privileged modes (TRUSTED_PLANNER/HUMAN_ONLY/FULL) require a
  trusted caller context; an untrusted request raises `E_REMEDIATION_DISCLOSURE`. A
  caller-provided mode string alone cannot unlock privileged disclosure.
- **Determinism.** No random ids, no wall-clock inside the projection (`now` is explicit);
  stable ordering; serialization round-trips.

## Limitations (honest)
- **Policy oracle.** Even STANDARD/MINIMAL leak *some* structure (an operator category, a
  retry class). This is inherent to any "why not" signal and is bounded — not eliminated — by
  disclosure levels. Deploy STANDARD to first-party authenticated callers and NONE/OFF to
  untrusted callers. `FULL` is a near-complete policy oracle; confine it to callers that could
  read the signed policy anyway.
- **Trusted-context is a reference stub.** R1 models trust with an explicit boolean
  (`trusted_context`) / CLI `--trusted-admin`. **Production transports MUST establish trust
  cryptographically** (authenticated caller identity / capability), not by a flag or a string.
- **Retry governance not enforced here.** `retry_budget` is an advisory container (all null).
  Attempt caps, budgets, timeouts, loop/duplicate detection are a broker responsibility for a
  later phase; R1 adds no orchestration, so it introduces no retry-DoS amplifier of its own.
- **Unknown operators.** The projection mirrors the gate: an unrecognized effect op is ignored
  (as the gate ignores it), so it neither crashes nor invents a retry path. Any unrecognized
  operator that reached classification would fail closed to `TERMINAL`.
- **Not a planner.** R1 emits advice; it does not modify actions or drive retries. A modified
  action is a new `action_hash` requiring fresh evaluation, approval, and evidence.

## Deployment guidance
- Default OFF. Enable STANDARD only for authenticated first-party callers; NONE for third
  parties. Gate FULL behind cryptographic admin capability, never a request field.
- Treat remediation as a documented policy side-channel in red-team exercises: verify
  disclosure cannot be self-escalated and that OFF truly omits the block.
