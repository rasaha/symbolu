# Changelog — ugence-context-minimization

All notable changes to this package are documented here. This package follows
SemVer for the distribution version and carries a separate `CONTRACT_VERSION` for
the minimization contract (result shape, reason-code vocabulary, oracle protocol).

## 0.2.0 — measurable token accounting (CM-TA1)

**Package maturity: `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED`** (upgrade to
`IMPLEMENTED_AND_CI_VERIFIED` only after the scoped Actions run is observed green).
Contract version `1.0.2` → `1.1.0`. **Purely additive**: the minimization algorithm,
protected-span behavior, oracle equivalence semantics, and BOTH fingerprint digests
(`outcome_fingerprint`, `run_fingerprint`) are byte-unchanged. No provider SDK, no
tokenizer, no network/database/filesystem persistence, and no pricing authority
enters the leaf.

### Added — a new neutral, stdlib-only `token_accounting` module
Three measurements are kept **distinct** and never collapsed into one field:

- **A — context reduction** (unchanged): `MinimizationResult.original_tokens /
  resulting_tokens / achieved_reduction`. The accounting module *copies* these; it
  never re-runs or mutates a minimization result.
- **B — complete-request estimate**: `RequestTokenEstimate` — the estimated input-token
  size of the *complete serialized request* (system + messages + minimized context +
  tool definitions + schemas + provider wrappers), produced by an **injected**
  `RequestTokenCounter`. The core ships only the transparent `DefaultApproximateRequestCounter`
  (word/punctuation, labelled `DEFAULT_APPROXIMATE`) — it implements **no** provider tokenizer.
- **C — provider-reported usage**: `ProviderTokenUsage` — optional non-negative ints for
  `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`,
  `reasoning_tokens`, `total_tokens`, plus `provider_request_id` / `usage_schema` /
  `adapter_id` / `adapter_version`. **Unknown is `None`, never fabricated as zero.**
  Cached/cache-write/reasoning are provider-specific subsets/details and are **not** added
  into input/output; `derived_total()` = input+output only and is explicitly *derived*,
  distinct from the provider-reported `total_tokens`.

New contracts: `TokenCountBasis`, `AttemptStatus`, `UsageAvailability`,
`RequestComponents`, `RequestTokenEstimate`, `ProviderTokenUsage`, `RequestAttribution`,
`ApiCallTokenRecord` (domain-separated `record_fingerprint`, `api-call/1`),
`LogicalRequestTokenSummary` (`logical-request/1`), the `RequestTokenCounter` and
`TokenAccountingSink` protocols, the `DefaultApproximateRequestCounter` and
`InMemoryTokenAccountingSink` reference implementations, and the
`prepare_api_call_measurement` / `reconcile_api_call_measurement` /
`aggregate_logical_request_usage` APIs.

### Accounting semantics (enforced, fail-closed)
- A retry is a **new** `attempt_id`; three attempts under one logical request stay three
  records. Retried/failed attempts are preserved separately, never collapsed into the
  final success.
- A failed attempt with known usage still contributes to consumption; a failed/exception
  attempt with no usage is `UNAVAILABLE_*` and keeps the logical-request summary
  `complete=False` — a gap is never reported as zero.
- Context-token savings and billed-token savings are **different quantities**; savings are
  attributed **once** per logical request (never multiplied per attempt).
- Negative / bool / float / NaN / inf / str token counts are rejected; a duplicate
  `attempt_id` with conflicting content is rejected (idempotent replay must be
  byte-identical). Deterministic replay reads no wall clock and generates no random ids —
  every id is caller-supplied.
- Provider-reported usage is authoritative for the API response being reconciled; it never
  overwrites the pre-call estimate, and it is **not** an invoice.

