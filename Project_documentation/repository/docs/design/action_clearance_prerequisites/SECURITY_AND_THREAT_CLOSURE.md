# Security & Threat Closure

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Expands the merged Action Clearance threat
model (`Project_documentation/repository/docs/design/action_clearance/THREAT_MODEL.md`) for the four prerequisites. For each threat:
control, owner, failure state, MVP requirement, production hardening.

## Threat table

| Threat | Control | Owner | Failure state | MVP requirement | Production hardening |
|---|---|---|---|---|---|
| forged signal source | source registry approval + provenance fingerprint | ingestion boundary / evaluator | `SIGNAL_UNTRUSTED → BLOCK` | Level 1 (approved adapter + digest) | Level 3 signature for high-risk |
| approved adapter with compromised payload | `content_digest` over canonical content; deterministic normalization | evaluator | `SIGNAL_UNTRUSTED → BLOCK` | Level 1 digest check | keyed/signed envelope (L2/L3) |
| stale-signal replay | `valid_until` + `captured_at ≤ evaluation_time`; dedup by `(signal_id, content_digest)` | evaluator | `SIGNAL_STALE → HOLD` | required | nonce/window tracking at ingestion |
| cross-tenant signal substitution | `tenant_id` bound in key and every signal; must equal request tenant | evaluator | `TENANT_MISMATCH → BLOCK` | required | per-tenant key isolation in store |
| signal bundle truncation | `signal_bundle_fingerprint` over the full ordered set; missing mandatory → fail closed | evaluator | `SIGNAL_MISSING → HOLD` | required | signed bundle manifest |
| policy-source downgrade | `policy_refs` evaluated; older/weaker version rejected | evaluator | `POLICY_VERSION_REJECTED → BLOCK` | required | policy version pinning + attestation |
| altered ClearanceReceipt | immutable body; `receipt_id = acr_<result_fingerprint>` recomputed at reservation | Workflow Service / execution boundary | `INVALID_RECEIPT`; chain `INVALIDATED` | required | tamper-evident hash chain (CG §6 roadmap) |
| receipt ID collision | content-addressed id (SHA-256) + `put_receipt` conflict detection | Workflow Service | `CONFLICT_DIFFERENT_BODY` | required | wider hash / audited collisions |
| receipt replay after supersession | lifecycle check (`ISSUED` only) at reservation | execution boundary | `STALE_AUTHORIZATION`/`INVALID_RECEIPT` | required | atomic supersession link |
| receipt used for another target | reservation validates target/operation vs execution key | execution boundary | reservation rejected | required | — |
| duplicate reservation race | atomic `reserve_once` (single conditional insert) | execution ledger | exactly one `ACQUIRED`; other `ALREADY_RESERVED` | **enforcement** (durable backend) | linearizable store |
| reservation-store split brain | uniqueness constraint / single-writer per key | execution ledger | `CONFLICT` → reconcile | enforcement | consensus/quorum store |
| dispatch after clearance expiry | `valid_until` check at reservation and dispatch | execution boundary | `EXPIRED_CLEARANCE` | required | — |
| lost dispatch response | `OUTCOME_UNCERTAIN` + mandatory reconciliation | execution boundary | no auto-release | enforcement | provider idempotency tokens |
| false release after uncertain outcome | uncertain reservations never auto-release | execution ledger | stays reserved until reconciled | enforcement | — |
| reconciliation forgery | reconciliation is permission-gated + immutable `ReconciliationResult` | reconciliation service | rejected | enforcement | signed reconciliation records |
| provider-operation ID substitution | `provider_operation_id`/`external_request_id` bound in observation linkage | execution boundary | mismatch → chain incomplete | enforcement | provider-signed operation ids |
| workflow bypass of reservation | dispatch requires a valid reservation; no reservation ⇒ no dispatch | execution boundary | `FAIL_CLOSED` | enforcement | provider refuses unreserved dispatch |
| direct provider invocation without a valid receipt | provider dispatch gated on reservation which validates the receipt/chain | execution boundary / provider | `FAIL_CLOSED` (missing receipt) | enforcement | provider-side receipt attestation |

## Fail-closed meta-invariant

Every row's failure state is non-executable. The union of these controls preserves the merged security
invariant set (SI-1…SI-18): **missing mandatory trust evidence fails closed; no failure becomes
executable permission; at most one caller executes per key.**

## Residual, staged to enforcement/production

The three race/uncertainty threats (duplicate reservation race, false release, split brain) are closed at
the **contract** level here and remain **enforcement blockers** at the implementation level until a
durable atomic backend exists (`EXECUTION_RESERVATION_CONTRACT.md`). Signature-based provenance (L3) is a
high-risk/production hardening, not an MVP requirement.
