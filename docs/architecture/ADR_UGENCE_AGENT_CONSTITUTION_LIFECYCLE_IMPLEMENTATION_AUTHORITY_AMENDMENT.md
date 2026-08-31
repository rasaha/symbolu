# ADR: Ugence Agent Constitution — lifecycle implementation authority, surface amendment

**Status:** **Accepted (owner ruling) — amendment, documentation only.** This
ADR amends the fixed surface of
[`ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_IMPLEMENTATION_AUTHORITY.md`](ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_IMPLEMENTATION_AUTHORITY.md)
(`ACC-LC-IA-BASE`). It changes **nothing else**: `ACC-LC-IA-1` – `ACC-LC-IA-5`
stand exactly as ruled, and every `ACC-LC` and earlier ruling is untouched.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31, after the blocker below was reported on PR #1547. On the standing
precedent: **where the conversation and this ADR differ, this ADR governs.**

**Numbering.** `[R]` Recorded as **`ACC-LC-IA-BASE-A1`**, ADR-scoped, on the
standing precedent. No new register item is created and no existing number moves.

## 1. Why an amendment was needed

`[R]` `ACC-LC-IA-BASE` bounds the authorized change set to *"the **shared Policy
Authority only** … and nothing else"*, and `ACC-LC-IA-5` records the other
distributions as untouched. `[R]` `ACC-LC-IA-2` simultaneously requires that
resolution deny a superseded predecessor *"with its own typed supersession
reason"*.

`[G]` **Those two cannot both hold.** A consumer distribution carries the
authority's refusals one-for-one into its own closed vocabulary and guards the
correspondence:

* `[V]` `packages/integration/cloud-scaling-policy-authenticity/tests/test_typed_outcomes.py:26`
  requires `RESOLUTION_REASON_OUTCOMES` to be **total** over every
  non-`RESOLVED` `PolicyResolutionReason`; `:32` requires it to be **injective**,
  so no two refusals may collapse onto one outcome. Together these mean a new
  authority reason is necessarily a new *public member* of that package's
  `PolicyAuthenticityOutcome`.
* `[V]` `packages/integration/cloud-scaling-policy-authenticity/tests/test_phase5a_untouched.py:55`
  pins the Policy Authority at `0.1.0`. Its own docstring states that a version
  move "surfaced here first, in a consumer, which is exactly what this file
  exists to do" — a deliberate tripwire, not an incidental assertion.

`[V]` Both guards failed on PR #1547 at head `a4a5ec4b`, taking ten CI checks
with them (the eight mutation-sweep shards and the guard-inventory job require a
green baseline). `[R]` Neither failure is a defect in the authorized
implementation and neither is a flake: the guards are correct, and they caught a
gap in the **authorization**, which had been written from the authority's side
only and never asked whether a consumer pinned the reason vocabulary.

`[R]` **Recorded as a process finding, not a defect of the code:** the
`LC-IA-5` row asked where the change set lands and was answered by inspecting
the authority. The ballot's `§0` facts did not include the consumer-side
totality guard, so the surface it produced was unsatisfiable. A future
implementation-authority ballot that changes a **shared closed vocabulary**
should enumerate that vocabulary's consumers before bounding its surface.

## 2. `ACC-LC-IA-BASE-A1` — the amended surface `[R]`

The authorized change set is the surface `ACC-LC-IA-BASE` describes — the shared
Policy Authority — **plus exactly five files** in
`packages/integration/cloud-scaling-policy-authenticity`, and nothing else:

| File | Authorized change |
|---|---|
| `src/ugence_cloud_scaling_policy_authenticity/outcomes.py` | two new `PolicyAuthenticityOutcome` members and their two `RESOLUTION_REASON_OUTCOMES` entries, distinct so injectivity holds |
| `tests/test_phase5a_untouched.py` | the Policy Authority pin moves `0.1.0` → `0.2.0`, and this package's own pin moves `0.8.0` → `0.9.0` to match its bump |
| `src/ugence_cloud_scaling_policy_authenticity/version.py` | `0.8.0` → `0.9.0`, since the public vocabulary grows |
| `tests/test_guard_coverage.py` | the five **authority-targeted** drift simulations re-anchor from `0.1.0` → `0.2.0` to `0.2.0` → `0.3.0` |
| `CHANGELOG.md` | the corresponding entry |

`[V]` The extension is closed: a repository-wide search finds **no other**
package carrying either guard, so no third distribution is reached.

`[G]` **This list was corrected during implementation, and the correction is
recorded rather than absorbed.** It first named four files. Two more failures
appeared only once the first two guards passed: this package's own version pin
(same file, entailed by the authorized bump — a bump whose consistency check
still asserted the old value would be incoherent), and
`tests/test_guard_coverage.py`, whose drift-simulation harness copies the
authority's source and rewrites `__version__ = "0.1.0"` to `"0.2.0"` to
*simulate* a future authority, asserting the anchor matches exactly once. Making
that simulated future real turned the anchor into a zero-match. `[R]` The five
sites move to `0.2.0` → `0.3.0`, and their labels with them; a sixth site
targeting `ugence_cloud_scaling_risk_integration` keeps `0.1.0` → `0.2.0`,
because that package has not moved.

`[R]` The same lesson as `§1`, one layer deeper: enumerating a shared
vocabulary's consumers is not enough when a consumer's *test harness* also
hard-codes the producer's version as a simulation anchor. A surface bounded by
running the failing tests once is bounded by what happened to fail first.

**Everything else remains unauthorized** `[R]`, unchanged from
`ACC-LC-IA-BASE`: no other file, package or workflow; no relaxation of the
unstructured-value refusal; no suspension mechanism (`ACC-LC-3`); no production
issuance, revocation or supersession; and no touching of a role or an agent
(`OD-C4=A`). **In particular** `[R]`: the pin at `test_phase5a_untouched.py:55`
is *moved*, never deleted or loosened — a consumer that stops pinning the
authority's version would destroy the very tripwire that produced this
amendment.

## 3. What this amendment does not do `[R]`

It does not revisit `ACC-LC-IA-1` – `ACC-LC-IA-5`, reopen any `ACC-LC` ruling,
or change what the supersession mechanism is or how it is proven. It grants no
new capability: two enum members and a mapping are how an existing capability is
*carried across a boundary that already existed*.

## 4. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record. No
lifecycle authority over agents or roles exists or is implied (`OD-C4=A`); no
verifier emits a disposition or reserved authority term (`OD-C3=B`); conformance
replay proves conformance of presented facts only. No constitution is issued,
superseded, suspended or revoked, and no signing key, trust root or approval
artifact enters the repository. Suspension remains unimplemented and its round
uncommissioned (`ACC-LC-3`); `/clauses/v2` remains out of scope and `ACC-AM-4`'s
re-arm untriggered.

## 5. What this ADR changed

One new documentation file. **No source, test, `public_api.json`, `version.py`,
CHANGELOG, package metadata or CI workflow is modified by this ADR**; it
authorizes a change set that lands as its own commit alongside it.
