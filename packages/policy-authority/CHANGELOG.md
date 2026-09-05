# Changelog — `ugence-policy-authority`

All notable changes to this package are documented here. The surface snapshot in
`public_api.json` is authoritative and is asserted against the live package by
`tests/packaging/test_public_api.py`, including dataclass field order and the
exact value of every string constant.

## 0.3.0 — durable single-node registry (ADR §15.7, decision D-3)

Closes the persistence deferral recorded in ADR §15.7, under decision D-3 of
`docs/architecture/ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md`
(adopting Benchmark Registry ruling D-22 Posture B). Purely additive: ten new
public names, none removed, no resolution semantics and no signing behaviour
changed.

### Added

- **`SqlitePolicyRegistry`** — the durable registry behind the unchanged
  `PolicyRegistry` seam: stdlib `sqlite3`, WAL, `BEGIN IMMEDIATE` around every
  append, exact-coordinate lookup only, three append-only tables guarded by
  triggers, a hash-linked `ledger_events` table with `verify_chain()`, idempotent
  only for a canonically identical record, typed conflict otherwise, cross-tenant
  lookup the same miss, successor plus supersession in one transaction.
  `SQLITE_REGISTRY_SCHEMA_VERSION` is refused on mismatch.
- **`PolicyArtifactCodec`** (core port) and **`UviPolicyArtifactCodec`** (adapter)
  — family-owned rehydration of the opaque `IssuedPolicyRecord.policy`. The core
  encodes records with its one canonical encoder and decodes them with a strict
  annotation-driven dataclass decoder; the UVI codec rebuilds the five families.
  A record the codec cannot rehydrate is a `PolicyRegistryStorageError`.
- **`PolicyRegistryConsistencyScope`**, **`PolicyRegistryConsistencyClaim`**,
  **`PolicyRegistryConsistencyDescriptor`**, **`declared_consistency`** — the
  typed consistency declaration. `SINGLE_NODE_DURABLE` claims durability,
  multi-process coordination and cross-process atomic revocation on one host;
  distributed strong consistency and eventual-consistency safety are explicitly
  disclaimed in every scope; the answers are derived properties, never fields.
- **`PolicyRegistryStorageError`**, **`PolicyRegistryProductionModeError`**.

### Changed

- `InMemoryPolicyRegistry` accepts `production_mode` and refuses `True`; it
  declares `PROCESS_LOCAL_ONLY`. Its constructor is otherwise unchanged.

### Verified

- Parity script against the in-memory reference (identical values and error
  classes), cold-start trusted resolution for all five UVI families, revocation
  on one connection visible to another at once, twelve forked processes racing
  one identity slot (one stored, eleven typed conflicts) and twelve identical
  writers (all idempotent, one row), append-only triggers, chain tamper
  detection, and byte-identical store after every failed append.

## 0.2.0 — structured policy-version supersession (the `ACC-LC` round)

The change set authorized as `ACC-LC-IA-2` (see
`docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_IMPLEMENTATION_AUTHORITY.md`,
over the `ACC-LC-BASE`/`ACC-LC-1`..`ACC-LC-5` ratification). Purely additive:
six new public names, none removed, and no existing behaviour relaxed.

### Added

- **A structured successor reference.**
  `PolicyArtifactDescriptor.supersedes_coordinate` carries the exact predecessor
  as a complete `PolicyCoordinate` — the only shape the registry can resolve,
  since exact-match lookup is the only lookup it performs (`ACC-LC-IA-1`).
  `None` is the default: an artifact supersedes nothing unless it says so.
- **Supersession as part of issuance, not a separate act.** There is no
  `supersede_policy` entry point and deliberately none: `ACC-LC-2` ruled that
  **one** signed act both admits the successor and stops the predecessor
  resolving. `issue_policy` gains `supersession_id` and `signature_verifier`,
  both required exactly when a structured predecessor is declared.
