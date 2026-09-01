# Changelog — `ugence-agent-constitution-policy`

## 0.2.0 — the family declares what it supersedes (the `ACC-SU` round)

The change set authorized as `ACC-SU-IA-5` (see
`docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_FAMILY_SUPERSESSION_IMPLEMENTATION_AUTHORITY.md`,
over the `ACC-SU-BASE`/`ACC-SU-1`..`ACC-SU-5` ratification). Additive: one new
optional field, nothing removed, **no existing digest moved**.

Policy Authority `0.2.0` shipped structured supersession, but no adapter
produced the descriptor's `supersedes_coordinate`, so no constitution could
lawfully declare a predecessor. This closes that.

### Added

- **`AgentConstitutionPolicyMetadata.supersedes_coordinate`**
  (`Optional[PolicyCoordinate]`, default `None`) — the exact predecessor, as the
  authority's own coordinate type, which the adapter maps straight into the
  descriptor (`ACC-SU-IA-1`). The family already imported that type to derive its
  own coordinate, so no new dependency and no parallel identity notion.
- **The three-leg proof** (`tests/test_supersession_opt_in.py`, `ACC-SU-3`):
  digest invariance against a pinned literal, a v2-supersedes-v1 chain through
  the shipped authority on ephemeral in-process keys, and the six `ACC-LC-IA-3`
  refusals re-driven over this family.

### Changed

- The canonical projection now removes `metadata.supersedes_coordinate` as well
  as `metadata.content_digest` (`ACC-SU-2`). What a version replaces is a claim
  about the **registry**, not part of the bytes it is identified by, so every
  digest issued before this field existed — the ratified v1 content's included —
  is unmoved and `ACC-FC-2`'s identity is untouched.

### The consequence, recorded

`[G]` A constitution therefore does **not** self-attest its predecessor: the
claim is carried by the signed `PolicySupersessionRecord` the authority writes
(`ACC-LC-IA-2`), which is where an auditor must look for it. That is the price of
leaving every existing digest unmoved, and it was ratified as disclosed.

### Unchanged, deliberately

- **No existing refusal is relaxed.** A non-empty *unstructured* `supersedes_ref`
  is still refused by the authority, whether or not a coordinate accompanies it —
  proven over this family.
- **Two shipped guards were not edited**, and must not be: the projection's
  metadata key set stays pinned closed, and the excluded field is absent from
  `test_every_body_field_moves_the_digest`'s parametrization (`ACC-SU-IA-2`).
  Editing either would be the tell that the exclusion had been abandoned.
- **No agent or role lifecycle authority** (`OD-C4=A`); no disposition or
  reserved authority term (`OD-C3=B`).

`[G]` Supersession is still **unexercisable**: `ACC-LC-IA-3` refuses an absent
predecessor and no constitution has been issued, because the `ACC-FC-5`
deployment gates are shut. This closes a contract gap, not an operational one.


All notable changes to this distribution.

## 0.1.0 — the Agent Constitution policy family

First release. Makes an agent constitution **issuable** for the first time, and
stops there. This is the first of the two ratified `ACC-S1-Q2` change sets;
`ACC-S1-IMPL=YES` authorizes it.

**What this release does not make true.** It does not make constitution
conformance verifiable end to end. A family that can be issued still needs the
conformance distribution's concrete resolver and structural verifier, which are
a separate distribution and a separate change set; first release of the slice
additionally awaits the separately balloted `OD-C1=B` contract-amendment round.
Until those land the capability cannot replay end to end.

### Added

- **`AgentConstitutionPolicy`** — a declarative, versioned, digest-bound
  artifact carrying the reference it is named by, the roles it governs, the
  three structural bounds a governed role's declared vocabulary sets must stay
  within, and the clause-vocabulary version those bounds are drawn from. Every
  declared set is duplicate-free and stored in ascending codepoint order; an
  unsorted tuple is **refused**, never silently reordered. A constitution that
  governs no role, or whose closed bound names nothing, is not issuable.
