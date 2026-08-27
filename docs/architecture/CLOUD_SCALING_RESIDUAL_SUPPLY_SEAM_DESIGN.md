# Cloud Scaling — Residual-Supply Seam Design

**Status:** **IMPLEMENTED AND SYNTHETICALLY TESTED — NO THIRD BASELINE RATIFIED.**
The seam described here is built: `interval_from_residuals` is the single interval formula,
`compute_uncertainty` delegates to it unchanged, and `CalibrationResiduals` /
`CalibrationProvider` carry bank-sourced residuals through
`forecast_with_evidence(..., calibration=)` and
`run_replay_evaluation(..., calibration_provider=)`. Ruled prerequisites are closed:
`EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK`, `calibration_input_digest` on the interval and on
evidence at `capacity-forecast-evidence-2`, and the extended `UncertaintyError`.
**Date:** 2026-08-27
**Package (designed against, not modified):** `packages/capabilities/cloud-scaling-controller`
(`ugence-cloud-scaling-controller`, currently `0.4.0`)
**Prerequisite recorded in:** [`CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md`](CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md) §10.2
**Evaluation design:** [`ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md`](ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md)
**Governing ADR:** [`ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md`](ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md)

> **No third baseline is ratified, and no telemetry has been accessed.** Synthetic tests make
> the replay executable in principle; only the authorized replay on representative data can
> ratify anything. Legacy uncertainty semantics remain authoritative: the no-provider path is
> byte-identical, proven against 216 outputs frozen before the extraction.

> This document writes no code, changes no export, adds no enum member, touches no telemetry
> and runs nothing. Every signature below is **proposed and conceptual**; names are chosen to
> match existing repository vocabulary but are not committed contracts.

---

## 1. Decision

**Candidate 2 — a separate public residuals-to-interval function — is the canonical seam.**

The architecture has **one canonical interval formula** and **two explicit residual-production
paths** that both delegate to it:

```
(1) shipped path      rolling_origin_residuals(window, forecaster, config)
                          → [the one public interval function]

(2) evaluation path   causal prequential residual bank (manifest §7.2)
                          → typed immutable calibration input
                          → [the same public interval function]
```

The evaluation path may change **how residuals are collected**. It may not change **how a
given residual sequence becomes an interval**.

## 2. Verified repository facts

Everything in this section was read from the tree before the design was written; the design
depends on each item being true.

| Fact | Evidence |
|---|---|
| Residuals are **signed**, computed as `actual − predicted` | `.../forecasting/uncertainty.py:191` |
| They are sorted **ascending in place**, then read at `alpha/2` and `1 − alpha/2` where `alpha = 1 − requested_coverage`; endpoints are `point + offset` | `.../forecasting/uncertainty.py:222-236` |
| The quantile is **type-7 linear interpolation**, module-private `_quantile`, absent from `__all__` | `.../forecasting/uncertainty.py:137-148`, `:239-249` |
| `compute_uncertainty` computes its own residuals unconditionally; **no caller-supplied residual parameter exists** | `.../forecasting/uncertainty.py:210` |
| `UncertaintyInterval` fields: `method`, `requested_coverage`, `calibration_sample_count`, `available`, `lower`, `upper`, `unavailable_reason`, `calibration_window_id` — **no calibration-source or digest field** | `.../forecasting/uncertainty.py:102-134` |
| `UncertaintyMethod` has exactly two members: `NONE`, `EMPIRICAL_ROLLING_ORIGIN_RESIDUAL` | `.../forecasting/uncertainty.py:40-42` |
| `UncertaintyError(ValueError)` exists and is raised today **only for invalid configuration** | `.../forecasting/uncertainty.py:45`, `:75-84` |
| Uncertainty is constructed inside evidence assembly | `.../forecasting/evidence.py:312` |
| `CapacityForecastEvidence` binds digests for series, input window, feature config, admission policy, uncertainty config, model config and normalization policy — **no calibration-input digest** | `.../forecasting/evidence.py:365-388` |
| A permitted digest facility already exists **inside** the boundary: `content_digest(domain, schema_version, value)`, sha256 over domain-separated canonical JSON, stdlib only, already imported by `uncertainty.py` | `.../canonical/serialization.py:126-134`; `.../forecasting/uncertainty.py:30` |

