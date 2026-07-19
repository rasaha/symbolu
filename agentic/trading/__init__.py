"""
Trading pre-trade governance — a self-contained ActionGate domain specialization
for cash-equity pre-trade authorization and simulated execution.

Positioning: "The strategy proposes the trade. ActionGate determines whether, how
much, and under what constraints it may execute." This is NOT a price predictor,
recommender, or profitability claim, and is not real-money ready.

The generic ActionGate engine is used unchanged; trading depends on generic
ActionGate, never the reverse.
"""

from agentic.trading.taxonomy import (
    AccountStatus,
    InstrumentType,
    OrderType,
    SessionStatus,
    Side,
    StrategyStatus,
    TimeInForce,
    TradingAction,
    TraderRole,
)
from agentic.trading.request import TradingActionRequest
from agentic.trading.criticality import (
    ApprovedUniverse,
    CriticalityDerivation,
    OrderConstraints,
    TradingLimits,
    compute_order_constraints,
    derive_criticality,
)
from agentic.trading.policy import (
    TRADING_HARD_BLOCK_CAPABILITIES,
    build_default_limits,
    build_default_universe,
    build_trading_criticality_registry,
    build_trading_forbidden_policy_resolution,
    build_trading_policy_book,
)
from agentic.trading.service import (
    TradingDecision,
    TradingGovernanceService,
    TradingOutcome,
)

__all__ = [
    "AccountStatus", "InstrumentType", "OrderType", "SessionStatus", "Side",
    "StrategyStatus", "TimeInForce", "TradingAction", "TraderRole",
    "TradingActionRequest", "ApprovedUniverse", "CriticalityDerivation",
    "OrderConstraints", "TradingLimits", "compute_order_constraints",
    "derive_criticality", "TRADING_HARD_BLOCK_CAPABILITIES",
    "build_default_limits", "build_default_universe",
    "build_trading_criticality_registry",
    "build_trading_forbidden_policy_resolution", "build_trading_policy_book",
    "TradingDecision", "TradingGovernanceService", "TradingOutcome",
]
