"""
Trading enforcement + adversarial validation (simulated broker/OMS).

Proves authorized constraints are enforced between authorization and order
submission and cannot be widened, retargeted, replayed, or bypassed. All data is
synthetic. Required unauthorized-execution count is ZERO.
"""

import json

import pytest

from agentic.trading import (
    OrderType, Side, TradingAction, TradingActionRequest, TraderRole,
)
from agentic.trading.taxonomy import AccountStatus, StrategyStatus
from agentic.trading.enforcement import (
    ExecutionOrder, MismatchCode, TradingEnforcementHarness,
)

GOOD = dict(model_quality=0.9, model_coherence=0.9, model_consistency=0.9,
            model_goal_alignment=0.9, model_trajectory_confidence=0.9)


def _req(**over):
    base = dict(
        tenant_id="firm-1", account_id="acct-1", portfolio_id="pf-1",
        actor_id="trader-1", actor_role=TraderRole.AI_EXECUTION_STRATEGY,
        strategy_id="strat-momentum", strategy_version="1.0",
        model_id="model-a", model_version="2025.1",
        action=TradingAction.PLACE_ORDER, side=Side.BUY, symbol="AAA",
        exchange="XNAS", requested_quantity=100, order_type=OrderType.LIMIT,
        limit_price=100.0, market_price=100.0, market_data_timestamp=1_000_000.0,
        now=1_000_001.0, available_cash=1_000_000, portfolio_value=1_000_000,
        destination="sim-broker-1", order_id="o1", **GOOD)
    base.update(over)
    return TradingActionRequest(**base)


@pytest.fixture()
def h():
    return TradingEnforcementHarness()


def _issue(h, **req_over):
    """authorize + issue a fresh (unexecuted) artifact for TOCTOU tests."""
    req = _req(**req_over)
    dec = h.authorize(req)
    art = h.issue(dec, req)
    return dec, art


def test_happy_path_submits(h):
    dec, art, res = h.run(_req(), order_id="ord-1")
    assert res.submitted and res.denial_code is None


# ---- Enforcement attacks (18–31) --------------------------------------------

def test_18_increase_quantity_rejected(h):
    _, art = _issue(h)
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a", quantity=1e9))
    assert r.denial_code == MismatchCode.QUANTITY_WIDENING.value


def test_19_increase_notional_rejected(h):
    _, art = _issue(h)
    # keep quantity legal but push the limit price to inflate notional past bound
    r = h.execute(art, ExecutionOrder.faithful_from(
        art, order_id="a", limit_price=(art.max_price or 100) * 5))
    assert r.denial_code in (MismatchCode.NOTIONAL_WIDENING.value,
                             MismatchCode.PRICE_OUT_OF_BOUNDS.value)


def test_20_change_symbol_rejected(h):
    _, art = _issue(h)
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a", symbol="BBB"))
    assert r.denial_code == MismatchCode.SYMBOL_MISMATCH.value


def test_21_change_account_rejected(h):
    _, art = _issue(h)
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a", account_id="acct-2"))
    assert r.denial_code == MismatchCode.ACCOUNT_MISMATCH.value


def test_22_change_venue_rejected(h):
    _, art = _issue(h)
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a", venue="evil-venue"))
    assert r.denial_code == MismatchCode.VENUE_MISMATCH.value


def test_23_limit_to_market_rejected(h):
    _, art = _issue(h)
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a", order_type="market"))
    assert r.denial_code == MismatchCode.ORDER_TYPE_MISMATCH.value


def test_24_price_outside_bounds_rejected(h):
    _, art = _issue(h)
    r = h.execute(art, ExecutionOrder.faithful_from(
        art, order_id="a", limit_price=(art.max_price or 100) + 50))
    assert r.denial_code in (MismatchCode.PRICE_OUT_OF_BOUNDS.value,
                             MismatchCode.NOTIONAL_WIDENING.value)


def test_25_change_side_and_strategy_rejected(h):
    _, art = _issue(h)
    r1 = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a", side="sell"))
    assert r1.denial_code == MismatchCode.SIDE_MISMATCH.value
    r2 = h.execute(art, ExecutionOrder.faithful_from(art, order_id="b", strategy_id="other"))
    assert r2.denial_code == MismatchCode.STRATEGY_MISMATCH.value
    r3 = h.execute(art, ExecutionOrder.faithful_from(art, order_id="c", model_version="9.9"))
    assert r3.denial_code == MismatchCode.MODEL_MISMATCH.value