### Artifacts / docs
- New `artifacts/token_accounting_schema.json`; extended `acceptance_scenarios.json`;
  regenerated `public_api.json`. New `docs/TOKEN_ACCOUNTING.md`. Boundary, limitations, and
  security/failure-mode docs updated. Adversarial + compatibility tests added under
  `tests/accounting/` (deny/failure/unknown paths outnumber happy paths); the isolated
  single-wheel verifier now proves the accounting surface on the installed wheel.

### Audit remediation (pre-merge; part of the same unreleased 0.2.0 contract)
- **F1 — total provenance is never blended.** `LogicalRequestTokenSummary.provider_total_tokens`
  (which had folded derived input+output totals into a "provider" field) is **replaced** by three
  distinctly-named quantities: `provider_reported_total_tokens` (ONLY explicit provider
  `total_tokens`), `derived_total_tokens` (input+output, cached/cache-write/reasoning excluded),
  and `settlement_token_units` (the documented per-attempt selection: reported total if present,
  else derived), plus `attempts_reporting_total`. A field named "provider … total" now contains
  only provider-reported values. Corrected in place (0.2.0 is unreleased, so no consumer depends
  on the ambiguous shape); the summary schema and fingerprint reflect the new fields.
- **F4 — `InMemoryTokenAccountingSink` is thread-safe.** Duplicate detection and insertion are
  atomic under a lock; snapshots never observe partial state. Still a reference/in-memory sink,
  **not** durable storage (production persistence remains follow-on work).
- **N1 — tenant-safe attempt identity + sink partition.** `RequestAttribution.tenant_id` now
  rejects whitespace-only values and exposes `tenant_namespace`; new `canonical_tenant_namespace`
  helper maps absence to a domain-separated single-tenant namespace (`"s"`, never an empty
  string) and a present tenant to `"t:" + tenant`. `InMemoryTokenAccountingSink` partitions
  idempotency/conflict detection by the pair **`(tenant_namespace, attempt_id)`** — two tenants
  may store the same explicit `attempt_id` (both retained), same-tenant replay stays idempotent,
  same-tenant conflict is still rejected, and tenant isolation does **not** rely on record
  fingerprints. `tenant_id` was already bound into `record_fingerprint` via attribution. (The
  matching tenant-bound attempt-id derivation lives in the integration package.)
- **N3 — explicit retry linkage is tenant-scoped and fails closed.** New
  `ExplicitAttemptReference(attempt_id, tenant_id)` binds a parent attempt's tenant namespace
  explicitly (never inferred from the opaque id). `reconcile_api_call_measurement` replaces the
  raw `retry_of_attempt_id: str` parameter with `retry_of: ExplicitAttemptReference` and **fails
  closed** with `InvalidRequestError` when the reference's tenant namespace does not equal this
  attempt's (`prepared.attribution.tenant_id`) — BEFORE any record is built or written to a sink,
  and it never substitutes the current tenant for a supplied one. This makes cross-tenant retry
  linkage impossible in both the explicit and derived identity modes (both converge on one
  tenant-scoped reference). The raw opaque string form is removed (unreleased, so no alias
  retained). This is tenant-scope validation only; it does **not** assert the referenced parent
  record exists (durable referential-integrity remains deferred). New export:
  `ExplicitAttemptReference`.

## 0.1.2 — timestamp validation & fingerprint documentation correction

**Package maturity: `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED`** (upgrade to
`IMPLEMENTED_AND_CI_VERIFIED` only after the scoped Actions run is observed green).
Contract version `1.0.1` → `1.0.2`. A small, bounded post-merge correction; the
architecture from PRs #1291/#1292 is intact. No ActionGate integration, no H22, no
Hybrid LLM packaging.

