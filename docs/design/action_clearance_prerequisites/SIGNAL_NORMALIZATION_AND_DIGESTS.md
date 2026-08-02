# Signal Normalization & Digest Rules

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Extends
`docs/design/action_clearance/DETERMINISM_AND_FINGERPRINTS.md`; introduces no new algorithm, reuses the
merged `action_clearance` domain-separated SHA-256 pattern.

## Canonical normalization (deterministic, total)

Trusted signals are normalized before any digest is computed, using the **same** canonical form the
merged design fixes for requests and results:

- **Field ordering:** JSON object keys sorted lexicographically.
- **Timestamps:** one canonical form — RFC3339 UTC with fixed precision, **or** integer epoch-nanoseconds
  (pick one at implementation and freeze it, per the merged determinism doc). No locale, no offset
  ambiguity.
- **Enums:** encoded by their string value (`ACTOR_STATUS`, `PRESENT`, …), never by ordinal.
- **Unicode:** NFC normalization on all string fields before hashing.
- **Map ordering:** mapping keys sorted; nested maps recursively.
- **Null handling:** absent optional fields are omitted, not encoded as `null`, except where `null` is a
  meaningful value (e.g. `authorization_ref = null` for a global incident signal) — such fields are
  encoded explicitly and documented in the schema.
- **Numbers:** `NaN`/`Inf` rejected; `-0.0 → 0.0`; integers and floats encoded canonically
  (`allow_nan=false`, compact separators `(",", ":")`, `ensure_ascii=true`).
- **Bytes:** hex-encoded.
- **Included fields (fingerprinted):** every `x-fingerprinted: true` field in
  `trusted_signal.schema.json` plus the provenance projection's integrity fields.
- **Excluded fields:** adapter extension maps not marked fingerprinted; storage metadata.

## Domain-separated prefix

Reusing the merged rule: `action_clearance\x1f<domain>\x1fv1\x1f` + canonical JSON, hashed SHA-256.

## Fingerprint forms (three, distinct)

| Fingerprint | Domain | Covers | Purpose |
|---|---|---|---|
| `signal_content_fingerprint` | `signal_content` | the normalized signal *value + identity* fields (`signal_type`, `tenant_id`, `subject_ref`, `captured_at`, `valid_until`, `normalized_value`, …) | the `content_digest` root; detects payload tampering |
| `signal_provenance_fingerprint` | `signal_provenance` | source/adapter/ingestion/policy fields (`source_id`, `source_kind`, `adapter_id`, `adapter_version`, `ingestion_boundary`, `policy_refs`, `signature_ref`) | binds *how* the signal was obtained; audited |
| `signal_bundle_fingerprint` | `signal_bundle` | the ordered set of per-signal content fingerprints | the request-level bundle identity (already in the merged design) |

Proposed printable form, following repository convention: `trusted_signal.v1:<sha256hex>`. (The merged
design uses `acr_<hash>` for results; this profile-neutral `trusted_signal.v1:` prefix mirrors it for
signals. The exact separator follows the frozen `identity.py` convention at implementation.)

**Why three fingerprints:** content and provenance must be independently verifiable — a signal whose
*content* is intact but whose *provenance* is unapproved must fail (`SIGNAL_UNTRUSTED`), and an auditor
must be able to prove either property in isolation. The bundle fingerprint composes the content
fingerprints so that adding, removing, or reordering signals changes the bundle identity.

## Bundle ordering & duplicates

- **Ordering:** signals sorted by `signal_id` (stable) before the bundle fingerprint is computed; order
  in the wire request does not change the fingerprint.
- **Duplicate signals** (same `signal_id`): a `NON_RETRYABLE_ERROR` (malformed bundle) — ids must be
  unique within a bundle.
- **Duplicate *content*** (different `signal_id`, identical content fingerprint): permitted but
  deterministically deduplicated for evaluation; it does not multiply weight (non-compensatory rules —
  see `SIGNAL_FRESHNESS_AND_CONFLICTS.md`).
- **Bundle omission:** removing a required signal changes the bundle fingerprint **and** triggers
  `SIGNAL_MISSING → HOLD` (fail closed). Acceptance scenario 10 proves omission changes the fingerprint.

## Closure

**CLOSED_BY_NEW_PRODUCT_INTERFACE** — the three fingerprint domains and normalization rules are additive
design artifacts over the merged determinism model; no new algorithm or dependency is introduced.
