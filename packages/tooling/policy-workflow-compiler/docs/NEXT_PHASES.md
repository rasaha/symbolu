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

1. ~~**PWC-P3A** — diff-driven review requirements and approval binding.~~
   **Delivered** — see "Already delivered" below and `DIFF_DRIVEN_REVIEW.md`.
2. **`policy_pack.v2`** — source-declarable semantic fields (next).
3. **PA/PWC-X1 carriage and validation** — activated by v2.
4. ~~**PWC-P3B** — declarative capability/contract binding **validation**.~~
   **Delivered** — see `BINDING_CONFORMANCE.md`.
5. ~~**PWC-P3C** — deterministic offline simulation.~~
   **Delivered** — see `OFFLINE_SIMULATION.md`.
6. **AI Hiring reference equivalence.**
7. A real pilot against a named policy corpus, then `pilot_validated`.

The PA/PWC-X1 **boundary** is ratified ahead of all of it; only its carriage waits
for v2. P3A leads because it expands no source contract, so it ships against
`policy_pack.v1` without approaching a frozen digest.

### PA/PWC-X1 — Policy Authority boundary and source linkage

Policy Authority owns authoritative issuance, exact-version identity, lifecycle,
supersession, revocation, and resolution. This package consumes an exact resolved
authoritative artifact and transforms it deterministically. Compiled artifacts
retain immutable linkage to the authoritative source policy coordinate and digest.

This is new work on this side only — Policy Authority requires no change; it already
issues the complete coordinate, issuance record, resolution and revocation records.
Today `models/provenance.py` carries **document**-level provenance
(`ProvenanceReference` with `source_id`, `title`, `version`, `content_digest`,
`clause`, `authority_level`, plus `SourceDocument`), which identifies a document
rather than an authoritative issuance.

The linkage is carried as **data** — a PWC-owned `AuthoritativeSourceRef` of plain
strings, never an import of `packages/policy-authority`. It is digest-bound through
`policy_pack.v2` only: an unconditional or defaulted field on the v1 payload would
move every existing v1 digest, so v1 stays byte-identical and carries no such field.

The compiler attests **carriage, not authenticity**. It proves that a release is
immutably bound to the authoritative-source assertion supplied at compilation; it
never claims to have verified a signature, key trust, or revocation state. Those
belong to Policy Authority and to a composition root in the integration layer, which
derives the reference from a `RESOLVED` resolution rather than accepting one by
assertion.

The full field set, carriage rules, validation codes and composition-root
requirements are in
`Project_documentation/repository/docs/audits/policy_workflow_compiler_x1/DESIGN.md`.

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

### PWC-P3A governed diff-driven review — delivered

Review requirements are derived deterministically from the structural diff and the
pack's own declared `ApprovalPath`; a fail-closed gate verifies a ledger of reviewer
dispositions against one, and an unsatisfied requirement refuses compilation
(ruling P3A-1). The reviewer authority reference stays opaque (ruling P3A-2).

Every artifact is standalone — nothing is stored in the pack, in an approval record,
or in the release's logical payload — so `policy_pack.v1`, `workflow_ir.v1` and
`workflow_ir.v2` bytes are unchanged and existing approvals stay valid. See
`DIFF_DRIVEN_REVIEW.md` and the `diff_driven_review_implemented` gate.

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