**Canonical residual representation: signed residuals.** This is verified from the
implementation, not inferred from the word "residual". Absolute or otherwise transformed
residuals would change the interval — the construction deliberately yields an **off-centre**
interval for a biased forecaster, which is the property the ADR relies on.

## 3. Candidate comparison

| Criterion | 1 — optional residuals parameter on `compute_uncertainty` | **2 — separate public residuals→interval function** | 3 — evaluation-only wrapper |
|---|---|---|---|
| Risk to existing callers | **High** — one function gains two calibration authorities; a default-argument slip silently changes production semantics | **Low** — existing signature and behavior untouched; the new function is additive | Low for callers, **high for truth** — the shipped path is bypassed, so what is evaluated is not what ships |
| Formula reuse | Yes | **Yes — single definition, both paths delegate** | **No** — duplicates type-7 quantile and endpoint construction |
| Provenance support | **Weak** — a bare sequence arrives with no proof of origin, binding or cutoff | **Strong** — a typed immutable calibration input carries count, origin bounds, binding and digest | Possible, but proven only against a copy of the formula |
| Required plumbing | Least | Moderate — one explicit optional parameter through `forecast_with_evidence` and `run_replay_evaluation` | Most — duplicate evidence assembly |
| Public API impact | Changes an existing public signature | **Adds one public function; changes none** | None to the package; grows an unreviewed parallel surface |
| Evidence duplication risk | Low | **Low** | **High** — a second evidence path can drift from the canonical one |
| Stdlib-and-local-only compliance | Compliant | **Compliant** | Compliant only by discipline, outside the boundary test's reach |
| Conformance burden | Moderate, but parity is hard to state — one function, two meanings | **Moderate and statable** — parity is exactly "same residuals in, same interval out" | **Highest** — every property must be re-proved against the duplicate |
| Ability to fail closed | Weak — validation competes with the config-validation path | **Strong** — one validation site owning one input type | Strong locally, meaningless globally |

**Conclusion: candidate 2.** It is the only option that keeps one interval formula, leaves the
shipped signature and semantics untouched, and gives calibration residuals a typed identity
that can be validated and digested. Candidate 1 gives one function two calibration
authorities and admits unproven residuals without provenance. Candidate 3 duplicates the
formula and evidence construction outside the shipped path, so a passing evaluation would say
nothing about what ships.

## 4. The seam (proposed, not implemented)

### 4.1 The public function

Conceptually — **the exact name, parameter names and module placement are an implementation
specification decision (§10)**:

```
interval_from_residuals(
    point:         float,                       # the point forecast, unchanged by this call
    calibration:   CalibrationResiduals,        # ordered immutable residuals + metadata
    config:        UncertaintyConfig,           # the frozen, preregistered configuration
) -> UncertaintyInterval                        # the existing canonical return type
```

It must preserve **exactly**: the type-7 quantile definition; requested-coverage handling;
minimum-calibration-sample behavior; point-only / uncalibrated behavior; endpoint
construction; validation and exception behavior; determinism and finite-value rules. It is a
pure function of its arguments and holds no state.

### 4.2 The calibration input type

`CalibrationResiduals` (proposed) is frozen and immutable, and carries a **discriminant** so
one type serves both paths without either inventing fields it cannot honestly fill:

| Field | Meaning |
|---|---|
| `source` | `IN_WINDOW_ROLLING_ORIGIN` (shipped path) or `EVALUATION_RESIDUAL_BANK` (manifest §7.2) |
| `values` | ordered, immutable, **signed** residuals in exactly the representation §2 verified |
| `count` | residual count |
| `earliest_origin` / `latest_origin` | contributing forecast origins; absent for the in-window source |
| `evaluation_cutoff` | the cutoff this calibration is valid at; absent for the in-window source |
| `subject_digest` / `target` / `horizon` / `arm_model_id` | the binding this calibration belongs to |
| `bank_cap` | the configured bound (672 for the evaluation source) |
| `cutoff_sequence_digest` / `config_digest` | the preregistered schedule and configuration identity |
| `residual_bank_digest` | `content_digest` over the ordered values and the binding |
| `observability_invariant` | assertion that every contributing actual was observable at `evaluation_cutoff` |

The discriminant is what keeps the shipped path honest: it constructs the in-window variant,
which simply has no bank fields, rather than fabricating them.

### 4.3 Existing-path preservation

`compute_uncertainty(window, forecaster, point, config)` keeps its **signature and default
behavior unchanged for every current caller**. Its future implementation performs:

