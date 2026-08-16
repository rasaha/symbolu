# Changelog — `ugence-uvi-policy-authority`

All notable changes to this package are documented here. The package follows
semantic versioning; the surface snapshot in `public_api.json` is authoritative
and is asserted against the live package by `tests/packaging/test_public_api.py`.

## 0.1.0 — GV-2C-b (initial release)

The first UVI Policy **Authority** leaf: the technical issuance, registry,
trusted-resolution and policy-version-revocation ownership that ADR §19 recorded
as a required dependency and ADR §26.1 left as an open owner ruling.

### Added

- **Content-digest definition.** `canonical_policy_body_digest` supplies the
  rule the merged contracts deliberately left to the Policy Authority: a
  single-pass canonical sha-256 over the whole artifact with the one
  self-referential path `metadata.content_digest` **removed** from the payload.
  No fixed-point iteration, no sentinel value, and no dependency on signature
  bytes (a policy artifact has no signature field). Domain-tagged and bound to
  the exact runtime dataclass name.
- **Closed policy-family union.** Exactly the five merged families
  (`GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy`, `ValuationPolicy`,
  `ReadinessPolicy`), matched by exact runtime type. No new families; subclasses
  and arbitrary dataclasses are refused.
- **Approval boundary.** `ApprovalEvidenceRef`, `ApprovalVerification`, the
  injected `ApprovalVerifier` protocol, and `DenyAllApprovalVerifier` as the only
  shipped production implementation. The authority independently re-checks that a
  verifier's result binds the exact policy, and refuses when the issuing
  authority names itself the approver.
- **Signing boundary.** Injected `PolicySigner` / `PolicySignatureVerifier`
  protocols, a stdlib-only Ed25519 (RFC 8032) reference signer following the
  repository's existing authority convention, `PolicyVerificationKey` /
  `PolicyKeyRing` with exact-`key_id` resolution and typed failure statuses, and
  `DenyAllSignatureVerifier`.
- **Domain-separated signed payloads** for issuance and policy-version
  revocation, binding every field required by the milestone.
- **Authority records.** `IssuedPolicyRecord`, `PolicyRevocationRecord`, and
  `PolicyResolution` — immutable, tuple-normalized, deterministic, and unable to
  carry private key material. A `PolicyResolution` structurally cannot return a
  policy alongside a failed status.
- **Registry.** The `PolicyRegistry` protocol and `InMemoryPolicyRegistry`
  reference implementation: exact-reference resolution only (no floating
  `latest` lookup exists), append-only, idempotent on byte-identical
  re-submission, conflict-rejecting, and tenant-isolated without leakage.
- **Services.** One canonical entry point each: `issue_policy`, `resolve_policy`,
  `revoke_policy`. The clock is injected everywhere; a successful issuance reads
  exactly one caller-supplied instant.
- **Typed status vocabulary.** `ApprovalVerificationStatus`,
  `KeyVerificationStatus`, `PolicyResolutionStatus`, `PolicyResolutionReason`,
  `PolicyRevocationReasonCode`, `HistoricalResolutionRule`, `SupersessionRule`,
  plus a typed error taxonomy rooted at `PolicyAuthorityError`.
- **Explicit historical-resolution rule.** Revocation is absolute at and after
  `revoked_at`; behaviour strictly before it is a configured decision, defaulting
  to `DENY_ALWAYS`.
- Package scaffolding: `api.py` with a controlled `__all__` (50 symbols),
  `public_api.json`, `py.typed`, README, this changelog, an isolated multi-wheel
  distribution verifier, and 231 contract/authority/packaging tests plus
  independent adversarial probes.

### Deferred

- **Successor-based supersession is not binding.** `supersedes_ref` is an
  unstructured `str` in the merged contracts and cannot bind a complete exact
  `PolicyReference`. The authority never infers supersession from it: it either
  ignores it (default) or fails closed with the typed
  `SUPERSESSION_UNDETERMINED` status. Making it binding requires a structured
  successor reference — a separate contract milestone and an owner ruling.
- **Benchmark-value registration** — a separate milestone (ADR D-3, M-2C.2).
- **Production persistence** — the reference registry is in-memory only.
- **Production key management** — HSM/KMS-backed signing is a deployment
  concern; the protocols are shaped for it.

### Unchanged

`ugence-governance-contracts` (0.2.0), `ugence-uvi-policy-contracts` (0.1.0),
`ugence-agent-value-readiness` (0.2.0), `governed-value` (0.2.0), every global
`CONTRACT_VERSION`, and the ratified ADR are all untouched by this milestone.
