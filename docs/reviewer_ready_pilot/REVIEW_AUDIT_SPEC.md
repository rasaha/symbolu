# Review Audit Specification (Phase 14)

*What the pilot records, and what an auditor can prove from it. Implemented in
`reviewer_ready_pilot/audit.py`. No real reviewer actions exist in this track; the log and its verifier
are exercised on constructed sequences only.*

## Purpose

The audit trail lets a later, independent auditor confirm that the **blinded** workflow was actually
followed and that nothing was quietly changed after the fact. It does **not** judge whether the policy's
labels are correct — that is human validation, which stays **NOT EVALUATED**.

## What is recorded

Every reviewer action becomes one append-only, hash-chained entry:

| Field | Meaning |
|---|---|
| `seq` | monotonic index |
| `ts` | logical timestamp (caller-supplied → deterministic, replayable) |
| `reviewer_id` | pseudonym (`REV-A`, …); never a real identity |
| `role` | assigned reviewer role |
| `artifact_id` | the artifact acted on |
| `event` | one of the event types below |
| `payload_hash` | SHA-256 of the action payload (the raw label/result stays out of the log) |
| `prev_hash` / `entry_hash` | hash chain linking each entry to the previous one |

**Event types:** `ASSIGNED`, `STAGE_A_SUBMITTED`, `REVEALED`, `STAGE_B_SUBMITTED`, `OVERRIDE`,
`ADJUDICATED`, `WITHDRAWN`.

## Guarantees the verifier checks

`verify()` re-derives the chain and returns findings (it never throws, so it can report every problem):

1. **Chain integrity.** Any edit to a recorded entry breaks `entry_hash` / `prev_hash`; tampering is
   detectable (`chain_ok = false`).
2. **Blinding order.** A `REVEALED` event for a `(reviewer, artifact)` pair must be preceded by that
   pair's `STAGE_A_SUBMITTED`. A reveal-before-Stage-A, or a Stage-A-after-reveal, is flagged as a
   blinding violation.
3. **Stage ordering & uniqueness.** Stage B must follow a reveal; no duplicate Stage A or Stage B per
   pair.
4. **Override provenance.** An override is recorded as its own `OVERRIDE` event (payload carries the
   reason); the metrics and adjudication phases consume this.

## Append-only by construction

`AuditLog` exposes `record` (and typed convenience recorders) and nothing else — there is no `update` and
no `delete`. `entries` returns a copy, so a caller cannot mutate the log through it.

## Honesty notes

- The log stores **hashes** of payloads, not raw reviewer text, keeping identity/content exposure minimal
  (governance Phase 3).
- Logical timestamps keep the log deterministic; the pilot administrator supplies wall-clock times at run
  time if desired, but determinism is what makes an audit replayable.
- Nothing in the audit path enforces a policy outcome or triggers an external action.
