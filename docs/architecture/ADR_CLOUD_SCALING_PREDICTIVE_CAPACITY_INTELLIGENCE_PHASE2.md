# ADR — Cloud Scaling: Predictive Capacity Intelligence (Phase 2)

**Status:** **ACCEPTED.** Amended 2026-08-27 (Amendments 1–4) to record owner rulings authorizing the design, the manifest preparation, the resolution of both run-blocking gaps, and the **shape** of the residual-supply seam for a third-baseline replay evaluation. No telemetry access or replay execution is authorized, and no seam is implemented. No third baseline is ratified; the two shipped baselines and the shipped uncertainty behavior are unchanged.
**Date:** 2026-08-11
**Package:** `packages/capabilities/cloud-scaling-controller` (`ugence-cloud-scaling-controller`), v0.2.0 → **v0.3.0**.
**Scope:** Additive, deterministic, provider-neutral, **shadow-only** forecasting and
replay-evaluation layer built *around* the Phase-1 canonical layer. The controller's
advisory authority, provider neutrality, and five-signal decision algorithm are unchanged,
and forecasts never feed the controller.

---

## Amendment 1 (2026-08-27) — owner rulings authorizing a third-baseline replay evaluation

> **Owner decisions authorize the evaluation design only. No third baseline is ratified.
> Ratification requires an authorized replay run to clear all applicable preregistered gates.**

**Documentation-only.** This amendment adds no code, no enum member, no schema, no digest and
no dependency; it changes no shipped behavior. `persistence` and `linear_trend` remain the
only forecasters this package ships, and the deferral recorded above — a third baseline
"only if justified by replay evaluation" — stands unresolved.

The evaluation design these rulings authorize is
[`ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md`](ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md).
It preregisters a four-arm ladder — `persistence` (P), `linear_trend` (T), a proposed
`seasonal_naive` control (N) and a proposed `harmonic_phase` candidate (H) — over the
existing leakage-safe replay harness, with per-cell gates and explicit falsification rules.
`seasonal_naive` and `harmonic_phase` do not exist in the package and are not created by
either document.

### The five rulings

**1 — Telemetry authorization.** Future replay against read-only historical production
telemetry is authorized under shadow-only scope. No live requests, production writes, scaling
actions, credential use or customer-identifying data are authorized. The run uses an
anonymized, preregistered manifest naming every eligible subject in the approved export;
subjects may not be selected after viewing results. Synthetic or staging data may validate
the harness but cannot ratify a baseline.

**2 — Clock and period definition.** UTC-fixed clock semantics for the first evaluation. Only
the 86,400-second daily period is ratified for this experiment. A weekly period is excluded:
it is not resolvable within the ratified lookback, and weekly evaluation requires a
separately ratified multiweek lookback. Local-calendar and DST-aware periods remain deferred
research.

**3 — Lookback and compute budget.** A seven-day lookback at the canonical 60-second cadence
(604,800 seconds / 10,080 samples before missing-data handling). All arms receive identical
cutoffs, observations, lookback, feature configuration and admission policy. If compute is
excessive, replay-origin density is reduced through a deterministic preregistered stride;
H's window is never shortened and no arm receives a different window. The estimated run size
is reported before execution.

**4 — Seasonal-naive outcome.** `seasonal_naive` is an **outcome-eligible control**. If it
satisfies the ratification gates and ties or beats `harmonic_phase`, then `harmonic_phase` is
retired and `seasonal_naive` is ratified as **the** third baseline — not as a fourth. If
`harmonic_phase` wins, `seasonal_naive` remains evaluation-only unless separately ratified.

**5 — Ratification scope (superseded by the final ruling below).** Restricted ratification was
permitted alongside an unconditional 8-of-12 floor. Those two statements contradicted each
other, and the final ruling replaces them with exactly **two** preregistered scopes: a
**general baseline** (at least 8 of 12 cells, all applicable gates), or a **60-minute-only
baseline** (all four gating targets passing at 60 minutes, enforced as a capability envelope
that rejects or abstains at 5 and 15 minutes). Passing 1–3 of the four 60-minute cells
ratifies nothing, and no other restricted scope is authorized. A **cadence preflight** is also
required before authorization: the replay runs only on subject × target series whose exported
timestamps already satisfy the ratified p95 (≤ 120 s) and maximum (≤ 900 s) gap limits, with
no interpolation, forward-fill or upsampling to make a coarse export appear eligible. If no
series qualifies, `harmonic_phase` is recorded **unevaluable on the approved export** — not as
a modelling win or loss. See the evaluation ADR §7.3 and the run manifest §6.2.

