# Implementation impact record — UVI ADR §26.3, §26.8, §26.9 rulings (2026-09-09)

- **Status:** RECORDED, pre-implementation. **No code has been changed under these
  rulings.** The owner ruling requires the canonical projection, derived-ID/digest
  impact and compatibility treatment to be recorded *before* changing code; this
  document is that record.
- **Governs:** decisions 2, 3 and 4 of the 2026-09-09 ruling. Decision 1 (delete the
  inert `api_snapshot_hash`) needs no impact record — see §0.
- **Ruling text and rationale:** UVI ADR §26.3, §26.8 (via the D-9 amendment), §26.9,
  §20 and §16.

Every file, line and behaviour below was verified against the repository at
`8d8d8fa0`. Nothing here is inferred from documentation.

---

## 0. Decision 1 — delete `api_snapshot_hash` (no impact record required)

`packages/governance-contracts/tests/serialization/frozen_contract_fixtures.json:220`
holds `"api_snapshot_hash": null`. A repository-wide grep finds **exactly one
reference — the definition itself**; no test, script or workflow reads it.

- **Canonical projection:** none. The field is test-fixture data, not a contract.
- **Derived ID / digest impact:** none. It participates in no digest.
- **Compatibility:** none. Deleting an unread null key changes no behaviour.
- **Replacement:** none is authorized. `tests/packaging/test_public_api.py` already
  owns the public-API check; the ruling forbids a second hash mechanism. The
  fixture's surrounding comment should point at that test so the absence is not
  later mistaken for an omission.

**Not deleted by this document.** The edit itself is implementation.

---

## 1. Decision 2 — `required_source_basis=SYNTHETIC` requires `EVALUATION_ONLY`

### What changes

`ComponentEvidenceRequirement`
(`packages/uvi-policy-contracts/src/ugence_uvi_policy_contracts/contracts/policies.py:253`)
today validates `required_source_basis` only for enum membership (`:275-276`). It
carries **no scope axis at all**, so the pairing the ruling requires is currently
inexpressible — a field must be added, not merely a check.

Present fields: `component`, `requirement_class`, `required_source_basis`,
`required_attribution`, `required_verification`.

### Canonical projection

`ComponentEvidenceRequirement` is not digested directly. It is carried in
`ValuationPolicy.required_components` (`policies.py:303`), and `ValuationPolicy`
**does** expose `canonical_digest()`. So the requirement's field set is inside the
policy's canonical projection: **adding a field changes `ValuationPolicy`'s canonical
bytes and therefore its digest**, for every policy that contains at least one
`ComponentEvidenceRequirement`.

### Derived-ID / digest impact

- `ValuationPolicy.canonical_digest()` moves for any policy carrying a component
  requirement. It does **not** move for policies with `required_components = ()`
  if the new field is omitted from the projection when unset — **which serialization
  discipline applies is the first thing implementation must settle, not assume.**
- Downstream: `PolicyReference.content_digest` is a caller-supplied token, not
  computed here, so no automatic cascade exists. Any stored policy artifact whose
  digest was computed over the old projection must be re-derived or explicitly
  grandfathered; this document does not choose between those.

### Compatibility

- **No SYNTHETIC requirement exists anywhere in the repository today.** The only
  construction outside `src/` is
  `uvi-policy-contracts/tests/contract/test_policy_contracts.py:305`, using
  `SourceBasis.OBSERVED`. The new refusal therefore breaks no existing caller.
- The new field must be optional with an unset default, or every existing
  `ComponentEvidenceRequirement` construction becomes a TypeError.
- The refusal is **construction-time**, per the ruling — not a later validation pass.

### Tests that must be revisited

`uvi-policy-contracts/tests/contract/test_policy_contracts.py` (82 tests in the
package today, all passing); any `ValuationPolicy` digest assertion.

---

## 2. Decision 3 — `EvidenceStatusView` must carry `usage_scope`

### What changes

`EvidenceStatusView`
(`packages/capabilities/reasoning-method-governance/src/ugence_reasoning_method_governance/contracts/envelopes.py:75`)
has fields `record_digest`, `source_basis`, `attestation_status`,
`verification_status`, `attested_fields`, `verified_fields`. It enforces one
internal rule — `VERIFIED` presupposes `ATTESTED` — and **no scope constraint**.

### The view does participate in canonicalization — this is the load-bearing finding

It is not a free-floating projection:

- `ReadinessComparisonResult.evidence_status: Tuple[EvidenceStatusView, ...]`
  (`reasoning-method-governance/contracts/ports.py:143`).
