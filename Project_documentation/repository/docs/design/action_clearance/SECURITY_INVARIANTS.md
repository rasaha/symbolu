# Security Invariants

The eighteen mandatory security properties. Each is testable and maps to an acceptance scenario and/or a
threat in [`THREAT_MODEL.md`](THREAT_MODEL.md).

| # | Invariant | Enforced by |
|---|---|---|
| 1 | Existing authorization required | eligibility gate: only `AUTHORIZED`/`AUTHORIZED_WITH_CONSTRAINTS` inputs |
| 2 | Action identity must match exactly | `authorized_action_fingerprint` re-verification |
| 3 | Clearance cannot broaden permissions | monotonicity: `effective ⊆ authorized` (§Monotonicity) |
| 4 | Required signals must be fresh and trusted | freshness + `integrity_digest` checks; fail closed |
| 5 | Tenant and subject bindings must match | `TENANT_MISMATCH` / `SUBJECT_MISMATCH` → BLOCK |
| 6 | Missing mandatory signals fail closed | `SIGNAL_MISSING` → HOLD (never CLEAR) |
| 7 | Clearance lifetime ≤ authorization & signal lifetime | `valid_until ≤ min(expires_at, min signal valid_until, max_lifetime)` |
| 8 | Result must be deterministic | pure function; no clock/random/network/env |
| 9 | Result must be fingerprinted | `result_fingerprint` over canonical serialization |
| 10 | No direct external-state access in the evaluator | signals are received; no clients in the core |
| 11 | No credentials in the core | request forbids credentials; malformed → error |
| 12 | No execution dispatch in the core | no dispatch surface |
| 13 | No authorization consumption in the core | consumption is a received signal; ledger owns it |
| 14 | Execution must atomically reserve one-time use | ledger reservation on the replay key |
| 15 | Stale or superseded clearance must not execute | `valid_until` + `RECEIPT_SUPERSEDED`/`REVOKED_BY_UPSTREAM_CHANGE` |
| 16 | A new action fingerprint requires a new clearance | fingerprint mismatch → BLOCK (scenario 21/22) |
| 17 | A changed authorization requires a new clearance | authorization fingerprint mismatch → BLOCK |
| 18 | Profile-specific constraints may only narrow | profile is narrowing-only by construction |

## Fail-closed everywhere

Every uncertain, missing, unknown, untrusted, or unrepresentable condition resolves away from `CLEAR`.
There is no code path from "I don't know" to "execute". The core raises typed exceptions only for
programming errors and malformed contracts; all expected operational problems are fail-closed *results*.