### Scope of these rulings

They authorize a design and a future run. They do not ratify a forecaster, do not permit
implementation, do not relax this ADR's prohibition on neural networks, model services,
hyperparameter search or automatic promotion, and do not alter Phase 2's shadow-only boundary:
`FORECAST != RECOMMENDATION != RISK EVALUATION != AUTHORITY != EXECUTION` is unchanged.

The evaluation concerns clock-anchored harmonic regression over timestamps. It bears on no
verdict about learned content phases, neural Phase retrieval, BindingSlots or Phase-Quad, and
reverses none of them.

## Amendment 2 (2026-08-27) — run-manifest thresholds authorized; execution still prohibited

> **No telemetry access or replay execution is authorized by this amendment. No third
> baseline is ratified.**

**Documentation-only.** This amendment adds no code, no enum member, no schema, no digest and
no dependency. It authorizes **preparation of the replay manifest only**.

Owner rulings fix the subject-anonymization scheme (`HMAC-SHA256(run_secret,
canonical_subject_id)`, secret and identifiers held outside the repository), outcome-blind
per-subject×target eligibility with typed countable exclusions, a 42-day span requirement
with a fixed 7-day burn-in and five 7-day scoring blocks, a deterministic 900-second
UTC-quarter-hour cutoff stride shared by all four arms, the five frozen cycle-resolvability
thresholds with a fixed reason precedence, and the as-of rule for regime-break exclusion.
They are recorded in
[`CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md`](CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md),
which governs the design in
[`ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md`](ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md).

The manifest is deliberately **incomplete**: export identity, anonymized subject hashes,
observation boundaries and exact run-size values are unpopulated, and the run is prohibited
until they are filled. Two **run-blocking repository gaps** are recorded in its §10 and are
not worked around: (1) the package has no canonical regime-break record type and no
`recorded_at` on `CanonicalCapacityState`, so the as-of exclusion rule cannot be evaluated
from repository contracts; (2) the rolling-origin calibration iterates every in-window
sample, so the uncertainty expansion is unbounded by the ratified cutoff stride. Both require
a further owner ruling.

The two abstention values the design needs remain **proposed vocabulary**; they are not added
to `AbstentionReason`. `seasonal_naive` and `harmonic_phase` remain proposed identities with
no implementation. This ADR's prohibition on neural networks, model services, hyperparameter
search and automatic promotion is unchanged, as is Phase 2's shadow-only boundary.

## Amendment 3 (2026-08-27) — both run-blocking gaps ruled; execution still prohibited

> **The replay remains unexecutable until the anonymized subject manifest and approved export
> identity are populated and an evaluation implementation of the bounded causal residual-bank
> protocol exists. No production uncertainty behavior is changed or ratified.**
>
> **No telemetry access is authorized by this amendment. No third baseline is ratified.**

**Documentation-only.** No code, enum member, schema, digest or dependency changes. In
particular `compute_uncertainty` and `rolling_origin_residuals` are **untouched**, and nothing
here ratifies production uncertainty behavior.

**Ruling 1 — regime breaks: none excluded.** The package has no canonical regime-break record
carrying both an effective event time and an independent knowledge timestamp, and no new
export-contract requirement is created to rescue the experiment. `DeploymentState`,
`ObservationProvenance.collected_at` and `TopologySnapshot.as_of` are **not** treated as
equivalent to a `recorded_at`. Every otherwise-eligible cutoff is retained, including those
spanning deployments, incidents and configuration changes; post-hoc removal by later-known
labels is prohibited; no regime-specific performance may be claimed; and if the harmonic arm
fails because periodicity breaks during operational changes, that failure counts. This is the
conservative direction — it retains the difficult origins. Adding exclusion later defines a
different evaluation requiring a new preregistration and replay.

