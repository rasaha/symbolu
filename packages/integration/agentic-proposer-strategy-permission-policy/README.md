# `ugence-agentic-proposer-strategy-permission-policy`

The Agentic Proposer **strategy-permission** policy family, and its adapter for
the shared Ugence Policy Authority.

## Why this exists

Reasoning Strategy Permission was ratified with a resolver protocol, a request
and a response shape, and a six-check replay — and with **no policy family for a
resolver to resolve against.** The Agentic Proposer owns the boundary and issues
no policy; the Policy Authority issues policy and knows no strategy vocabulary.
Nothing in the tree could be *issued* and then *permitted against*.

This distribution is the artifact half of the missing piece: an issuable,
signable, digest-bound statement of which reasoning strategies a role may
declare.

## Status — what this distribution does and does not make true

It makes a strategy permission **issuable**. It does **not** make Reasoning
Strategy Permission executable: a family that can be issued still needs a
concrete resolver before anything runs end to end, and that resolver is a
separate distribution. Until it lands, the capability still cannot execute end to
end, and nothing here should be read as saying otherwise.

## What it is

A `StrategyPermissionPolicy` carries:

| Field | What it states |
|---|---|
| `metadata` | This family's own identity envelope: id, version, content digest, scope, tenant, lifecycle label, effective interval |
| `strategy_policy_ref` | **The reference this policy asserts it answers to.** Signed, so the reference-to-policy binding is not merely deployment configuration |
| `permitted_strategies` | The strategies the role may declare — non-empty, duplicate-free, in ascending codepoint order |
| `vocabulary_version` | The vocabulary those strategies are drawn from, a value fixed by owner ruling |

It is issued, signed, registered, resolved and revoked entirely by the shared
Policy Authority. This package adds an artifact and a `PolicyFamilyAdapter`, and
nothing else.

It is the authority's **third** policy family and the **second** registered from
*outside* the authority's own distribution. `tests/test_authority_registration.py`
exercises that across a real package boundary, driving genuine issuance, real
Ed25519 signing, the real registry and real resolution — nothing is stubbed,
because an adapter proven against a stub core proves nothing about the authority
it registers with.

## The permitted set

Non-empty, free of duplicates, and stored in **ascending codepoint order** — an
unsorted tuple is *refused*, never silently reordered, so the artifact a reader
sees is the artifact its author wrote. Every element is the exact string value of
a member of `ReasoningStrategy`, which is **imported** from
`ugence-agentic-proposer` as the single source of truth. A test asserts set
equality between this family's accepted tokens and `set(ReasoningStrategy)`: no
fork is possible, because there is no second spelling here to fork from.

A policy that permits nothing is not issuable. That state stays representable at
the resolver-response boundary, where the ratified replay reports it; it is
simply not something this family issues.

## Identity, not configuration

`adapter_id`, `policy_family`, `policy_type` and `vocabulary_version` are each
framed into a body digest, a coordinate, or both. Moving one moves every issued
policy's digest, which is the point. `vocabulary_version` is
`ugence.agentic-proposer.reasoning-strategy/v1`, a value **fixed by owner
ruling**: changing it later is a new policy version, not an edit.

`policy_id` and `version` are additionally checked against the Agentic Proposer's
C5b `Token` grammar at construction. Without that check a policy could be
lawfully issued, signed and resolved and then be unusable, because those values
are stamped straight onto the advisory.

## What it deliberately does not do

| Not done | Why |
|---|---|
| Resolve anything | Resolution belongs to the authority, and the concrete resolver is a separate distribution. This package holds no registry, no reference mapping and no resolver. |
| Sign anything | Issuance and signing belong to the authority. An import-boundary test refuses signing calls and key material in shipped source. |
| Compel, order or compose strategies | The permitted set is a permission, never an instruction. Composition, ordering and required strategies are ungranted. |
| Name a compute budget, quota, token count, capability tier or provider | Permission grants no compute and no consequential execution authority. |
| Carry a role identity | Permission is role-level and the role *references* this policy; a role list inside it would invert the ratified direction. |
| Map a permission failure to an operational outcome | Which component does that is deliberately unruled, and nothing here names one. |
| Read a clock, open a socket, touch storage or load a plugin | A declarative artifact has no present tense; every instant is a caller's. |

## What a resolution of this family proves

Under the trust roots the call was configured with, and at an explicit `as_of`:
the artifact was signed by an authorized, entitled, un-revoked key over exactly
this canonical body; external approval evidence verified; the lifecycle and
effective period admit it; and no verified revocation applies.

It proves **nothing** about whether the permitted set is wise, correct, lawful or
commercially sound. It establishes nothing about a model's private reasoning. It
does not prove that any producer executed any declared procedure. And it
**authorizes no runtime action** — consequential execution remains with Risk
Authority, ActionGate and Decision Authority.

Digest membership proves integrity after construction, never provenance.

## Dependencies

Two first-party dependencies and no third-party runtime dependency of its own:

- `ugence-policy-authority`, reached through its **public `api` module only**;
  every `...core` / `...adapters` module is internal, and a repository-wide scan
  in the authority's own suite enforces that.
- `ugence-agentic-proposer`, for `ReasoningStrategy` **alone**. The direction is
  one-way: the Agentic Proposer imports nothing new, and its own suite bars it
  from importing the authority at all.

The adapter cannot live inside the authority: every module under
`ugence_policy_authority` may import only the standard library, itself and one
contracts leaf, and this family imports the proposer's vocabulary. Registering
from outside is the authority's ratified additive path anyway.

## Wiring

Registration is the composition root's job:

```python
from ugence_policy_authority.api import AdapterRegistry
from ugence_agentic_proposer_strategy_permission_policy import (
    StrategyPermissionPolicyFamilyAdapter,
)

adapters = AdapterRegistry([StrategyPermissionPolicyFamilyAdapter(), *existing])
```

Approval remains external. The authority ships only a deny-by-default approval
verifier, so an incompletely configured deployment cannot issue this family's
policy at all — the failure mode is a refusal, never an unapproved issuance.

## Tests

```
python -m pytest packages/integration/agentic-proposer-strategy-permission-policy/tests -q
```

- `test_artifact.py` — construction rules, fail-closed on every one.
- `test_vocabulary_binding.py` — one vocabulary, one source of truth; and a
  lawfully issued policy's identity is stampable on the advisory.
- `test_authority_registration.py` — genuine issuance, signing, registry and
  resolution across a real package boundary.
- `test_import_boundary.py` — what this distribution may import, measured.
- `test_no_authority_claimed.py` — no compute claim, no lifecycle authority, and
  no reserved authority term in any name or message, under the same
  uppercased-substring rule the Agentic Proposer's own guard applies.
- `test_public_api.py` — the shipped snapshot equals the actual surface.

## Distribution verification

```
python packages/integration/agentic-proposer-strategy-permission-policy/verify_agentic_proposer_strategy_permission_policy_distribution.py
```

Builds the wheel, installs it into a clean venv with no monorepo path, and there
proves that the artifact constructs and binds its own digest, that every
construction rule fires, that the accepted token set still equals
`set(ReasoningStrategy)` from the *installed* proposer distribution, and that the
family issues and resolves through the real shared authority while a body swap
under the same coordinate fails closed.
