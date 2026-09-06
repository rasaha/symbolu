# Changelog — ugence-governed-value

## [0.3.0] — GV-2 observation ingress (GV-DEP, GV-PRODUCER, GV-ORDER)

Ratified by `docs/architecture/ADR_UGENCE_GOVERNED_VALUE_OBSERVATION_INGRESS.md`.
Additive over 0.2.0: **no money rule, guard, reason, advisory or classification
changes.** The kernel stays EXPERIMENTAL over caller-reported, unverified inputs
and still emits exactly `POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED`.

### Added

- `GovernedValueApplication.score(case, observations=())` and
  `admit_observations(case, observations)` (GV-PRODUCER): bind
  `MetricObservation` values built elsewhere to the case — exact type, matching
  `tenant_id`, `governed_unit` equal to the case's `natural_unit`, no repeated
  `observation_id`. Any violation raises `ObservationBindingError` and **no
  result is produced**: the set refuses as a whole. The kernel constructs no
  observation and attests none.
- `ObservedMetric` and `GovernedValueResult.observed_metrics` (GV-ORDER): what
  the seam checked — observation id, metric id, governed unit, window bounds,
  evidence-reference count, content digest — carried outside every monetary term
  and outside the scorability verdict, and read by nothing.
- `ObservationBindingError`, a `GovernedValueError`.

### Changed

- **The zero-dependency leaf posture ends, deliberately** (GV-DEP):
  `dependencies = ["ugence-governance-contracts>=0.2.0"]`, the release that first
  defines `MetricObservation`. No third-party dependency is added. Copying the
  shapes instead — the BR-2 precedent — is closed: that precedent copies from a
  package BR-2 is forbidden to import, whereas this is the shared contract layer,
  and a second copy of the evidence vocabulary is the fork that layer exists to
  prevent.
- `verify_governed_value_distribution.py` builds a two-wheel local wheelhouse and
  installs from it, still `--no-index`, so an undeclared dependency fails to
  resolve rather than being fetched. It now also proves a bound observation is
  carried without lifting either quality axis, and that a foreign-tenant
  observation refuses.
- `conftest.py` puts `governance-contracts/src` on `sys.path`, matching the other
  governance capabilities.

### Unchanged, and stated because it is the point

**A bound observation does not make a figure observed.** The caller who supplies
the case also supplies the observation, so emitting `EvidenceStatus.OBSERVED` on
that basis is the caller-elevated evidence the platform's anti-gaming invariants
forbid — elevation needs provenance *and* method *and* authority, and a producer
may never attest its own output. `evidence_status` stays `REPORTED` and
`authority_status` stays `UNVERIFIED` with observations present, pinned by test.
The authority adapter (GV-4) remains absent and blocked on an attesting
authority.

Every GV-0 and GV-1 rule is untouched: additive unbounded expected loss, no
re-discounting of reported benefit, investment distinct from cost-to-serve,
historical loss distinct from forward expected loss, exact minor-unit money,
`None` unequal to explicit zero, determinism, fail-closed headline suppression,
geography and domain touching no money, and `reported_confidence` out of the
arithmetic.

### Measured

Suite **53 passed, 0 failed**; distribution verifier **verified** offline from
the two-wheel wheelhouse. Figures are re-run, never edited.

## [0.2.0] — GV-0 classification + GV-1 corrected money model

### Audit polish (RF-1..RF-4 + honest naming)
- **RF-1**: removed the vestigial `inference_multiplier` argument (and its
  geography/data-residency doc) from `CostToServe.total()`; it now accepts no
  caller-controlled multiplier.
- **RF-2**: removed the unused `nonneg_multiplier` helper and
  `InvalidMultiplierError` (zero consumers repo-wide).
- **RF-3**: `AgentValueCase` now fails closed with a typed `GovernedValueError`
  when `actual_losses` (or `reported_net_per_period`) is missing/wrong-typed,
  instead of an incidental `AttributeError`.