**Ruling 2 — bounded causal uncertainty calibration.** The seven-day feature lookback is not
shortened and the interval-coverage gate is not withdrawn. For this evaluation only, the
nested per-forecast rolling-origin expansion is replaced by a causal prequential residual bank
applied identically to all four arms: one bank per `(subject, target, horizon, arm)`,
calibration origins on the ratified 15-minute UTC schedule, at most 672 residuals with
deterministic oldest-origin-first eviction, a strict as-of admission rule, the preregistered
`UncertaintyConfig` values unchanged with `allow_point_only_when_uncalibrated = false`, and the
repository's existing interval mathematics reused without inventing a second formula. The
history requirement rises from 42 to **49 days** (burn-in 0–7, calibration 7–14, scoring
14–49); the calibration block enters no gate. Per fully eligible subject the run is bounded at
**193,536 forecaster calls** (32,256 calibration + 161,280 scoring) with **no multiplicative R
expansion**.

**What this costs in meaning.** Interval estimates describe the error distribution at the
preregistered decision-origin schedule, not at every raw telemetry timestamp; and because the
protocol differs from the shipped nested implementation, **a successful replay does not by
itself ratify production uncertainty implementation**. Point accuracy and interval calibration
remain **separate ratification claims**: failure of the interval gate retires the harmonic arm
even if its point MAE passes. The evaluation remains outcome-neutral — ratifying H, N, T, or no
third baseline are all permitted conclusions.

**Prerequisite recorded, not resolved.** `compute_uncertainty` computes its own residuals and
accepts none from the caller, and the interval construction is inline with a module-private
quantile helper, so **no residual-supply seam exists**. Building one — reusing the existing
interval formula unchanged and carrying its own conformance evidence — is an implementation
prerequisite recorded in the run manifest §10.2. `rolling_origin_residuals` must not be
reinterpreted as already satisfying this ruling.

Both rulings are recorded in
[`CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md`](CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md)
§7 and §10, and in
[`ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md`](ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md)
§8.3–§8.4.

## Amendment 4 (2026-08-27) — residual-supply seam shape selected; nothing implemented

> **The seam shape is selected. No seam is implemented.** Existing uncertainty semantics remain
> authoritative. No replay is executable yet. **No third baseline is ratified.** The exact public
> API and any new evidence vocabulary remain subject to repository-grounded implementation
> specification and owner ratification.

**Documentation-only.** No code, export, enum member, schema, digest or dependency changes.
`compute_uncertainty`, `rolling_origin_residuals` and the inline interval formula are untouched.

**Decision: a separate public residuals-to-interval function is the canonical seam.** The
architecture carries **one canonical interval formula** and **two explicit residual-production
paths** that both delegate to it: the shipped `rolling_origin_residuals` path, and the
preregistered causal prequential residual bank of the run manifest §7.2. The evaluation path may
change how residuals are collected; it may not change how a residual sequence becomes an
interval.

**Rejected as the primary design.** An optional raw-residuals parameter on `compute_uncertainty`
— it would give one function two calibration authorities, admit unproven caller-supplied
residuals without provenance, and make production semantics easier to change accidentally. An
evaluation-only wrapper — it would duplicate evidence construction, the type-7 quantile logic and
the interval mathematics outside the shipped forecasting path, so a passing evaluation would say
nothing about what ships.

**Preserved exactly:** `compute_uncertainty`'s signature and default behavior for every current
caller; the type-7 quantile definition; requested-coverage handling; minimum-calibration-sample
behavior; point-only/uncalibrated behavior; endpoint construction; validation and exception
behavior; determinism and finite-value rules. Calls through `forecast_with_evidence` and
`run_replay_evaluation` **with no provider** must remain semantically — and where feasible
byte-for-byte — identical. Extraction of the inline formula is a **later** implementation
prerequisite, not authorized here.

**Plumbing.** A typed, evaluation-owned `CalibrationProvider` returns an immutable calibration
object bound to subject, target, horizon and arm, carrying ordered signed residuals, count,
contributing-origin bounds, evaluation cutoff, bank cap, configuration and bank digests, and the
observability invariant. It reaches evidence assembly through **one explicitly-typed optional
parameter** on `run_replay_evaluation` and `forecast_with_evidence`. Unlabelled residual tuples,
mutable callbacks, module globals, monkeypatching, context variables, model-ID inspection and
calls to private helpers are prohibited.

**Authority.** The provider supplies calibration evidence, not a forecast: it cannot change the
point prediction, `requested_coverage`, `min_calibration_samples` or the configured method, and
cannot introduce cross-binding, future, reordered or unmatched residuals. Its absence preserves
the shipped path exactly. Invalid calibration must fail closed; insufficient calibration remains
the existing typed *unavailable* contract, not an error.