- That result carries `schema_version` (`ports.py:139`),
  `COMPARISON_RESULT_SCHEMA_VERSION = "readiness_comparison.result.v1"`
  (`ports.py:27`), and a settled `result_digest` (`ports.py:149`, `:182`).
- `_stable_digest()` excludes only `result_digest`, `produced_at` and `assessments`
  (`ports.py:187`) — **`evidence_status` is inside the digested body.**

### Derived-ID / digest impact

- Adding `usage_scope` changes the canonical projection of every
  `ReadinessComparisonResult` carrying at least one view, and therefore moves
  `result_digest`.
- **`COMPARISON_RESULT_SCHEMA_VERSION` must move** from
  `readiness_comparison.result.v1`. The ruling requires this be determined before
  implementation; it is determined here as *required*. The successor identifier and
  whether v1 remains readable are implementation decisions this record does not make.
- `readiness-comparison` pins `ENGINE_IDENTITY`/`engine_version` in its result; a
  schema movement should be reflected there deliberately rather than incidentally.

### Compatibility

- The sole construction path is `readiness-comparison/engine.py:274`, which copies
  `source_basis` from `ReasoningMethodExecutionRecord`. That record's `source_basis`
  is a **`ClassVar` pinned to `OBSERVED`** (`record.py:38`, `:191`), so in practice
  no view can carry `SYNTHETIC` today. The gap is **latent, not active** — which is
  why the ruling is a hardening, not a defect fix.
- Because the producing record has no scope axis either, `engine.py:274` cannot
  simply forward one. The ruling forbids silently defaulting a missing scope, so
  implementation must decide where the scope originates. **This is the open
  implementation question**, and it may require `ReasoningMethodExecutionRecord` to
  carry the axis too — a second contract movement the ruling did not name.

### Tests that must be revisited

`reasoning-method-governance` (62 tests) and `readiness-comparison` (45 tests), both
green today; every `result_digest` and schema-version assertion in either package.

---

## 3. Decision 4 — `SystemManifest` in `governance-contracts`, opaque references

### Stop condition: cleared

The ruling says to **stop if implementing the opaque collections requires a new
shared neutral reference type prohibited by an existing ruling**. It does not.

- `MetricClaim.policy_refs: tuple[str, ...]` and `benchmark_refs: tuple[str, ...]`
  already carry policy and benchmark references **opaquely, as plain strings, inside
  the neutral leaf**. Direct precedent, same package.
- `AssessedSystemBinding` already establishes the paired `*_ref` + `*_digest`
  primitive discipline across five pairs, all `str`/`datetime`.
- So the established primitive ref-plus-digest discipline suffices. **No new shared
  neutral reference type is needed and none is authorized.**

### Canonical projection

`SystemManifest` is a **new** type: it has no existing projection to move. It must
be constructed to the neutral leaf's existing canonicalization discipline from the
outset.

The one projection that **does** move is the relationship, not the data:
`AssessedSystemBinding.system_manifest_ref` / `system_manifest_digest` remain
**exactly as they are** — opaque `str` fields. The binding gains **no** typed field
pointing at `SystemManifest`, or the neutral leaf would acquire an internal coupling
the opaque-token discipline exists to prevent. **`AssessedSystemBinding`'s canonical
projection and digest do not move**, and its frozen expectations stand.

### Derived-ID / digest impact

- `AssessedSystemBinding`: **none.** No field added, no default moved.
- `governance-contracts` `CONTRACT_VERSION`: **stays `1.0.0`.** `SystemManifest` is
  another additive neutral family, by the same test §26.9 just closed — provided no
  provider module imports it. That must be asserted, not assumed.
- Package `__version__` advances (0.8.0 → next minor), consistent with how G7/G8/G4,
  DE-5, VR-5 and AE-5 were each released.
- `public_api.json` gains the new symbols; `tests/packaging/test_public_api.py`
  enforces parity and will fail until regenerated — the intended behaviour.

### Compatibility

- Purely additive. No existing caller constructs a `SystemManifest`, and none can be
  broken by one appearing.
- The `system_manifest_ref` + `system_manifest_digest` pair keeps working unchanged
  for callers that never mint a manifest, so adoption is opt-in.
- **The substantive-binding requirement is a real constraint on the shape**: the
  ruling forbids a nominal manifest, so the type must make empty component bindings
  unconstructable rather than merely discouraged.

### Boundary assertions required

`governance-contracts` imports **no** UVI, Policy Authority, readiness, risk or
execution package today (verified: the only occurrences of those names are docstring
prose). The new module must not change that, and
`tests/packaging/test_leaf_dependency.py` should be extended to cover it explicitly.

