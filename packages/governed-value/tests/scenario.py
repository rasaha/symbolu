"""Reusable scenario builders for the governed-value suite.

``scorable_support_case`` is the canonical happy path: a support-deflection
agent with a captured baseline, a priced wrong-action term, a complete TCO, and
authorized actions to normalize over. Tests mutate one facet at a time to prove
each guard fires (or does not) independently.
"""

from __future__ import annotations

from decimal import Decimal

from governed_value.api import (
    AgentValueCase,
    AttributionContext,
    AuthorizedActionRef,
    CostToServe,
    DomainKind,
    DomainProfile,
    ErrorProfile,
    GeographyProfile,
    Money,
    OutcomeClass,
    RealizedValue,
    ValueSource,
)

USD = "USD"


def money(units: int, currency: str = USD) -> Money:
    return Money(units, currency)


def full_cost(currency: str = USD) -> CostToServe:
    """A TCO that speaks to all seven components (some deliberately zero)."""

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


def scorable_support_case(**overrides) -> AgentValueCase:
    base = dict(
        agent_id="support-manila-1",
        domain=DomainProfile(
            kind=DomainKind.SUPPORT,
            natural_unit="contact_deflected_quality_adjusted",
            dominant_source=ValueSource.LABOR_DISPLACED,
        ),
        geography=GeographyProfile(label="PH", currency=USD),
        outcome=OutcomeClass.DETERMINISTIC_AUTOMATION,
        realized=RealizedValue(
            labor_displaced=money(1_000_00),
            throughput_gained=money(0),
            loss_avoided=money(0),
        ),
        error_profile=ErrorProfile(p_error=Decimal("0.05"), severity=Decimal("0.20")),
        cost=full_cost(),
        attribution=AttributionContext(
            baseline_captured=True,
            realization_rate=Decimal("0.90"),
            headcount_or_scope_changed=True,
            attribution_fraction=Decimal("1.0"),
            concurrent_changes=0,
            holdout_or_staged=False,
        ),
        action=AuthorizedActionRef(
            tenant_id="tenant-a",
            envelope_id="env-1",
            action_digest="digest-1",
            authorized_count=500,
        ),
    )
    base.update(overrides)
    return AgentValueCase(**base)
