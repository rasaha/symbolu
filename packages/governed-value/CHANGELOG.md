# Changelog — ugence-governed-value

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
