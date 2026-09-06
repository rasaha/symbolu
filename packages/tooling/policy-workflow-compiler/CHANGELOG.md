# Changelog

All notable changes to `ugence-policy-workflow-compiler` are documented here.
This project adheres to semantic-ish versioning for its distribution wheel; the
product version tracks capability maturity separately.

## Unreleased — PA/PWC-X1: authoritative source carriage

A `policy_pack.v2` pack may carry the exact Policy Authority issuance it was
compiled from. `policy_pack.v1`, `workflow_ir.v1` and `workflow_ir.v2` are unchanged.

### Added
- Structural validation of `AuthoritativeSourceRef`: `MISSING_AUTHORITATIVE_SOURCE`
  (only when a caller requires the linkage), `MALFORMED_AUTHORITATIVE_COORDINATE`,
  `INCOMPLETE_ISSUANCE_ATTESTATION` (all-or-none), `AUTHORITATIVE_SOURCE_MISMATCH`.
- `ReleaseManifest.authoritative_source_coordinate` — denormalized for offline
  inspection, outside the logical digest; the binding stays the pack's own reference.
- Maturity gates `authoritative_source_carriage_implemented=true` and
  `authoritative_source_verification_implemented=false`; public API 121 → 123;
  `AUTHORITATIVE_SOURCE.md`.

### Never claimed
The compiler attests carriage, not authenticity. It imports nothing from
`packages/policy-authority` — enforced by a boundary test — and no diagnostic may
imply a signature, key-trust or revocation check it did not perform.

## Unreleased — `workflow_ir.v2` consumption of source-declared semantics

Completes decision D2. `workflow_ir.v2` enrichment now reads `policy_pack.v2`
declarations; v1-sourced graphs are byte-identical.

### Added
- Node semantics fill `data_classification_refs`, `permission_intent_refs`,
  `required_tool_refs` and `DataContractRef.contract_data_version` from the
  declarations attached to a node's source objects, unioned and canonically ordered.
- `DeclaredValueProvenance`: per-value provenance with `DerivationClass.EXPLICIT`
  under the rules `source_declared_semantics` and `source_declared_contract_version`,
  carried in a top-level collection whose digest key is **omitted when empty** — a
  per-node field would have moved every existing v2 fingerprint.
- `source_declared_semantics_implemented=true`; public API 120 → 121.

### Unchanged
An undeclared value stays unresolved and is never defaulted. A v1-sourced graph
enriches to the same `sha256:2e031c78…` fingerprint as before.

## Unreleased — `policy_pack.v2`: source-declarable semantics

Additive schema. `policy_pack.v1` packs, digests and approvals are byte-identical.

### Added
- **`policy_pack.v2`** in `SUPPORTED_SCHEMA_VERSIONS`, with `SemanticDeclaration`
  (a `PolicyObject` under the new `ObjectType.SEMANTIC_DECLARATION`),
  `DeclaredContractRef`, and `AuthoritativeSourceRef` for the PA/PWC-X1 coordinate.
- A sidecar `semantic_declarations` collection and an `authoritative_source` slot on
  the pack, both included in the canonical view **only** for a v2 pack.
- The schema gate inside the single `canonical_pack_view` extracted in step one, so
  the release digest and the approval digest can never diverge on it.
- Fail-closed checks: `V2_FIELD_IN_V1_PACK` (FATAL), `DANGLING_DECLARATION_SUBJECT`,
  `DUPLICATE_DECLARATION_SUBJECT`, `MALFORMED_CONTRACT_VERSION_REF`.
- Ruling **V2-B**: `SEMANTIC_DECLARATION` joins `APPROVAL_SENSITIVE_OBJECT_TYPES`, so
  a changed data classification routes to P3A review.
- Public API 116 → 120 names; maturity gates `policy_pack_v2_supported=true` and
  `source_declared_semantics_implemented=false`.

### Not implemented
`workflow_ir.v2` enrichment does not yet read declared values into node semantics.
Declarations are carried, digest-bound and validated; they are not yet consumed.

## Unreleased — Phase 3A: Governed Diff-Driven Review

Additive and contracts-only. No policy-pack, workflow-IR, compiler, assurance or
release **semantics** change: `policy_pack.v1`, `workflow_ir.v1` and `workflow_ir.v2`
canonical bytes and fingerprints are unchanged, and existing approvals stay valid.

### Added
- **`review/`** — standalone review artifacts (`ReviewRequirement`,
  `ReviewStepRequirement`, `ReviewDisposition`, `ReviewLedger`, `ReviewCheck`),
  deterministic routing (`derive_review_requirement`) from the structural diff and
  the pack's own declared `ApprovalPath`, and a fail-closed gate (`check_review`)
  with nine typed refusal codes.
- Compile-time enforcement (ruling **P3A-1**, `REVIEW_ENFORCEMENT = BLOCKING`):
  `compile_policy_pack(..., review_requirement=, review_ledger=)` refuses an
  unsatisfied requirement and a requirement that describes a different pack.
- `APPROVAL_SENSITIVE_OBJECT_TYPES` made public so routing and
  `approval_re_review_required` read one table rather than two.