### Fixed (fail-closed hardening)
- **Strict timestamp value contract.** A timestamp (`evaluation_time`, `valid_until`)
  must be a **finite real number that is not a Boolean**. Caller `evaluation_time`
  is validated at the public boundary and raises `InvalidRequestError` **before the
  oracle is called** (an invalid caller time never reaches an oracle, comparison, or
  fingerprint). Oracle `valid_until` is validated as oracle **output** and fails
  closed with `ORACLE_RESULT_MALFORMED` (never an uncaught `TypeError`; NaN never
  silently mis-orders a comparison). Inclusive expiry (`>=`) is unchanged. Validation
  order: type → key → oracle_id → contract_version → correlation → valid_until
  finiteness → required evaluation_time → inclusive expiry.
- **Strict canonical serialization.** All fingerprint/policy JSON now uses
  `allow_nan=False`, so a digest can never contain `NaN` / `Infinity`; a non-finite
  value raises deterministically instead of producing an unstable digest.
- **Token-count value contract.** Caller `ContextUnit.token_count` and injected
  `TokenCounter.count()` results must be **non-negative ints** (never bool, non-integral
  float, NaN, inf, or str); malformed values raise `InvalidUnitError`.
- **Scalar metadata contract.** Metadata keys must be `str`; values must be JSON
  scalars (`str` / finite number / `bool` / `None`). Non-scalar values are rejected
  with `InvalidUnitError` instead of being `str()`-coerced (which could embed
  nondeterministic object reprs).

### Changed
- **Token-counter run-fingerprint identity** is now module-qualified
  (`module.qualname`, or an explicit optional `counter_id`/`counter_version`) instead
  of the bare class name. The **run-fingerprint domain** is bumped honestly
  (`run/1` → `run/2`); `run_fingerprint` is a v0.1.1 addition with no external
  consumer. `InvalidRequestError` and `InvalidUnitError` now also subclass
  `ValueError` (backward compatible).

### Documentation corrected
- `outcome_fingerprint` does **not** bind token counts (or unit text, requested
  reduction/budget, evaluation time, reason codes, policy fingerprint, or oracle
  validity/correlation). Corrected in the `MinimizationResult` docstring,
  `fingerprint.py`, `docs/DETERMINISM.md`, and the generated invariance-contract
  artifact (now with explicit `binds`/`excludes` inventories). Token counts remain
  bound by `run_fingerprint`.

### Compatibility
- The **outcome digest is byte-unchanged** (a frozen fixture test guards it).
  `run_fingerprint` values change (domain `run/2` + counter identity) — no external
  consumer depends on them. New validation rejects inputs that were previously
  coerced/mis-handled; audited callers (Console) pass only valid values.

## 0.1.1 — oracle & result contract hardening

**Package maturity: `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED`** (upgrade to
`IMPLEMENTED_AND_CI_VERIFIED` only after the scoped Actions run is observed green).
Contract version `1.0.0` → `1.0.1`. A bounded post-merge contract correction; the
extraction from PR #1291 is otherwise intact. No ActionGate integration, no H22.

### Fixed (fail-closed tightening)
- **Inclusive oracle expiry.** An evaluation is now expired when
  `evaluation_time >= valid_until` (was `>`). The exact `valid_until` instant fails
  closed.
- **Expiry cannot be bypassed.** If `valid_until` is supplied but no `evaluation_time`
  is given, the run fails closed (`ORACLE_EVALUATION_TIME_REQUIRED`) instead of being
  treated as unexpired. The core still never reads a wall clock.
- **Mandatory correlation binding.** When the context carries a non-empty
  `correlation_id`, every usable oracle evaluation (baseline, reduced, per-unit
  restoration, final restored) MUST carry the identical id. Missing vs. mismatched
  are distinct, non-collapsed reason codes (`ORACLE_CORRELATION_MISSING` /
  `ORACLE_CORRELATION_MISMATCH`).
- **Stricter oracle-identity validation.** A non-empty string `oracle_id` and
  `contract_version` are now required; a string equivalence key alone is not enough.
- **`requested_reduction` preserved.** The result now echoes the caller's actual
  `target_reduction` on every path (was hardcoded to `0.0`).

