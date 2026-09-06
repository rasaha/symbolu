# Policy Workflow Compiler — Owner Ratification of D1–D5 and PA/PWC-X1

**Status:** ratified by the repository owner.
**Scope:** `packages/tooling/policy-workflow-compiler` at product 0.2.0, plus one
cross-package boundary ruling binding Policy Authority and the compiler.
**Supersedes:** the pending-decision language in the package's `MATURITY.md`,
`NEXT_PHASES.md` and `KNOWN_LIMITATIONS.md`.

This document records decisions. It authorizes no implementation by itself; each
ratified phase is built and reviewed on its own merits.

Findings carry `[V]` verified against the repository, `[I]` inferred, `[R]` requires
ratification, `[G]` gap.

## Ratified rulings

| Decision | Ruling |
| --- | --- |
| **D1** | All three next-phase strands approved, **sequentially**: diff-driven review (P3A) → declarative capability/contract binding validation (P3B) → deterministic offline simulation (P3C). No provider imports, runtime calls, authority, credentials or side effects inside the compiler at any strand. |
| **D2** | Approve an additive `policy_pack.v2`: explicit data-classification, permission-intent, required-tool and typed contract/version declarations. The compiler preserves declared semantics and never infers absent values. `policy_pack.v1` remains supported and existing v1 digests remain byte-identical. |
| **D3** | AI Hiring second-domain reference equivalence is required before `pilot_validated=true`, and **not** before P3 development begins. |
| **D4** | Pilot and production certification evidence gates are defined now (below). Both must be earned by recorded evidence, never flipped administratively. |
| **D5** | `awc_adapter_updated` is **deprecated**, not removed: it must not be used to represent platform state. It stays `false` through the 0.2.x line for compatibility and is removed only at the next compatibility-controlled version. |
| **PA/PWC-X1** | Policy Authority establishes authoritative policy identity, lifecycle, supersession, revocation and resolution. The compiler consumes an exact resolved authoritative artifact, transforms it deterministically, and retains immutable linkage to the source policy coordinate and digest. Neither establishes the other's authority. |

## D1 — Three strands, sequenced, with a hard boundary

**Ruling.** The compiler may emit and validate **declarative** capability-binding
requirements. It may not instantiate, import or invoke runtime providers. Actual
provider resolution belongs to a composition root, a simulator, or a consuming
product.

**Why this wording rather than "capability-adapter binding".** The strand as
originally described in `NEXT_PHASES.md` — binding a node's `owning_capability` to a
concrete canonical implementation — would have introduced provider imports. `[V]`
The package's scoped CI enforces the opposite: the `import-boundary-suite` job in
`.github/workflows/policy-workflow-compiler-p2-ci.yml` fails if any `semantics/`
module imports a downstream package. `[V]` `compiler/capability_registry.py` resolves
capability targets from metadata alone and documents that core compilation "never
imports a runtime provider to emit an IR". The ruling preserves that invariant while
keeping the strand's governance value.

**Scope correction for P3B — validation, not emission.** `[V]` The v2 contract
already emits declarative capability binding: `CapabilityRequirement`
(`capability_id`, `requirement_level`, `source`, `resolution`, `authority_context`,
`provenance`) and `DataContractRef` (`contract_id`, `contract_data_version`,
`schema_ref`, `data_classification_ref`) in `semantics/models.py`. `[V]` Release
validation currently checks only that capability requirements are not duplicated
(`validation/release_validator.py`). P3B's genuine delta is therefore **conformance
validation** of already-emitted requirements against registry metadata — authority
disposition compatibility, advisory-versus-authoritative misuse, optionality,
minimum version, unresolved or unknown capability references — not a second
emission path. Defining P3B as emission would re-specify shipped capability.

**Scope note for P3A.** `[V]` Two of its inputs already exist: the structural diff
emits `approval_re_review_required` (`diff/change_impact.py`), and the approval gate
already rejects an approval whose `policy_pack_digest` does not match the pack
(`approval/service.py`). P3A is the governed **workflow** around those signals —
routing, reviewer assignment, re-binding on change — not their invention.

