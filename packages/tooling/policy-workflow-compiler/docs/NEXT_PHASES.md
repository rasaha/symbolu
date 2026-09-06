# Next Phases

This document **describes** — it does not implement — the work ratified to follow
the current tooling product. Nothing described here as future work is present in the
shipped build; the maturity gates reported by `version_info()` (see `MATURITY.md`)
remain the authoritative statement of what exists today. Where a section records
work as delivered, it says so explicitly and names the evidence.

The plan below is **owner-ratified**. The binding record is
`Project_documentation/repository/docs/audits/policy_workflow_compiler_ratification/RATIFICATION.md`,
which rules on the five open compiler decisions (D1–D5) and one cross-package
boundary (PA/PWC-X1). Where this document and that record differ, the ratification
governs.

## The boundary that holds across every ratified phase

The compiler may **emit and validate declarative** capability-binding requirements.
It may not instantiate, import, or invoke runtime providers. Actual provider
resolution belongs to a composition root, a simulator, or a consuming product.

This is why the ratified plan does not include the "optional canonical capability
adapters" once sketched here: binding an IR node to a concrete provider
implementation would require importing that provider. The package's scoped CI
enforces the opposite (the `import-boundary-suite` job), and
`CAPABILITY_REGISTRY.md` records that core compilation resolves capability targets
from metadata alone. The ratified strands keep that invariant intact.

No ratified phase adds a runtime call, credential, network access, or side effect.
`runtime_deployment_implemented` and `runtime_execution_implemented` stay `false`
through all of them. The product boundary (see `PRODUCT_BOUNDARY.md`) is unchanged:
the tooling compiles, describes, and — at P3C — simulates; humans and canonical
capabilities keep decision, approval, authorization, and execution authority.

## Ratified order

1. **PA/PWC-X1** — the Policy Authority boundary and the source-linkage coordinate.
2. **PWC-P3A** — diff-driven review requirements and approval binding.
3. **`policy_pack.v2`** — source-declarable semantic fields.
4. **PWC-P3B** — declarative capability/contract binding **validation**.
5. **PWC-P3C** — deterministic offline simulation.
6. **AI Hiring reference equivalence.**
7. A real pilot against a named policy corpus, then `pilot_validated`.

### PA/PWC-X1 — Policy Authority boundary and source linkage

Policy Authority owns authoritative issuance, exact-version identity, lifecycle,
supersession, revocation, and resolution. This package consumes an exact resolved
authoritative artifact and transforms it deterministically. Compiled artifacts
retain immutable linkage to the authoritative source policy coordinate and digest.

This is new work. Today `models/provenance.py` carries **document**-level provenance
(`ProvenanceReference` with `source_id`, `title`, `version`, `content_digest`,
`clause`, `authority_level`, plus `SourceDocument`), which identifies a document
rather than an authoritative issuance. Nothing binds a compiled release to an issued
policy version, its registration or signature reference, or its revocation state.

The linkage must be carried as **data** in the pack and compiled release — an exact
policy coordinate plus digest, validated structurally. It must not become an import
of `packages/policy-authority`; resolution and revocation checking belong to the
consumer or composition root.

### PWC-P3A — Governed diff-driven review and approval binding

The structural diff already reports change types and an impact summary including
`approval_re_review_required` (see `STRUCTURAL_DIFF.md`), and the approval gate
already rejects an approval whose digest does not match the pack (see
`HUMAN_APPROVAL.md`). P3A builds the governed **workflow** around those existing
signals: a structurally meaningful change routes to a reviewer, and approval re-binds
to the new structural digest. P3A does not invent the signals; it governs them. The
no-self-approval and digest-binding rules carry forward unchanged.

### `policy_pack.v2` — source-declarable semantic fields

An additive schema permitting explicit declaration of data-classification
references, permission intents, required tools, and versioned contract references.
These are ratified because they are **policy semantics** — governance facts a source
policy can state — not because a particular phase consumes them.

`policy_pack.v1` remains supported and every existing v1 digest stays
byte-identical: `schema_version` participates in the release logical digest, so a
pack declaring v2 receives a new digest while v1 packs are untouched, and
`check_schema_version` fails closed so widening the supported set stays an explicit,
reviewable act. The standing rule is unchanged — a declared value is preserved, an
absent one is never inferred.

### PWC-P3B — Declarative binding **validation**

P3B is conformance validation, not a second emission path. `workflow_ir.v2` already
emits declarative capability binding: `CapabilityRequirement` and `DataContractRef`,
each provenance-backed (see `CAPABILITY_REQUIREMENTS.md` and `DATA_CONTRACTS.md`).
Release validation currently checks only that capability requirements are not
duplicated.

P3B's delta is validating what is already emitted against registry metadata:
authority-disposition compatibility, advisory-versus-authoritative misuse,
optionality, minimum version, and unresolved or unknown capability references. It
preserves the authority-boundary guarantees in `AUTHORITY_BOUNDARIES.md` — no
validation may let an advisory capability decide, nor a decision maker perform action
authorization.

### PWC-P3C — Deterministic offline simulation

Exercising the compiled IR and its assurance specifications in a reproducible
sandbox, inheriting the package's offline-determinism and fail-closed posture (see
`DETERMINISM.md` and `SECURITY_AND_FAILURE_MODEL.md`). P3C simulates; it does not
execute. No runtime authority, no side effects.

### Reference equivalence beyond Procurement

Procurement **and** AI Hiring equivalence are both required before
`pilot_validated=true`. Neither blocks P3 development. AI Hiring is the ratified
second domain because its governance shape differs — advisory-AI versus
binding-human-decision separation, rather than Procurement's threshold-and-limit
authorization path — so agreement across the two is evidence of generality rather
than repetition. See `PROCUREMENT_REFERENCE_VALIDATION.md` for the existing harness
and `MATURITY.md` for the full pilot evidence list.

## Already delivered

### workflow_ir.v2 semantic enrichment

The `workflow_ir.v2` semantic-enrichment contract once described here as future work
is **implemented** in product 0.2.0 (see `WORKFLOW_IR_V2.md` and the P2 maturity
flags in `version_info()`). It enriches the workflow description only; it does not
bind a runtime or execute anything.

### AWC P2.1 — delivered, in the AWC package

**AWC P2.1 — Policy Workflow Compiler v2 Compatibility Adapter, Overlay Reduction and
P1/P2 Fingerprint-Preserving Migration** updated the Agent Workforce Composer to
consume enriched `workflow_ir.v2`, reducing only the temporary overlay fields this
compiler now emits (`role_name`, `role_description`, `human_review_requirement`, the
functional base capability, typed contracts) while preserving every enterprise-policy
overlay that remains correctly external.

That work is delivered, and it landed where it belongs — in the AWC package, not
here. Its evidence is AWC-side: `ugence_agent_workforce_composer.adapter_v2`, the
`COMPILER_V2_ADAPTER.md` contract document, the scoped
`agent-workforce-composer-p2-1-ci.yml` workflow, and the AWC maturity gates
`compiler_v2_adapter_implemented`, `overlay_reduction_implemented` and
`v1_v2_equivalence_harness_implemented`.

This package emitted no new contract for it and changed no digest. Its own
`awc_adapter_updated` gate still reports `false` and is now **deprecated** by
ratification: it must not be read as platform state, it is held `false` through the
0.2.x line for compatibility, and it is removed only at the next
compatibility-controlled version. See `MATURITY.md`.