**Unratified prerequisites, recorded rather than invented.** `UncertaintyMethod` has no member
describing bank-sourced residuals, and neither `UncertaintyInterval` nor
`CapacityForecastEvidence` can carry the source and digest of externally supplied calibration
residuals — both require owner ratification with a schema-version consequence. Whether invalid
calibration raises the existing `UncertaintyError` or a distinct type is unresolved. A permitted
in-boundary digest facility does exist (`content_digest`), so no digest-facility gap is recorded,
and `forecasting/` remains standard-library-and-local-only.

Full design, three-candidate comparison and the fourteen required conformance tests — including
a negative control proving a future-contaminated bank that would *flatter* interval coverage is
rejected — are in
[`CLOUD_SCALING_RESIDUAL_SUPPLY_SEAM_DESIGN.md`](CLOUD_SCALING_RESIDUAL_SUPPLY_SEAM_DESIGN.md).
A seam passing every test would still **not** ratify production uncertainty implementation; point
accuracy and interval calibration remain separate ratification claims.

---

## Context

Phase 1 established a trustworthy, provider-neutral representation of *current* capacity
state (`CanonicalCapacityState`), explicit normalization/projection onto the unchanged
`ScalingObservation`, and immutable recommendation evidence (`CapacityDecisionEvidence`).

Phase 2 answers a forward-looking question **without touching the live decision path**:

> Given the capacity history available *at event time*, what capacity pressure is likely at
> a future horizon, how uncertain is that prediction, and how well has the forecasting
> method performed in replay?

The naive path — feed a forecast into the controller as a hidden signal, or let a
predicted value trigger a scaling action — would (a) silently change the tested five-signal
decision model, (b) entangle an unproven prediction with real authority, and (c) risk
leakage (training/scoring on data that would not have been available at decision time). We
reject it. Phase 2 is **descriptive shadow intelligence only**.

## Decision

Add a leaf subpackage `ugence_cloud_scaling_controller.forecasting` (pure standard library,
no new dependency, no network/subprocess/credential/LLM) implementing this flow:

```text
CanonicalCapacityState history
        ↓  series validation + strict event-time ordering (explicit construction policy)
CanonicalCapacitySeries
        ↓  leakage-safe input window (event_time <= cutoff, invariant-checked)
ForecastInputWindow
        ↓  deterministic baseline forecaster (persistence / linear trend)
CapacityForecast          (point estimate + uncertainty  OR  typed abstention)
        ↓  controlled service path binds real window + config + output
CapacityForecastEvidence  (immutable, sha256 content-identity digest)
        ↓  shadow replay against strictly-later actual observations
ForecastEvaluationRecord  + deterministic aggregate evaluation report
```

The existing live path — `ScalingObservation → CloudScalingController → ScalingRecommendation`
— is **byte-for-byte unchanged**, and forecast results are never a hidden input to it.

### Event-time semantics

Event time is `CanonicalCapacityState.observed_at` — *when the measurement was taken* —
never `collected_at` (record production) or evidence-production time. Every ordering,
windowing, staleness, cadence, and matching decision uses event time. Timestamps must be
timezone-aware (safe default; a policy may opt into naive-as-UTC). This is the single most
important rule for leakage safety: a record inserted late but *observed* early is placed by
its event time, and a record collected late for an early observation still uses its event
time.

### Series construction policy

`CanonicalCapacitySeries.build(states, policy)` binds one `CapacitySubject` (tenant/scope
included), the ordered observations, the event-time range, the observation count, a schema
version (`capacity-series-1`), and a deterministic content digest. It **fails closed** on:
subject/tenant/scope inconsistency (cross-subject or cross-tenant contamination), naive
timestamps (unless permitted), invalid event-time ordering, and **conflicting duplicates**
(same timestamp, different content — *always* rejected, not a knob). Non-identity
transformations require explicit opt-in and are disclosed: `OrderingPolicy.SORT` (records
`applied_sort`) and `DuplicateTimestampPolicy.COLLAPSE_IDENTICAL` (records
`collapsed_duplicate_count`). Missing capacity signals are **never** imputed.

### Supported targets and horizons

Targets are read from the *same* canonical fields the Phase-1 projection uses, so a
forecast can never silently substitute a different semantic:

