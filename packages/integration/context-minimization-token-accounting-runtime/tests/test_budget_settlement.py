"""H22-D budget settlement from measured usage (CM-TA1 §6).

Measured usage settles the actual amount; unavailable usage falls back to the
conservative full-reservation settlement; a measured overrun surfaces
BudgetEstimateExceeded (never clamped or hidden).
"""

from __future__ import annotations

import pytest

from ugence_agent_runtime.orchestration import (
    BudgetCoordinator,
    BudgetEstimateExceeded,
    BudgetRequirement,
    PortfolioBudget,
)

from ugence_context_minimization.api import ProviderTokenUsage

from ugence_cm_token_accounting_runtime import (
    DEFAULT_TOKEN_DIMENSION,
    settle_budget_from_usage,
    token_units_from_usage,
)


def _coord(limit=10000.0):
    return BudgetCoordinator(PortfolioBudget({DEFAULT_TOKEN_DIMENSION: limit}))


def test_measured_usage_settles_actual_amount():
    coord = _coord()
    ok, _ = coord.reserve("wf-1", BudgetRequirement({DEFAULT_TOKEN_DIMENSION: 5000.0}))
    assert ok
    usage = ProviderTokenUsage(input_tokens=2000, output_tokens=300, total_tokens=2300)
    settlement = settle_budget_from_usage(coord, "wf-1", usage)
    assert settlement.actual_known is True
    assert settlement.charged[DEFAULT_TOKEN_DIMENSION] == 2300.0
    # The unused remainder of the reservation is released.
    assert coord.consumed(DEFAULT_TOKEN_DIMENSION) == 2300.0
    assert coord.reserved(DEFAULT_TOKEN_DIMENSION) == 0.0


def test_unavailable_usage_falls_back_to_conservative_settlement():
    coord = _coord()
    coord.reserve("wf-1", BudgetRequirement({DEFAULT_TOKEN_DIMENSION: 5000.0}))
    settlement = settle_budget_from_usage(coord, "wf-1", None)  # usage unavailable
    assert settlement.actual_known is False
    # Conservative: the FULL reservation is charged (never under-charge).
    assert coord.consumed(DEFAULT_TOKEN_DIMENSION) == 5000.0


def test_usage_without_derivable_total_is_conservative():
    coord = _coord()
    coord.reserve("wf-1", BudgetRequirement({DEFAULT_TOKEN_DIMENSION: 5000.0}))
    # input only, no output and no total -> no derivable magnitude.
    usage = ProviderTokenUsage(input_tokens=1000)
    assert token_units_from_usage(usage) is None
    settlement = settle_budget_from_usage(coord, "wf-1", usage)
    assert settlement.actual_known is False
    assert coord.consumed(DEFAULT_TOKEN_DIMENSION) == 5000.0


def test_measured_overrun_surfaces_budget_estimate_exceeded():
    coord = _coord()
    coord.reserve("wf-1", BudgetRequirement({DEFAULT_TOKEN_DIMENSION: 1000.0}))
    usage = ProviderTokenUsage(input_tokens=2000, output_tokens=500, total_tokens=2500)
    with pytest.raises(BudgetEstimateExceeded):
        settle_budget_from_usage(coord, "wf-1", usage)  # 2500 > 1000 reservation
    # The reservation is left intact for the caller to release explicitly.
    assert coord.reserved(DEFAULT_TOKEN_DIMENSION) == 1000.0


def test_derived_total_used_when_no_reported_total():
    usage = ProviderTokenUsage(input_tokens=100, output_tokens=50)  # no total_tokens
    assert token_units_from_usage(usage) == 150.0


def test_reported_total_preferred_over_derived():
    usage = ProviderTokenUsage(input_tokens=100, output_tokens=50, total_tokens=999)
    assert token_units_from_usage(usage) == 999.0
