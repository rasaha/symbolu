# Changelog — `ugence-policy-authority`

All notable changes to this package are documented here. The surface snapshot in
`public_api.json` is authoritative and is asserted against the live package by
`tests/packaging/test_public_api.py`, including dataclass field order and the
exact value of every string constant.

## 0.1.0 — initial release (unreleased)

The shared, platform-wide **Ugence Policy Authority**, ratified in
`docs/architecture/ADR_UGENCE_POLICY_AUTHORITY.md`. Internal platform
infrastructure: not a customer-facing module, not a product, and not a UVI
engine. **UVI policy schemas are its first policy-family adapter.**

### Added

- **Shared core + policy-family adapters.** A generic core that imports no
  policy family, names no family type, and contains no family type-branch;
  family semantics arrive only through a registered `PolicyFamilyAdapter`. A
  second family is added by registering a second adapter, with no core change —
  enforced by an AST boundary test and demonstrated end to end by a synthetic
  non-UVI family in the test suite.
- **Family-neutral identity.** `PolicyCoordinate` (family, id, version, content
  digest, scope, tenant) plus `PolicyArtifactDescriptor` and `AdapterRegistry`.
  `GLOBAL_TENANT` names the canonical empty tenant component explicitly.
- **The UVI adapter** (`UviPolicyFamilyAdapter`) for the five merged UVI policy
  families, shipped inside this distribution per ADR §10.3 with the
  core/adapter boundary preserved in code.
- **Versioned, domain-separated canonicalization**
  (`ugence.policy-authority/canonicalization/v1`) with an exactly specified JSON
  encoding, key ordering, hash input, UTC datetime rendering, `float` and
  unsupported-type rejection, and **Unicode posture (a): NFC required, non-NFC
  rejected recursively** rather than silently normalized. Naive datetimes are
  refused everywhere, including at the public helpers. `canonical_bytes`,
  `sha256_hex`, `framed_body_bytes` and `framed_body_digest` are public so a
  third party can verify any digest independently.
- **Approval boundary.** `ApprovalEvidenceRef`, `ApprovalVerification`, the
  injected `ApprovalVerifier` protocol, and `DenyAllApprovalVerifier` as the only
  shipped implementation. The authority independently re-checks the verifier's
  binding and refuses when the issuer names itself the approver or when a
  fabricated duck-typed result is returned.
- **Signing boundary.** Injected `PolicySigner` / `PolicySignatureVerifier`
  protocols, a stdlib-only Ed25519 (RFC 8032) reference signer, and
  `DenyAllSignatureVerifier`.
- **Immutable trust anchors.** `PolicyKeyRing` defensively copies caller
  mappings and sequences, exposes a `MappingProxyType` view, and refuses
  attribute rebinding. `PolicyVerificationKey` binds identity, authority,
  tenant/scope, validity window, algorithm, key id and a `KeyEntitlement` set.
- **Signed, authorized, resolution-verified revocation.** A revocation signer is
  mandatory; the revoking authority is the signer's; the record binds the
  complete exact coordinate under a distinct versioned domain; the key must hold
  `REVOKE_POLICY` for that exact scope; and resolution re-verifies the whole
  thing, failing closed as `REVOCATION_INTEGRITY_INVALID` on anything forged,
  replayed or tampered.
- **Historical-resolution disclosure.** `HistoricalResolutionRule` defaults to
  `DENY_ALWAYS`; an explicitly historical answer carries `historical=True`, its
  own `as_of`, and `implies_current_validity is False`.
- **Registry.** `PolicyRegistry` protocol and a process-local, lock-guarded
  `InMemoryPolicyRegistry`: exact-coordinate lookup only (no floating lookup
  exists), append-only, idempotent only on canonically identical resubmission,
  conflict-rejecting, and non-disclosing across tenants.
- **Services.** One canonical entry point each: `issue_policy`,
  `resolve_policy`, `revoke_policy`, plus `verify_revocation_record`. The clock
  is injected everywhere and read exactly once per issuance.
- **Typed vocabulary.** `ApprovalVerificationStatus`, `KeyEntitlement`,
  `KeyVerificationStatus`, `PolicyResolutionStatus`, `PolicyResolutionReason`,
  `PolicyRevocationReasonCode`, `HistoricalResolutionRule`, and an error taxonomy
  rooted at `PolicyAuthorityError`.
- Package scaffolding: `api.py` with a controlled `__all__` (65 symbols),
  `public_api.json` snapshotting constants and field order, `py.typed`, README,
  this changelog, an isolated multi-wheel distribution verifier, 327 tests and 34
  independent adversarial probes.

### Changed — corrections to the pre-ratification draft (PR #1435)

The draft was a **UVI-owned** authority. It is now the **shared platform**
authority, with these corrections:

- **Renamed without compatibility shims.** `packages/uvi-policy-authority/` →
  `packages/policy-authority/`; `ugence-uvi-policy-authority` →
  `ugence-policy-authority`; `ugence_uvi_policy_authority` →
  `ugence_policy_authority`. No alias, shim, old namespace or second wheel
  exists; the old import fails in a clean environment. Version stays 0.1.0
  because nothing was ever released.
- **Protocol identity is platform-neutral.** `GV-2C-b.1` →
  `ugence.policy-authority/v0.1`. All domain tags moved to the
  `ugence.policy-authority/…` namespace.
- **Supersession posture replaced.** The configurable `SELF_DECLARED_ONLY` /
  `SUPERSESSION_UNDETERMINED` posture is removed; v0.1 rejects a non-empty
  unstructured `supersedes_ref` at issuance, before any collaborator runs.
- **Revocation hardened.** The optional/unchecked path is replaced by mandatory
  signing, entitlement authorization, and resolution-time verification.
- **Key-ring mutability fixed.** Caller mappings are defensively copied and the
  store is neither mutable nor rebindable.
- **Unused dependency removed.** `ugence-governance-contracts` was declared but
  never imported; the declaration is gone.
- **Registry concurrency made real.** Compound operations are lock-guarded, and
  the documentation now states process-local scope rather than implying more.

### Deferred

- **Structured successor references** (supersession activation, predecessor
  invalidation, successor authorization, historical resolution across a
  supersession boundary, cross-tenant/family restrictions) — a separate contract
  milestone with its own owner ruling (ADR §13.4, P-7).
- **Benchmark-value governance** (UVI ADR D-3 / M-2C.2).
- **Production persistence and distributed concurrency** (ADR §15.7).
- **Production key management** (HSM/KMS); the reference signer is not a
  production posture.
- Moving the UVI canonicalization projection into `uvi-policy-contracts` — a
  separately reviewed compatibility decision (ADR §12.2).
- Readiness integration, forecasting, attribution, and financial valuation —
  out of scope entirely.

### Unchanged

`ugence-uvi-policy-contracts` (0.1.0), `ugence-governance-contracts` (0.2.0),
`ugence-agent-value-readiness` (0.2.0), `governed-value` (0.2.0), every global
`CONTRACT_VERSION`, and both ratified ADRs are untouched by this package.
