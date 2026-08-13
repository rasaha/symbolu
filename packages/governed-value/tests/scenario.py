"""Reusable scenario builders for the realized (POST_DEPLOYMENT_VALUE) suite.

``scorable_support_case`` is the canonical happy path: a captured baseline, a
complete cost-to-serve and investment, explicit zero actual losses, and one
residual expected-loss item. Tests mutate one facet at a time.
"""

from __future__ import annotations

from decimal import Decimal

from governed_value.api import (
    AgentValueCase,
    AttributionEvidence,
    CostToServe,
    DomainKind,
    DomainProfile,
    ExpectedLoss,
    ExpectedLossItem,
    GeographyProfile,
    Money,
    OutcomeClass,
    RealizedValue,
    TotalInvestment,
    ValueSource,
)

USD = "USD"


def money(units: int, currency: str = USD) -> Money:
    return Money(units, currency)


def full_cost(currency: str = USD) -> CostToServe:
    return CostToServe(
        currency=currency,
        inference=money(200_00, currency),
        retries=money(20_00, currency),
        evals=money(15_00, currency),
        monitoring=money(10_00, currency),
        human_in_loop_review=money(50_00, currency),
        incident_remediation=money(5_00, currency),
        model_migration=money(0, currency),
    )


def full_investment(currency: str = USD) -> TotalInvestment:
    return TotalInvestment(
        currency=currency,
        capital_expenditure=money(100_00, currency),
        one_time_build=money(300_00, currency),
        integration=money(100_00, currency),
        amortized_cost_to_serve=money(0, currency),
    )


def one_expected_loss(currency: str = USD) -> ExpectedLoss:
    # 1% chance of a $200 wrongful action -> expected value $2.00 (200 minor units).
    return ExpectedLoss(
        currency=currency,
        items=(
            ExpectedLossItem(
                label="wrongful_action",
                probability=Decimal("0.01"),
                loss_magnitude=money(200_00, currency),
            ),
        ),
    )


def scorable_support_case(**overrides) -> AgentValueCase:
    base = dict(
        tenant_id="tenant-a",
        agent_id="support-manila-1",
        domain=DomainProfile(
            kind=DomainKind.SUPPORT,
            natural_unit="contact_deflected_quality_adjusted",
            dominant_source=ValueSource.LABOR_DISPLACED,
        ),
        geography=GeographyProfile(label="PH", currency=USD),
        outcome=OutcomeClass.DETERMINISTIC_AUTOMATION,
        benefit=RealizedValue(
            labor_displaced=money(1_000_00),
            throughput_gained=money(0),
            loss_avoided=money(0),
        ),
        actual_losses=money(0),
        residual_expected_loss=one_expected_loss(),
        cost=full_cost(),
        investment=full_investment(),
        attribution=AttributionEvidence(baseline_captured=True),
    )
    base.update(overrides)
    return AgentValueCase(**base)
