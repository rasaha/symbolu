# Ugence Governed Value (`ugence-governed-value`)

Governed-value accounting kernel. This independently packaged module turns an
agent's **realized value**, **wrong-action risk**, and **cost of ownership** into
one auditable figure — **net governed value per authorized action (NGVA)** —
measured at the control-plane chokepoint where authorization already happens.

> Your ROI deck tells you an agent is positive. Ugence tells you whether that
> number survives its own error term, its baseline, and its attribution.

## The spine

```
ROI            = (realized value − TCO) / TCO
realized value = labor displaced + throughput/revenue gained + loss avoided
net gov. value = realized value × (1 − p_error × severity) − cost to serve
NGVA           = net governed value / authorized actions
```

Realized value decomposes into **only three sources**. Everything else
(satisfaction, "productivity", adoption) is a leading indicator, not value, and
is intentionally not representable in the numerator. Critically, net value is
reduced by the cost of the agent's *wrong* actions — the term that most models
omit, and the reason agents that look strongly positive usually aren't.

**Domain, geography and intended outcome are modifiers on the spine's terms, not
three separate frameworks.**

| Lens | What it moves |
|---|---|
| **Domain** | the natural value unit + the error asymmetry (`min_severity` floor in high-consequence domains) |
| **Geography** | the *denominator* mostly — regulatory load and residency inference cost add to TCO; locale performance scales the realization rate |
| **Intended outcome** | the *measurement method* — deterministic → before/after; judgment → holdout; discovery → option value; risk containment → actuarial baseline |

## Design invariants (enforced + tested)

| Invariant | Where | Test |
|---|---|---|
| **Fail closed** — no defensible basis ⇒ headline `ngva`/`roi` suppressed | `services.scorer` | `adversarial/test_fatal_guards_suppress_headline.py` |
| **Error term is mandatory** — an unpriced `p_error`/`severity` is NOT_SCORABLE | `services.scorer`, `domain.error_profile` | `adversarial/test_fatal_guards_suppress_headline.py` |
| **Baseline required** — no pre-deployment baseline ⇒ NOT_SCORABLE | `services.scorer`, `domain.attribution` | `adversarial/…` |
| **Holdout where attribution is unrecoverable** — judgment/risk-containment need it | `services.scorer` | `adversarial/…` |
| **One action, one denominator** — normalize per authorized action or nothing | `domain.action`, `services.scorer` | `adversarial/…` |
| **Error asymmetry floor** — regulated domains reject an under-priced severity | `domain.modifiers`, `services.scorer` | `adversarial/…` |
| **Exact money** — integer minor units, one half-even rounding, no binary drift | `domain.money` | `unit/test_money.py` |
| **Determinism** — same inputs ⇒ bit-identical result; NGVA is `Decimal` | `services.scorer` | `contract/test_determinism.py` |
| **Currency isolation** — no silent cross-currency add; portfolio needs one base | `domain.money`, `services.portfolio` | `unit/test_money.py`, `adversarial/test_portfolio_commensurability.py` |
| **Decay is per-period** — value is recomputed as drift accrues, not once | `domain.attribution`, `services.decay` | `unit/test_decay.py` |

### The five ROI-model failures, as executable guards

| Failure | Guard | Verdict |
|---|---|---|
| 1. No baseline before go-live | `attribution.baseline_captured` | **NOT_SCORABLE** |
| 2. Realization assumed at 100% | `realization_rate == 1 & not headcount_or_scope_changed` | DEGRADED |
| 3. TCO omits retries/evals/monitoring/HITL/remediation/migration | `cost.missing_components()` | DEGRADED |
| 4. No decay term | `decay_per_period == 0 & periods_elapsed > 0` | DEGRADED |
| 5. Full credit amid several concurrent changes | `concurrent_changes > 0 & not holdout_or_staged` | DEGRADED |
| (spine) Unpriced wrong-action term | `error_profile.is_priced()` | **NOT_SCORABLE** |

`NOT_SCORABLE` suppresses the headline; `DEGRADED` keeps it with an attached,
auditable advisory. A number without a defensible basis is worse than no number.

## Package layout

```
src/governed_value/
  domain/         money · value sources · error profile · cost · modifiers · attribution · case
  services/       scorer (NGVA + guards) · decay projection · portfolio normalization
  integrations/   AuthorizedActionPort chokepoint seam (+ reference ledger)
  observability/  governance-event bus
  api/            application facade + public surface
tests/            unit · contract · adversarial (+ reusable scenario builder)
```

## Quick start

```python
from decimal import Decimal
from governed_value.api import (GovernedValueApplication, AgentValueCase, AttributionContext,
    AuthorizedActionRef, CostToServe, DomainKind, DomainProfile, ErrorProfile,
    GeographyProfile, Money, OutcomeClass, RealizedValue, ValueSource)

case = AgentValueCase(
    agent_id="support-manila-1",
    domain=DomainProfile(DomainKind.SUPPORT, "contact_deflected", ValueSource.LABOR_DISPLACED),
    geography=GeographyProfile(label="PH", currency="USD"),
    outcome=OutcomeClass.DETERMINISTIC_AUTOMATION,
    realized=RealizedValue(Money(1_000_00, "USD"), Money(0, "USD"), Money(0, "USD")),
    error_profile=ErrorProfile(p_error=Decimal("0.05"), severity=Decimal("0.20")),
    cost=CostToServe(currency="USD", inference=Money(200_00, "USD"), retries=Money(20_00, "USD"),
        evals=Money(15_00, "USD"), monitoring=Money(10_00, "USD"),
        human_in_loop_review=Money(50_00, "USD"), incident_remediation=Money(5_00, "USD"),
        model_migration=Money(0, "USD")),
    attribution=AttributionContext(baseline_captured=True, realization_rate=Decimal("0.90"),
        headcount_or_scope_changed=True),
    action=AuthorizedActionRef("tenant-a", "env-1", "digest-1", authorized_count=500),
)

app = GovernedValueApplication()
result = app.score(case)
print(result.scorability, result.ngva_per_action)   # Scorability.SCORABLE 118.2
```

`app.compare([...], base_currency="USD")` ranks a heterogeneous portfolio by
NGVA; `app.project(case, horizon=4)` recomputes it per period under decay.

## The chokepoint seam

`governed_value` never imports the authority kernel. It measures *per authorized
action*, so the count of authorized actions is resolved through
`integrations.authorization.AuthorizedActionPort`. A production deployment adapts
a signed `RiskAuthorizationEnvelope` (`ugence-risk-authority`) onto that port —
through the contract — exactly as `risk_authority` consumes ActionGate/TAP/PWC
through *its* ports. This keeps the package a **stdlib-only leaf**: the
conformance suite installs the single wheel into a clean `--no-index` venv with
zero third-party packages, like the other governance leaves.

## Why exact `Decimal` money?

Because a CFO audits this figure. Money is integer minor units; ratios are
`Decimal`; scaling rounds once, half-to-even. Floats are rejected at the door
(`Decimal(0.1) != 0.1`), so no binary drift reaches a reported number.

## Verify the distribution

```
python packages/governed-value/verify_governed_value_distribution.py
```

## Scope note

This slice ships the scoring spine, the modifier lenses, the five-failure
guards, decay projection and portfolio normalization. It deliberately **excludes**
FX conversion (bring a base currency), a persistence backend, and an HTTP route
adapter — their seams are present (transport-neutral facade, per-currency
portfolio) and layer on without touching the kernel.