**Boundary that survives all three strands.** P3C simulates; it does not execute.
No runtime authority, no side effects, no credentials, no network. `[V]`
`runtime_deployment_implemented` and `runtime_execution_implemented` stay `false`
through P3C.

## D2 — `policy_pack.v2`, ratified on policy-semantics grounds

**Ruling.** Introduce additive `policy_pack.v2` support permitting explicit
declaration of data-classification references, permission intents, required tools,
and versioned contract references. The compiler preserves declared semantics and
must never infer absent values.

**Rationale, corrected.** These fields are ratified because they are **policy
semantics** — "this workflow may access customer PII", "this node requires write
permission", "this action requires Salesforce", "this contract must be version 3"
are governance facts that the compiler should preserve whenever the source policy
declares them. Their value does not depend on which compiler phase happens to
consume them. The earlier analysis made consumption the criterion; that was the
wrong test and is not the ratified basis.

**Compatibility, verified.** `[V]` `SUPPORTED_SCHEMA_VERSIONS` is a one-element
tuple and `validation/provenance.py::check_schema_version` fails closed on anything
else, so v2 requires an explicit, reviewable widening. `[V]` `schema_version`
participates in the release logical digest through `_pack_logical`
(`compiler/release.py`), so a pack declaring v2 receives a new digest while every
existing v1 pack stays byte-identical. The extension is additive-safe by
construction.

**Standing constraint.** `[V]` The P2 rule that no value is fabricated (derivation
classes `EXPLICIT` … `UNRESOLVED`, never invented) carries into v2 unchanged. A
`policy_pack.v2` slot left undeclared stays unresolved; it is never defaulted into a
governance claim.

## D3 — Second-domain equivalence gates the pilot, not the phase

**Ruling.** Procurement **and** AI Hiring reference equivalence are mandatory before
`pilot_validated=true`. Neither blocks P3 development.

**Evidence.** `[V]` The current gate is `EQUIVALENT` across 5 dimensions and 28
checks against exactly one product, `ugence-procurement`. `[V]` `packages/products/
ai-hiring` is a real packaged product (`ugence-ai-hiring`, distribution 0.1.1,
product 0.6.0, `PACKAGE_READY_FOR_CONTROLLED_PILOT`, `production_certified=False`).
`[I]` It is a strong second domain precisely because its governance shape differs:
advisory-AI versus binding-human-decision separation, rather than Procurement's
threshold-and-limit authorization path. Agreement across two differently shaped
domains is meaningful evidence of generality; agreement within one is not.

**Limit on the claim.** Equivalence is measured against a reference product's
modeled behavior. It is not, and must not be reported as, a certification of either
product.

## D4 — Earnable evidence gates

**Ruling.** Both gates are earned by recorded evidence and never flipped
administratively.

### `pilot_validated=true` requires all of

1. Procurement reference equivalence `[V]` — already achieved.
2. AI Hiring reference equivalence `[G]` — not yet built.
3. One named **real pilot policy corpus** (an internal design-partner corpus
   qualifies; formal tenancy modeling is not a precondition) `[G]`.
4. The source policy passed a legitimate human approval `[G]` for the pilot corpus;
   the mechanism exists `[V]` (`approval/service.py`, no compiler self-approval).
5. The exact source artifact and its digest retained `[G]` — see PA/PWC-X1.
6. Deterministic compilation `[V]` — verified, with pinned v1 and v2 digests.
7. Diff-driven re-review demonstrated end to end `[G]` — the signal exists `[V]`,
   the governed workflow is P3A.
8. Approval bound to the exact changed pack `[V]` — digest binding is implemented;
   demonstration on the pilot corpus is outstanding.
9. No critical unresolved semantics in the compiled corpus `[G]`.
10. Assurance package generated `[V]` — implemented with a fail-closed coverage
    invariant.
