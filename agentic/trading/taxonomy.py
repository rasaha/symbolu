"""
Trading taxonomies — configurable, NON-exhaustive classifications for the
cash-equity pre-trade governance pilot.

These enums are a starting configuration, not a claim of market/regulatory
completeness. A deployment replaces/extends them. Nothing here predicts prices,
recommends trades, or encodes a regulatory determination.
"""

from __future__ import annotations

from enum import Enum


class TradingAction(str, Enum):
    """Governed trading actions. V1 executes only the cash-equity order ops."""

    READ_MARKET_DATA = "READ_MARKET_DATA"
    GENERATE_SIGNAL = "GENERATE_SIGNAL"
    RECOMMEND_TRADE = "RECOMMEND_TRADE"
    PLACE_ORDER = "PLACE_ORDER"
    MODIFY_ORDER = "MODIFY_ORDER"
    CANCEL_ORDER = "CANCEL_ORDER"
    INCREASE_POSITION = "INCREASE_POSITION"
    REDUCE_POSITION = "REDUCE_POSITION"
    CLOSE_POSITION = "CLOSE_POSITION"
    ACTIVATE_STRATEGY = "ACTIVATE_STRATEGY"
    HALT_STRATEGY = "HALT_STRATEGY"
    CHANGE_RISK_LIMIT = "CHANGE_RISK_LIMIT"
    TRANSFER_FUNDS = "TRANSFER_FUNDS"


# Actions that place/modify executable risk in V1 (produce an artifact + broker call).
EXECUTABLE_ORDER_ACTIONS = frozenset({
    TradingAction.PLACE_ORDER,
    TradingAction.MODIFY_ORDER,
    TradingAction.INCREASE_POSITION,
    TradingAction.REDUCE_POSITION,
    TradingAction.CLOSE_POSITION,
})

# Cancel is executable but risk-reducing; represented, kept simple in V1.
RISK_REDUCING_ACTIONS = frozenset({
    TradingAction.CANCEL_ORDER,
    TradingAction.REDUCE_POSITION,
    TradingAction.CLOSE_POSITION,
    TradingAction.HALT_STRATEGY,
})

# Actions represented but NOT executed in V1 (governed, no broker submission).
NON_EXECUTED_ACTIONS = frozenset({
    TradingAction.READ_MARKET_DATA,
    TradingAction.GENERATE_SIGNAL,
    TradingAction.RECOMMEND_TRADE,
    TradingAction.ACTIVATE_STRATEGY,
    TradingAction.CHANGE_RISK_LIMIT,
    TradingAction.TRANSFER_FUNDS,
})


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(str, Enum):
    DAY = "day"
    IOC = "ioc"
    GTC = "gtc"


class InstrumentType(str, Enum):
    """V1 supports CASH_EQUITY only; others are represented for hard-block tests."""

    CASH_EQUITY = "cash_equity"
    OPTION = "option"
    FUTURE = "future"
    FX = "fx"
    CRYPTO = "crypto"


SUPPORTED_INSTRUMENTS = frozenset({InstrumentType.CASH_EQUITY})


class SessionStatus(str, Enum):
    OPEN = "open"
    PRE_OPEN = "pre_open"
    CLOSED = "closed"
    HALTED = "halted"


class StrategyStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    UNAPPROVED = "unapproved"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    RESTRICTED = "restricted"
    SUSPENDED = "suspended"


class TraderRole(str, Enum):
    EXECUTION_TRADER = "execution_trader"
    PORTFOLIO_MANAGER = "portfolio_manager"
    RISK_MANAGER = "risk_manager"
    FIRM_ADMIN = "firm_admin"
    AI_EXECUTION_STRATEGY = "ai_execution_strategy"
    AI_SIGNAL_MODEL = "ai_signal_model"
    EXTERNAL = "external"
    UNKNOWN_ACTOR = "unknown_actor"


AI_ROLES = frozenset({
    TraderRole.AI_EXECUTION_STRATEGY,
    TraderRole.AI_SIGNAL_MODEL,
})
