"""
Simulated broker / OMS + live market and firm-risk state.

Live state (kill switch, daily loss, account/strategy status, quote timestamps)
is held here and queried by the enforcement adapter at execution time, so tests
can mutate it BETWEEN authorization and execution to exercise TOCTOU handling.
No live market feed, no real brokerage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from agentic.trading.taxonomy import AccountStatus, StrategyStatus


@dataclass
class MarketState:
    """Synthetic quotes: symbol → (price, quote_timestamp_epoch_seconds)."""

    quotes: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    def set_quote(self, symbol: str, price: float, ts: float) -> None:
        self.quotes[symbol] = (price, ts)

    def price(self, symbol: str) -> Optional[float]:
        q = self.quotes.get(symbol)
        return q[0] if q else None

    def quote_timestamp(self, symbol: str) -> Optional[float]:
        q = self.quotes.get(symbol)
        return q[1] if q else None


@dataclass
class FirmRiskState:
    kill_switch: bool = False
    daily_loss: Dict[str, float] = field(default_factory=dict)  # account → magnitude
    account_status: Dict[str, AccountStatus] = field(default_factory=dict)
    strategy_status: Dict[str, StrategyStatus] = field(default_factory=dict)

    def loss(self, account: str) -> float:
        return self.daily_loss.get(account, 0.0)

    def account_state(self, account: str) -> AccountStatus:
        return self.account_status.get(account, AccountStatus.ACTIVE)

    def strategy_state(self, strategy: Optional[str]) -> StrategyStatus:
        if strategy is None:
            return StrategyStatus.ACTIVE
        return self.strategy_status.get(strategy, StrategyStatus.ACTIVE)


@dataclass
class SimulatedBroker:
    market: MarketState = field(default_factory=MarketState)
    risk: FirmRiskState = field(default_factory=FirmRiskState)
    submitted_order_ids: set = field(default_factory=set)

    def is_duplicate(self, order_id: str) -> bool:
        return order_id in self.submitted_order_ids

    def record(self, order_id: str) -> None:
        self.submitted_order_ids.add(order_id)


def build_synthetic_broker(*, now: float = 1_000_000.0) -> SimulatedBroker:
    b = SimulatedBroker()
    for sym, px in (("AAA", 100.0), ("BBB", 50.0), ("CCC", 250.0)):
        b.market.set_quote(sym, px, now)  # fresh at `now`
    b.risk.account_status["acct-1"] = AccountStatus.ACTIVE
    b.risk.account_status["acct-2"] = AccountStatus.ACTIVE
    b.risk.strategy_status["strat-momentum"] = StrategyStatus.ACTIVE
    return b
