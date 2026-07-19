"""
Trading pre-trade governance tests (decision layer).

Covers normal authorization, human/model authority, risk/policy controls, the
deterministic-criticality precedence invariants, and backward-compatibility of
the generic engine + healthcare package.
"""

import pytest

from agentic.trading import (
    ApprovedUniverse,
    InstrumentType,
    OrderType,
    Side,
    SessionStatus,
    TradingAction,
    TradingActionRequest,
    TradingGovernanceService,
    TradingLimits,
    TraderRole,
    build_trading_criticality_registry,
    derive_criticality,
    build_default_limits,
    build_default_universe,
)
from agentic.trading.service import TradingOutcome
from agentic.agentic_framework.human_policy import CriticalityClass, RequestContext

GOOD = dict(model_quality=0.9, model_coherence=0.9, model_consistency=0.9,
            model_goal_alignment=0.9, model_trajectory_confidence=0.9)
BAD = dict(model_quality=0.0, model_coherence=0.0, model_consistency=0.0,
           model_goal_alignment=0.0, model_trajectory_confidence=0.0)


@pytest.fixture()
def svc():
    return TradingGovernanceService()


def _req(**over):
    base = dict(
        tenant_id="firm-1", account_id="acct-1", portfolio_id="pf-1",
        actor_id="trader-1", actor_role=TraderRole.AI_EXECUTION_STRATEGY,
        strategy_id="strat-momentum", strategy_version="1.0",
        model_id="model-a", model_version="2025.1",
        action=TradingAction.PLACE_ORDER, side=Side.BUY, symbol="AAA",
        exchange="XNAS", requested_quantity=100, order_type=OrderType.LIMIT,
        limit_price=100.0, market_price=100.0, market_data_timestamp=1000.0,
        now=1002.0, available_cash=1_000_000, portfolio_value=1_000_000,
        destination="sim-broker-1", order_id="o1", **GOOD)
    base.update(over)
    return TradingActionRequest(**base)


# ---- Normal authorization ---------------------------------------------------

def test_01_small_approved_order_allowed(svc):
    d = svc.authorize(_req())
    assert d.outcome == TradingOutcome.ALLOW
    assert d.effective_authority_mode == "baseline"


def test_02_large_order_resized_with_constraints(svc):
    d = svc.authorize(_req(requested_quantity=2000, order_type=OrderType.MARKET))
    assert d.outcome == TradingOutcome.ALLOW_WITH_CONSTRAINTS
    assert d.order_constraints.max_quantity == 400
    assert d.constraints["permitted_order_types"] == ["limit"]


def test_03_position_close_allowed(svc):
    d = svc.authorize(_req(action=TradingAction.CLOSE_POSITION, side=Side.SELL,
                           current_position=100, projected_position=0))
    assert d.outcome == TradingOutcome.ALLOW


def test_04_cancel_allowed(svc):
    d = svc.authorize(_req(action=TradingAction.CANCEL_ORDER))
    assert d.outcome == TradingOutcome.ALLOW


# ---- Human / model authority ------------------------------------------------

def test_05_noncritical_baseline_model_tightens(svc):
    d = svc.authorize(_req(**BAD))
    assert d.effective_authority_mode == "baseline"
    assert d.outcome == TradingOutcome.DENY  # model tightened the baseline


def test_06_critical_source_of_truth_human_controls(svc):
    d = svc.authorize(_req(requested_quantity=2000, **BAD))
    assert d.governance_decision == "ALLOW"
    assert d.outcome == TradingOutcome.ALLOW_WITH_CONSTRAINTS
    assert d.effective_authority_mode == "source_of_truth"
    assert d.final_authority_used == "HUMAN_SOURCE_OF_TRUTH"
    assert d.model_advisory_decision == "DENY"


def test_07_critical_with_hard_block_denies(svc):
    d = svc.authorize(_req(requested_quantity=2000, kill_switch_active=True))
    assert d.outcome == TradingOutcome.DENY
    assert d.hard_block and d.final_authority_used == "HARD_BLOCK"


def test_08_unknown_classification_conservative(svc):
    d = svc.authorize(_req(account_id="acct-unknown"))
    assert d.outcome in (TradingOutcome.REQUIRE_APPROVAL, TradingOutcome.DENY)


# ---- Risk and policy --------------------------------------------------------

def test_09_unapproved_symbol_denied(svc):
    d = svc.authorize(_req(symbol="ZZZ"))
    assert d.outcome == TradingOutcome.DENY
    assert any("symbol_unapproved" in p for p in d.hard_block_provenance)


def test_10_unapproved_model_requires_approval(svc):
    d = svc.authorize(_req(model_version="9.9"))
    assert d.outcome == TradingOutcome.REQUIRE_APPROVAL
    assert d.effective_authority_mode == "source_of_truth"


def test_11_concentration_over_limit_constrained(svc):
    d = svc.authorize(_req(projected_concentration=0.30))
    assert d.outcome in (TradingOutcome.ALLOW_WITH_CONSTRAINTS,
                         TradingOutcome.REQUIRE_APPROVAL, TradingOutcome.DENY)
    assert d.criticality == "critical"


