# ugence-benchmark-registry — BR-1: benchmark-definition contracts

Internal platform infrastructure for the **Ugence Benchmark Registry**, the one
shared, platform-wide registry ratified in
[`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](../../docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md)
(B-1, §6.2). This distribution implements milestone **BR-1** of §30:

> **BR-1 — Benchmark Definition Contracts.** Benchmark identity (§15), lifecycle
> state, structured references. **Contracts only; no registry.**

| | |
|---|---|
| Distribution | `ugence-benchmark-registry` |
| Namespace | `ugence_benchmark_registry` |
| Version | `0.1.0` |
| Runtime dependencies | **none** — stdlib only |
| Curated public symbols | 31 |
| Milestone | **BR-1**, implemented. **BR-2 not started.** |

---

## 1. The question BR-1 answers

**Which exact benchmark definition is this, and what does it declare about
itself?**

It answers that precisely enough that

* moving **any** one of ADR §15's twenty identity coordinates changes the
  digest, so a definition favourable under one tenant, geography, domain,
  metric, unit, population, aggregation, observation window or effective period
  is mechanically detectable when replayed under another; and
* a reference to "the latest version" **cannot be written down** — not
  discouraged, not validated away later, but unrepresentable in the type (B-8,
  §17.2).

## 2. The question BR-1 does **not** answer

**May this benchmark be trusted?** Nothing in this package can answer that.

ADR B-9 is the governing rule: *"Possession is not validity; retrieval is not
resolution."* Constructing any object here is possession. Answering the trust
question needs admission, approval verification, publisher key trust,
append-only registration and exact-coordinate resolution — the whole of §16.2 and
§17 — and every one of those is **BR-2**.

Concretely, a `CanonicalBenchmarkDefinitionIdentity` that constructs proves
**only** that it is internally consistent and digest-bound. It proves nothing
about:

| Unproved | Owner |
|---|---|
| that the declared **content digest** matches any actual benchmark content | §16.2 stage 2 — BR-2 |
| that the cited **approval** exists, was issued by an entitled approver, or verified | §16.2 stage 3 — BR-2, through an external approval boundary (B-4: the Registry never approves its own input) |
| that the **publisher** is authorized, or that any signature or key is trusted | §16.2 stage 4 — BR-2 |
| that the declared **lifecycle state** was ever reached, or is admissible | §16.2 stage 5 — BR-2 |
| that it was ever **registered**, at this or any coordinate | §16.2 stage 6 — BR-2 |
| that it **resolves**, is unrevoked, unsuperseded, or disclosable to this tenant | §17.6, §17.10-13 — BR-2 |

Every identity therefore reports, permanently and non-settably:

```python
identity.structural_status            # STRUCTURAL_UNVERIFIED — one enum member
identity.trusted_resolution_performed # False
identity.unresolved_reason            # BENCHMARK_RESOLUTION_NOT_PERFORMED
```

There is no member of `BenchmarkRefusalReason` that would represent success, and
`structural_refusals_at()` **always** contains
`BENCHMARK_RESOLUTION_NOT_PERFORMED` — there is no input for which BR-1 reports
"nothing is wrong".

---

## 3. What is structural, and what is trusted

| Structural (BR-1, here) | Trusted (BR-2, not started) |
|---|---|
| the exact coordinate that *names* one benchmark version | resolving that coordinate to a record |
| the twenty-coordinate identity and its digest | verifying the content digest against real content |
| an approval **reference** that binds a content digest | verifying that approval at a trusted boundary |
| a publisher **identifier** | publisher authorization, signature, key trust, key revocation |
| a lifecycle **state** the artifact declares about itself | whether that state is admissible, and whether it was ever reached |
| a half-open effective period, evaluated at a caller-supplied instant | whether the definition is *currently valid* under §17 |
| a supersession declaration of `UNDETERMINED` | determining the active successor (DD-4, then BR-2) |
| the typed refusal vocabulary | the refusals a running registry emits |

Two cross-field invariants **are** enforced here, and neither is a verification:

* **B-5** — the cited approval must bind *this* definition's content digest.
  "Approval binds an exact **content digest**, not a name and not an intent." An
  approval for different content cannot travel with the definition.
* **B-3 / B-4** — the publisher may not also be the approving authority. "No
  component occupies two adjacent roles for the same benchmark version", and B-4
  requires approver ≠ registrar be "checked by the Registry itself, not merely
  assumed". Checking two declared identifiers is what BR-1 can do; verifying that
  either identity is genuine remains BR-2's.

---

## 4. Why a benchmark definition is not a benchmark result

ADR §18 separates four artifacts and rules that **"no renaming promotes one into
another"**:

| Artifact | What it is | Owner |
|---|---|---|
| **Benchmark definition** | an approved, versioned reference describing *what is measured and how comparison is interpreted* | **Ugence Benchmark Registry** — this package holds its *identity* |
| **Observed measurement** | an evidence-backed value | measurement systems; its evidence is verified by the Trusted Evidence Authority |
| **Benchmark comparison result** | a deterministic comparison of a verified observation against an exactly resolved definition | the consuming evaluation engine |
| **Policy decision** | whether that comparison matters | Ugence Policy Authority |

B-12 is categorical: **"the Registry computes nothing."** No object in this
package holds a measured value, a threshold verdict, a comparison, a readiness
determination or a monetary figure, and no exported callable computes one. The
package tests and the adversarial probes both assert this on the actual surface.

The definition is not its **content** either. Benchmark content is authored by
domain owners (§7.2 row 1) and appears here only as §15 row 4's declared content
digest — so there is nothing in this package a caller could mistake for the
benchmark itself.

## 5. Why a Policy Authority citation is not a resolution

ADR §19: *"A policy reference to a benchmark is not proof that the benchmark
resolved successfully. A policy artifact may name benchmark coordinates that are
unregistered, revoked, superseded, expired, or belong to another tenant."*

A `BenchmarkCoordinate` built from this package is a **name**. Naming is not
finding, and finding is not trusting — §17.14 keeps "retrieval distinct from
trusted resolution … different operations, different return types", and BR-1
implements neither. There is no resolver, no store and no lookup function
anywhere in the package, and the milestone-boundary test asserts it structurally.

Nothing here integrates with the Policy Authority, and nothing here is
entitled by one (B-6: benchmark signing is *not* silently assigned to the Policy
Authority; whether an instance may act as approval verifier for a family is
**DD-3**, still open).

---

## 6. ADR §15's twenty coordinates

Every row is represented **explicitly**. None is optional, none has an implicit
default, and none can be written into a free-form dictionary: the canonical
encoder refuses mappings outright, so an "extension bag" is not expressible, and
a test asserts no public dataclass declares a mapping-typed or metadata-named
field.

| §15 | Coordinate | Field | In the digest |
|---|---|---|---|
| 1 | Benchmark id | `coordinate.benchmark_id` | ✅ |
| 2 | Family / type | `coordinate.benchmark_family` | ✅ |
| 3 | Semantic version | `coordinate.benchmark_version` | ✅ |
| 4 | Content digest | `content_digest` | ✅ |
| 5 | Tenant / scope | `coordinate.scope` (`PLATFORM_WIDE` \| `TENANT`) | ✅ |
| 6 | Geography | `coordinate.geography` (`APPLICABLE` \| `NOT_APPLICABLE`) | ✅ |
| 7 | Domain | `coordinate.domain` (`APPLICABLE` \| `NOT_APPLICABLE`) | ✅ |
| 8 | Intended outcome / metric purpose | `measurement.intended_outcome_ref` | ✅ |
| 9 | Metric identity | `measurement.metric_ref` | ✅ |
| 10 | Unit | `measurement.unit` | ✅ |
| 11 | Measurement protocol / reference | `measurement.measurement_protocol_ref` | ✅ |
| 12 | Population / cohort | `measurement.population_ref` | ✅ |
| 13 | Aggregation semantics | `measurement.aggregation_semantics_ref` | ✅ |
| 14 | Observation window | `measurement.observation_window_ref` | ✅ |
| 15 | Effective period | `effective_period` (half-open, §17.9) | ✅ |
| 16 | Source / provenance requirements | `source_requirements` | ✅ |
| 17 | Approval reference | `approval` | ✅ |
| 18 | Publisher identity | `publisher_id` | ✅ |
| 19 | Lifecycle state | `lifecycle_state` | ✅ |
| 20 | Structured supersession / revocation reference | `supersession` | ✅ |

`BENCHMARK_IDENTITY_COORDINATES` is the machine-readable form of that table, and
the coverage is **checked, not asserted in prose**: the tests walk every leaf of
the dataclass tree (28 leaves under the 20 rows), prove each is present in the
canonical body, and prove each is *independently* digest-sensitive. A field added
later without a corresponding coverage entry fails the suite.

**Absence is structurally impossible or explicitly declared.** Geography and
domain use `BenchmarkApplicabilityCoordinate`, whose two declarations are
cross-checked against the value they carry — §15: *"An explicit `NOT_APPLICABLE`
is a decision on the record; an omitted field is not."* Scope uses the same
discipline for §15 row 5's "may denote a platform-wide scope explicitly, never by
omission", and the effective period's open right bound uses
`TemporalBoundDeclaration` so "no end bound" and "an end bound the author forgot"
never share one encoding.

### Opaque tokens, and why

No unit vocabulary, metric registry, population taxonomy, aggregation grammar,
observation-window grammar, geography code list or domain code list is ratified
anywhere in the ADR, so **none is invented here**. Each is a required, exact,
digest-bound token — the discipline the merged `AssessedSystemBinding` applies to
`deployment_environment_ref`. Once one is ratified, the token points at it with
no shape change.

---

## 7. Exact-only coordinates

ADR B-8: *"A floating reference must be **unrepresentable** on the trusted path,
not merely discouraged."* `BenchmarkCoordinate` is where that is made literal.

| Refused | How |
|---|---|
| `latest`, `current`, `newest`, `head`, `tip`, `any`, `default`, `active`, `stable`, `*`, `-`, `?` — in any letter case | an explicit floating-token check on every coordinate identifier |
| `^1.2.3`, `~1.2.3`, `>=1.2.3`, `1.2.x`, `1.2`, `1.2.3 - 1.4.0`, `1.2.3 \|\| 1.3.0` | the version must parse as an exact Semantic Versioning 2.0.0 core-plus-prerelease string |
| `1.02.0` (a second spelling of `1.2.0`) | the published semver grammar rejects leading zeroes |
| `1.2.3+a`, `1.2.3+build.7`, `1.2.3-alpha+build` (SemVer **build metadata**) | refused, not merely ignored: SemVer 2.0.0 ignores build metadata for precedence, so `1.2.3` and `1.2.3+build` would be two coordinate spellings of one precedence-equivalent version — a "two spellings, one thing" gap B-8 exists to close, and the governing ADR authorizes no exception for it |
| a wildcard or range character anywhere (`* ? % ^ ~ > < \| , [ ] { }`) | refused in every coordinate token |
| a **partial** coordinate | every field is mandatory with no default; omission is a `TypeError` |
| a padded or non-NFC identifier | refused, never trimmed and never normalized |
| a case-insensitive near match | coordinates are case-sensitive; a different case is a different coordinate |

There is no `latest()`, no `current()`, no mutable alias, no implicit version
selection and no resolver — and the milestone-boundary test asserts that no
exported symbol, method or module-level function offers one.

---

## 8. Lifecycle (ADR §29)

Four states, three arrows, one terminal state. Every one of the sixteen ordered
pairs is tested individually.

```
AUTHORED ──▶ APPROVED ──▶ REGISTERED ──▶ REVOKED (terminal)
```

There is **no self-transition**, so "no change" can never be recorded as
lifecycle movement.

**`SUPERSEDED` is deliberately not a state.** §17.12 admits supersession
*"**only** through a structured successor reference"*, and that reference is
**DD-4**, deferred. A `SUPERSEDED` label with no structured successor would be
the "guessed supersession … unsigned authority decision" §17.12 prohibits.
Supersession is recorded instead by `BenchmarkSupersessionDeclaration`, whose one
ratified status is `UNDETERMINED` — and §15 row 20 is explicit that this
**never implies "not superseded"**. A consumer that needs to know must fail
closed (§17.13) until DD-4 lands.

**`EXPIRED` is deliberately not a state.** Expiry is a temporal question about
the declared effective period at a caller-supplied instant, and §16.2 stage 5
keeps "state admissible" and "effective period well-formed" as two separate
checks. Making expiry a state would create a second source of truth and would
require something to mutate the state as time passes — a clock-driven mutation,
which §22.9 forbids outright.

**`REVOKED` is a state**, because §16.2 stage 5's "state admissible" is vacuous
unless at least one state is not, and §19 names a revoked benchmark among the
things a resolution must refuse. A revoked version must be *representable* to be
refused. It carries no revoker, no revocation reference and no revocation
instant, so it can never masquerade as the signed, entitled, verified revocation
record §17.10-11 requires — that record is BR-2's.

**This relation is not the §16.2 six-stage registration ordering.** Those six
stages are the ordered checks a *registry* performs, and §30 assigns them to
BR-2. BR-1 implements none of them and mints no vocabulary for them.

---

## 9. Canonicalization and the digest boundary

One encoder, one digest path, no legacy path, no fallback, no dual acceptance.

| Pinned | Value |
|---|---|
| Canonicalization version | `ugence.benchmark-registry/canonicalization/v1` |
| Digest domain (the **only** one BR-1 mints) | `ugence.benchmark-registry/benchmark-definition-identity/v1` |
| Minimal identity digest | `9162ba434cff5b64678bf58f2dd8d9019ea8fafecc30817bf5953a62e7264a69` |
| Representative full identity digest | `f27044eafb0519399d71cac460d8820d5c0748aa8de9083346b394f434d93fd9` |
| Representative exact coordinate digest | `4c4395db71a09426bb52097f6029b808388ccba22df66ca79f77726b388d26ce` |

Both the package tests and the distribution verifier reconstruct the minimal
vector from **hand-written literal bytes** and `hashlib` alone, so the pin is
independent of the package's own encoder rather than a restatement of it.

Every canonical byte sequence is framed as

```
{"body": {...}, "canonicalization": <version>, "domain": <tag>, "type": <name>}
```

so the same body under two contract types can never produce the same bytes.

**Only the exact registered BR-1 contract classes are canonicalizable.**
Membership is decided by class *identity* — compared with Python's `is`
primitive, which no class or metaclass has a dunder method to override —
against a closed registry populated once at package import — never by
`__name__`, `__module__`, or the class object's own `__eq__`/`__hash__`. A
subclass, a same-named foreign dataclass defined anywhere else (even with its
`__module__` forged to match this package), a duck type, an arbitrary
dataclass, or a foreign class whose **metaclass** forges the class object's own
equality or hash to collide with a genuine registered class, is refused
outright: none of them reaches the encoder, and none of them produces bytes or
a digest, "borrowed" or otherwise. The registry itself lives entirely inside a
closure — there is deliberately no module-level name bound to the mapping (a
`MappingProxyType` stops the *mapping* from being mutated, but nothing stops a
module attribute that *holds* one from being rebound wholesale by any caller
who imported the module, underscore or not) — so no caller, including code
inside this package, can widen it after import by any means short of reaching
into the closure's cells directly, a fundamentally different and far deeper
capability than mapping mutation or attribute replacement, equivalent to being
able to rebind any other name in the process and not defended against here or
anywhere else in the standard library. Before producing bytes, `canonical_bytes`
also revalidates the complete exact contract graph reachable from the root, so
a frozen instance corrupted after construction via `object.__setattr__` into a
state its public constructor would have refused is refused here too, rather
than silently canonicalized.

**Exactly one domain is minted (DD-9).** BR-1 introduces exactly one artifact
class — the benchmark-definition identity and the coordinates that make it up.
BR-2's registration record, resolution result, signed publication, revocation
record, trust anchor and audit record do not exist, so their tags do not exist
either: a tag without an artifact is an unused constant a later milestone would
have to either honour or break. The successor/supersession domain is likewise
unminted, because DD-4 defers the reference itself.

### Encoder rules

* UTF-8 JSON, `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`.
* **Total field inclusion** — every dataclass field, always, by declared name.
  Nothing is dropped when empty; no field is conditionally omitted.
* `None` is explicit JSON `null`; `None` and `""` are distinct digests.
* Aware datetimes normalized to UTC, rendered `%Y-%m-%dT%H:%M:%S.%fZ` —
  **microseconds preserved**. **Naive datetimes rejected**, at construction and
  again at encoding.
* Strings must be Unicode **NFC**; non-canonical input is **rejected, never
  normalized**. Padding is rejected, never trimmed.
* `bool` dispatched before `int`, so a boolean is never serialized as `0`/`1`.
* **`float` rejected outright** — which subsumes `nan`, `inf`, `-inf`.
* **Mappings and `bytes` rejected**, so a coordinate cannot be hidden in a
  dictionary and every digest and reference has exactly one spelling.
* **Unknown types fail closed** — no `default=` hook, no `str()` fallback, no
  `repr()` anywhere in the module.
* Sequences preserve order. Where a collection's order is *semantically
  irrelevant* — §15 row 16's source/provenance requirements — the **contract**
  normalizes it into sorted order before it reaches the encoder, and duplicates
  are **refused, never de-duplicated**. The encoder itself never reorders, so a
  future collection whose order is meaningful keeps it.
* No wall clock, locale, timezone database, environment variable, filesystem or
  network is consulted, and `astimezone` is always called with an explicit UTC
  target. Asserted structurally over the whole source tree.

### The identity digest is not the content digest

§15 row 4's **content digest** is a coordinate the definition *declares*: the
digest of benchmark content that lives outside this package and that the Registry
never authors (§7.2 row 1). What `canonical_digest()` computes is the digest **of
the identity**. §16.2 stage 2's "declared digest equals the computed canonical
digest" check — over the benchmark *content* — is BR-2's, because it needs content
this package never holds.

---

## 10. Refusal vocabulary

Seventeen codes, all namespaced `BENCHMARK_`, all **refusals**. There is no
success member, and none can be added without changing the type's name and
documentation. DD-1 delegates the exact vocabulary to this milestone; §16.3 and
§22.11 require it to be stable, typed and namespace-scoped.

| Group | Codes |
|---|---|
| presence | `BENCHMARK_DEFINITION_MISSING` |
| structure | `BENCHMARK_MALFORMED_CONTRACT`, `BENCHMARK_CANONICALIZATION_FAILED` |
| identity | `BENCHMARK_IDENTITY_COORDINATE_MISSING` |
| exactness | `BENCHMARK_COORDINATE_NOT_EXACT` |
| applicability | `BENCHMARK_APPLICABILITY_INCONSISTENT` |
| measurement | `BENCHMARK_MEASUREMENT_SEMANTICS_INCOMPLETE` |
| source | `BENCHMARK_SOURCE_REQUIREMENTS_INVALID` |
| approval & roles | `BENCHMARK_APPROVAL_REFERENCE_INVALID`, `BENCHMARK_ROLE_SEPARATION_VIOLATED` |
| time | `BENCHMARK_EFFECTIVE_PERIOD_INVALID`, `BENCHMARK_NOT_YET_EFFECTIVE`, `BENCHMARK_EXPIRED` |
| lifecycle | `BENCHMARK_INVALID_LIFECYCLE_TRANSITION`, `BENCHMARK_REVOKED` |
| supersession | `BENCHMARK_SUPERSESSION_DECLARATION_INVALID` |
| resolution unavailable | `BENCHMARK_RESOLUTION_NOT_PERFORMED` |

**No BR-2 runtime code is minted.** Registry unavailable, lookup failure,
admission denial, slot conflict, approval-verification failure, signature and key
failures, trust-anchor failures, revocation-record verification, cross-tenant
disclosure outcomes, storage failure and successor resolution all belong to BR-2
(§30, §32), and a code no code path can raise is a promise about behaviour that
does not exist. Lifecycle-state *admissibility* is BR-2's rule; BR-1 ships only
the one condition it can decide structurally, `BENCHMARK_REVOKED`.

Every code except `BENCHMARK_DEFINITION_MISSING` — which only a consumer can
observe, since it means nothing arrived — is produced by a real code path, and a
test demonstrates each producer. `BENCHMARK_SUPERSESSION_DECLARATION_INVALID` is
the one **defence-in-depth** gate: it cannot fire while `BenchmarkSupersessionStatus`
has a single member, and a test pins the structure that makes it unreachable so
the claim fails loudly if that ever loosens. See the mutation ledger in the PR.

---

## 11. Dependency and authority boundary

```
governance-contracts                  (depends on nothing)
     ▲          ▲          ▲          ▲            ▲
uvi-policy-  agent-value-  governed-  ugence-      ugence-
contracts    readiness     value      benchmark-   trusted-evidence-
                                      registry     authority
                                      (BR-1 here)  (TEV-2, merged)
```

ADR §23 permits the Benchmark Registry to consume `governance-contracts` and
forbids it from importing TAP, the Policy Authority, any engine and the Risk
Authority. **BR-1 takes the narrower option and imports nothing at all**: DD-2 —
which contracts land in the neutral leaf — is explicitly blocked on "the concrete
contract shapes from TEV-1/**BR-1**", so importing that leaf now would decide DD-2
by implementation.

Confirmed by test:

* no `AssessedSystemBinding`, `SystemManifest` (DD-11) or `SubjectContext` is
  defined here;
* no competing `BenchmarkReference` is defined — that type is already merged in
  `ugence-governance-contracts`, and §6.3 assigns this capability the **values**
  it points at, not the type;
* no benchmark result type masquerades as evidence, and no evidence type appears
  at all;
* no reverse import: nothing in the monorepo imports this package, because §30
  authorizes no consumer integration at BR-1;
* the reverse-dependency guard is AST-based, so a *denylist mention* of another
  package is correctly read as asserting the boundary rather than crossing it;
* no module in this package writes the merged trusted-evidence package's module
  name, so that package's own (substring-based) reverse guard still passes.

**No TEV-1 or TEV-2 contract is modified by this milestone.** No file outside
`packages/benchmark-registry/` and the one new CI workflow changes.

---

## 12. What remains, and to whom

| Remaining work | Milestone | Status |
|---|---|---|
| Registry, trusted resolver, §16.2 admission ordering, append-only registration, byte-identical idempotence and typed conflict, exact-coordinate resolution, publisher signature and key trust, trust anchors, signed revocation, cross-tenant non-disclosure, historical resolution | **BR-2** | Not started |
| Structured successor/predecessor reference — shape, successor authorization, activation instant, predecessor invalidation, historical resolution across the boundary, cross-tenant/cross-family restrictions | **DD-4** | Deferred, undecided |
| Whether a Policy Authority instance is *entitled* to act as benchmark approval verifier, and for which families | **DD-3** | Deferred, undecided |
| Which contracts land in `governance-contracts` versus stay capability-local | **DD-2** | Deferred; unblocked by BR-1's shapes but deliberately not decided here |
| Readiness consumption of resolved definitions and receipts (§20) | **M-3R.4 / UVI-EV-1** | Not started; depends on TEV-2 **and BR-2** |
| Forecast / Observed / Attributed / Verified ROI (§21) | **GV-F / GV-O / GV-A / GV-V** (M-VAL.2–5) | Deferred |
| Attestation cadence for benchmark definitions | **DD-8** | Deferred |
| Production persistence, distributed concurrency, HSM/KMS posture | **DD-10** | Deferred |

### Milestone context

| Milestone | Status |
|---|---|
| Agent Readiness through M-3R.3 | Implemented / merged |
| TEV-1 | Merged |
| TEV-2 | Merged |
| **BR-1** | **Implemented in this PR, unmerged** |
| BR-2 | Not started |
| M-3R.4 / UVI-EV-1 | Not started |
| Forecasting / attribution / valuation / verified ROI | Deferred |

*This table records dependency context only. It is not a reconstruction of the
Agent Readiness ledger, which is a separate documentation-only workstream.*

**BR-1 is not trusted registry resolution.** Trusted resolution does not exist
until BR-2.

---

## 13. Name collisions this package is **not**

ADR §6.3 records that "benchmark" is already an overloaded word in this
repository. For the avoidance of doubt, this package is **not**:

| Existing use | Relationship |
|---|---|
| `comparative_governance_benchmark` — the frozen comparative-governance dataset gating `platform_freeze.verify`'s `benchmark_identity` check | **Unrelated.** An evaluation dataset, not a governed benchmark definition. Untouched; a test asserts this package never names it in code. |
| ML/performance harnesses (`CTM_plus/Bench/`, `symbolu_extensions/**/benchmarks/`, `symbolu_bcvf_llm/benchmark/`, `ndol/bench.py`) | **Unrelated.** Research performance measurement. |
| `BenchmarkReference` in `ugence-governance-contracts` | **Related, and not redefined.** The reference *type*; this capability owns the **values** it points at (§6.3). |
| `ugence-uvi-benchmark-registry` / `packages/uvi-benchmark-registry/` | **Prohibited by name** (B-1, §6.2). No UVI-scoped alias is minted, and a test asserts it. |

---

## 14. Layout and verification

```
packages/benchmark-registry/
├── pyproject.toml
├── public_api.json                                # machine-readable API snapshot
├── adversarial_probes.py                          # 57 independent probes, curated API only
├── verify_benchmark_registry_distribution.py      # wheel + sdist + isolated --no-index install
├── src/ugence_benchmark_registry/
│   ├── __init__.py            api.py    version.py    py.typed
│   └── contracts/
│       ├── canonical.py       # one encoder, one digest path, one domain
│       ├── enums.py           # applicability, scope, temporal bound, lifecycle, status
│       ├── errors.py          # typed contract errors carrying refusal codes
│       ├── identity.py        # the twenty ADR §15 coordinates
│       ├── lifecycle.py       # the closed ADR §29 transition relation
│       ├── reasons.py         # the seventeen typed refusals
│       └── _validation.py     # fail-closed structural primitives (private)
└── tests/
    ├── contract/     # identity, exactness, canonicalization, digest coverage,
    │                 # lifecycle, temporal, applicability, reasons, anti-forgery, NFC
    └── packaging/    # public API, dependency boundary, milestone boundary, no-clock
```

```bash
# package suite
python -m pytest packages/benchmark-registry/tests

# independent probes (curated API + stdlib only)
PYTHONPATH=packages/benchmark-registry/src \
    python packages/benchmark-registry/adversarial_probes.py

# wheel + sdist build, isolated --no-index install, API parity, pinned digests
python packages/benchmark-registry/verify_benchmark_registry_distribution.py
```

CI: [`.github/workflows/benchmark-registry-ci.yml`](../../.github/workflows/benchmark-registry-ci.yml).

---

## 15. Security posture

* **Nothing here is a trust decision.** No signature, no key, no trust anchor, no
  cryptography beyond one sha-256 digest path — and a digest is not a signature
  (B-5, §13.3). The milestone-boundary test asserts `hashlib` appears in exactly
  one module and that `hmac`, `secrets`, `cryptography`, `nacl` and `ecdsa`
  appear in none.
* **No I/O.** No filesystem, socket, subprocess, network or process-environment
  access anywhere in the package; asserted structurally.
* **No clock.** Every temporal method takes the instant as a mandatory parameter
  with no default (§22.9, §22.10).
* **Fail closed.** Every rejection is a typed refusal at construction. There is
  no permissive fallback, no repair, no silent normalization and no default that
  stands in for a missing decision.
* **Immutable.** Every contract is a frozen dataclass; caller-owned sequences are
  defensively copied; the lifecycle relation is a `MappingProxyType` over
  `frozenset`s so no consumer can widen it after import.
* **Forgery is detectable, not prevented by wishful thinking.** `object.__setattr__`
  defeats `frozen=True` — nothing in Python stops it — so the guarantee is stated
  honestly: the digest is a pure function of the fields, so a tampered identity
  matches no digest anyone recorded. The honest-status properties are *properties*
  rather than fields, so there is no instance slot to write at all, and a subclass
  that lies about itself gets its own `type` in the frame and therefore its own
  bytes.