| Target | Canonical field |
| --- | --- |
| `CPU_UTILIZATION` | `infrastructure.cpu_utilization` |
| `MEMORY_UTILIZATION` | `infrastructure.memory_utilization` |
| `P99_LATENCY` | `performance.latency_p99` |
| `ERROR_RATE` | `reliability.error_rate` |
| `QUEUE_DEPTH` | `workload.queue_depth` |
| `RUNNING_REPLICAS` | `capacity.running_replicas` (the SAME field the projection maps to `ScalingObservation.current_replicas` — never desired/ready/healthy) |

Extraction is **raw** — value and unit are preserved unchanged (no silent unit conversion).
Horizons are explicitly configured `ForecastHorizon` durations (e.g. 5m / 15m / 60m);
**no horizon-specific scaling behavior is hardcoded**. Each forecast binds its target,
horizon, cutoff, and forecast-for time.

### Baseline models

Two deterministic baselines ship: **persistence** (last observed value; the canonical
hard-to-beat baseline) and **linear-trend** (closed-form OLS over event-time seconds,
extrapolated to the forecast-for time; requires ≥ 2 distinct timestamps and a configurable
`min_history`). Each has a stable `model_id`/`model_version`, an explicit configuration
with a digest, a minimum-history requirement, declared supported targets/horizons,
deterministic output, and typed abstention. No training or mutation occurs during a
forecast. A **third baseline is deliberately deferred** until replay evaluation on
representative data justifies it (the spec permits a third "only if justified by replay
evaluation"). No neural networks, model services, hyperparameter search, or automatic
promotion.

### Uncertainty limitations

Uncertainty is an **empirical rolling-origin residual interval** (`UncertaintyMethod`
`EMPIRICAL_ROLLING_ORIGIN_RESIDUAL`): the forecaster is replayed over rolling origins
*inside the leakage-safe window*, signed horizon-ahead residuals are collected, and the
interval is `point + [q(α/2), q(1-α/2)]` from empirical residual quantiles at the requested
coverage. **No Gaussian assumption is made.** Because the interval is centered on the
residual quantiles rather than symmetric around the point, a biased forecaster yields an
off-center interval that faithfully reflects its observed error. If fewer than
`min_calibration_samples` residuals exist, the interval is a typed **unavailable** contract;
the forecast is retained as point-only *only* if the config explicitly permits it, otherwise
the layer abstains (`INSUFFICIENT_CALIBRATION_HISTORY`). A heuristic score is never
presented as a probability.

### Abstention semantics

An abstention is a **first-class, evidence-producing** output — not an error and not a
fabricated prediction. Typed reasons include: insufficient history, stale history, excessive
missingness, subject mismatch, tenant/scope mismatch, invalid time order, conflicting
duplicate, unsupported target, unsupported horizon, irregular cadence, missing normalization
policy, invalid/non-finite measurement, inconsistent unit, insufficient calibration history,
and forecast outside permitted domain. Safe defaults reject/abstain. The domain gate never
silently clamps: an out-of-domain forecast abstains unless an explicit
`allow_out_of_domain` policy retains it *with a disclosed warning*.

### Evidence identity boundary

`CapacityForecastEvidence` is produced only through the controlled `forecast_with_evidence`
service path, which runs the real window construction, the real forecaster, and the real
uncertainty calibration, then binds their outputs. The `sha256:` digest covers **all
authoritative fields**: schema versions; subject/tenant; source-series and input-window
digests; cutoff/forecast-for; target/horizon; model id/version and config digest; feature-
config digest; normalization-policy digest; the forecast-or-abstention output; and the
uncertainty method/config. It **excludes** only `evidence_produced_at` (a production
timestamp) and `diagnostic_annotation` (a non-authoritative human note that must not
contradict the structured evidence). Changing any authoritative input, model, configuration,
provenance, output, or uncertainty field changes the digest. The digest is a **content
identity** — not a signature, an authorization, or any proof of forecast accuracy.

### Replay / evaluation method and leakage prevention

`run_replay_evaluation` advances through cutoffs; at each cutoff it builds history from
**only** observations with `event_time <= cutoff`, constructs the series, forecasts, then
matches the forecast against a **strictly-later** actual observation of the same subject that
carries the target, within an explicit horizon + timestamp tolerance. Two independent guards
enforce leakage safety: the input window's own construction-time invariant (no sample after
the cutoff), and a harness assertion that the constructed series ends at or before the
cutoff. The matched actual is drawn only from `event_time > cutoff`, so the scored value can
never have been a feature. The harness is robust to adversarial input — future records
preloaded into the source, randomized input order, duplicate timestamps, collection-time
later than observation-time, and an early-inserted future-event-time record — because it
filters by event time, not input position, and **fails closed** on any residual leakage.
Each match yields an immutable `ForecastEvaluationRecord`; the aggregate reports forecast
count, abstention count/rate, MAE, RMSE, mean signed error (bias), empirical interval
coverage, average interval width, and unmatched count. **Percentage-error metrics
(MAPE/SMAPE) are intentionally omitted** — several targets (queue depth, error rate,
replicas) are legitimately zero, which invalidates a percentage denominator.

