# Ugence Governed Value (`ugence-governed-value`)

> **Scope (read first).** This package is an **experimental, downstream
> realized-value _calculation kernel_**. It computes a post-deployment
> governed-value figure from **caller-reported, unverified inputs**. It is **not**
> an ROI governance system: it has no evidence, attribution, or authority binding
> yet, so it can never claim a figure is observed, attributed, or verified —
> naming an input "realized" does not make it so. It is one stage (the
> _Governed Value Verification_ engine's downstream calculator) of the larger
> **Ugence Value Intelligence** capability; the readiness and forecast engines,
> evidence/attribution/authority binding, FX, and portfolio comparison are
> separate, later, reviewed phases and are **not** in this package.

## What it computes (GV-1)

```
total benefit    = attributable realized benefit + attributed avoided loss
                   (= labor displaced + throughput/revenue gained + loss avoided)
RealizedNGV      = total benefit − actual losses − cost to serve
RiskAdjustedNGV  = RealizedNGV − residual expected loss     (Σ probability × loss magnitude)
RealizedROI      = RealizedNGV / Total Investment
RiskAdjustedROI  = RiskAdjustedNGV / Total Investment
```

Three properties are the point of this version:

1. **Expected loss is additive, absolute money and unbounded relative to
   benefit.** It is `Σ probability × loss_magnitude`, not a `(1 − p×severity)`
   haircut. A low-probability, high-magnitude item can exceed total benefit and
   drive risk-adjusted net governed value deeply negative — the case a
   high-consequence agent must surface.
2. **Realized benefit is never realization-discounted.** Post-deployment benefit
   is already realized and already attributable; applying a realization/decay/
   locale factor here would double-discount it. Those factors are forecast
   concerns and are deferred.
3. **Total Investment is the ROI denominator, distinct from cost-to-serve.**

**Historical vs forward loss are separate:** `actual_losses` (incurred, subtracted
in `RealizedNGV`) is never mixed into the forward `residual_expected_loss`, which
appears only in the explicit risk-adjusted view.

## Classification — four orthogonal axes (GV-0)

Every result carries all four; they are independent, not one enum:

| Axis | Values | This kernel emits |
|---|---|---|
| `AssessmentStage` | `PRE_ROI_READINESS` · `FORECAST` · `POST_DEPLOYMENT_VALUE` | **`POST_DEPLOYMENT_VALUE`** |
| `EvidenceStatus` | `REPORTED` · `MODELED` · `OBSERVED` · `ATTRIBUTED` · `VERIFIED` | **`REPORTED`** only |
| `AuthorityStatus` | `UNVERIFIED` · `ATTESTED` · `VERIFIED` | **`UNVERIFIED`** only |
| `Scorability` | `SCORABLE` · `DEGRADED` · `NOT_SCORABLE` | computed |

Rising above `REPORTED`/`UNVERIFIED` requires the evidence (GV-2) and authority
(GV-4) layers, which do not exist. The classification is invariant across
`SCORABLE`/`DEGRADED`/`NOT_SCORABLE`.

## Design invariants (enforced + tested)

| Invariant | Where | Test |
|---|---|---|
| **Additive expected loss, unbounded vs benefit** | `domain/expected_loss.py`, `services/scorer.py` | `adversarial/test_expected_loss.py` |
| **Catastrophic loss ⇒ deeply negative NGV** | `services/scorer.py` | `adversarial/test_expected_loss.py` |
| **Realized benefit not re-discounted** | `domain/value.py`, `services/scorer.py` | `unit/test_no_double_discount.py` |
| **Investment ≠ cost-to-serve** | `domain/investment.py` | `unit/test_scorer_happy_path.py` |
| **Actual (historical) loss ≠ forward expected loss** | `domain/case.py`, `services/scorer.py` | `adversarial/test_expected_loss.py` |
| **Honest classification; never over-claims** | `services/scorer.py` | `contract/test_classification.py` |
| **Fail closed** — no basis ⇒ ROI + payback suppressed | `services/scorer.py` | `adversarial/test_fatal_guards_suppress_headline.py` |
| **Geography/domain touch no money** | `domain/modifiers.py` | `unit/test_modifiers.py` |
| **Exact money** — integer minor units, half-even, no float | `domain/money.py` | `unit/test_money.py` |
| **`None` ≠ explicit zero** (cost & investment) | `domain/cost.py`, `domain/investment.py` | `adversarial/test_degrade_guards_keep_headline.py` |
| **Determinism** — same inputs ⇒ identical; ROI is `Decimal` | `services/scorer.py` | `contract/test_determinism.py` |
| **Payback only on a defensible run-rate** | `services/scorer.py` | `unit/test_scorer_happy_path.py` |
| **Confidence never enters the arithmetic** | `services/scorer.py` | (carried, not multiplied) |

## Package layout

```
src/governed_value/
  domain/         money · value · expected_loss · cost · investment · modifiers · attribution · case · enums
  services/       scorer (realized NGV + risk-adjusted view + guards + classification)
  observability/  governance-event bus
  api/            application facade + public surface
tests/            unit · contract · adversarial (+ reusable scenario builder)
```

## Quick start

```python
from decimal import Decimal
from governed_value.api import (GovernedValueApplication, AgentValueCase, AttributionEvidence,
    CostToServe, DomainKind, DomainProfile, ExpectedLoss, ExpectedLossItem, GeographyProfile,
    Money, OutcomeClass, RealizedValue, TotalInvestment, ValueSource)

M = lambda u: Money(u, "USD")
case = AgentValueCase(
    tenant_id="tenant-a", agent_id="support-manila-1",
    domain=DomainProfile(DomainKind.SUPPORT, "contact_deflected", ValueSource.LABOR_DISPLACED),
    geography=GeographyProfile(label="PH", currency="USD"),
    outcome=OutcomeClass.DETERMINISTIC_AUTOMATION,
    benefit=RealizedValue(M(1_000_00), M(0), M(0)),
    actual_losses=M(0),
    residual_expected_loss=ExpectedLoss("USD", (ExpectedLossItem("wrong", Decimal("0.01"), M(200_00)),)),
    cost=CostToServe(currency="USD", inference=M(200_00), retries=M(20_00), evals=M(15_00),
        monitoring=M(10_00), human_in_loop_review=M(50_00), incident_remediation=M(5_00),
        model_migration=M(0)),
    investment=TotalInvestment(currency="USD", capital_expenditure=M(100_00),
        one_time_build=M(300_00), integration=M(100_00), amortized_cost_to_serve=M(0)),
    attribution=AttributionEvidence(baseline_captured=True),
)

r = GovernedValueApplication().score(case)
print(r.stage.value, r.evidence_status.value, r.scorability.value)  # post_deployment_value reported scorable
print(r.realized_roi, r.risk_adjusted_roi)                          # 1.4  1.396
```

## Why exact `Decimal` money?

A CFO audits these figures. Money is integer minor units; probabilities are
`Decimal`; scaling rounds once, half-to-even; floats are rejected at the door.
No binary drift reaches a reported number.

## Verify the distribution

```
python packages/governed-value/verify_governed_value_distribution.py
```

Builds the single wheel, installs it into a clean `--no-index` venv (zero
third-party packages), and proves the realized calculation, the honest
classification, the fail-closed suppression, and the additive-catastrophic-loss
behaviour.

## Not in this package (separate, reviewed phases)

Pre-ROI readiness scoring (Intelligence / Capabilities / Adoption), forecast
modelling, geography/domain/outcome as **versioned policy context**, evidence &
attribution binding, authority adapters, FX / valuation basis / discounting,
per-unit normalization (`NormalizationBasis`), and portfolio comparison. This
kernel deliberately stops at a deterministic realized calculation over reported
inputs.
