# Ugence Procurement Policy Compilation (`ugence-procurement-policy-compilation`)

The Procurement family's deterministic mapping from a resolved policy artifact to a
`policy_pack.v2` pack — the `PolicyPackBuilder` the PA/PWC-X1 composition root
requires and deliberately does not ship (ruling CR-2).

```text
Policy Authority     resolves and authenticates the artifact
composition root     derives the authoritative reference
THIS PACKAGE         maps the Procurement artifact to a structured pack
compiler             validates, compiles and binds
```

## Where it lives, and why (ruling CR-2a)

- **Not in the compiler** — a family-to-pack mapping is not compiler behaviour, and
  the compiler stays a leaf with no Policy Authority coupling.
- **Not in `packages/products/procurement`** — that would make the product depend on
  the compiler, inverting the direction the product boundary keeps.
- **Here, in the integration layer**, where components depending on two capabilities
  already live.

One runtime dependency: `ugence-policy-workflow-compiler`, through its public `api`
module. **No Policy Authority dependency** — this builder maps a typed artifact, not
a resolution.

## Nothing is invented

The parser is strict and total. An unknown key is a **refusal**, not something to
ignore: the projection is the policy's own statement of itself, and quietly dropping
part of it would compile a workflow that governs less than the policy says. A
missing required key is a refusal too, never a default.

Where the artifact is silent, the pack is silent. A policy that states no approval
roles gets no approval path; one that states no declared semantics gets no
`SemanticDeclaration`. Tests pin both directions.

## What it maps

| The artifact states | The pack gets |
| --- | --- |
| `approval_threshold` | a `DecisionRule` over the stated amount fact |
| `hard_limit` | a `HARD_LIMIT` `ActionConstraint` |
| `approval_roles` | ordered `ApprovalStep`s, an `ApprovalPath`, and segregation pairs between consecutive declared roles |
| `evidence_requirements` | `RequiredEvidence`, fail-closed on absence |
| `prohibited_facts` | `ProhibitedCondition`s |
| `declared_*` semantics | one `SemanticDeclaration` about the decision rule |

It never authors an `authoritative_source`: on the authoritative path that reference
is derived by the composition root from a verified resolution (ruling X1-B), and a
builder that supplied one would be refused.

## Determinism

Identical artifacts produce identical packs, byte for byte, including object ids —
so the same policy always yields the same pack digest, whatever order its projection
keys arrive in.