- Public API 105 → 116 names; CLI `review-requirements` and `check-review`; new
  honest maturity gate `diff_driven_review_implemented`; `DIFF_DRIVEN_REVIEW.md`.

### Rulings implemented
- **P3A-1** `REVIEW_ENFORCEMENT = BLOCKING` — no minor-change exemption, no approval
  carry-forward, and no defaulted reviewer when no covering path is declared.
- **P3A-2** `REVIEWER_IDENTITY = OPAQUE_REFERENCE` — the authority reference is
  carried verbatim; this package neither imports nor resolves an authority directory.
- The **non-weakening invariant**: the review gate is additional to the approval
  gate, never a substitute. A satisfied review cannot rescue a failed approval.

### Not implemented (maturity booleans report false)
Runtime execution and deployment, action authorization, identity resolution,
enterprise policy evaluation, pilot validation, production certification.

## Product 0.2.0 — Phase 2: Semantic Workflow Enrichment (contract `workflow_ir.v2`)

Additive. Distribution and product versions are both **0.2.0**. The version a
workflow-IR logical digest commits to is a FROZEN semantic identity per contract
(`workflow_ir.v1` -> `0.1.0`, `workflow_ir.v2` -> `0.2.0`), decoupled from the
package version, so publishing 0.2.0 leaves every existing `workflow_ir.v1`
fingerprint byte-identical. `workflow_ir.v1` is otherwise unchanged.

### Added
- **`workflow_ir.v2`** semantic-enrichment contract that embeds the unchanged v1
  graph and adds, per role-relevant node: semantic purpose, role relevance,
  functional capability requirements, typed input/output data-contract references,
  authority + human-review classification, governance boundary references, and
  per-value policy provenance — each deterministic and provenance-backed.
- **Dependency semantics** (`DATA` / `CONTROL` / `ORDERING` / `REVIEW` / `AUTHORITY`
  / `GOVERNANCE` / `CONDITIONAL`) derived from typed edges.
- **`CompiledReleaseValidator`** with states `VALID` / `VALID_WITH_WARNINGS` /
  `INVALID` / `UNSUPPORTED_VERSION` / `INTEGRITY_FAILURE` and structural / semantic /
  authority / contract / dependency / provenance / digest integrity checks. Authority
  and digest failures are never downgraded to warnings.
- Public API additions (surface 71 → 105), CLI additions (`compile --contract`,
  `validate-release`, `inspect-semantics`, `inspect-dependencies`,
  `inspect-provenance`, `compare-contracts`, `upgrade-v1`), honest P2 maturity flags,
  and an extended isolated-distribution verifier + scoped CI.

### Not implemented (maturity booleans report false)
AWC adapter update, agent eligibility / ranking / team composition / permission
proposals / fallback planning, runtime execution, live scheduling, action
authorization, enterprise deployment-policy evaluation, pilot validation, production
certification.

### Compatibility
All P1 tests pass; v1 fingerprints byte-stable (release `sha256:fb9fd4b9…`, IR
`sha256:169ad24c…`); AWC P1/P2 and Governance Studio P3A unchanged; platform-freeze
digest unchanged.

## 0.1.0 — Phase 1: Structured Policy Core and Deterministic Compiler MVP

Initial independent distribution.

### Added
- Structured, typed, versioned, provenance-aware policy-pack object model (20
  object categories) with explicit lifecycle states and deterministic
  serialization.
- Deterministic validation engine with structured diagnostics (severity levels
  INFO / WARNING / REVIEW_REQUIRED / ERROR / FATAL): duplicate ids, dangling
  references, missing provenance, unresolved authority, malformed approval paths,
  segregation-of-duties contradictions, unknown capabilities, missing expected
  outcomes, embedded secrets, non-deterministic values, unsupported schema.
- Deterministic governed-workflow IR (14 node kinds, 9 edge kinds) with
  content-addressed node ids and deterministic edge ordering.
- Data-driven capability registry (TAP, Decision Authority, ActionGate, Action
  Clearance, StoryGraph, Model Selection, optional orchestrator) resolved from
  metadata — no runtime provider imports.
- Authority-boundary enforcement: illegal authority compositions fail compilation.
- Deterministic assurance generation (14 test categories) with a coverage matrix
  and a fail-closed coverage invariant.
- Audit-schema generation with a canonical (non-cryptographic) event-digest chain.
- Human-approval records and an approval gate (no compiler self-approval).
- Content-addressed compiled release package with a reproducible logical digest.
- Object-level structural diff and change-impact analysis.
- Procurement reference policy pack and a deterministic equivalence harness
  against `ugence-procurement`.
- Public API (`ugence_policy_workflow_compiler.api`), CLI, and `python -m` entry.

### Not implemented (by design, Phase 1)
- Document/PDF/Word ingestion, OCR, NLP/LLM extraction, learned enforcement.
- Runtime deployment, live workflow execution, connector writes.
- No model SDK, web framework, database driver, cloud/ERP SDK dependency.
- Not pilot-validated; not production-certified.