1. the same `rolling_origin_residuals(window, forecaster, config)` call it performs today;
2. delegation of that residual collection — wrapped as the `IN_WINDOW_ROLLING_ORIGIN` variant —
   to `interval_from_residuals`;
3. return of the same canonical `UncertaintyInterval`.

Calls through `forecast_with_evidence` and `run_replay_evaluation` **with no provider** must
remain semantically identical and, where feasible, byte-for-byte identical in their evidence.

**Extracting the inline formula is authorized only as a later implementation prerequisite. It
is not authorized in this documentation task.**

## 5. Evaluation plumbing

### 5.1 The provider interface

A typed, evaluation-scoped residual-provider interface, **owned by the replay/evaluation
layer**, never a bare sequence threaded anonymously through production APIs:

```
CalibrationProvider (evaluation-owned, proposed)
    calibration_for(subject, target, horizon, arm_model_id, cutoff) -> CalibrationResiduals | None
```

`run_replay_evaluation` owns or receives the provider and selects the calibration object for
each forecast origin. The provider is the residual **bank** of manifest §7.2: one per
`(subject, target, horizon, arm)`, 672-residual cap, oldest-origin-first eviction, strict
as-of admission.

### 5.2 Minimum plumbing through the evidence layer

Because `forecast_with_evidence` currently owns uncertainty construction
(`.../forecasting/evidence.py:312`), the minimum explicit plumbing is **one optional,
explicitly-typed parameter** on each of two functions:

```
run_replay_evaluation(..., calibration_provider: CalibrationProvider | None = None)
    per cutoff:
        calibration = calibration_provider.calibration_for(...) if calibration_provider else None
        forecast_with_evidence(..., calibration: CalibrationResiduals | None = None)
            point = forecaster.point_estimate(window)          # unchanged, provider-independent
            if calibration is None:
                interval = compute_uncertainty(window, forecaster, point, config)   # today's path
            else:
                interval = interval_from_residuals(point, calibration, config)
```

The `None` branch is the shipped path, unchanged. Nothing else in evidence assembly moves.

### 5.3 Explicitly prohibited mechanisms

An unlabelled residual tuple · a mutable callback with hidden state · module globals ·
monkeypatching · context variables · inspecting model IDs to infer intent · evaluation code
calling private helpers such as `_quantile`. Each of these would either defeat provenance or
couple the evaluation to internals the boundary tests do not protect.

## 6. Authority and misuse constraints

The provider supplies **calibration evidence, not a forecast**. It cannot:

- change the point prediction — `point_estimate` is computed before and independently of it;
- change `requested_coverage`, lower `min_calibration_samples`, or select a different
  `method` — all three come from the frozen `UncertaintyConfig`, never from the calibration
  input;
- introduce residuals from another subject, target, horizon or arm;
- include an actual that was unavailable at the evaluation cutoff;
- reorder residuals opportunistically;
- bypass abstention or matching outcomes.

**Absence of the provider preserves the shipped rolling-origin path**, exactly.

### 6.1 Fail-closed behavior

A digest mismatch, binding mismatch, future residual, excessive bank size or invalid numeric
value must fail closed. `UncertaintyError` (`.../forecasting/uncertainty.py:45`) is the
existing canonical failure type in this module and is the natural carrier — but today it is
raised **only for invalid configuration** (`:75-84`), so using it for invalid *calibration
input* extends its meaning. **Whether to extend `UncertaintyError` or introduce a distinct
error type is an unresolved implementation decision (§10.3), not selected here.**

Note the deliberate asymmetry: insufficient calibration is **not** an error — it is the
existing typed `unavailable` contract with `REASON_INSUFFICIENT_CALIBRATION`, and under
`allow_point_only_when_uncalibrated = false` the service abstains. Invalid or untrustworthy
calibration is a different thing and must raise.

## 7. Standard-library boundary

The design stays **stdlib-and-local-only** inside `forecasting/`. No NumPy, SciPy, pandas,
`hybrid_llm`, or new external numerical or serialization dependency — each is a forbidden
import root already enforced by `.../tests/forecasting/test_boundary.py:35-43`.

**A permitted digest facility exists inside the boundary**, so no gap is recorded here:
`content_digest(domain, schema_version, value)`
(`.../canonical/serialization.py:126-134`) computes a `sha256:`-prefixed, domain-separated
digest over canonical JSON using only stdlib `hashlib`/`json`, and `uncertainty.py` already
imports it (`:30`). `residual_bank_digest`, `cutoff_sequence_digest` and `config_digest` use
it with their own domain strings and schema versions.