def test_26_replay_one_time_rejected(h):
    dec, art, res = h.run(_req(), order_id="first")
    assert res.submitted
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="second"))
    assert r.denial_code == MismatchCode.REPLAY.value


def test_27_expired_artifact_rejected(h):
    _, art = _issue(h)
    h.clock.advance(10_000)
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a"))
    assert r.denial_code == MismatchCode.EXPIRED.value


def test_28_kill_switch_between_auth_and_exec_rejected(h):
    _, art = _issue(h)
    h.broker.risk.kill_switch = True
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a"))
    assert r.denial_code == MismatchCode.KILL_SWITCH.value


def test_29_daily_loss_crossed_between_auth_and_exec_rejected(h):
    _, art = _issue(h)
    h.broker.risk.daily_loss["acct-1"] = 60_000
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a"))
    assert r.denial_code == MismatchCode.DAILY_LOSS.value


def test_30_market_data_stale_between_auth_and_exec_rejected(h):
    _, art = _issue(h)
    h.broker.market.set_quote("AAA", 100.0, h.clock() - 10_000)  # now stale
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a"))
    assert r.denial_code == MismatchCode.STALE_MARKET_DATA.value


def test_31_reuse_artifact_for_second_order_rejected(h):
    dec, art, res = h.run(_req(), order_id="first")
    assert res.submitted
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="second-order"))
    assert r.denial_code == MismatchCode.REPLAY.value


def test_account_or_strategy_suspended_between_auth_and_exec(h):
    _, art = _issue(h)
    h.broker.risk.account_status["acct-1"] = AccountStatus.SUSPENDED
    r = h.execute(art, ExecutionOrder.faithful_from(art, order_id="a"))
    assert r.denial_code == MismatchCode.ACCOUNT_SUSPENDED.value


# ---- Duplicate / burst (35) -------------------------------------------------

def test_35_duplicate_order_id_blocked(h):
    dec, art, res = h.run(_req(), order_id="dup-1")  # consumes; but not one_time? it is
    # Use a non-one-time artifact to isolate duplicate detection.
    dec2, art2 = _issue(h)
    art2 = art2  # one_time True by default; issue with one_time False for reuse
    dec3 = h.authorize(_req())
    art3 = h.issue(dec3, _req(), one_time=False)
    o1 = ExecutionOrder.faithful_from(art3, order_id="same-id")
    r1 = h.execute(art3, o1)
    assert r1.submitted
    r2 = h.execute(art3, ExecutionOrder.faithful_from(art3, order_id="same-id"))
    assert r2.denial_code == MismatchCode.DUPLICATE_ORDER.value


# ---- Receipt / audit safety (36) --------------------------------------------

def test_36_receipt_and_artifact_have_no_secrets(h):
    dec, art, res = h.run(_req(), order_id="ord-x")
    blob = json.dumps(res.receipt.to_dict()) + json.dumps(art.safe_dict())
    for banned in ("api_key", "apikey", "secret", "password", "token", "credential"):
        assert banned not in blob.lower()
    # HMAC tag is an authentication tag, exposed only as presence flag in safe_dict.
    assert "hmac_present" in art.safe_dict()


# ---- Zero unauthorized executions + metrics ---------------------------------

def test_metrics_zero_unauthorized_and_correlation_complete(h):
    # A spread of allowed, constrained, denied, and attacked flows.
    h.run(_req(), order_id="m1")                                   # allow+submit
    h.run(_req(requested_quantity=2000), order_id="m2")           # constrained+submit
    _, artk = _issue(h)
    h.broker.risk.kill_switch = True
    h.execute(artk, ExecutionOrder.faithful_from(artk, order_id="m3"))  # blocked
    h.broker.risk.kill_switch = False
    _, arts = _issue(h)
    h.execute(arts, ExecutionOrder.faithful_from(arts, order_id="m4", quantity=1e9))  # widen
    m = h.metrics.to_dict()
    assert m["unauthorized_executions"] == 0
    assert m["scope_widening_attempts_blocked"] >= 1
    assert m["risk_limit_breaches_blocked"] >= 1
    assert m["audit_correlation_completeness"] == 1.0
