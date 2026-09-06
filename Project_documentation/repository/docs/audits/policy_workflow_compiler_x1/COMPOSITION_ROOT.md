# X1 Composition Root — Design and Rulings

**Status:** ruled and implemented as
`packages/integration/authoritative-policy-compilation`.
**Scope:** the component that turns a `RESOLVED` Policy Authority resolution into a
compiled release. Ratified placement is X1-B
(`../policy_workflow_compiler_ratification/RATIFICATION.md`).

Findings carry `[V]` verified, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

## Why the root exists

The compiler attests **carriage, not authenticity**: it can carry an
`AuthoritativeSourceRef` faithfully, but it cannot tell a derived one from an
asserted one. The root closes exactly that gap and owns nothing else.

```text
Policy Authority   authenticates the policy
composition root   derives the reference from a verified resolution
compiler           binds it immutably into the release
```

## Placement and dependency direction

`[V]` The precedent is exact. `packages/integration/agent-constitution-activation`
describes itself as "the composition root … Orchestration, not authority: every
issuance, resolution or revocation act is the Policy Authority's, under trust the
operator injects already constructed", depends on `ugence-policy-authority` reached
"through its public `api` module ONLY", and carries no third-party runtime
dependency. This package copies that structure rather than inventing one.

```text
packages/policy-authority            ▲
                                     │
packages/integration/                │ depends on both public api modules
  authoritative-policy-compilation   │
                                     ▼
packages/tooling/policy-workflow-compiler
```

Never `compiler -> Policy Authority`, never the reverse. `[V]` The compiler gains no
dependency; its own boundary test still fails if `ugence_policy_authority` appears
anywhere in its source.

## Ruling CR-1 — human approval

**The root compiles with `require_approval=False` and returns the constructed pack
for approval. It never accepts or brokers an approval.**

The compiler requires a `HumanApprovalRecord` bound to the pack's structural digest,
and the pack is built *inside* the root — so its digest is not knowable until
construction completes. The two candidate shapes were an approval callback invoked
mid-flow, or a two-phase flow.

Two-phase wins because approval authority must not pass through an orchestrator. A
callback would put the root on the path between a reviewer and the artifact they
approve, which is precisely the seam the no-self-approval rule protects. The root
therefore returns an `AuthoritativeCompilationDraft` carrying the pack, its digest
and the derived reference; a human approves that digest by the existing mechanism,
and the caller compiles with the approval in hand.

`[I]` This also keeps the root free of approval flow entirely, so it can never be
mistaken for an approval authority.

## Ruling CR-2 — how a resolved artifact becomes a `policy_pack.v2`

**The mapping is family-specific and is injected, never invented by the root.**

The root accepts a `PolicyPackBuilder` — a callable taking the resolved artifact and
returning a structured `policy_pack.v2` pack. It ships no builder of its own and
refuses to proceed without one (`NO_PACK_BUILDER`).

`[G]` No such mapping exists in the repository today. A policy family knows how its
own artifact becomes structured policy; the root does not, and a generic mapping
would be exactly the kind of inference this architecture refuses everywhere else.
Each family supplies its own builder, tested against its own artifacts.

`[I]` The consequence is honest: the root is complete and usable, and it cannot
compile anything until a family provides a builder. That is a real dependency, not a
missing feature.

## The service flow

`AuthoritativePolicyCompilationService.draft_from_coordinate(...)`, taking trust
**already constructed** by the operator — registry, signature verifier, adapter
registry, optional approval verifier, historical rule — exactly as `resolve_policy`
requires. The root never builds a key, verifier or registry.

```text
1. receive a PolicyCoordinate + as_of + a PolicyPackBuilder
2. resolve through Policy Authority under the injected trust
3. require status == RESOLVED
4. require the requested coordinate == the resolved coordinate
5. require the resolution descriptor triple complete
6. re-verify framed_body_digest(triple) == record.policy_body_digest
7. build policy_pack.v2 through the injected builder
8. DERIVE AuthoritativeSourceRef from the resolution — never from a caller
9. return a draft: pack, pack digest, derived reference
   (the caller obtains human approval, then compiles)
```

`[V]` Step 6 is possible because Policy Authority publishes `framed_body_digest`,
`canonical_bytes` and `sha256_hex` in its public `api`, and `PolicyResolution`
publishes its descriptor triple all-or-none precisely so "a consumer that holds no
adapter registry can nonetheless recompute … and compare it against
`record.policy_body_digest`". The root uses Policy Authority's own function — there
is no second canonicalization to drift.

## The typed refusals

| Refusal | Raised when |
| --- | --- |
| `POLICY_NOT_RESOLVED` | The resolution status is anything but `RESOLVED`, carrying Policy Authority's own reason |
| `RESOLVED_COORDINATE_MISMATCH` | The resolved coordinate is not the one requested |
| `INCOMPLETE_RESOLUTION_DESCRIPTOR` | The descriptor triple is absent or partial, so the body digest cannot be re-verified |
| `BODY_DIGEST_MISMATCH` | The recomputed framed body digest does not equal the record's |
| `HISTORICAL_RESOLUTION_NOT_REQUESTED` | The answer is historical but the caller asked for current governance |
| `AUTHORED_SOURCE_REFUSED` | The supplied pack already carries an `authoritative_source` |
| `NO_PACK_BUILDER` | No family builder was supplied (ruling CR-2) |

`[I]` `HISTORICAL_RESOLUTION_NOT_REQUESTED` matters more than it reads. Policy
Authority marks a historical answer explicitly and states it "never implies current
validity"; without this check a careless `as_of` would yield a release built from a
superseded issuance and nothing downstream would notice.

## Enforcing the derivation prohibition

1. **No parameter accepts a reference.** The entry point takes a coordinate.
2. **One construction site.** `AuthoritativeSourceRef(...)` is built only inside
   `_derive_source_ref(resolution)`, from the resolution's own record and coordinate.
3. **An AST test proves it.** `[V]` The precedent already uses this technique — its
   import-boundary suite walks the AST to prove the package "could not build one if
   asked". Here the test asserts exactly one instantiation node, inside that
   function, and that a pack arriving with an `authoritative_source` is refused
   rather than forwarded.

`[I]` Mechanism 3 is what makes the rule durable: 1 and 2 are conventions a later
edit could relax quietly; the AST test fails the suite.

## Maturity

| Gate | Value |
| --- | --- |
| `composition_root_implemented` | `true` |
| `derived_source_reference_implemented` | `true` |
| `body_digest_reverification_implemented` | `true` |
| `authored_source_reference_accepted` | `false` — permanently |
| `issues_policy` / `revokes_policy` / `grants_approval` | `false` — the root owns no authority |
| `policy_pack_builder_shipped` | `false` — families supply their own (CR-2) |
| `runtime_execution_implemented` | `false` |
| `pilot_validated` / `production_certified` | `false` |

## What the root does not own

It cannot change Policy Authority's answer and cannot waive compiler validation: the
caller's compile runs the approval, review and X1 carriage gates unchanged. It
issues nothing, revokes nothing, approves nothing, and holds no key material.