### Added
- `MinimizationResult.requested_token_budget` — the caller's absolute budget, if any
  (a token budget is never reported as a fractional target).
- **Two fingerprints.** `run_fingerprint` binds the complete auditable run identity
  (request + policy fingerprint + oracle identity + outcome incl. reason codes);
  `outcome_fingerprint` binds the selected outcome only. `fingerprint` is retained as
  a **byte-identical deprecated alias** of `outcome_fingerprint` (unchanged from 0.1.0),
  so no consumer of the old digest breaks.
- Reason codes: `ORACLE_EVALUATION_TIME_REQUIRED`, `ORACLE_CORRELATION_MISSING`,
  `ORACLE_CORRELATION_MISMATCH`. The pre-0.1.1 `CORRELATION_MISMATCH` constant is kept
  (deprecated, no longer emitted, not in the curated vocabulary).

### Compatibility
- The outcome digest is unchanged; new result fields are additive. The emitted
  correlation reason code changed from `CORRELATION_MISMATCH` to the two specific codes
  — verified to have no live consumer (only the Console gateway consumes results, and it
  reads ids only).

## 0.1.0 — initial independent extraction

**Package maturity: `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED`** (CI recorded on the
PR; see the PR body for the run URL before claiming `IMPLEMENTED_AND_CI_VERIFIED`).

First independently-buildable release of the Context Minimization capability,
extracted from `experiments/actiongate_context_ablation/` into a clean, stdlib-only
leaf package. Contract version `1.0.0`.

### Added
- Immutable neutral models: `Context`, `ContextUnit`, `MinimizationRequest`,
  `MinimizationResult`, `OracleEvaluation`, `ProtectionResult`, `MinimizationMode`,
  `EquivalenceStatus`, `MinimizationPolicy`.
- Neutral runtime protocols: `InvarianceOracle`, `ProtectionProvider`, `TokenCounter`.
- **Structural mode** (`structural_minimize` / `deduplicate_context`) — structurally
  lossless exact-duplicate / redundancy-set removal; needs no oracle.
- **Oracle-verified mode** (`minimize_context`) — extractive removal proven equivalent
  to the full context against a neutral invariance oracle, with per-span restoration
  and full-context fail-closed fallback.
- Deterministic reason-code vocabulary, error taxonomy, and result fingerprinting.
- `py.typed`, machine-readable artifacts (`public_api.json`, `invariance_contract.json`,
  `minimization_result_schema.json`, `reason_codes.json`, `acceptance_scenarios.json`),
  an isolated-install verifier, and scoped CI.

### Changed (behaviour hardened vs. the experimental prototype)
- **Protected-span invariant fixed.** The experimental `structural_compress` accepted a
  `protected_ids` argument but ignored it, so a protected unit could be dropped when a
  duplicate remained. The canonical contract is: **a protected unit is never removed by
  any stage**; deduplication applies only to unprotected units; two protected duplicates
  are both retained (v1 contract). See `docs/PROTECTION_CONTRACT.md`.
- **Equivalence signature is now opaque and oracle-owned.** The experiment compared a
  `repr()`-based tuple signature computed inside the compressor. The canonical core
  compares an **opaque, oracle-supplied `equivalence_key`** and never interprets
  ActionGate decision structures. See `docs/INVARIANCE_CONTRACT.md`.
- **The core imports no ActionGate.** The oracle is injected via a neutral protocol; a
  concrete ActionGate-derived oracle lives outside this package.

### Migrated
- `ugence_console_api/capabilities/context_gateway.py` now imports the canonical
  distribution (structural mode) instead of injecting `experiments/` onto `sys.path`.

### Intentionally excluded / preserved (not in the wheel)
- The frozen benchmark corpus, real-model harnesses/clients, RunPod scripts, plots,
  detector-training code, and result directories remain in the experiment as **frozen
  legacy evidence** — not rewired, so historical fingerprints are unchanged.
