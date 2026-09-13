# ugence-change-effect-policy

**Contracts only. Inert by construction, and not an authorization.** The change-effect
classification policy family and the adapter that registers it with the shared Policy
Authority. The artifact has three members — the protected-registry list, the delegation
table, and a typed coordinate naming a separately governed `ClosureBundleMapping` — and
they version and digest **together**. Scoped by
`docs/architecture/ADR_UGENCE_CHANGE_EFFECT_CLASSIFIER_SCOPING.md` (CEC-2 as amended
2026-09-13, ADR §11) and
`docs/architecture/STAGE1_CHANGE_EFFECT_CLASSIFIER_CONTRACTS_SCOPING.md` (item 3.2),
against GERL target classification version 4.2.10 and its recorded erratum.

> This package holds a policy artifact's shape. It **never** classifies, routes,
> projects an effect, computes or verifies a closure, admits anything, resolves policy,
> resolves itself, signs, grants, reads or writes governed memory, or registers itself
> anywhere. A policy artifact is not a permission.

## The three members, and the one thing that is not here

| Member | In Stage 1 | Governed by |
|---|---|---|
| Protected-registry list | Seven registries, each with a prose admission rule | This artifact |
| Delegation table | **Empty.** A non-empty one is refused at construction | This artifact |
| Mapping coordinate | A complete `PolicyCoordinate`, or absent | This artifact |
| Mapping **content** | **Absent — separately governed, deferred out of Stage 1** | A separate object |

The last row is the distinction the owner's ruling 8 required the documents to draw, and
this package holds it structurally. The coordinate is a *reference*. No obligation-to-effect
rule, required-primitive table or executable predicate is defined, embedded or activated
here, and no D1, D3, D4 or D5 semantics or parameters. The artifact's digest covering a
coordinate says **nothing** about whether the mapping that coordinate names is sound or
ratified.

## What "atomically versioned" means here

A property of the projection, not a promise in prose. `_canonical_projection` projects the
whole artifact and removes **exactly one declared path**, `metadata.content_digest`. All
three members are therefore inside the digested body, so changing any one of them changes
the body digest, and a changed digest is a different artifact version.

## Two structural refusals

* **A sentinel, placeholder or fabricated mapping coordinate is refused.** A coordinate
  that names nothing real is worse than an absent one: absence is visible and blocks
  operation, while a placeholder would pass every check that merely tests presence.
* **An artifact with no valid mapping coordinate cannot be operative** (ruling 6). It
  cannot carry an operative lifecycle state and supports no `COMPLETED` closure. Absence
  is lawful in the initial shipped artifact; what it forecloses is operation, not
  existence.

## Inertness condition, not invented behaviour

Ruling 7: the absence of mapping content creates **no** new GERL routing outcome and **no**
new refusal code in Stage 1, because Stage 1 has no classifier, closure verifier, resolver
consumer, admission boundary or executor. What this package raises are construction-time
type refusals inside a contract package. Reading them as runtime governance results would
be inventing behaviour for a stage that executes nothing.

## Dependencies

One first-party dependency: `ugence-policy-authority`, through its public `api` module
only, for `PolicyCoordinate`, `PolicyArtifactDescriptor` and the canonicalizer. Ruling 3's
"stop and report the exact missing contract" branch did not fire: the repository's existing
`PolicyCoordinate` carries `policy_family`, `policy_id`, `version`, `content_digest`,
`scope` and `tenant_id`, so no reduced ad-hoc reference was created.

There is deliberately **no** dependency on `ugence-change-effect-records`, on
`ugence-control-plane-root`, or on any classifier, resolver, executor, admission boundary
or governed-memory implementation — none of which exists.

## Status

`MATURITY = "REFERENCE_GRADE_CONTRACT_ONLY"`, `ENFORCEMENT_ENABLED = False`. Stage 1
registers this adapter nowhere; wiring is a composition root's act, and no composition root
performs it. Progress beyond Stage 1 remains unauthorized.

## Tests

```
UGENCE_REPO_ROOT=$(git rev-parse --show-toplevel) python -m pytest packages/integration/change-effect-policy/tests -q
```

Regenerate the curated-surface manifest after a deliberate `__all__` change:

```
python packages/integration/change-effect-policy/scripts/generate_public_api.py
```