11. Replay evidence retained `[V]` — `deterministic_replay_verified=true`.

### `production_certified=true` requires

`pilot_validated`, plus distribution integrity, upgrade compatibility, a security
review, an authority-boundary review, demonstrated fail-closed behavior, release
provenance, operational recovery and replay, supported contract migration, and a
formal production certification record. `[R]` Each of these needs its own acceptance
definition before it can be assessed; this ruling names the set, not the thresholds.

**Standing:** the compiler remains tooling. It does not need to become a runtime
package to be production-certified.

## D5 — Deprecate, keep, remove later

**Ruling.** `awc_adapter_updated` is deprecated as a cross-package maturity flag and
must not be used to represent platform state. It remains `false` for compatibility
through the current 0.2.x line and is removed only at the next
compatibility-controlled version.

**Why not remove now.** `[V]` The flag is read in four places, all internal to the
package: `version.py`, the distribution verifier's version assertion, one test, and
the P2 CI maturity block. No external consumer exists. But `version_info().to_dict()`
is a published contract, and removing a key from it is a contract change requiring a
version bump. Spending one to delete a single stale field is not warranted while the
documented deprecation carries the same information. `[V]` The ambiguity is already
recorded in the package's `MATURITY.md`.

## PA/PWC-X1 — Policy Authority and compiler boundary

**Ruling.** Policy Authority owns authoritative issuance, exact-version identity,
lifecycle, supersession, revocation and resolution of structured policy artifacts.
The compiler consumes an exact authoritative policy artifact and deterministically
transforms it into Workflow IR and assurance artifacts. The compiler does not
establish policy authority; Policy Authority does not compile workflow semantics.
Compiled artifacts retain immutable linkage to the authoritative source policy
coordinate and digest.

**This is new work, not a restatement.** `[V]` `packages/policy-authority` exists.
`[V]` The compiler's `models/provenance.py` carries document-level provenance —
`ProvenanceReference` with `source_id`, `title`, `version`, `content_digest`,
`clause`, `authority_level`, and `SourceDocument` — which identifies a *document*,
not an *authoritative issuance*. `[G]` There is no field binding a compiled release
to an issued policy version, its registration or signature reference, or its
revocation state. Satisfying X1 requires adding that coordinate.

**Implementation constraint.** `[V]` The compiler currently declares no dependency
on `packages/policy-authority`, and D1's boundary forbids adding one. The linkage
must therefore be carried as **data** in the pack and compiled release — an exact
policy coordinate plus digest, validated structurally — never as an import or a
resolution call. Resolution and revocation checking belong to the consumer or
composition root.

**Target chain.** Author → structured `policy_pack.v2` → approval workflow /
legitimate approver → Policy Authority (signed, registered, exact version) →
compiler → Workflow IR → AWC / Agent Runtime / governance.

## Ratified implementation order

**Amended** after the X1 design established that source linkage cannot be
digest-bound on `policy_pack.v1` without moving every frozen v1 digest. X1 is
ratified first as an *architectural rule*; its carriage ships with `policy_pack.v2`.
See `../policy_workflow_compiler_x1/DESIGN.md`.

1. **PWC ratifications** — D1–D5 and the X1 architectural boundary (this document).
2. **PWC-P3A** — diff-driven review requirements and approval binding. It expands no
   source contract, so it ships against v1 without approaching a frozen digest.
3. **`policy_pack.v2`** — source-declarable semantic fields; the first
   source-contract expansion.
4. **PA/PWC-X1 carriage and validation** — activated by v2.
5. **PWC-P3B** — declarative capability/contract binding **validation**.
6. **PWC-P3C** — deterministic offline simulation.
7. **AI Hiring reference equivalence.**
8. **Real pilot** against a named policy corpus.
9. **`pilot_validated`** — only when every D4 item is evidenced.

### X1-A — the sequencing ruling

