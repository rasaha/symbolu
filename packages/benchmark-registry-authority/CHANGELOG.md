# Changelog — ugence-benchmark-registry-authority

All notable changes to this distribution. The format follows Keep a Changelog;
versioning is Semantic Versioning, and the version ladder is the ratified
subphase ladder: BR-2A `0.1.0`, BR-2B `0.2.0`, BR-2C `0.3.0`, BR-2D `0.4.0`,
BR-2E `0.5.0` (ADR §35 D-01, amended 2026-08-20).

## [0.2.0] — BR-2B: the non-authoritative lifecycle kernel

**Determines what a transition would be. Makes none occur.**

Ships no store, no verifier, no clock, no append path and no authority-issued
result, and cannot admit, register, revoke or resolve. Non-authoritative *by
construction*, not by an injected default: there is nothing here for a
substituted component to unlock.

### Added

- `BenchmarkRegistrySnapshotAssertion` — what a caller **asserts** the registry
  holds for one exact locator. Never a reading; every field is `asserted_`.
- `BenchmarkTransitionPlan` — a move that would be admissible against exactly
  the nested assertion. Unconstructible for an inadmissible one, and bound to
  the assertion it was computed from by a recomputed digest.
- `BenchmarkTransitionRefusal` — the typed negative, carrying one reason from
  the BR-2 vocabulary.
- `BenchmarkRegistrationRecordPresence` — a closed two-member enum, not a
  Boolean, gating `ADMITTED -> REJECTED`.
- `plan_transition`, `plan_submission_outcome`, `is_byte_identical_resubmission`
  and the `BenchmarkPlanningOutcome` alias. Total functions: exact contracts in,
  a plan or a refusal out, no third outcome and no raw digest or byte argument.
- Three digest domains, appended never inserted: registry-snapshot-assertion,
  transition-plan, transition-refusal.

### Ruling notes

- Idempotence compares canonical **bytes**, recomputed from both records
  (D-06). Neither side may be supplied as bytes or as a digest.
- Confusable handling stays **rejection-only**. No algorithm is claimed, no
  locator is normalized, casefolded, rewritten or stored.
- Self-inconsistent assertions fail closed with `STALE_REGISTRY_SNAPSHOT`
  rather than being repaired.
- **No exported callable accepts a `BenchmarkTransitionPlan`.** Asserted on live
  signatures and again over the source tree, so the seam through which applying
  a plan could arrive does not exist.

### Changed

- Curated surface 82 -> 93 symbols; `public_api.json` 81 -> 92; pinned vectors
  and digest domains 15 -> 18. Moved deliberately in every assertion site, per
  D-18.
- Capability-token bans are milestone-conditional (D-19) and, at this version,
  identical to the set BR-2A froze. Permanent bans stay permanent.
- The distribution's own four-phase prose is corrected to the five-phase
  ratification (ADR §35 D-01, amended 2026-08-20).

## [0.1.0] — BR-2A: registry and exact-resolution contracts

First release. **Contracts and pure validation only.**

### Added

* **Three inbound assertion envelopes** carrying *declared* signature material:
  `BenchmarkPublisherSubmissionEnvelope` (the sole source of publisher identity
  in the entire chain), `BenchmarkApprovalEnvelope` (nesting the exact publisher
  envelope, never its digest) and `BenchmarkRevocationEnvelope`. Each declares a
  closed signature profile — never an unconstrained algorithm string — and its
  own pinned signing-frame domain, so a signature under one frame can never be
  replayed under another.
* **A completely specified signing frame** — framing order, `uint32_be` length
  prefixing of every element including the framing elements, domain tag and
  version — published as `BENCHMARK_SIGNING_FRAME_SPECIFICATION` so BR-2C need
  never reinterpret a contract this milestone already published. Nothing here
  builds, signs or verifies a signing input.
* **Six administrative chain payloads**, one structural representation bound to
  each transition, including `BenchmarkPostAdmissionRejectionEventPayload` for
  `ADMITTED → REJECTED` — a distinct type because that transition has a distinct
  predecessor. Every payload except the initial submission record exposes a
  mandatory `prev_event_digest` derived from its exact nested predecessor.
* **Two read payloads** as different exact types, so a historical answer cannot
  be consumed as a current one, with pure type guards proving the separation.
* **Two request shapes and two registry scope expectations.** The trusted
  resolution request has no `as_of` at all; the scope expectation is derived from
  the locator's own scope rather than accepted as a second, disagreeable field.
* **One canonicalization path and one digest path**, versioned, with fifteen
  minted domain-separation tags — one per artifact class this subphase actually
  ships, and no tag for an artifact that does not exist — and a pinned canonical
  byte vector and digest for every one of them.
* **`BenchmarkRegistrationState`** (`SUBMITTED · ADMITTED · REGISTERED · REVOKED
  · REJECTED`), its closed transition relation with terminal states expressed as
  empty sets, and the immutable, test-asserted transition-to-payload binding.
* **`BenchmarkRegistryRefusalReason`** — seventeen BR-2 reasons, provably
  disjoint from BR-1's frozen seventeen — the ordered composite
  `BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS`, and a total classification into
  seven `BenchmarkRegistryFaultClass` members.
* **Four inert `Protocol` ports**, a frozen consistency descriptor with no
  flippable Boolean, and the typed `BenchmarkRegistryCompositionError` — defined
  for later use and raised by nothing here.
* **The confusable comparison contract**, rejection-only, with its algorithm slot
  explicitly empty and no completeness claimed.
* **Machine-readable manifests**: `public_api.json`,
  `public_contract_inventory.json`, `canonical_domain_inventory.json`,
  `pinned_canonical_vectors.json` and `gate_inventory.json`, every one asserted
  against the live surface rather than maintained by hand.
* **Verification tooling**: an independent probe harness, a distribution
  verifier with eight negative controls, a BR-1 freeze-matrix verifier, and a
  gate-deletion mutation sweep over a 48-gate inventory.

### Deliberately not added

No admission engine, storage implementation, signature verifier, key parser,
trust-anchor store, approval verifier, clock read, resolver, convenience
resolver, selection API, supersession implementation, adapter registry, identity
allow-list, production composition root, or cryptographic dependency. No
placeholder verifier, permissive fallback, dormant capability field, reserved
future field, executable stub, TODO-backed runtime path, or `NotImplementedError`
pretending to be a port implementation.

The authority-issued result types `BenchmarkAdmissionDecision`,
`BenchmarkRegistrationEvent` and `BenchmarkResolution` are **reserved and
undefined**.

### Unchanged elsewhere

`ugence-benchmark-registry` stays at `0.1.0` with its zero-dependency proof, its
593 tests, its 57 probes and its pinned digests intact. No other package and no
existing CI workflow is modified.