## Boundary: what Phase 2 does NOT own or do

Phase 2 preserves `FORECAST != RECOMMENDATION != RISK EVALUATION != AUTHORITY !=
EXECUTION`. It does **not** add: live predictive scaling; any change to the controller
decision kernel; forecast-fed live recommendations; AWS/Azure/GCP/Kubernetes write APIs or
provider actuation adapters; cost/dependency optimization or cross-cloud placement; Risk
Authority integration, risk evaluation, authorization, ActionGate matching, execution
clearance/receipts, effect verification, or rollback; online learning or automatic model
selection/promotion. Forecasted pressure is **not** "Risk Authority risk"; it is descriptive
shadow capacity intelligence. Every forecast and evidence artifact carries
`advisory_only=True`, `shadow_only=True`, `actuation_performed=False`,
`authority_class=ADVISORY`, `execution_capability=NONE`.

## Relationship to Phase 1

Phase 2 is strictly additive on top of Phase 1. It consumes `CanonicalCapacityState`,
reuses the Phase-1 canonical serialization/digest conventions and the `CapacitySubject`,
`Measurement`/`Unit`, and `NormalizationPolicy` contracts, and reads targets from the exact
canonical fields Phase-1 projection uses. It changes no Phase-1 public contract. The
independent schema versions are new (`capacity-series-1`, `capacity-forecast-window-1`,
`capacity-forecast-1`, `capacity-forecast-evidence-1`, `capacity-forecast-evaluation-1`,
plus feature/uncertainty/admission config schemas); `ScalingObservation`,
`ScalingRecommendation`, and all Phase-1 canonical schemas are untouched.

## Independent-audit corrections (v0.3.0)

Accepted independent-audit findings were corrected in place on the Phase-2 branch:

- **Controlled evaluation construction (structurally bound to the actual state).** An
  `EVALUATED` `ForecastEvaluationRecord` **embeds the canonical actual `CanonicalCapacityState`**
  and derives — and re-validates at construction *and* at `from_dict` reconstruction — every
  outcome field from it: `actual_state_digest` (= `actual_state.digest()`), `actual_value`/
  `unit` (from `extract_sample(actual_state, target)`), the subject/tenant/scope binding
  (`actual_state.subject == subject`), and the recomputed signed/absolute/squared errors and
  interval coverage/width. Because the state is embedded, a caller cannot present a forged
  `actual_value` with an unrelated `actual_state_digest` and self-consistent arithmetic — the
  digest is checked against the embedded state and the value/unit are re-extracted from it, so
  a forged value, forged digest, or subject/target/unit mismatch is rejected. This closes the
  gap that a digest string alone cannot prove which value a referenced state contained. The
  evaluation digest remains a canonical content identity/integrity value — **not** a signature
  or a proof of authenticity.

- **Deterministic, fail-closed matching.** Replay actual-matching filters candidates by
  subject/tenant/scope, target, strictly-future event time, horizon, and tolerance, then
  selects the unique closest candidate under a documented total order. Equally-eligible
  (equidistant) candidates yield a typed `AMBIGUOUS`, unscored outcome — never a silent
  first-by-input-order pick. The result is independent of caller input order.

- **Value space / normalization.** Forecast values are precisely disclosed as one of:
  *projected without conversion* (the default — raw canonical target domain, e.g. CPU
  percent stays percent, `running_replicas` stays an integer count mapped to
  `current_replicas` without substitution) or *explicitly normalized* (the Phase-1
  `normalize_signal` authority applied to a ratio in `[0, 1]`). The applied space, the
  `normalization_applied` flag, and the normalization-policy digest are bound into the
  input-window and evidence digests. A supplied policy must actually apply to the
  observations (method present for the signal + compatible unit) or the layer abstains
  (`MISSING_NORMALIZATION_POLICY` / `INCONSISTENT_UNIT`); no unit is ever silently converted.

