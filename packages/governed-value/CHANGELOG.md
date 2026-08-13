# Changelog — ugence-governed-value

## [0.2.0] — GV-0 classification + GV-1 corrected money model

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