---

## 4. The five open questions — SETTLED (2026-09-09)

Each was settled against the repository, not by preference. Two were decided *for*
us by existing helpers; one dissolved on inspection.

### Q1 — where does `EvidenceStatusView.usage_scope` originate? **No second contract movement.**

`ReasoningMethodExecutionRecord` already declares its three evidence axes as
**read-only v1 `ClassVar` constants** (`record.py:38-41`, `:191-193`), guarded by
`guard_kwargs(...)` so no producer can set them and by an assertion that they never
become instance fields (`record.py:244-247`). `usage_scope` joins them as a fourth:
`RECORD_V1_USAGE_SCOPE = EvidenceUsageScope.GENERAL`, added to
`EVIDENCE_AXIS_FIELD_NAMES`.

This is **not** a silent default — it is an explicit schema constant, exactly as
`source_basis = OBSERVED` already is, and an `OBSERVED` record is by construction
never `SYNTHETIC`. Crucially it is **free of digest impact**: `payload()` iterates
`dataclasses.fields()` (`contracts/_util.py:95-100`), and `ClassVar`s are not
fields, so the record's canonical projection and `record_digest` do not move and
`RECORD_SCHEMA_VERSION` stays `reasoning_method.execution_record.v1`.
`engine.py:274` then forwards `r.usage_scope` explicitly, mirroring how it already
forwards `r.source_basis`.

### Q2 — successor for `COMPARISON_RESULT_SCHEMA_VERSION`; is v1 still readable?

`readiness_comparison.result.v1` → **`readiness_comparison.result.v2`**. v1 is **not**
retained: the package is `RESEARCH_ONLY` / `REQUESTER_ASSERTED`, approval-bearing for
nothing, and no store replays a v1 result, so there is no reader to keep compatible.

**One downstream coupling, and it is a signed one.**
`packages/integration/reasoning-method-result-attestation` signs a projection
containing `schema_version` and `result_digest`
(`tests/test_deterministic_digest.py:50-75`). The *shape* of that projection does not
change — it carries `result_digest` opaquely and never `evidence_status` — but both
its `schema_version` string and its pinned digest values move. Its
`reasoning_method.signed_comparison_result.v1` envelope version does **not** move: the
envelope is unchanged; only the value it signs over is.

### Q3 — is an unset scope omitted from or included in the projection? **Included, and this is not a choice.**

`uvi-policy-contracts` canonicalizes with `dataclasses.asdict(obj)`
(`contracts/_util.py:101-110`), which emits **every** field including `None`
Optionals. So `"required_usage_scope": null` enters the projection of every
`ComponentEvidenceRequirement`, and `ValuationPolicy.canonical_digest()` moves for
every policy carrying at least one requirement — set or unset.

Omitting it would require changing the shared `canonical_digest` helper, which would
move digests for `GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy`,
`ReadinessPolicy` and `AssessmentContext` as well. **The helper is not touched.**

### Q4 — re-derive or grandfather policy artifacts? **Neither: nothing is pinned.**

Every digest assertion in `uvi-policy-contracts` is *relative* — `a.canonical_digest()
== b.canonical_digest()`, or a value captured within the same test
(`test_policy_contracts.py:437`, `test_hardening_immutability_temporal.py:146,172,184`).
`policy-authority` computes its content digests rather than pinning them
(`verify_policy_authority_distribution.py:117`); a grep for 64-hex literals in its
fixtures and verifier returns nothing. No stored artifact needs re-derivation and no
grandfathering clause is required.

### Q5 — `SystemManifest` component-binding shape

Component bindings are tuples of frozen `(ref, digest)` pairs — **pure strings, no
datetimes, no nested collections**.

That is a hard constraint discovered in the target module, not a stylistic
preference: `_canonical_payload` (`system_identity.py:181-196`) normalizes instants in
a **single top-level pass** over `dataclasses.asdict`, and its own docstring says this
is sound only because "every field of `AssessedSystemBinding` is a scalar". A datetime
nested inside a component binding would silently escape UTC normalization and break
digest stability. String-only pairs keep the existing helper correct as written.

The manifest binds five families — models, prompts/configurations, tools/capability
sets, workflows and policies. The ruling forbids a nominal manifest, so **at least one
component binding must be present**, enforced at construction rather than documented.

---

## 5. Implementation status

All four rulings are **implemented** in the commit carrying this record. See that
commit message for the verification matrix. Nothing in §4 was left for later.