- **Input + output domain enforcement.** A `SignalDomain` sourced from the single Phase-1
  `unit_domain` authority (no divergent duplicate bounds) is enforced on both input
  observations and output forecasts, including integer semantics: a fractional
  running-replica observation fails closed at the Phase-1 contract, and a fractional
  running-replica *forecast* is out-of-domain and abstains (`FORECAST_OUTSIDE_DOMAIN`) rather
  than being presented as valid. Nothing is silently clamped, rounded, or coerced; domain
  failures are evidence-producing.

- **Reachable typed abstentions.** `forecast_from_observations` is a controlled admission
  boundary that maps expected series-construction data-quality failures — invalid event-time
  order, conflicting/duplicate timestamps, cross-subject/tenant contamination — to typed,
  evidence-producing abstentions (`INVALID_TIME_ORDER`, `CONFLICTING_DUPLICATE`,
  `SUBJECT_MISMATCH`, `TENANT_SCOPE_MISMATCH`), while the strict
  `CanonicalCapacitySeries.build` API and its fail-closed exceptions are preserved and any
  unrelated/programming error is re-raised (never swallowed). Every `AbstentionReason` is now
  reachable through a supported service path (including `INVALID_MEASUREMENT`, exercised via a
  forecaster that yields a non-finite point) — proven by the reachability test suite.

- **Operations compatibility.** The `cloud-scaling-operations` distribution declared
  `ugence-cloud-scaling-controller >=0.1.1,<0.2`, unsatisfiable once the controller advanced
  to 0.2.0/0.3.0. After confirming operations imports only stable controller APIs
  (unchanged by Phase 2), the constraint was corrected to the narrowest installed-wheel-
  verified range `>=0.3.0,<0.4`; the shadow-harness version check now reads the controller's
  single-source version instead of hardcoding it; and the committed shadow evidence was
  regenerated through the canonical harness (advisory version `0.1.1 → 0.3.0`). The one-way
  `operations → controller` dependency is preserved; no `controller → operations` dependency
  is introduced.

## Consequences

- The capability now offers deterministic shadow forecasting + replay evaluation as a
  clearly-bounded, provider-neutral, dependency-free additive surface, with content-identity
  evidence a future separately-governed integration could reference.
- Two failure modes are made explicit and non-negotiable: **leakage** (prevented by
  event-time windowing + strictly-later matching + fail-closed guards) and **overclaiming**
  (prevented by first-class abstention, empirical-only uncertainty, and the maturity split
  below).
- No new runtime dependency; the wheel remains numpy-core + optional read-only `requests`.

## What Phase 2 does and does NOT prove

Passing tests and CI prove the **implementation** is correct — contracts, invariants,
leakage prevention, digest identity, and determinism. They do **not** prove the forecasts
are production-accurate. Synthetic fixtures are chosen to exercise contracts, not to
demonstrate accuracy (a low error on a synthetic ramp is a property of the fixture). Two
maturity axes are reported separately:

- **Implementation maturity:** `IMPLEMENTED_AND_LOCALLY_VERIFIED` (→ `IMPLEMENTED_AND_CI_VERIFIED`
  once every required Phase-2-relevant merge-gating check is green on the exact head).
- **Forecasting-model quality:** `BASELINE_FORECASTING_IMPLEMENTED` and, because the
  baselines have **not** been evaluated on representative external workloads against
  preregistered acceptance thresholds, `PREDICTIVE_QUALITY_NOT_ESTABLISHED`.

## Verification

Package suite (controller + Phase-1 canonical + Phase-2 forecasting/replay/leakage),
behavior-baseline parity (unchanged), compatibility/contract/boundary/side-effect/
provider-neutrality suites, the advisory distribution verifier (wheel build, isolated
install, packaged-source scans, and an **installed-wheel forecasting smoke** exercising the
full chain and confirming the live recommendation path is unchanged), manifest/authority
inventory, public-API stability, and version single-source consistency across `version.py`,
`module_manifest.json`, `artifacts/wheel_authority_inventory.json`, and the verifier's
`EXPECTED_VERSION`. Exact figures are recorded in the Phase-2 PR.
