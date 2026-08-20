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

### Closure-audit remediation

The first closure audit confirmed the property — *no callable consumes a
`BenchmarkTransitionPlan`* — and **refuted the gates asserting it**. Three plan-
consumption gates matched the literal substring `"BenchmarkTransitionPlan"` and
skipped parameters annotated `None`; the return-type gate claimed to read a live
annotation but, under PEP 563, read the *string* `"BenchmarkPlanningOutcome"`
without ever inspecting the Union's members. A plan-consuming, event-returning
exported callable would have passed all four.

- Annotations are now resolved to **class objects** via `typing.get_type_hints`,
  with every `Union`/`Optional`/generic walked to its leaves, and membership
  decided by identity. An alias, a nested `Optional` and a PEP 563 string are
  each seen.
- An unannotated parameter under `contracts/` is a **failure**, not a skip.
  `self`/`cls` remain exempt; dataclass- and Enum-synthesized methods are
  excluded by checking that a function's code lives in a file this package
  contains.
- The return gate resolves hints and walks `typing.get_args`, so widening the
  outcome alias is visible.
- `BenchmarkPlanningOutcome` was recorded as `"kind": "pure_validation_function"`
  — a `Union` described as a function, because a `Union` is callable in CPython.
  It is now `"closed_type_alias"` with its **member set pinned**, so widening it
  fails a gate rather than only moving a symbol count.
- Thirteen new properties plant each attack — aliased parameter, nested
  `Optional`, PEP 563 string, unannotated parameter, private helper,
  keyword-only parameter, widened return Union — and require the checking logic
  to report it. Three new mutation gates (G-54, G-55, G-56) plant the same
  attacks in the shipped source; all three are killed.
- D-06 gains a **behavioural** discriminator alongside the source assertion: two
  submissions whose asserted identity *and* content digests are identical but
  whose canonical bytes differ. A digest-only rule returns
  `IDEMPOTENT_DUPLICATE`; comparing bytes returns `COORDINATE_SLOT_CONFLICT`.
  Only one of those is D-06's answer, and no source string is consulted.

### Second closure-audit remediation

The second audit confirmed `tests/_boundary.py` resolves correctly and found the
gates **consuming** it were scoped to `contracts/` and asked each function where
its code came from. Three planted callables kept the suite and probes green:

- **D** — a function `exec`-compiled inside `planning.py` with
  `co_filename="/tmp/not_under_contracts.py"`.
- **E** — the same exemption via one `__code__.replace(co_filename=...)` on an
  ordinary `def`, no `exec` at all.
- **F** — a module-level alias and a plain plan-consuming `def` in `api.py`,
  which the `contracts/`-scoped module walk and alias walk never visited.

D and E are the same mistake as the substring rule they replaced: letting
something the attacker supplies decide what this package contains. `co_filename`
travels with the code object and is chosen by whoever compiled it. **Ownership
now follows the scanned path** — the module walk imports exactly the files the
AST scan reads, and the alias set is gathered from every one of them.

- The plan-consumption check carries **no exemption of any kind**. A synthesized
  method has no annotation naming a plan, so excluding one would buy nothing and
  cost the guarantee.
- The annotation requirement keeps a narrow exemption, decided by **identity
  against a base class** (`EnumType` copies `_generate_next_value_` into every
  subclass), by the dataclass machinery's fixed method set, or by the module's
  **own source text** (`typing.Protocol` installs `__init__` and
  `__subclasshook__`; `from dataclasses import fields` binds a stdlib function).
  Never by a filename.
- The return check is scoped to planners, since BR-2A's
  `require_exact_resolution_record_payload` legitimately returns a resolution
  record and `BenchmarkRegistryStorePort.read_historical` legitimately declares
  one. Nothing rests on it: a callable consuming a plan and returning an event
  is caught by the parameter check.
- Probe Q-62 had the identical `contracts/` blind spot and is widened the same
  way, verified to catch F independently of the suite.
- G-57, G-58 and G-59 plant exactly D, E and F in shipped source; all three are
  killed by `test_no_callable_anywhere_under_src_accepts_a_plan_however_spelled`.
  The sweep gained explicit support for gates outside `contracts/`, since a
  sweep confined to `contracts/` could not have planted F.

### Verification performed for this release

Measured, not asserted. Every number below came from a run against this tree.

- **Suite** 1734 tests, 473 distinct properties (441 adversarial : 32 happy,
  13.78:1). Movement from 1730 is +4: seven properties added and three renamed
  away in `test_milestone_boundary.py` as the three `contracts/`-scoped gates
  became `src/`-wide ones. The two monorepo-scope properties ran rather than skipping: no
  package in the monorepo imports this one, and no workflow but its own
  references it.
- **Independent probes** 65/65, run twice — Q-62 rewritten to resolve types
  independently of the suite's helper, Q-64 added for the return boundary — against the source tree, and again
  from inside the installed wheel.
- **Offline distribution verifier** PASSED, 41 checks. Both wheels are built in
  the host environment; the isolated environment only ever *installs* a wheel,
  never builds source. A fresh venv without system site packages, with
  `--no-index`, `PIP_NO_INDEX=1`, an emptied `PYTHONPATH` and
  `PYTHONNOUSERSITE=1`, resolving only from a wheelhouse holding exactly the
  BR-2B wheel and the permitted BR-1 wheel. Source/wheel/sdist/installed-runtime
  parity holds on all four manifests, all 18 pinned vectors and both counts.
- **Negative controls** 8/8 caught: a smuggled test file, a smuggled conftest
  and probe harness, an extra declared dependency, an injected distribution, a
  moved pinned digest, monorepo source shadowing the installed wheel, a leaked
  `PYTHONPATH`, and installing with the one dependency unavailable.
- **BR-1 freeze matrix** VERIFIED, with BR-1's own suite (593 tests) and probes
  (57) run unmodified. No BR-1 file is touched by this release.
- **Mutation sweep** 59 gates inventoried, 54 killed, 5 survived, 0 errored —
  +3 scope gates over the previous 56/51, all killed. The sweep also gained
  correct handling of *additive* mutations, whose replacement text contains the
  original: demanding the original's absence had reported a correctly applied
  insertion as an unprovable mutant.
  Every restore is proven byte-identical to the proven-green baseline before
  mutating, and every mutant is proven loaded — by the import system, not the
  filesystem — before a KILL or SURVIVE is accepted. A harness control aborts
  the run if that proof cannot itself fail.

The five survivors are unchanged from BR-2A and none is a gap: **G-12** is
shadowed by G-11 (identical bytes necessarily hash identically, so killing it in
isolation would need a hash collision); **G-28**, **G-29** and **G-30** are the
encoder's float, NFC and aware-datetime branches, each shadowed by construction-
time validation and by graph revalidation (G-17), so the encoder's own branch is
never the first refusal; **G-43** is equivalent while BR-1 is frozen, and the
BR-1 freeze matrix is the independent gate that would catch that drift.

**Not claimed.** This release has had no independent closure audit. The
delivering session wrote, ran and reported all of the above, and an author-owned
test, probe or mutation run is not an audit.

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
