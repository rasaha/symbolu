# Changelog — `ugence-agentic-proposer-strategy-permission-policy`

All notable changes to this distribution.

## 0.1.0 — the strategy-permission policy family

First release. Makes a reasoning-strategy permission **issuable** for the first
time, and stops there.

**What this release does not make true.** It does not make Reasoning Strategy
Permission executable. A family that can be issued still needs a concrete
resolver before anything runs end to end, and that resolver is a separate
distribution. Until it lands the capability still cannot execute end to end.

### Added

- **`StrategyPermissionPolicy`** — a declarative, versioned, digest-bound
  artifact carrying the reference it answers to, the strategies it permits, and
  the vocabulary version those strategies are drawn from. The permitted set is
  non-empty, duplicate-free and stored in ascending codepoint order; an unsorted
  tuple is **refused**, never silently reordered. A policy that permits nothing is
  not issuable — that state stays representable at the resolver-response boundary,
  where the ratified replay reports it.
- **`strategy_policy_ref` as a signed body field** — the reference this policy
  asserts it answers to. It makes the reference-to-policy binding signed rather
  than deployment configuration: a caller-supplied value never becomes
  authoritative, it must *match* a value the issuing authority signed.
- **`vocabulary_version`** — `ugence.agentic-proposer.reasoning-strategy/v1`, a
  value fixed by owner ruling. It participates in the canonical projection and
  therefore in every issued policy's body digest, so changing it later is a new
  policy version rather than an edit.
- **`StrategyPermissionPolicyMetadata`** — this family's own identity envelope.
  Scope and tenant are validated as one fact: a `GLOBAL` policy carries the
  authority's canonical empty tenant component, and a `TENANT` policy must name a
  non-empty tenant. The effective interval is half-open `[from, to)` and an empty
  one is refused rather than issued as unresolvable. `policy_id` and `version` are
  additionally held to the Agentic Proposer's C5b `Token` grammar, so a policy
  that could not be stamped onto an advisory is refused here rather than at that
  boundary.
- **`StrategyPermissionPolicyFamilyAdapter`** — the shared Policy Authority's
  third policy family, and the second registered from **outside** the authority's
  own distribution. Recognition is an exact runtime type test, not `isinstance`:
  a subclass could add fields this family never validates. `policy_type` is a
  constant rather than `type(artifact).__name__`, so a class rename cannot
  silently move every body digest, and the family component is re-checked by the
  adapter rather than trusted from the envelope.
- **Canonical projection** mirroring the shipped adapters' discipline: exactly one
  declared path, `metadata.content_digest`, is removed — by path, not by name, and
  removed rather than blanked, so no sentinel participates and no fixed point is
  involved. The artifact carries no signature field, so the projection is
  structurally incapable of depending on one.
- **Four typed construction errors** under one root. None names a denial, an
  abstention, a reserved authority term, a terminal outcome or a candidate
  disposition, and a test enforces that under the same uppercased-substring rule
  the Agentic Proposer's own guard applies.
- **`public_api.json`** — the curated surface, asserted by `tests/test_public_api.py`
  including dataclass field order and the exact value of every string constant.

### Deliberately absent

Required strategies; composition, ordering or subordinate strategies; compute
budgets, quotas or token counts; model capability tiers; provider names; terminal
outcomes or dispositions; any execution or runtime-authorization field; any role
identity; and any resolver, registry or reference mapping. None may be added
without a new ruling.

### Boundaries, measured rather than asserted

- `ReasoningStrategy` is **imported** from `ugence-agentic-proposer` as the single
  source of truth; a test asserts this family's accepted token set equals
  `set(ReasoningStrategy)`, so no fork is possible.
- The Policy Authority is reached through its public `api` module only.
- No module reads a clock, opens a socket, touches storage or loads a plugin, and
  none reimplements canonicalization, hashing or signing.
- `tests/test_authority_registration.py` drives genuine issuance, real Ed25519
  signing, the real registry and real resolution across a package boundary.