PA/PWC-X1 is ratified now as an architectural boundary. Its digest-bound
`AuthoritativeSourceRef` carriage activates **only** for `policy_pack.v2`.
`policy_pack.v1` remains structurally and digest-byte identical and gains no
unconditional or defaulted authoritative-source field — a defaulted `None` on the v1
logical payload is explicitly prohibited, because it moves every existing v1 digest.

### X1-B — composition-root placement

The component that turns a `RESOLVED` `PolicyResolution` into a compiled release
lives in **neither** Policy Authority **nor** the compiler, and not in the Governance
Studio (which is `NON_AUTHORITY_STUDIO` by its own audit). It belongs in the
deployment/product integration layer, which may depend on both packages —
`packages/integration/agent-constitution-activation` is the existing precedent. It
owns no new authority: it cannot change Policy Authority's answer and cannot waive
compiler validation.

**Derivation prohibition.** Neither the compiler nor an untrusted caller may
construct a production-trusted `AuthoritativeSourceRef` by assertion alone.
Production authoritative-source linkage must originate from a successfully verified
Policy Authority resolution through the designated composition root; on that path the
reference is derived, never authored.

**Attestation boundary.** The compiler attests **carriage, not authenticity**: it
proves a release is immutably bound to the authoritative-source assertion supplied at
compilation, and never that the policy was independently established as currently
authoritative. Its diagnostics must not imply a signature, key-trust or revocation
check it did not perform.

The governing principle: the compiler becomes richer as a deterministic policy
compiler and pre-execution analyzer. It does not gradually become a runtime
orchestrator. That is what keeps Policy Authority, the compiler, AWC, the
decision and risk authorities, and the execution stack cleanly separated.

## PWC-P3A rulings

| Ruling | Decision |
| --- | --- |
| **P3A-1** | `REVIEW_ENFORCEMENT = BLOCKING`. An unsatisfied `ReviewRequirement` refuses compilation with a typed refusal when an approval-sensitive change has a declared covering `ApprovalPath`. No minor-change exemption, no approval carry-forward. With no covering path, refuse `NO_APPROVAL_PATH_FOR_CHANGE`; never default a reviewer. |
| **P3A-2** | `REVIEWER_IDENTITY = OPAQUE_REFERENCE`. `reviewer_authority_reference` stays an uninterpreted binding reference. P3A does not import or resolve `authority-directory`; identity resolution needs a separate ruling. |

The **non-weakening invariant** is ratified with them: P3A never makes an approval
valid that the existing approval gate would reject. The gates compose as AND — a
satisfied review cannot rescue a failed approval, and a valid approval cannot excuse
an unsatisfied review. Design: `../policy_workflow_compiler_p3a/DESIGN.md`.

## `policy_pack.v2` rulings

| Ruling | Decision |
| --- | --- |
| **V2-A** | The shared canonical-pack-view extraction is **its own prior commit**, with digests pinned, so a refactor that could silently invalidate every approval is reviewable apart from the schema change. **Delivered**: `models/pack_view.py::canonical_pack_view`, with both the release payload and the approval digest delegating to it. |
| **V2-B** | *Open.* Whether `SemanticDeclaration` becomes a `PolicyObject` in `APPROVAL_SENSITIVE_OBJECT_TYPES`. Recommendation: yes — a changed data classification should route to P3A review. |

Design: `../policy_workflow_compiler_pack_v2/DESIGN.md`.

## What this ratification does not authorize

- No change to `workflow_ir.v1` or `workflow_ir.v2` canonical output. `[V]` Pinned:
  v1 release `sha256:fb9fd4b9…`, v1 IR `sha256:169ad24c…`, v2 fingerprint
  `sha256:2e031c78…`.
- No provider import, runtime call, credential, network access or side effect in the
  compiler, at any ratified strand.
- No maturity boolean flipped by this document. `pilot_validated` and
  `production_certified` stay `false` until their D4 evidence exists.
- No removal of `awc_adapter_updated` before the next compatibility-controlled
  version.
