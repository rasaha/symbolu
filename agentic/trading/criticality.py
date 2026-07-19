"""
Deterministic trading criticality + risk derivation and order-sizing.

Criticality and hard-block conditions are derived ONLY from deterministic request
facts and human-authored registries (limits + approved universe). Caller-declared
labels (low_risk, non_critical, routine, approved, safe, small_order) are ignored;
caller facts may only promote conservatism, never downgrade.

Precedence (safest first): hard-block > critical > missing-fact(unknown) >
non-critical > unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

from agentic.trading.request import TradingActionRequest
from agentic.trading.taxonomy import (
    AI_ROLES,
    AccountStatus,
    EXECUTABLE_ORDER_ACTIONS,
    InstrumentType,
    NON_EXECUTED_ACTIONS,
    OrderType,
    RISK_REDUCING_ACTIONS,
    SUPPORTED_INSTRUMENTS,
    SessionStatus,
    Side,
    StrategyStatus,
    TradingAction,
    TraderRole,
)

# ---- Hard-block capability tokens (routed through generic forbidden layer) ----
HB_NO_ACTOR = "trade.no_actor_identity"
HB_KILL_SWITCH = "trade.kill_switch_active"
HB_ACCOUNT_SUSPENDED = "trade.account_suspended"
HB_STRATEGY_SUSPENDED = "trade.strategy_suspended"
HB_UNSUPPORTED_INSTRUMENT = "trade.unsupported_instrument"
HB_SHORT_SALE = "trade.short_sale_unsupported"
HB_SYMBOL_UNAPPROVED = "trade.symbol_unapproved"
HB_VENUE_UNAPPROVED = "trade.venue_unapproved"
HB_EXCHANGE_UNAPPROVED = "trade.exchange_unapproved"
HB_STALE_DATA = "trade.stale_market_data"
HB_DAILY_LOSS = "trade.daily_loss_breached"
HB_POSITION_MAX = "trade.position_over_absolute_max"
HB_INSUFFICIENT_CASH = "trade.insufficient_cash"
HB_RISK_CHANGE_UNAUTH = "trade.risk_limit_change_unauthorized"
HB_HARD_BLOCK_OVERRIDE = "trade.hard_block_override_attempt"

ALL_HARD_BLOCK_TOKENS: Tuple[str, ...] = (
    HB_NO_ACTOR, HB_KILL_SWITCH, HB_ACCOUNT_SUSPENDED, HB_STRATEGY_SUSPENDED,
    HB_UNSUPPORTED_INSTRUMENT, HB_SHORT_SALE, HB_SYMBOL_UNAPPROVED,
    HB_VENUE_UNAPPROVED, HB_EXCHANGE_UNAPPROVED, HB_STALE_DATA, HB_DAILY_LOSS,
    HB_POSITION_MAX, HB_INSUFFICIENT_CASH, HB_RISK_CHANGE_UNAUTH,
    HB_HARD_BLOCK_OVERRIDE,
)


@dataclass(frozen=True)
class TradingLimits:
    """Human-authored risk limits (configurable)."""

    preferred_order_quantity: float = 400.0
    max_order_quantity: float = 5000.0
    max_order_notional: float = 100_000.0
    max_position: float = 10_000.0
    absolute_max_position: float = 20_000.0
    max_concentration_pct: float = 0.25
    max_sector_concentration_pct: float = 0.40
    max_daily_turnover: float = 1_000_000.0
    max_daily_loss: float = 50_000.0        # magnitude
    soft_loss_ratio: float = 0.80
    max_quote_age_seconds: float = 5.0
    max_price_deviation_pct: float = 0.02
    constrained_price_deviation_pct: float = 0.005
    min_cash: float = 0.0
    burst_threshold: int = 5


@dataclass(frozen=True)
class ApprovedUniverse:
    """Human-authored approved trading universe (configurable)."""

    accounts: FrozenSet[str] = field(default_factory=frozenset)
    strategies: Mapping[str, FrozenSet[str]] = field(default_factory=dict)
    models: Mapping[str, FrozenSet[str]] = field(default_factory=dict)
    exchanges: FrozenSet[str] = field(default_factory=frozenset)
    symbols: FrozenSet[str] = field(default_factory=frozenset)
    venues: FrozenSet[str] = field(default_factory=frozenset)
    permitted_sessions: FrozenSet[SessionStatus] = field(
        default_factory=lambda: frozenset({SessionStatus.OPEN}))

    def account_ok(self, a: Optional[str]) -> bool:
        return bool(a) and a in self.accounts

    def strategy_ok(self, sid: Optional[str], ver: Optional[str]) -> bool:
        return bool(sid) and ver in self.strategies.get(sid, frozenset())

    def model_ok(self, mid: Optional[str], ver: Optional[str]) -> bool:
        if mid is None and ver is None:
            return True  # no model attached (e.g. human trader)
        return bool(mid) and ver in self.models.get(mid, frozenset())

    def exchange_ok(self, e: Optional[str]) -> bool:
        return bool(e) and e in self.exchanges

    def symbol_ok(self, s: Optional[str]) -> bool:
        return bool(s) and s in self.symbols

    def venue_ok(self, v: Optional[str]) -> bool:
        return bool(v) and v in self.venues

    def session_ok(self, s: SessionStatus) -> bool:
        return s in self.permitted_sessions


@dataclass(frozen=True)
class CriticalityDerivation:
    signal: str  # "critical" | "non_critical" | "unknown"
    facts: Dict[str, Any]
    hard_block_capabilities: Tuple[str, ...]
    basis: Tuple[str, ...]

    @property
    def hard_blocked(self) -> bool:
        return bool(self.hard_block_capabilities)


def _notional(request: TradingActionRequest) -> float:
    if request.requested_notional > 0:
        return request.requested_notional
    return request.requested_quantity * request.market_price


def derive_criticality(
    request: TradingActionRequest,
    limits: TradingLimits,
    universe: ApprovedUniverse,
) -> CriticalityDerivation:
    action = request.action
    is_order = action in EXECUTABLE_ORDER_ACTIONS
    is_buy = request.side == Side.BUY
    is_sell = request.side == Side.SELL
    qty = request.requested_quantity
    notional = _notional(request)

    quote_age = (
        request.now - request.market_data_timestamp
        if request.now > 0 and request.market_data_timestamp > 0 else None)
    loss = max(0.0, -(request.realized_pnl + request.unrealized_pnl))
    loss_breached = loss >= limits.max_daily_loss
    loss_soft = loss >= limits.soft_loss_ratio * limits.max_daily_loss
    price_dev = (
        abs((request.limit_price or 0.0) - request.market_price) / request.market_price
        if request.market_price > 0 and request.limit_price else 0.0)

    over_absolute_position = request.projected_position > limits.absolute_max_position
    over_position = request.projected_position > limits.max_position
    over_preferred = qty > limits.preferred_order_quantity
    over_max_qty = qty > limits.max_order_quantity
    over_notional = notional > limits.max_order_notional
    over_conc = request.projected_concentration >= limits.max_concentration_pct
    over_sector = (request.sector_concentration is not None
                   and request.sector_concentration >= limits.max_sector_concentration_pct)
    over_turnover = request.daily_turnover + notional > limits.max_daily_turnover
    insufficient_cash = is_buy and notional > request.available_cash
    short_sale = is_sell and request.projected_position < 0
    unsupported = request.instrument_type not in SUPPORTED_INSTRUMENTS
    stale = quote_age is not None and quote_age > limits.max_quote_age_seconds
    no_actor = not (request.actor_id and request.actor_id.strip())
    risk_change = action == TradingAction.CHANGE_RISK_LIMIT
    override_attempt = bool(
        request.kill_switch_active is False and (
            request.declared_facts.get("override_kill_switch")
            or request.declared_facts.get("disable_hard_block")))

    symbol_ok = universe.symbol_ok(request.symbol)
    venue_ok = universe.venue_ok(request.destination)
    exchange_ok = universe.exchange_ok(request.exchange)
    account_ok = universe.account_ok(request.account_id)
    strategy_ok = universe.strategy_ok(request.strategy_id, request.strategy_version)
    model_ok = universe.model_ok(request.model_id, request.model_version)
    session_ok = universe.session_ok(request.session_status)

    facts: Dict[str, Any] = {
        f"action:{action.value}": True,
        f"side:{request.side.value}" if request.side else "side:none": True,
        f"order_type:{request.order_type.value}": True,
        f"actor_role:{request.actor_role.value}": True,
        "is_order_action": is_order,
        "risk_reducing": action in RISK_REDUCING_ACTIONS,
        "symbol_approved": symbol_ok,
        "venue_approved": venue_ok,
        "exchange_approved": exchange_ok,
        "account_approved": account_ok,
        "strategy_approved": strategy_ok,
        "model_approved": model_ok,
        "session_open": session_ok,
        "over_preferred_quantity": over_preferred,
        "over_max_quantity": over_max_qty,
        "over_order_notional": over_notional,
        "over_position": over_position,
        "over_absolute_position": over_absolute_position,
        "over_concentration": over_conc,
        "over_sector_concentration": bool(over_sector),
        "over_turnover": over_turnover,
        "insufficient_cash": insufficient_cash,
        "short_sale": short_sale,
        "unsupported_instrument": unsupported,
        "stale_market_data": bool(stale),
        "price_deviation_exceeded": price_dev > limits.max_price_deviation_pct,
        "daily_loss_breached": loss_breached,
        "daily_loss_soft": loss_soft,
        "kill_switch_active": request.kill_switch_active,
        "account_suspended": request.account_status == AccountStatus.SUSPENDED,
        "strategy_suspended": request.strategy_status == StrategyStatus.SUSPENDED,
        "burst": request.burst_count > limits.burst_threshold,
        "risk_change": risk_change,
        "no_actor_identity": no_actor,
        "is_ai_actor": request.actor_role in AI_ROLES,
        "constrainable_order": is_order and (
            over_preferred or over_max_qty or over_notional or over_position
            or over_conc or bool(over_sector) or over_turnover
            or price_dev > limits.max_price_deviation_pct),
    }

    for k, v in dict(request.declared_facts).items():
        if k in ("hc_critical", "hc_non_critical"):
            continue
        facts.setdefault(f"declared_{k}", v)

    basis: List[str] = []
    hard_blocks: List[str] = []

    def hb(token: str, reason: str) -> None:
        hard_blocks.append(token)
        basis.append(f"hard_block:{reason}")

    # ---- 1. Hard blocks ----------------------------------------------------
    if no_actor:
        hb(HB_NO_ACTOR, "no_actor_identity")
    if request.kill_switch_active:
        hb(HB_KILL_SWITCH, "kill_switch_active")
    if override_attempt:
        hb(HB_HARD_BLOCK_OVERRIDE, "hard_block_override_attempt")
    if request.account_status == AccountStatus.SUSPENDED:
        hb(HB_ACCOUNT_SUSPENDED, "account_suspended")
    if request.strategy_status == StrategyStatus.SUSPENDED:
        hb(HB_STRATEGY_SUSPENDED, "strategy_suspended")
    if is_order or action == TradingAction.INCREASE_POSITION:
        if unsupported:
            hb(HB_UNSUPPORTED_INSTRUMENT, "unsupported_instrument")
        if short_sale:
            hb(HB_SHORT_SALE, "short_sale_unsupported")
        if not symbol_ok:
            hb(HB_SYMBOL_UNAPPROVED, "symbol_unapproved")
        if request.destination is not None and not venue_ok:
            hb(HB_VENUE_UNAPPROVED, "venue_unapproved")
        if request.exchange is not None and not exchange_ok:
            hb(HB_EXCHANGE_UNAPPROVED, "exchange_unapproved")
        if stale:
            hb(HB_STALE_DATA, "stale_market_data")
        if over_absolute_position:
            hb(HB_POSITION_MAX, "position_over_absolute_max")
        if insufficient_cash:
            hb(HB_INSUFFICIENT_CASH, "insufficient_cash")
    if loss_breached:
        hb(HB_DAILY_LOSS, "daily_loss_breached")
    if risk_change and not request.risk_change_authorized:
        hb(HB_RISK_CHANGE_UNAUTH, "risk_limit_change_unauthorized")

    if hard_blocks:
        facts["hc_critical"] = True
        facts["missing_material_facts"] = False
        return CriticalityDerivation(
            "critical", facts, tuple(dict.fromkeys(hard_blocks)), tuple(basis))

    # ---- 2. Missing material facts (recorded; conservative if not critical) -
    missing: List[str] = []
    if is_order:
        if not request.account_id:
            missing.append("missing:account")
        if request.strategy_id is None:
            missing.append("missing:strategy")
        if request.symbol is None:
            missing.append("missing:symbol")
        if request.market_data_timestamp <= 0:
            missing.append("missing:market_data_timestamp")
        if request.portfolio_id is None:
            missing.append("missing:portfolio")
    facts["missing_material_facts"] = bool(missing)
    basis.extend(missing)

    # ---- 3. Critical -------------------------------------------------------
    crit: List[str] = []
    if action in (TradingAction.CHANGE_RISK_LIMIT, TradingAction.ACTIVATE_STRATEGY,
                  TradingAction.TRANSFER_FUNDS):
        crit.append(f"critical:action:{action.value}")
    if is_order:
        if not account_ok:
            crit.append("critical:unapproved_account")
        if request.strategy_id is not None and not strategy_ok:
            crit.append("critical:unapproved_strategy")
        if (request.model_id is not None or request.model_version is not None) and not model_ok:
            crit.append("critical:unapproved_model")
        if not session_ok:
            crit.append("critical:session_not_open")
        if over_preferred or over_max_qty or over_notional or over_position:
            crit.append("critical:large_order")
        if over_conc or over_sector:
            crit.append("critical:concentration")
        if over_turnover:
            crit.append("critical:turnover")
        if price_dev > limits.max_price_deviation_pct:
            crit.append("critical:price_deviation")
        if request.burst_count > limits.burst_threshold:
            crit.append("critical:burst")
    if loss_soft:
        crit.append("critical:daily_loss_soft")
    if crit:
        facts["hc_critical"] = True
        basis.extend(crit)
        return CriticalityDerivation("critical", facts, (), tuple(basis))

    # ---- 4. Missing (not critical) → conservative UNKNOWN ------------------
    if missing:
        return CriticalityDerivation("unknown", facts, (), tuple(basis))

    # ---- 5. Non-critical ---------------------------------------------------
    non_crit = False
    if action in NON_EXECUTED_ACTIONS and action not in (
        TradingAction.ACTIVATE_STRATEGY, TradingAction.CHANGE_RISK_LIMIT,
        TradingAction.TRANSFER_FUNDS,
    ):
        non_crit = True  # read/signal/recommend
        basis.append("non_critical:read_or_advisory")
    elif action in RISK_REDUCING_ACTIONS:
        non_crit = True
        basis.append("non_critical:risk_reducing")
    elif is_order and account_ok and strategy_ok and model_ok and symbol_ok \
            and (request.destination is None or venue_ok) and session_ok \
            and not (over_preferred or over_notional or over_position or over_conc
                     or over_turnover or loss_soft):
        non_crit = True
        basis.append("non_critical:within_approved_limits")
    if non_crit:
        facts["hc_non_critical"] = True
        return CriticalityDerivation("non_critical", facts, (), tuple(basis))

    basis.append("unknown:unclassified")
    return CriticalityDerivation("unknown", facts, (), tuple(basis))


# =============================================================================
# Order-sizing (constrained-execution envelope)
# =============================================================================


@dataclass(frozen=True)
class OrderConstraints:
    max_quantity: float
    max_notional: float
    permitted_order_types: Tuple[str, ...]
    min_price: Optional[float]
    max_price: Optional[float]
    max_price_deviation_pct: float
    resized: bool
    reasons: Tuple[str, ...]


def compute_order_constraints(
    request: TradingActionRequest, limits: TradingLimits,
) -> OrderConstraints:
    """Deterministic minimum-necessary order envelope.

    Caps quantity by preferred size, absolute max, position headroom, notional,
    and available cash (cash-only pilot); forces LIMIT order type and tight
    price bounds when the request must be constrained.
    """
    price = request.market_price
    qty = request.requested_quantity
    reasons: List[str] = []

    caps = [qty, limits.preferred_order_quantity, limits.max_order_quantity]
    if request.side == Side.BUY:
        pos_headroom = max(0.0, limits.max_position - request.current_position)
        caps.append(pos_headroom)
        if price > 0:
            caps.append(limits.max_order_notional / price)
            if request.available_cash >= 0:
                caps.append(request.available_cash / price)
    else:  # SELL: cannot sell more than held (no shorting in V1)
        caps.append(max(0.0, request.current_position))

    authorized_qty = max(0.0, min(caps))
    # Whole shares for cash equities.
    authorized_qty = float(int(authorized_qty))

    resized = authorized_qty < qty
    if resized:
        reasons.append("quantity_capped")

    force_limit = resized or request.order_type == OrderType.MARKET
    permitted_types: Tuple[str, ...] = (
        (OrderType.LIMIT.value,) if force_limit
        else (request.order_type.value,))
    if force_limit and request.order_type == OrderType.MARKET:
        reasons.append("market_to_limit")

    dev = (limits.constrained_price_deviation_pct if resized
           else limits.max_price_deviation_pct)
    min_price = round(price * (1 - dev), 6) if price > 0 else None
    max_price = round(price * (1 + dev), 6) if price > 0 else None
    # Worst-case notional at the maximum acceptable limit price (upper bound).
    authorized_notional = authorized_qty * (max_price if max_price else price)

    return OrderConstraints(
        max_quantity=authorized_qty,
        max_notional=round(authorized_notional, 6),
        permitted_order_types=permitted_types,
        min_price=min_price,
        max_price=max_price,
        max_price_deviation_pct=dev,
        resized=resized or force_limit,
        reasons=tuple(reasons),
    )
