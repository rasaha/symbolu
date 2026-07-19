"""
TradingActionRequest — the trading-domain request object.

Carries classifications, references, and numeric risk facts — NOT broker
credentials, API keys, or raw proprietary strategy internals. Caller-declared
facts may only promote conservatism; declared risk labels are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

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


@dataclass(frozen=True)
class TradingActionRequest:
    """A proposed trading action awaiting pre-trade authorization."""

    # Identity / ownership
    tenant_id: str
    account_id: str
    actor_id: str
    actor_role: TraderRole
    action: TradingAction

    # Strategy / model provenance
    strategy_id: Optional[str] = None
    strategy_version: Optional[str] = None
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    portfolio_id: Optional[str] = None

    # Order specifics
    side: Optional[Side] = None
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    instrument_type: InstrumentType = InstrumentType.CASH_EQUITY
    requested_quantity: float = 0.0
    requested_notional: float = 0.0
    order_type: OrderType = OrderType.LIMIT
    limit_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY

    # Market-data reference
    market_price: float = 0.0
    market_data_timestamp: float = 0.0  # epoch seconds
    now: float = 0.0  # epoch seconds at request time

    # Portfolio / risk state
    current_position: float = 0.0
    projected_position: float = 0.0
    available_cash: float = 0.0
    portfolio_value: float = 0.0
    current_concentration: float = 0.0   # fraction [0,1]
    projected_concentration: float = 0.0  # fraction [0,1]
    sector_concentration: Optional[float] = None
    daily_turnover: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    # Operational state
    session_status: SessionStatus = SessionStatus.OPEN
    strategy_status: StrategyStatus = StrategyStatus.ACTIVE
    account_status: AccountStatus = AccountStatus.ACTIVE
    kill_switch_active: bool = False

    # Destination
    destination: Optional[str] = None  # broker / simulated venue id

    # De-dup / burst
    order_id: Optional[str] = None
    burst_count: int = 0

    # Risk-limit change control
    risk_change_authorized: bool = False

    # Advisory model signals (advisory only; never override human policy nor
    # downgrade criticality). Defaults conservative (0.5).
    model_quality: float = 0.5
    model_coherence: float = 0.5
    model_consistency: float = 0.5
    model_goal_alignment: float = 0.5
    model_trajectory_confidence: float = 0.5

    # Caller-declared facts (promotion-only; reserved keys stripped downstream).
    declared_facts: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: Tuple[str, ...] = ()

    def safe_reference(self) -> Dict[str, Any]:
        """PHI/secret-free reference view for audit (ids/classifications/nums)."""
        return {
            "tenant_id": self.tenant_id,
            "account_id": self.account_id,
            "portfolio_id": self.portfolio_id,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role.value,
            "action": self.action.value,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "side": self.side.value if self.side else None,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "instrument_type": self.instrument_type.value,
            "requested_quantity": self.requested_quantity,
            "requested_notional": self.requested_notional,
            "order_type": self.order_type.value,
            "time_in_force": self.time_in_force.value,
            "destination": self.destination,
            "order_id": self.order_id,
            "evidence_refs": list(self.evidence_refs),
        }
