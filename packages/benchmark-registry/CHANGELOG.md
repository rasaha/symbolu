# Changelog — ugence-benchmark-registry

## [0.1.0] — BR-1: benchmark-definition contracts

First version. Implements milestone **BR-1** of
[`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](../../docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md)
§30 — "Benchmark Definition Contracts: benchmark identity (§15), lifecycle state,
structured references. **Contracts only; no registry.**"

The Ugence Benchmark Registry is one shared, platform-wide capability (B-1),
**internal platform infrastructure**, not a customer-facing module and not a
fourth UVI engine (B-2). This distribution is its contract layer.

### Added — contract shapes (ADR §15)

* `BenchmarkCoordinate` — ADR §15 rows 1, 2, 3, 5, 6, 7: the complete, exact set
  of coordinates that names **one** benchmark version. Every field mandatory with
  no default, so a partial coordinate cannot be constructed; every identifier an
  exact token, so a wildcard cannot be written; the version an exact Semantic
  Versioning 2.0.0 string, so a range, a comparator, a two-component version or a
  leading-zero second spelling cannot be written either. B-8's "a floating
  reference must be **unrepresentable**" holds in the type.
* `CanonicalBenchmarkDefinitionIdentity` — all twenty §15 coordinates, every one
  mandatory and every one in the digest.
* `BenchmarkScope` (`PLATFORM_WIDE` | `TENANT`) — §15 row 5's "may denote a
  platform-wide scope explicitly, **never by omission**", cross-checked against
  the tenant it carries.
* `BenchmarkApplicabilityCoordinate` (`APPLICABLE` | `NOT_APPLICABLE`) — §15 rows
  6-7's "explicitly `NOT_APPLICABLE` otherwise — never omitted", cross-checked
  against the value it carries.
* `BenchmarkMeasurementSemantics` — §15 rows 8-14, all seven required, no partial
  state.
* `BenchmarkEffectivePeriod` — §15 row 15, half-open `[effective_from,
  effective_to)` per §17.9, with `TemporalBoundDeclaration` making an open right
  bound a recorded decision rather than a `None` a reader must interpret.
* `BenchmarkSourceRequirements` — §15 row 16; an order-irrelevant requirement set
  normalized to canonical order in the contract, with duplicates **refused**
  rather than de-duplicated.
* `BenchmarkApprovalReference` — §15 row 17, carrying the exact content digest
  the approval binds (B-5: "approval binds an exact **content digest**, not a
  name and not an intent").
* `BenchmarkSupersessionDeclaration` — §15 row 20. Mandatory, because §15 rules
  that its absence "never implies 'not superseded'". Its one ratified status is
  `UNDETERMINED`: §17.12 admits supersession *only* through a structured
  successor reference, and that reference is **DD-4**, deferred.

### Added — vocabularies

* `BenchmarkLifecycleState` — the ADR §29 lifecycle: `AUTHORED` → `APPROVED` →
  `REGISTERED` → `REVOKED` (terminal), with `BENCHMARK_LIFECYCLE_TRANSITIONS` as
  a closed, immutable relation and every one of the sixteen ordered pairs tested.
  No `SUPERSEDED` state (DD-4), no `EXPIRED` state (expiry is temporal, and a
  state that changed with time would be the clock-driven mutation §22.9 forbids),
  no self-transition.
* `BenchmarkRefusalReason` — seventeen typed, `BENCHMARK_`-namespaced refusals
  (DD-1, §16.3, §22.11). **No success member.** No BR-2 runtime code is minted.
* `BenchmarkStructuralStatus` — one member, `STRUCTURAL_UNVERIFIED`, mirroring
  the merged `SystemBindingAuthenticityStatus` discipline ADR §14.5 cites.
* `BenchmarkScopeKind`, `BenchmarkApplicabilityDeclaration`,
  `TemporalBoundDeclaration`, `BenchmarkSupersessionStatus`.

### Added — canonicalization (ADR §22, DD-9)

* `canonical_bytes` / `canonical_digest` — one deterministic, versioned,
  domain-separated path. Framed
  `{"body", "canonicalization", "domain", "type"}`; UTF-8 JSON with sorted keys
  and no insignificant whitespace; total field inclusion; explicit `null`; UTC
  normalization with microseconds preserved; naive datetimes, non-NFC strings,
  padded strings, floats (and therefore `nan`/`inf`), mappings, `bytes` and
  unknown types all **refused**, never coerced, never normalized.
* `BENCHMARK_REGISTRY_CANONICALIZATION_VERSION` =
  `ugence.benchmark-registry/canonicalization/v1`.
* `BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN` =
  `ugence.benchmark-registry/benchmark-definition-identity/v1` — the **only**
  domain BR-1 mints, because BR-1 introduces exactly one artifact class. No BR-2
  service, resolution-result, signed-publication, revocation, trust-anchor or
  audit domain is reserved, and no successor domain (DD-4).

### Added — typed errors

* `BenchmarkContractError` (a `ValueError`), `BenchmarkCanonicalizationError`,
  `BenchmarkLifecycleError`, each carrying the ratified refusal code.

### Enforced structural invariants

* **B-5** — the cited approval must bind this definition's exact content digest.
* **B-3 / B-4** — the publisher may not also be the approving authority.
* Applicability, scope and temporal-bound declarations are cross-checked against
  the values they carry; neither half is silently repaired into the other.
* Subclasses and duck-typed lookalikes are refused at every load-bearing
  boundary (`type(x) is T`, never `isinstance`).

### Explicitly **not** in this version

Everything §30 assigns to **BR-2**: the registry, the trusted resolver, §16.2's
six-stage admission ordering, append-only registration, byte-identical
idempotence and typed conflict, exact-coordinate resolution execution, publisher
signature and key trust, trust anchors, signed and verified revocation records,
cross-tenant non-disclosure, historical resolution.

Also absent: any `latest()`/`current()` selection or mutable alias (B-8, §17.2);
any benchmark result, comparison, observation or threshold (B-12, §18); any
evidence, receipt or verification artifact (that vocabulary belongs to the
Trusted Evidence Authority); any Policy Authority integration or entitlement
(§19, DD-3); any Readiness / M-3R.4 / UVI-EV-1 integration (§20); any Governed
Value, forecasting, attribution, valuation or ROI surface (§21); any Cloud
Scaling integration; any deployment or execution authorization.

No placeholder, stub, permissive resolver or field reserved for a later
milestone ships. No `CONTRACT_VERSION` constant is minted — that is the
*provider* convention in this repository, and the contract-shape packages carry
only `__version__`.

### Dependency posture

A **leaf with no runtime dependency at all** — no Ugence package, no third
party, stdlib only. ADR §23 permits a dependency on `governance-contracts`; BR-1
takes the narrower option because **DD-2** is explicitly blocked on "the concrete
contract shapes from TEV-1/BR-1", and importing that leaf now would decide DD-2
by implementation. `BenchmarkReference` stays Governance Contracts' single merged
definition and is never redefined here (§6.3); `AssessedSystemBinding` likewise
(§14); no `SystemManifest` is defined (DD-11).

Nothing in the monorepo imports this package: §30 authorizes no consumer
integration at BR-1, and a test enforces it in both directions.

### Verification

* **582** package tests (contract + packaging).
* **51** independent adversarial probes, importing only the curated API and the
  standard library — run against the source tree **and** inside the installed
  wheel.
* Wheel **and sdist** built from a clean tree; isolated `--no-index` install into
  a fresh venv with no system site packages and no `PYTHONPATH`; the installed
  distribution list is exactly `ugence-benchmark-registry==0.1.0` and nothing
  else.
* Exact public-API parity across source exports, `api.__all__`, top-level
  re-exports, `public_api.json`, the wheel and the isolated install — every
  symbol, kind, enum member **and order**, dataclass field **and order**, and
  pinned constant value.
* Pinned canonical bytes and digests reconstructed from hand-written literal
  bytes with `hashlib` alone, in the tests **and independently** in the
  distribution verifier.
* Machine-checkable coordinate coverage: all twenty §15 rows resolve, all 28
  leaves of the identity tree are present in the canonical body, and each is
  independently digest-sensitive.
