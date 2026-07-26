# H5 — Failure-Injection Report

Deterministic failure injection via `CaseSpec` flags and reference-provider/adapter
behaviors (`test_h5_failure_injection.py`, plus H2/H4 failure tests). For every injected
failure we verify a fail-safe state, no unauthorized progression, no silent data loss, no
false execution success, a visible unresolved status where applicable, and preserved
diagnostic/reconstruction evidence.

| Injected failure | Verified outcome |
|---|---|
| Generator timeout | `generation_failed`; no recommendation |
| Malformed recommendation output | `generation_failed` (schema-rejected) |
| TAP timeout | claim UNEVALUABLE → `ASSERTION_REVIEW_REQUIRED`; not review-ready |
| Malformed TAP assessment | `ASSERTION_REVIEW_REQUIRED` (fail-safe) |
| DGM access denial / missing human authority | decision blocked (H3 gate; `ReviewerAuthorityError`) |
| ActionGate timeout / unavailable | not authorized; no execution |
| Malformed ActionGate authorization | non-executable (fail-safe) |
| Authorization expiry (exec time) | `HiringAuthorizationExpiredError`; not executed |
| Adapter transport failure (transient) | `EXECUTION_FAILED`; bounded retry available |
| Adapter permanent failure | `EXECUTION_FAILED`; no retry |
| Duplicate dispatch | idempotent; DUPLICATE detected; no second external action |
| Malformed receipt | `MalformedReceiptError`; `EXECUTION_FAILED` (never EXECUTED) |
| Target mismatch | `TargetMismatchError`; `EXECUTION_FAILED` |
| Audit tamper / corrupted hash chain | reconstruction detects; `reconstructed == False` |
| Broken causation/link | reconstruction `links_intact == False` |

**No injected failure produced a false execution success or a silent reconciliation**
(`test_no_failure_path_marks_false_success`).