## 8. Required conformance evidence

Later implementation must carry at least these tests. None is written by this document.

| # | Test | Requirement |
|---|---|---|
| 1 | **Legacy formula parity** | Freeze representative current `compute_uncertainty` outputs **before** refactoring. After extraction require **exact equality** where operations are identical; any deviation requires a numeric bound specified and justified **before** implementation |
| 2 | **Public-function parity** | Given the exact sequence from `rolling_origin_residuals`, the new function returns the same result as the pre-extraction inline formula |
| 3 | **No-provider invariance** | `forecast_with_evidence` and `run_replay_evaluation` with no provider produce unchanged outputs and evidence |
| 4 | **Provider isolation** | With calibration supplied, the interval uses **only** the supplied collection and `rolling_origin_residuals` is neither called nor mixed in |
| 5 | **Point-prediction invariance** | Supplying calibration cannot alter the point forecast |
| 6 | **Causality** | Residuals whose matched actual was not observable at the cutoff are rejected |
| 7 | **Binding** | Cross-subject, cross-target, cross-horizon and cross-arm calibration is rejected |
| 8 | **Order and cap** | Deterministic oldest-origin eviction, 672 maximum, collision tie-breaking |
| 9 | **Config authority** | The provider cannot override method, requested coverage, minimum samples or point-only policy |
| 10 | **Invalid inputs** | Empty, insufficient, non-finite, malformed, duplicate and digest-mismatched inputs behave per canonical rules |
| 11 | **Replay determinism** | Same observations, manifest and configuration → identical bank digests, intervals and evaluation records across repeated runs |
| 12 | **Boundary** | No forbidden import root or new external dependency enters `forecasting/` |
| 13 | **Negative control** | A deliberately future-contaminated bank that *would improve* apparent interval coverage is **rejected** |
| 14 | **Four-arm fairness** | P, T, N and H share the calibration-origin schedule and bank policy, and share **no residual values** across arms |

Test 13 is the one that matters most: a leak that degrades coverage would be noticed anyway,
and a leak that flatters it is what the whole as-of rule exists to prevent.

## 9. What this design does not establish

A seam that passes every test above proves the *evaluation* interval is computed by the
canonical formula from a causally admissible residual set. It does **not** ratify production
uncertainty implementation — the shipped path still collects residuals differently (manifest
§7.4). Point accuracy and interval calibration remain **separate ratification claims**.

## 10. Prerequisites and open owner decisions

### 10.1 New evidence vocabulary — required, not invented here

`UncertaintyMethod` has exactly two members, and neither describes bank-sourced residuals.
Labelling evaluation intervals `EMPIRICAL_ROLLING_ORIGIN_RESIDUAL` would **misdescribe their
provenance in evidence**, since the bank's origins are quarter-hourly and its actuals are not
restricted to the forecast window. A distinct member is therefore required. **It is not added
here** and requires owner ratification.

### 10.2 Missing evidence field — required, not invented here

Neither `UncertaintyInterval` nor `CapacityForecastEvidence` can carry the **source and digest
of externally supplied calibration residuals**. `calibration_window_id` is a free-text label,
not a digest, and overloading it would invent semantics the field does not have.
`CapacityForecastEvidence` binds seven digests but none for a calibration input. A field (or
fields) must be added, with a schema-version consequence. **Not invented here**; owner
ratification required.

### 10.3 Failure-type decision — unresolved

Whether invalid calibration input raises the existing `UncertaintyError` (extending its
current configuration-only meaning) or a distinct error type. Recorded, not selected.

### 10.4 Implementation specification — unresolved

Exact public function name, parameter names, module placement, the `CalibrationResiduals`
field names and their canonical-dict shape, and the schema versions for the new digests.

### 10.5 Sequencing

The formula extraction (§4.3) is a **later implementation prerequisite** and must land with
tests 1 and 2 green before any evaluation path is built on it.

## 11. Citations

Paths under `.../` are relative to `packages/capabilities/cloud-scaling-controller/`.
Every anchor in §2 was verified against the tree on 2026-08-27 at
`ugence-cloud-scaling-controller` version `0.4.0`
(`.../src/ugence_cloud_scaling_controller/version.py:7`).
