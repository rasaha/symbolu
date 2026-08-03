# Changelog — ugence-context-minimization

All notable changes to this package are documented here. This package follows
SemVer for the distribution version and carries a separate `CONTRACT_VERSION` for
the minimization contract (result shape, reason-code vocabulary, oracle protocol).

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