def test_12_insufficient_cash_denied_or_constrained(svc):
    d = svc.authorize(_req(requested_quantity=100, available_cash=50))
    assert d.outcome in (TradingOutcome.DENY, TradingOutcome.ALLOW_WITH_CONSTRAINTS)


def test_13_daily_loss_breached_hard_deny(svc):
    d = svc.authorize(_req(realized_pnl=-60_000))
    assert d.outcome == TradingOutcome.DENY and d.hard_block


def test_14_kill_switch_hard_deny(svc):
    d = svc.authorize(_req(kill_switch_active=True))
    assert d.outcome == TradingOutcome.DENY and d.hard_block


def test_15_stale_market_data_hard_deny(svc):
    d = svc.authorize(_req(now=2000.0))  # quote age 1000s >> max
    assert d.outcome == TradingOutcome.DENY and d.hard_block


def test_16_excessive_price_deviation_constrained(svc):
    d = svc.authorize(_req(limit_price=110.0))  # 10% deviation
    assert d.outcome in (TradingOutcome.ALLOW_WITH_CONSTRAINTS,
                         TradingOutcome.REQUIRE_APPROVAL)
    if d.order_constraints:
        assert d.order_constraints.max_price <= 100 * (1 + 0.02)


def test_17_unsupported_instrument_hard_deny(svc):
    d = svc.authorize(_req(instrument_type=InstrumentType.OPTION))
    assert d.outcome == TradingOutcome.DENY and d.hard_block
    # short sale (V1) also hard-blocked
    d2 = svc.authorize(_req(side=Side.SELL, projected_position=-100))
    assert d2.outcome == TradingOutcome.DENY and d2.hard_block


# ---- Deterministic-classifier trust invariants ------------------------------

def test_32_caller_label_large_order_routine_still_promoted(svc):
    d = svc.authorize(_req(requested_quantity=2000,
                           declared_facts={"low_risk": True, "non_critical": True,
                                           "routine": True, "small_order": True}))
    assert d.criticality == "critical"
    assert d.effective_authority_mode == "source_of_truth"


def test_33_critical_promoting_overrides_non_critical():
    limits, universe = build_default_limits(), build_default_universe()
    d = derive_criticality(_req(requested_quantity=2000,
                                declared_facts={"hc_non_critical": True}),
                           limits, universe)
    assert d.signal == "critical"
    assert "hc_non_critical" not in d.facts


def test_34_missing_material_facts_conservative(svc):
    for over in (dict(account_id=""), dict(strategy_id=None), dict(symbol=None),
                 dict(market_data_timestamp=0.0), dict(portfolio_id=None)):
        d = svc.authorize(_req(**over))
        assert d.outcome in (TradingOutcome.REQUIRE_APPROVAL, TradingOutcome.DENY), over


# ---- Generic-registry precedence invariants ---------------------------------

def _ctx(facts):
    return RequestContext(action_type="X", tool_name="t", risk_level="write",
                          actor_id="a", agency_level="FULL", capabilities=(),
                          facts=facts, target_haystack="")


def test_registry_promotion_wins_over_non_critical_fact():
    reg = build_trading_criticality_registry()
    crit, _ = reg.classify(_ctx({"hc_critical": True, "hc_non_critical": True}))
    assert crit == CriticalityClass.CRITICAL


def test_registry_unknown_not_downgraded_by_stray_fact():
    reg = build_trading_criticality_registry()
    crit, _ = reg.classify(_ctx({"routine": True}))
    assert crit == CriticalityClass.UNKNOWN


# ---- Backward compatibility -------------------------------------------------

def test_37_generic_and_healthcare_unchanged():
    # Generic engine, no engine configured → human_policy None.
    from agentic.agentic_framework.governance_service import GovernanceService
    from agentic.agentic_framework.governance_models import AuthorizationRequest
    r = GovernanceService().authorize(AuthorizationRequest(
        actor_id="a", action_type="file_read", tool_name="read_file",
        quality_score=0.9, coherence_score=0.9, internal_consistency=0.9,
        goal_alignment=0.9, trajectory_confidence=0.9, agency_level="FULL"))
    assert r.human_policy is None and r.governance_decision.value == "ALLOW"
    # Healthcare service still functions.
    from agentic.healthcare import (
        HealthcareGovernanceService, HealthcareAccessRequest,
        DataCategory, Operation, Purpose, Role)
    hd = HealthcareGovernanceService().authorize(HealthcareAccessRequest(
        tenant_id="h", actor_id="b", actor_role=Role.AI_BILLING_AGENT,
        operation=Operation.READ, purpose=Purpose.PAYMENT,
        requested_categories=(DataCategory.BILLING,), patient_ref="p1", **GOOD))
    assert hd.outcome.value in ("ALLOW", "ALLOW_WITH_CONSTRAINTS")
