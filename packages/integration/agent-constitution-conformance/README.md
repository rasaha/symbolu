# `ugence-agent-constitution-conformance`

Agent Constitution **conformance**: the concrete fail-closed resolver and the
ratified first-slice structural conformance verifier, backed by the shared
Ugence Policy Authority.

## Why this exists

The family distribution (`ugence-agent-constitution-policy`) makes an agent
constitution issuable — and stops there. Nothing in the tree could *resolve* an
issued constitution for a governed role, or check anything against its signed
bounds. This distribution is that boundary, the second of the two ratified
`ACC-S1-Q2` change sets (`ACC-S1-IMPL=YES`,
`docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_FIRST_SLICE_RATIFICATION.md`).

## Status — what this distribution does and does not make true

With the family package it makes constitution issuance, binding and structural
conformance replay run **end to end**: issue through the real authority, resolve
by role reference, verify presented facts against the signed bounds. It does
**not** complete the first slice's release path: first release awaits the
separately balloted `OD-C1=B` contract-amendment round, which alone ratifies the
role- and proposal-surface binding. Nothing here should be read as saying
otherwise.

## The resolver (§5.2 of the ratified specification)

`PolicyAuthorityConstitutionResolver.resolve(tenant_id=…, role_contract_ref=…,
as_of=…, presented_constitution_ref="")` returns the exact resolved
`AgentConstitutionPolicy`, or raises. Its discipline, on the ratified
strategy-permission runtime pattern:

- **Injected, immutable, defensively copied mapping** keyed by
  `(tenant_id, role_contract_ref)` to a complete `PolicyCoordinate`. An unknown
  key fails closed: no fallback, no prefix match, no newest-version rule. A
  stored coordinate carries its digest, so a floating reference is
  unrepresentable — and, keyed by role, a deployment cannot represent two active
  constitutions for one role at one `as_of` (`ACC-S1-Q4`'s enforceable half).
- **Caller-supplied, tz-aware `as_of`**, passed through verbatim. No clock.
- **Request-derived `expected_reference_tenant_id`** — never read off the
  coordinate, so the authority's tenant comparison stays non-vacuous.
- **An approval verifier is always supplied**, so an approval withdrawn after
  issuance invalidates resolution. There is no default and no shortcut.
- **Historical resolution stays deny-always.** An answer about the past is
  never accepted.
- **An artifact is returned only on `RESOLVED`**; every other authority outcome
  raises, with the `PolicyResolutionReason` carried verbatim on the exception's
  `reason` attribute — and through nothing else, never message text (§5.3).
- **Four post-checks, each with its own error class**: exact runtime artifact
  type; the requested role a member of the signed `governed_role_refs`; every
  closed-bound element a member of its source enum; and, where a constitution
  reference is presented, exact equality with the signed
  `agent_constitution_ref`.

## The verifier — the §2.3 predicate, whole

`role_facts_conform(policy=…, facts=…)` answers `True` iff the role reference is
a member of `governed_role_refs` and each of the three declared sets is a subset
of its signed bound. Set semantics, order-insensitive; empty declared tool
scopes conform to any bound. The answer is a `bool` and nothing else: no
artifact on failure, no disposition, no denial, no abstention — the
structural-failure operational-disposition owner remains deliberately unassigned
(`OD-C3=B`).

## The presented-facts input, and its caveat

A repository-wide scan refuses the role projection's name in every `.py` outside
the capability that owns it, so this boundary never receives a role: it is
handed `GovernedRoleFacts` — a package-local frozen dataclass of plain presented
facts, assembled by the caller. Disclosed plainly: replay proves conformance of
the **presented** facts to the resolved constitution; that those facts equal a
live role's declarations is the caller's assertion, exactly as digest membership
proves integrity after construction, never provenance.

## Composition

`build_constitution_resolver(…)` wires a resolver whose adapter registry
certainly carries this family — through the family package's own registration
helpers, so **every composition path runs the `ACC-S1-Q3` registration-time
family-collision guard**. A registry in which this family does not answer
exactly once fails to compose before any request is served. The helper supplies
no trust anchors, no registry and no approval verifier: an unconfigured
deployment fails to construct, never quietly resolves.

## What is deliberately absent

No role lifecycle authority (`OD-C4=A`); no operational disposition (`OD-C3=B`);
no compute, tools, evidence access or consequential execution; no policy source,
registry or coordinate minting — the mapping is injected configuration, and its
population remains ungoverned, a disclosed, carried gap; no `verified` boolean;
no amendment content — the `OD-C1=B` round is separately balloted. None may be
added without a new ruling.

## Boundaries, measured rather than asserted

- The Policy Authority is reached through its public `api` module only; the
  family package supplies every identity value, imported never restated.
- No module reads a clock, opens a socket, touches storage or loads a plugin,
  and none reimplements canonicalization, hashing or signing.
- No error name or message template carries a reserved authority term, a
  terminal-outcome value or a candidate-disposition value, under the
  uppercased-substring rule.
- `tests/test_end_to_end.py` drives genuine issuance, real Ed25519 signing, the
  real registry, real resolution and the predicate in both directions;
  `verify_agent_constitution_conformance_distribution.py` proves the same from
  built wheels in an offline clean venv, both constitution distributions
  installed and exercised.
- `public_api.json` is the curated surface, asserted by
  `tests/test_public_api.py` including dataclass field order.
