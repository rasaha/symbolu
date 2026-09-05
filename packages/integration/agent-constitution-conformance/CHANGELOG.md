# Changelog — `ugence-agent-constitution-conformance`

All notable changes to this distribution.

## 0.1.0 — Agent Constitution conformance

First release. The second of the two ratified `ACC-S1-Q2` change sets
(`ACC-S1-IMPL=YES`): with the family distribution it makes constitution
issuance, resolution and structural conformance replay run **end to end**.

**What this release does not make true.** It does not complete the first
slice's release path: first release awaits the separately balloted `OD-C1=B`
contract-amendment round, which alone ratifies the role- and proposal-surface
binding. It performs no caller authorization, maps no failure to any
operational outcome, and holds no authority of any kind.

### Added

- **`PolicyAuthorityConstitutionResolver`** — the concrete §5.2 resolver on the
  ratified strategy-permission runtime pattern: an injected, immutable,
  defensively copied mapping keyed by `(tenant_id, role_contract_ref)` to a
  complete `PolicyCoordinate`; unknown keys fail closed with no fallback,
  prefix match or newest-version rule; caller-supplied tz-aware `as_of` passed
  through verbatim; request-derived `expected_reference_tenant_id` with a
  redundant scope/tenant pre-check; an approval verifier always required, so an
  approval withdrawn after issuance invalidates resolution; historical
  resolution deny-always; the exact artifact returned only on `RESOLVED`.
- **Four post-checks, each with its own error class**: exact runtime artifact
  type (`ConstitutionArtifactTypeError`); the requested role a member of the
  signed `governed_role_refs` (`ConstitutionRoleBindingError` — the `ACC-S1-Q4`
  signed-side binding); every closed-bound element a member of its source enum
  (`ConstitutionVocabularyError`, re-checked from the resolved artifact); and
  presented-reference equality with the signed `agent_constitution_ref`
  (`ConstitutionReferenceBindingError`), optional until the amendment round
  gives the role surface a reference field.
- **`role_facts_conform`** — the ratified §2.3 first-slice structural
  conformance predicate, whole: role membership plus three subset checks, set
  semantics, order-insensitive, empty declared tool scopes conforming to any
  bound. Returns `True` or `False` and nothing else: no artifact on failure and
  no disposition (`OD-C3=B`).
- **`GovernedRoleFacts`** — the §5.1 package-local frozen presented-facts input,
  forced by the repository-wide role-projection scan: role reference, the three
  declared sets, tenant; exact types, C5a/C5b grammar, duplicates refused,
  order not enforced. The presented-facts caveat is disclosed in the type's own
  documentation and pinned by a test: replay proves the presented facts only.
- **§5.3 disposition-free failure taxonomy** — one root
  (`AgentConstitutionConformanceError`), eight leaves, none naming a denial,
  abstention, reserved authority term, terminal outcome or candidate
  disposition; a `PolicyResolutionReason` reaches a caller only through
  `ConstitutionUnresolvedError.reason`, never message text, and a test asserts
  the reason token absent from the message.
- **`build_constitution_resolver`** — the one composition helper. Registration
  goes through the family package's own helpers, so **every composition path
  runs the `ACC-S1-Q3` registration-time family-collision guard**; the helper
  supplies no trust anchors and no approval verifier of its own.
- **`public_api.json`** — the curated surface (13 symbols, no constants: every
  identity value is the family package's, imported never restated), asserted by
  `tests/test_public_api.py` including dataclass field order.
- **Full §5.4 end-to-end proof** — genuine issuance with real Ed25519 signing
  and independent recomputation of the framed body digest; deny-by-default
  approval refusal at issuance; exact-only mapping with near-miss role
  references refused; mutated artifact, forged signature and unknown key fail
  closed; revocation, effective-window and lifecycle refusals with historical
  resolution proven deny-always; role-not-governed raises; the predicate proven
  in both directions; the reserved-term guard over names and message templates;
  and no networking, storage, service-discovery, plugin-loading or clock
  import — all deterministic, clock- and network-free.
- **Isolated distribution verification**
  (`verify_agent_constitution_conformance_distribution.py`) — clean-venv,
  offline, pinned wheel build covering **both** constitution distributions:
  installs the built wheels, drives issuance, guarded composition, resolution
  and the predicate in both directions inside the venv, and proves by negative
  control that a missing first-party wheel refuses rather than substitutes.
  Covers the family distribution too, on the sequencing its own CHANGELOG
  recorded — the same point in the pair's history at which the
  strategy-permission distributions gained theirs.
- **Shared CI** (`.github/workflows/agent-constitution-ci.yml`) — one workflow
  for both constitution distributions: both package suites, the neighbouring
  repository-wide scans they must satisfy, the isolated-install verification,
  and the blocking platform-freeze check.

### Deliberately absent

Any role lifecycle verb or authority (`OD-C4=A`); any operational disposition,
denial, abstention or `verified` boolean (`OD-C3=B`); any caller authorization;
compute budgets, quotas, capability tiers or provider names; any policy source,
registry, coordinate minting or reference-map population mechanism — the
mapping is injected configuration and its population remains ungoverned, a
disclosed, carried gap; and any amendment content, which the separately
balloted `OD-C1=B` round alone ratifies. None may be added without a new
ruling.

### Boundaries, measured rather than asserted

- The Policy Authority is reached through its public `api` module only.
- `CandidateDisposition` and `ReviewAction` are imported for the closed-bound
  re-check; no vocabulary is restated anywhere in this distribution.
- No module reads a clock, opens a socket, touches storage or loads a plugin,
  and none reimplements canonicalization, hashing or signing.
- The role projection is named nowhere in this distribution, prose included.
