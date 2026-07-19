"""
Trading enforcement + adversarial validation harness.

Signed (HMAC-authenticated) constraint-bearing authorization + deterministic
simulated broker/OMS enforcement between authorization and order submission.
Synthetic data only; no real broker connectivity.
"""

from agentic.trading.enforcement.artifact import (
    DEFAULT_HMAC_KEY,
    ExecutionOrder,
    ExecutionReceipt,
    ExecutionResult,
    ExecutionStatus,
    MismatchCode,
    TradingAuthorizationArtifact,
    compute_hmac,
)
from agentic.trading.enforcement.broker import (
    FirmRiskState,
    MarketState,
    SimulatedBroker,
    build_synthetic_broker,
)
from agentic.trading.enforcement.enforcement import (
    AuthorizationIssuer,
    BrokerEnforcementAdapter,
    EnforcementConfig,
    EnforcementState,
    FixedClock,
    HarnessMetrics,
    TradingEnforcementHarness,
)

__all__ = [
    "DEFAULT_HMAC_KEY", "ExecutionOrder", "ExecutionReceipt", "ExecutionResult",
    "ExecutionStatus", "MismatchCode", "TradingAuthorizationArtifact", "compute_hmac",
    "FirmRiskState", "MarketState", "SimulatedBroker", "build_synthetic_broker",
    "AuthorizationIssuer", "BrokerEnforcementAdapter", "EnforcementConfig",
    "EnforcementState", "FixedClock", "HarnessMetrics", "TradingEnforcementHarness",
]
