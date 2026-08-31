# `ugence-agent-constitution-policy`

The **Agent Constitution** policy family, its adapter for the shared Ugence
Policy Authority, and the ratified registration-time family-collision guard.

## Why this exists

`OD-C2=A` ruled that an agent constitution is issued through the shared Policy
Authority as a new policy family, and the first-slice ratification
(`ACC-S1-BASE`, `ACC-S1-Q1`–`Q5`, `ACC-S1-IMPL=YES` —
`docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_FIRST_SLICE_RATIFICATION.md`)
fixed and authorized the design. Nothing in the tree could previously *issue* a
constitution for governed roles to be checked against.

This distribution is the family half of the ratified first slice: an issuable,
signable, digest-bound statement of the structural bounds a governed role's
declared vocabulary sets must stay within.

## Status — what this distribution does and does not make true

It makes an agent constitution **issuable**. It does **not** make constitution
conformance verifiable end to end: a family that can be issued still needs the
conformance distribution's concrete resolver and structural verifier, which ship
separately as their own change set (`ACC-S1-Q2`), and first release additionally
awaits the separately balloted `OD-C1=B` contract-amendment round. Until those
land, nothing here should be read as saying otherwise.

## What it is

An `AgentConstitutionPolicy` carries:

| Field | What it states |
|---|---|
| `metadata` | This family's own identity envelope: id, version, content digest, scope, tenant, lifecycle label, effective interval |
| `agent_constitution_ref` | **The reference this constitution asserts it is named by.** Signed, so the reference-to-constitution binding is not merely deployment configuration; the amendment round is its consumer |
| `governed_role_refs` | The roles this constitution claims to govern — references only, non-empty, duplicate-free, in ascending codepoint order |
| `permitted_candidate_dispositions_bound` | The maximal candidate-disposition set a governed role may declare — every member the exact string value of an imported `CandidateDisposition` member |
| `permitted_review_actions_bound` | The maximal review-action set — every member the exact string value of an imported `ReviewAction` member |
| `permitted_tool_scopes_bound` | The maximal tool-scope set — an **open** C5b `Token` vocabulary, bounded not enumerated, and the one bound that may be empty |
| `constitution_vocabulary_version` | The clause vocabulary the bounds are drawn from, a value fixed by owner ruling |

It is issued, signed, registered, resolved and revoked entirely by the shared
Policy Authority. This package adds an artifact, a `PolicyFamilyAdapter`, and
the registration helpers — nothing else.

It is the authority's **fourth** policy family and the **third** registered from
*outside* the authority's own distribution. `tests/test_authority_registration.py`
exercises that across a real package boundary, driving genuine issuance, real
Ed25519 signing, the real registry and real resolution — nothing is stubbed,
because an adapter proven against a stub core proves nothing about the authority
it registers with.

## The registration-time family-collision guard (`ACC-S1-Q3`)

The authority's core refuses a duplicate `adapter_id` and nothing more: two
adapters under distinct ids claiming one `policy_family` value would pass
registration and collide only coordinate-by-coordinate, after issuance. Ruled
`ACC-S1-Q3=A`, this family ships the stronger guard at its own boundary:

```python
from ugence_agent_constitution_policy import register_agent_constitution_policy_family

adapters = register_agent_constitution_policy_family(existing_registry)
```

The helper appends the adapter and asserts, over the assembled registry, that
exactly one adapter answers for this family's ratified value — on both routing
seams, `recognizes` and `coordinate_for` — and that no other registered adapter
advertises the value. `tests/test_family_collision_guard.py` proves both
directions, and pins the ratified family value and adapter id against the
repository's real registered constants, imported never copied. A core-level
uniqueness guard for all families remains a raised Policy Authority milestone,
not built and not claimed.

## The bounds

Each closed bound is non-empty, duplicate-free and stored in **ascending
codepoint order** — an unsorted tuple is *refused*, never silently reordered, so
the artifact a reader sees is the artifact its author wrote. The two closed
vocabularies are **imported** from `ugence-agentic-proposer` as the single
source of truth; tests assert set equality in both directions, so no fork is
possible, because there is no second spelling here to fork from. A constitution
that governs no role, or whose closed bound names nothing, is not issuable.

## What is deliberately absent

No resolution, no conformance verification, no role-facts input type and no
composition with a resolver — the `ACC-S1-Q2` conformance distribution owns all
of that. No role lifecycle authority of any kind (`OD-C4=A`): governed roles are
referenced, never minted, changed or ended. No operational disposition for a
structural failure (`OD-C3=B`): that owner remains deliberately unassigned. No
compute, tools, evidence access or consequential execution: a bound is a ceiling
on declarations and grants nothing. No strategy-permission content: that family
owns it. No amendment content: the `OD-C1=B` round is separately balloted. None
may be added without a new ruling.

## Boundaries, measured rather than asserted

- The Policy Authority is reached through its public `api` module only.
- No module reads a clock, opens a socket, touches storage or loads a plugin,
  and none reimplements canonicalization, hashing or signing.
- No error name or message template carries a reserved authority term, a
  terminal-outcome value or a candidate-disposition value, under the same
  uppercased-substring rule the Agentic Proposer's own guard applies.
- `public_api.json` is the curated surface, asserted by `tests/test_public_api.py`
  including dataclass field order and the exact value of every string constant.
