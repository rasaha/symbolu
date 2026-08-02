# Threat Model

Threats against pre-execution clearance and the mitigation each design property provides. Mitigations
reference the security invariants (SI-#) in [`SECURITY_INVARIANTS.md`](SECURITY_INVARIANTS.md).

| Threat | Scenario | Mitigation |
|---|---|---|
| **Replay** | a valid clearance/authorization re-used to execute twice | one-time-use in the execution ledger; `PRIOR_CONSUMPTION` signal → `ALREADY_CONSUMED`/BLOCK; atomic reservation on the replay key (SI-13/14) |
| **TOCTOU** | state changes between authorization and execution | clearance is evaluated *immediately before* execution; `valid_until` bounds the window; re-clearance on any identity change (SI-2/7/15/16) |
| **Stale signals** | old operational facts pass as current | freshness window + `valid_until`; boundary-at-expiry = expired; missing bound → fail closed (SI-4/6/7) |
| **Forged signals** | attacker injects a fabricated "all clear" signal | `integrity_digest` required for trust-required signals; `SIGNAL_UNTRUSTED` → BLOCK; `provenance_ref` audited (SI-4) |
| **Tenant confusion** | signal from tenant A used to clear tenant B | `TENANT_MISMATCH` → BLOCK (SI-5) |
| **Signal-source impersonation** | wrong source claims to be the authority for a signal type | `source_kind`/`source_ref` bound + integrity check; ownership matrix pins the authoritative owner (SI-4/5) |
| **Action substitution** | swap the authorized action for another | `authorized_action_fingerprint` re-verification → `ACTION_FINGERPRINT_MISMATCH`/BLOCK (SI-2/16) |
| **Target substitution** | redirect to a different target | `target_ref` bound in `action_fingerprint` → `TARGET_MISMATCH`/BLOCK (SI-2) |
| **Policy downgrade** | present an older, weaker policy version | `POLICY_VERSION_REJECTED` → BLOCK; policy_ref evaluated (SI-3) |
| **Clock manipulation** | shift time to dodge expiry | evaluation time is caller-supplied & audited; expiry strict; skew tolerance never applies to expiry (SI-7/8) |
| **Duplicate dispatch** | two dispatches share one clearance | atomic ledger reservation → exactly one; other = DUPLICATE (SI-14) |
| **Clearance reuse** | reuse a clearance past its window | `valid_until` enforced at dispatch; expired clearance → no dispatch (SI-7/15) |
| **Missing receipt** | dispatch without a clearance receipt | Workflow Service fails closed unless the full chain reconstructs (CG §4.7) |
| **Incomplete chain** | a broken decision→CER→auth→clearance link | chain-reconstruction check; any missing/mismatched link → no dispatch (SI-1/2) |
| **Fail-open exception handling** | an internal error is swallowed as CLEAR | exceptions never produce CLEAR; expected problems are fail-closed results; unexpected errors raise, never default-permit (SI-8, fail-closed rule) |

## Trust assumptions (explicit)

- The **caller** supplies a trustworthy `evaluation_time` (audited; a compromised caller is out of the
  clearance core's scope — mitigated by the execution ledger and audit chain, not the evaluator).
- **Adapters** are trusted to normalize honestly, but their output is still integrity-checked and
  provenance-audited; a compromised adapter is bounded by `integrity_digest`, `source_kind` binding, and
  the ownership matrix.
- The **execution ledger** is the sole atomic authority for consumption; the clearance core never
  assumes it can prevent a race alone.

## Residual risks (to implementation)

Signal provenance/integrity mechanism selection (how `integrity_digest` is produced/verified per source)
is an implementation-prerequisite, not settled here (P1; [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) Q3).