- **RF-4**: `confidence` → `reported_confidence`, documented as caller-reported,
  unverified, separate from `EvidenceStatus`, and never used in the arithmetic.
- **Honest naming**: `RealizedValue` → `ReportedValue`; result/event fields
  `attributed_avoided_loss` → `reported_avoided_loss`,
  `realized_net_governed_value` → `reported_net_governed_value`,
  `realized_roi` → `reported_roi`; `realized_net_per_period` →
  `reported_net_per_period`. No name implies the kernel observed, attributed, or
  verified anything. **No mathematics changed.**


**Breaking, internal-only** (the leaf has zero reverse dependencies and was
unmerged). Corrects the mathematical model flagged in the architectural audit and
relabels the package as an experimental downstream calculation kernel.

### GV-0 — honest, orthogonal classification
- Added `AssessmentStage` (`PRE_ROI_READINESS`/`FORECAST`/`POST_DEPLOYMENT_VALUE`),
  `EvidenceStatus` (`REPORTED`…`VERIFIED`), `AuthorityStatus` (`UNVERIFIED`…),
  `ConfidenceClass`. Every result carries all four axes; this kernel emits only
  `POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED` and can never claim
  observed/attributed/verified. README scope corrected accordingly.

### GV-1 — corrected money model
- Replaced ratio `severity` with additive, absolute-money `ExpectedLossItem`
  (`probability × loss_magnitude`) and `ExpectedLoss`; expected loss may exceed
  total benefit and drive risk-adjusted NGV deeply negative.
- Distinguished historical `actual_losses` from forward `residual_expected_loss`
  (risk-adjusted view only).
- Added `TotalInvestment` as the ROI denominator, distinct from `CostToServe`
  (`None` ≠ explicit zero preserved on both).
- Removed all realization/attribution/decay/locale multipliers from the realized
  path — realized benefit is no longer discounted a second time.
- `payback_periods` computed only from a caller-stated, defensible per-period
  run-rate (else `None`). Confidence carried, never in the arithmetic.
- Decimal/minor-unit exactness and currency fail-closed preserved.

### Removed (deferred to later reviewed phases)
- `ErrorProfile` (ratio severity), `AuthorizedActionRef`/NGVA-per-authorized-action
  (needs a defensible `NormalizationBasis`, GV-3), decay projection (GV-5),
  portfolio comparison, and the authority-adapter seam (GV-4). Geography/domain
  reduced to descriptive context (versioned policy is GV-2c).

## [0.1.0] — governed-value spine

First cut of the governed-value accounting kernel: one spine (ROI with a
three-source realized-value decomposition and a mandatory wrong-action term),
with domain, geography and intended outcome as **modifiers** on its terms rather
than as separate frameworks. Normalizes to **net governed value per authorized
action (NGVA)**, measured at the control-plane chokepoint.

### Added
- `domain/` — exact minor-unit `Money`, `RealizedValue` (labor / throughput /
  loss-avoided), `ErrorProfile` (priced `p_error × severity`), itemized
  `CostToServe` (seven TCO components, omission detected), `DomainProfile` /
  `GeographyProfile` modifiers, `AttributionContext` (the five-failure guards),
  `AuthorizedActionRef` (the chokepoint denominator), and the `AgentValueCase`
  aggregate. All frozen, currency-isolated, `Decimal`-exact.
- `services/` — `score_case` (NGVA + fail-closed scorability verdict),
  `project_periods` (per-period decay recompute), `normalize_portfolio`
  (commensurable ranking in one base currency, excluding NOT_SCORABLE agents).
- `integrations/authorization.py` — `AuthorizedActionPort` seam + reference
  ledger; no import of the authority kernel (stdlib-only leaf).
- `observability/` — governance-event bus; `api/` — `GovernedValueApplication`
  facade and the public surface.
- Tests (unit · contract · adversarial) encoding the invariants and the five
  ROI-model failures; `verify_governed_value_distribution.py` clean-venv proof.