- **A third append-only store.** `PolicySupersessionRecord` (signed, naming both
  coordinates), `append_issuance_with_supersession`, `append_supersession` and
  `supersessions_for`. An issued record is immutable and its `lifecycle_state`
  is signed artifact content, so nothing edits a predecessor into `SUPERSEDED`;
  the transition is an append, on revocation's exact precedent (`ACC-LC-IA-2`).
  The compound append is atomic: if the supersession cannot be written, the
  issuance is rolled back, because a stored successor whose predecessor still
  resolves is the one state this act exists to prevent.
- **Six admissibility refusals at issuance step 4** (`ACC-LC-IA-3`), each raising
  `PolicySupersessionError` before the digest, the approval verifier, the signer
  and any append: self-reference, cross-tenant, cross-scope, absent predecessor,
  already-revoked predecessor, already-superseded predecessor. Step 4 now
  *reads* the registry; the invariant is unchanged and still proven — **nothing
  from a rejected artifact is stored**.
- **Resolution consults the store.** A verified supersession denies with the new
  `PolicyResolutionReason.SUPERSEDED`, naming the successor; an unverifiable one
  fails closed as `SUPERSESSION_INTEGRITY_INVALID` rather than being ignored,
  exactly as its revocation counterpart does. A stored supersession is never
  trusted merely because it is stored.
- **Its own signing domain**
  (`ugence.policy-authority/policy-supersession/v1`), so a supersession
  signature can never be replayed as an issuance or a revocation.
- **`SUPERSESSION_PREDECESSOR_INADMISSIBLE`**, the stable typed token consumers
  branch on instead of string-matching a message.

### Unchanged, deliberately

- **The unstructured refusal stands.** A non-empty `supersedes_ref` string is
  still rejected at step 4, whether or not a structured coordinate accompanies
  it. No existing refusal is relaxed and no already-valid artifact is
  invalidated.
- **No new key entitlement.** The supersession record is signed by the issuing
  key in the same act and verified against `ISSUE_POLICY`; a separate "may
  supersede" capability could never be exercised on its own, since the only path
  to supersession is issuing a successor.
- **Supersession is not revocation.** Separate stores, separate concepts,
  neither implying the other: a superseded version is replaced, not withdrawn,
  and keeps its record.
- **No suspension.** Deferred to its own round with its cost recorded
  (`ACC-LC-3`); a reversible pause needs a state absent from the ratified closed
  lifecycle set.
- **No agent or role lifecycle authority** (`OD-C4=A`). This is the lifecycle of
  a signed, versioned policy artifact and nothing else.

`[G]` No **shipped** adapter yet produces a `supersedes_coordinate`, so no
shipped policy family can supersede until that family opts in — a separate
authorization. The capability is proven end to end against a synthetic family in
`tests/authority/test_supersession.py`, which also keeps it family-neutral.

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
- **The resolved descriptor projection.** A `RESOLVED` `PolicyResolution` carries
  three optional trailing fields — `descriptor_adapter_id`,
  `descriptor_policy_type` and `descriptor_canonical_projection` — populated by
  `resolve_policy` from the descriptor it already re-derives. `resolve_policy`
  has always enforced `descriptor.body_digest() == record.policy_body_digest`
  before returning; these fields republish the *inputs* to that digest so a
  consumer holding no adapter registry can rebuild the frame through the public
  `framed_body_digest` and reach the same value. Downstream, `policy_body_digest`
  is otherwise a one-way hash with nothing to check against — notably for
  `policy_type`, which is framed into the body digest but absent from the
  issuance signing payload. This is a **republication of an already-enforced
  equality, not a new claim**: nothing about what a resolution proves changes.
  The fields are optional because `PolicyResolution` is a public dataclass anyone
  may hand-assemble, not because absence is acceptable to a consumer — a verifier
  relying on them must refuse `None`. The constructor requires all three together
  or none, so a partial triple that looks checkable and is not cannot exist, and
  the projection is defensively copied behind a `MappingProxyType` as
  `PolicyKeyRing` already does. Version stays 0.1.0: nothing has been released.
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
