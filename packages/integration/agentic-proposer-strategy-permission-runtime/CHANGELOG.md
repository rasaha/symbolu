# Changelog — `ugence-agentic-proposer-strategy-permission-runtime`

All notable changes to this distribution.

## 0.1.0 — the concrete strategy-permission resolver

First release. With the strategy-permission family package, this is what makes
Reasoning Strategy Permission run end to end: a policy issued and signed through
the shared Policy Authority is resolved through configured trust and stamped onto
an advisory by the Agentic Proposer's own builder, with neither of those two
packages modified.

**What the end-to-end proof establishes, and what it does not.** It establishes
that the ratified pieces compose. It establishes **nothing** about private
reasoning or chain-of-thought; it does **not** prove that any declared procedure
was *executed*; it establishes no observable-stage conformance beyond what an
advisory's own shape shows, since no component records reasoning stages; and it
creates **no compute authorization and no consequential execution authority**,
which remain with Risk Authority, ActionGate and Decision Authority.

### Added

- **`PolicyAuthorityStrategyPolicyResolver`** — maps `(tenant_id,
  strategy_policy_ref)` to one exact `PolicyCoordinate` through an injected,
  immutable, defensively copied mapping, resolves that coordinate through the
  authority, and returns the four ratified response fields. The mapping is
  exposed as a read-only view and the resolver is not rebindable after
  construction: replacing it wholesale would be exactly the coordinate injection
  the defensive copy exists to prevent. An unknown key fails closed — no
  fallback, no prefix match, no newest-version rule — and because a stored
  coordinate carries its content digest, a new permitted set requires a new
  configured entry rather than a silent re-point.
- **The signed reference binding.** The resolved artifact's own
  `strategy_policy_ref`, inside the digest the authority signed, must equal the
  request's reference exactly. Configuration locates the policy; the authority
  states which reference it answers to.
- **Request-derived tenant verification.** `expected_reference_tenant_id` is
  never read off the coordinate — doing so would make the authority's comparison
  vacuous for every coordinate. A resolver-side scope/tenant pre-check stands
  beside it, so the two checks are redundant rather than co-dependent.
- **An always-supplied approval verifier**, required at construction. Without one
  an approval withdrawn after issuance would still resolve, because the issuance
  signature proves only that approval held at issuance time.
- **Deny-always historical resolution**, stated as a constant so that relaxing it
  is a visible edit rather than an omitted keyword.
- **A fail-closed taxonomy** — one root and six leaves. A response is produced
  only when the authority answered with a resolution; every other outcome raises,
  which covers the authority's whole reason enumeration by construction.
- **The reason-token discipline.** A `PolicyResolutionReason` reaches a caller on
  the `reason` attribute and nowhere else, never in message text. Two of the
  authority's reasons are reserved authority terms under the uppercased-substring
  rule, so interpolating one into a message would emit reserved vocabulary
  without anyone choosing to.
- **Two composition helpers** — one that registers the family adapter
  idempotently, and one that builds a resolver whose registry certainly carries
  it. Neither supplies a default for any injected trust dependency.
- **Distribution verification** for this package and for the family package:
  clean-venv build, install and exercise, on the existing `verify_*` pattern.
- **CI wiring** covering both distributions' suites, both distribution
  verifications, the neighbouring repository-wide scans these packages must
  satisfy, and platform-freeze verification.

### Deliberately absent

No `verified` boolean; no clock, socket, storage or plugin loading; no compute
budget, quota, token count, capability tier or provider name; no role identity;
no default trust anchor or approval verifier; and no mapping from a permission
failure to an operational outcome, which remains deliberately unruled.

### Boundaries, measured rather than asserted

- The authority is reached through `ugence_policy_authority.api` only.
- The end-to-end proof drives the genuine pipeline on both sides — real issuance,
  real Ed25519 signing, the real registry, real resolution, the proposer's own
  ratified builders, and its six-check replay with each check failing
  independently.
- The role projection appears nowhere in the distribution, test sources included.