- **`agent_constitution_ref` as a signed body field** — the reference this
  constitution asserts it is named by, on the `S2B-PF-C` signed-reference
  precedent. It makes the reference-to-constitution binding signed rather than
  deployment configuration; the `OD-C1=B` amendment round is its consumer.
- **The three bounds** — `permitted_candidate_dispositions_bound` and
  `permitted_review_actions_bound` closed over the imported `CandidateDisposition`
  and `ReviewAction` enums as the single sources of truth (no second spelling
  exists here to fork from), and `permitted_tool_scopes_bound` as the one open
  C5b `Token` vocabulary, bounded not enumerated, which alone may be empty.
- **`constitution_vocabulary_version`** — `ugence.agent-constitution/clauses/v1`,
  a value fixed by owner ruling (`ACC-S1-Q1`). It participates in the canonical
  projection and therefore in every issued constitution's body digest, so
  changing it later is a new policy version rather than an edit.
- **`AgentConstitutionPolicyMetadata`** — this family's own identity envelope,
  identical in shape and rules to the ratified strategy-permission metadata.
  Scope and tenant are validated as one fact; the effective interval is
  half-open `[from, to)` and an empty one is refused rather than issued as
  unresolvable; `policy_id` and `version` are held to the C5b `Token` grammar.
- **`AgentConstitutionPolicyFamilyAdapter`** — the shared Policy Authority's
  fourth policy family, and the third registered from **outside** the
  authority's own distribution. Recognition is an exact runtime type test, not
  `isinstance`; `policy_type` is a constant rather than
  `type(artifact).__name__`; the family component is re-checked by the adapter
  rather than trusted from the envelope; and the adapter advertises its
  `policy_family` so registration-time guards can compare values across an
  assembled registry.
- **The `ACC-S1-Q3` registration-time family-collision guard** —
  `register_agent_constitution_policy_family` appends the adapter and asserts,
  over the assembled registry, that exactly one adapter answers for this
  family's ratified value on both routing seams, and that no other registered
  adapter advertises it; `assert_agent_constitution_family_registration` runs
  the same assertion over any assembled registry. A packaged test pins the
  ratified family value and adapter id against the repository's real registered
  constants. The core-level uniqueness guard for all families is a raised Policy
  Authority milestone, not built and not claimed.
- **Canonical projection** mirroring the shipped adapters' discipline: exactly
  one declared path, `metadata.content_digest`, is removed — by path, not by
  name, and removed rather than blanked, so no sentinel participates and no
  fixed point is involved. The artifact carries no signature field, so the
  projection is structurally incapable of depending on one.
- **Five typed errors** under one root, the family-collision refusal included.
  None names a denial, an abstention, a reserved authority term, a terminal
  outcome or a candidate disposition, and a test enforces that under the same
  uppercased-substring rule the Agentic Proposer's own guard applies.
- **`public_api.json`** — the curated surface, asserted by
  `tests/test_public_api.py` including dataclass field order and the exact value
  of every string constant.

### Deliberately absent

Any resolver, verifier, registry, reference mapping or role-facts input type
(the conformance distribution owns them); any role lifecycle verb or authority
(`OD-C4=A`); any operational disposition, denial or abstention (`OD-C3=B`);
compute budgets, quotas, capability tiers or provider names; any execution or
runtime-authorization field; any strategy-permission content; and any amendment
content, which the separately balloted `OD-C1=B` round alone ratifies. None may
be added without a new ruling. Distribution verification on the isolated
clean-venv pattern arrives with the conformance change set, when the shared CI
covering both distributions lands — the same sequencing the strategy-permission
pair followed.

### Boundaries, measured rather than asserted

- `CandidateDisposition` and `ReviewAction` are **imported** from
  `ugence-agentic-proposer` as the single sources of truth; tests assert set
  equality in both directions, so no fork is possible.
- The Policy Authority is reached through its public `api` module only.
- No module reads a clock, opens a socket, touches storage or loads a plugin,
  and none reimplements canonicalization, hashing or signing.
- `tests/test_authority_registration.py` drives genuine issuance, real Ed25519
  signing, the real registry and real resolution across a package boundary.
