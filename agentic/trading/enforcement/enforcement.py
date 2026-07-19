"""
Trading issuer + broker enforcement adapter + metrics + harness.

The enforcement adapter is the trust boundary between an authorized decision and
the simulated broker. It honors the HMAC-authenticated artifact, re-verifies all
material facts at execution time against live broker/market state (TOCTOU),
rejects any widening/retarget/replay, and only then "submits" the order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from agentic.trading.request import TradingActionRequest
from agentic.trading.taxonomy import (
    AccountStatus,
    EXECUTABLE_ORDER_ACTIONS,
    StrategyStatus,
)
from agentic.trading.criticality import TradingLimits
from agentic.trading.service import (
    TradingDecision,
    TradingGovernanceService,
    TradingOutcome,
)
from agentic.trading.enforcement.artifact import (
    DEFAULT_HMAC_KEY,
    ExecutionOrder,
    ExecutionReceipt,
    ExecutionResult,
    ExecutionStatus,
    MismatchCode,
    TradingAuthorizationArtifact,
)
from agentic.trading.enforcement.broker import SimulatedBroker, build_synthetic_broker

GOVERNANCE_VERSION = "actiongate-trading/1.0"


class FixedClock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = float(now)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


@dataclass
class EnforcementConfig:
    default_ttl_seconds: float = 60.0


@dataclass
class EnforcementState:
    used_nonces: set = field(default_factory=set)


@dataclass
class HarnessMetrics:
    orders_allowed: int = 0
    orders_constrained: int = 0
    orders_requiring_approval: int = 0
    orders_denied: int = 0
    hard_blocks_triggered: int = 0
    executions_submitted: int = 0
    executions_rejected: int = 0
    scope_widening_blocked: int = 0
    replay_blocked: int = 0
    stale_market_data_blocked: int = 0
    risk_limit_blocked: int = 0
    duplicate_blocked: int = 0
    unauthorized_executions: int = 0
    receipts_total: int = 0
    receipts_with_correlation: int = 0
    model_human_disagreements: int = 0

    def record_decision(self, d: TradingDecision) -> None:
        if d.outcome == TradingOutcome.ALLOW:
            self.orders_allowed += 1
        elif d.outcome == TradingOutcome.ALLOW_WITH_CONSTRAINTS:
            self.orders_constrained += 1
        elif d.outcome == TradingOutcome.REQUIRE_APPROVAL:
            self.orders_requiring_approval += 1
        else:
            self.orders_denied += 1
        if d.hard_block:
            self.hard_blocks_triggered += 1
        if d.human_verdict and d.model_advisory_decision:
            hv = "DENY" if d.human_verdict == "DENY" else (
                "DEFER" if d.human_verdict == "REQUIRE_APPROVAL" else "ALLOW")
            if hv != d.model_advisory_decision:
                self.model_human_disagreements += 1

    def to_dict(self) -> Dict[str, Any]:
        def rate(n, d): return round(n / d, 4) if d else 0.0
        return {
            "orders_allowed": self.orders_allowed,
            "orders_constrained": self.orders_constrained,
            "orders_requiring_approval": self.orders_requiring_approval,
            "orders_denied": self.orders_denied,
            "hard_blocks_triggered": self.hard_blocks_triggered,
            "scope_widening_attempts_blocked": self.scope_widening_blocked,
            "replay_attempts_blocked": self.replay_blocked,
            "stale_market_data_attempts_blocked": self.stale_market_data_blocked,
            "risk_limit_breaches_blocked": self.risk_limit_blocked,
            "duplicate_orders_blocked": self.duplicate_blocked,
            "unauthorized_executions": self.unauthorized_executions,
            "executions_submitted": self.executions_submitted,
            "executions_rejected": self.executions_rejected,
            "audit_correlation_completeness": rate(
                self.receipts_with_correlation, self.receipts_total),
            "model_versus_human_disagreement_rate": rate(
                self.model_human_disagreements,
                self.orders_allowed + self.orders_constrained
                + self.orders_requiring_approval + self.orders_denied),
        }


# =============================================================================
# Issuer
# =============================================================================


class AuthorizationIssuer:
    _EXECUTABLE = (TradingOutcome.ALLOW, TradingOutcome.ALLOW_WITH_CONSTRAINTS)

    def __init__(self, *, hmac_key: bytes = DEFAULT_HMAC_KEY,
                 clock: Callable[[], float] = None,
                 config: Optional[EnforcementConfig] = None,
                 limits: Optional[TradingLimits] = None,
                 metrics: Optional[HarnessMetrics] = None) -> None:
        self._key = hmac_key
        self._clock = clock or FixedClock()
        self._config = config or EnforcementConfig()
        self._limits = limits or TradingLimits()
        self._metrics = metrics
        self._counter = 0

    def issue(self, decision: TradingDecision, request: TradingActionRequest, *,
              ttl_seconds: Optional[float] = None, one_time: bool = True,
              require_policy_freshness: bool = False,
              approval_required: bool = False,
              ) -> Optional[TradingAuthorizationArtifact]:
        if decision.outcome not in self._EXECUTABLE:
            return None
        if request.action not in EXECUTABLE_ORDER_ACTIONS:
            return None  # only executable order actions get a broker artifact
        oc = decision.order_constraints
        if oc is None or oc.max_quantity <= 0:
            return None
        self._counter += 1
        now = self._clock()
        ttl = ttl_seconds if ttl_seconds is not None else self._config.default_ttl_seconds
        art = TradingAuthorizationArtifact(
            authorization_id=f"tauth-{self._counter:06d}",
            tenant_id=request.tenant_id, account_id=request.account_id,
            portfolio_id=request.portfolio_id, actor_id=request.actor_id,
            strategy_id=request.strategy_id, strategy_version=request.strategy_version,
            model_id=request.model_id, model_version=request.model_version,
            action=request.action.value,
            side=request.side.value if request.side else None,
            symbol=request.symbol or "", venue=request.destination,
            permitted_order_types=tuple(oc.permitted_order_types),
            max_quantity=oc.max_quantity, max_notional=oc.max_notional,
            min_price=oc.min_price, max_price=oc.max_price,
            max_price_deviation_pct=oc.max_price_deviation_pct,
            time_in_force=request.time_in_force.value,
            strategy_mandate=request.strategy_id,
            policy_version=decision.policy_version, policy_hash=decision.policy_hash,
            governance_version=GOVERNANCE_VERSION,
            market_data_ref=request.symbol or "",
            freshness_bound_seconds=self._limits.max_quote_age_seconds,
            daily_loss_limit=self._limits.max_daily_loss,
            issued_at=now, expires_at=now + ttl, nonce=f"tnonce-{self._counter:06d}",
            one_time=one_time, final_authority_used=decision.final_authority_used,
            approval_required=approval_required,
            require_policy_freshness=require_policy_freshness,
        ).authenticated(self._key)
        return art


# =============================================================================
# Broker enforcement adapter
# =============================================================================


class BrokerEnforcementAdapter:
    def __init__(self, broker: SimulatedBroker, *, hmac_key: bytes = DEFAULT_HMAC_KEY,
                 clock: Callable[[], float] = None,
                 state: Optional[EnforcementState] = None,
                 metrics: Optional[HarnessMetrics] = None) -> None:
        self._broker = broker
        self._key = hmac_key
        self._clock = clock or FixedClock()
        self._state = state or EnforcementState()
        self._metrics = metrics

    def execute(self, artifact: Optional[TradingAuthorizationArtifact],
                order: ExecutionOrder) -> ExecutionResult:
        if artifact is None:
            return self._reject(None, order, MismatchCode.NO_AUTHORIZATION)
        code = self._check(artifact, order)
        if code is not MismatchCode.OK:
            return self._reject(artifact, order, code)
        return self._submit(artifact, order)

    def _check(self, a: TradingAuthorizationArtifact, o: ExecutionOrder) -> MismatchCode:
        if not a.verify(self._key):
            return MismatchCode.HMAC_INVALID
        if o.authorization_id != a.authorization_id:
            return MismatchCode.NO_AUTHORIZATION
        if self._clock() > a.expires_at:
            return MismatchCode.EXPIRED
        if a.one_time and a.nonce in self._state.used_nonces:
            return MismatchCode.REPLAY
        if self._broker.is_duplicate(o.order_id):
            return MismatchCode.DUPLICATE_ORDER
        if a.approval_required and not o.approval_completed:
            return MismatchCode.APPROVAL_INCOMPLETE
        # Binding (TOCTOU material-fact re-verification vs the artifact)
        if o.tenant_id != a.tenant_id:
            return MismatchCode.TENANT_MISMATCH
        if o.account_id != a.account_id:
            return MismatchCode.ACCOUNT_MISMATCH
        if o.actor_id != a.actor_id:
            return MismatchCode.ACTOR_MISMATCH
        if a.strategy_id is not None and o.strategy_id != a.strategy_id:
            return MismatchCode.STRATEGY_MISMATCH
        if a.strategy_version is not None and o.strategy_version != a.strategy_version:
            return MismatchCode.STRATEGY_MISMATCH
        if a.model_version is not None and o.model_version != a.model_version:
            return MismatchCode.MODEL_MISMATCH
        if o.symbol != a.symbol:
            return MismatchCode.SYMBOL_MISMATCH
        if a.side is not None and o.side != a.side:
            return MismatchCode.SIDE_MISMATCH
        if a.venue is not None and o.venue != a.venue:
            return MismatchCode.VENUE_MISMATCH
        if o.order_type not in a.permitted_order_types:
            return MismatchCode.ORDER_TYPE_MISMATCH
        if o.quantity > a.max_quantity:
            return MismatchCode.QUANTITY_WIDENING
        price = self._broker.market.price(a.symbol) or 0.0
        submitted_notional = o.quantity * (o.limit_price or price)
        if submitted_notional > a.max_notional + 1e-6:
            return MismatchCode.NOTIONAL_WIDENING
        if o.order_type == "limit" and o.limit_price is not None:
            if a.min_price is not None and o.limit_price < a.min_price - 1e-9:
                return MismatchCode.PRICE_OUT_OF_BOUNDS
            if a.max_price is not None and o.limit_price > a.max_price + 1e-9:
                return MismatchCode.PRICE_OUT_OF_BOUNDS
            if price > 0 and abs(o.limit_price - price) / price > a.max_price_deviation_pct + 1e-9:
                return MismatchCode.PRICE_DEVIATION
        if o.time_in_force != a.time_in_force:
            return MismatchCode.TIF_MISMATCH
        # Live TOCTOU state (broker-side; may have changed since authorization)
        if self._broker.risk.kill_switch:
            return MismatchCode.KILL_SWITCH
        if self._broker.risk.account_state(a.account_id) != AccountStatus.ACTIVE:
            return MismatchCode.ACCOUNT_SUSPENDED
        if self._broker.risk.strategy_state(a.strategy_id) != StrategyStatus.ACTIVE:
            return MismatchCode.STRATEGY_SUSPENDED
        qts = self._broker.market.quote_timestamp(a.symbol)
        if qts is None or (self._clock() - qts) > a.freshness_bound_seconds:
            return MismatchCode.STALE_MARKET_DATA
        if self._broker.risk.loss(a.account_id) >= a.daily_loss_limit:
            return MismatchCode.DAILY_LOSS
        if a.require_policy_freshness and o.policy_version != a.policy_version:
            return MismatchCode.POLICY_STALE
        return MismatchCode.OK

    def _submit(self, a: TradingAuthorizationArtifact, o: ExecutionOrder) -> ExecutionResult:
        if a.one_time:
            self._state.used_nonces.add(a.nonce)
        self._broker.record(o.order_id)
        # Invariant: nothing submitted may exceed the authorized envelope.
        unauthorized = (o.quantity > a.max_quantity
                        or o.order_type not in a.permitted_order_types)
        receipt = ExecutionReceipt(
            authorization_id=a.authorization_id, order_request_id=o.order_id,
            execution_status=ExecutionStatus.SUBMITTED.value,
            tenant_ref=a.tenant_id, account_ref=a.account_id, actor_ref=a.actor_id,
            strategy_ref=a.strategy_id, model_version_ref=a.model_version,
            symbol=a.symbol, side=a.side, authorized_quantity=a.max_quantity,
            submitted_quantity=o.quantity, authorized_order_types=a.permitted_order_types,
            submitted_order_type=o.order_type, min_price=a.min_price, max_price=a.max_price,
            submitted_limit_price=o.limit_price, venue=a.venue,
            policy_version=a.policy_version, timestamp=self._clock(),
            denial_code=None, audit_correlation_id=f"corr:{a.authorization_id}:{a.nonce}",
            final_authority_used=a.final_authority_used)
        if self._metrics:
            self._metrics.executions_submitted += 1
            self._metrics.receipts_total += 1
            self._metrics.receipts_with_correlation += 1
            if unauthorized:
                self._metrics.unauthorized_executions += 1
        return ExecutionResult(receipt=receipt)

    def _reject(self, a: Optional[TradingAuthorizationArtifact], o: ExecutionOrder,
                code: MismatchCode) -> ExecutionResult:
        auth_id = a.authorization_id if a else "(none)"
        receipt = ExecutionReceipt(
            authorization_id=auth_id, order_request_id=o.order_id,
            execution_status=ExecutionStatus.REJECTED.value,
            tenant_ref=o.tenant_id, account_ref=o.account_id, actor_ref=o.actor_id,
            strategy_ref=o.strategy_id, model_version_ref=o.model_version,
            symbol=o.symbol, side=o.side, authorized_quantity=(a.max_quantity if a else 0.0),
            submitted_quantity=o.quantity,
            authorized_order_types=(a.permitted_order_types if a else ()),
            submitted_order_type=o.order_type, min_price=(a.min_price if a else None),
            max_price=(a.max_price if a else None), submitted_limit_price=o.limit_price,
            venue=o.venue, policy_version=o.policy_version, timestamp=self._clock(),
            denial_code=code.value, audit_correlation_id=f"corr:{auth_id}:reject",
            final_authority_used=(a.final_authority_used if a else "MODEL"))
        if self._metrics:
            self._metrics.executions_rejected += 1
            self._metrics.receipts_total += 1
            self._metrics.receipts_with_correlation += 1
            if code in (MismatchCode.QUANTITY_WIDENING, MismatchCode.NOTIONAL_WIDENING,
                        MismatchCode.SYMBOL_MISMATCH, MismatchCode.SIDE_MISMATCH,
                        MismatchCode.ORDER_TYPE_MISMATCH, MismatchCode.PRICE_OUT_OF_BOUNDS,
                        MismatchCode.PRICE_DEVIATION, MismatchCode.ACCOUNT_MISMATCH,
                        MismatchCode.VENUE_MISMATCH):
                self._metrics.scope_widening_blocked += 1
            if code == MismatchCode.REPLAY:
                self._metrics.replay_blocked += 1
            if code == MismatchCode.STALE_MARKET_DATA:
                self._metrics.stale_market_data_blocked += 1
            if code in (MismatchCode.DAILY_LOSS, MismatchCode.KILL_SWITCH):
                self._metrics.risk_limit_blocked += 1
            if code == MismatchCode.DUPLICATE_ORDER:
                self._metrics.duplicate_blocked += 1
        return ExecutionResult(receipt=receipt)


# =============================================================================
# Harness
# =============================================================================


class TradingEnforcementHarness:
    def __init__(self, *, broker: Optional[SimulatedBroker] = None,
                 service: Optional[TradingGovernanceService] = None,
                 hmac_key: bytes = DEFAULT_HMAC_KEY,
                 clock: Callable[[], float] = None,
                 config: Optional[EnforcementConfig] = None) -> None:
        self.metrics = HarnessMetrics()
        self.clock = clock or FixedClock()
        self.config = config or EnforcementConfig()
        self.state = EnforcementState()
        self.service = service or TradingGovernanceService()
        self.broker = broker if broker is not None else build_synthetic_broker(
            now=self.clock())
        self.issuer = AuthorizationIssuer(
            hmac_key=hmac_key, clock=self.clock, config=self.config,
            limits=self.service.limits, metrics=self.metrics)
        self.adapter = BrokerEnforcementAdapter(
            self.broker, hmac_key=hmac_key, clock=self.clock, state=self.state,
            metrics=self.metrics)

    def authorize(self, request: TradingActionRequest) -> TradingDecision:
        d = self.service.authorize(request)
        self.metrics.record_decision(d)
        return d

    def issue(self, decision, request, **kw):
        return self.issuer.issue(decision, request, **kw)

    def execute(self, artifact, order):
        return self.adapter.execute(artifact, order)

    def run(self, request, *, order_overrides=None, order_id="ord-1",
            session_id="default-session", **issue_kw):
        decision = self.authorize(request)
        artifact = self.issue(decision, request, **issue_kw)
        if artifact is None:
            return decision, None, None
        order = ExecutionOrder.faithful_from(
            artifact, order_id=order_id, session_id=session_id,
            **(order_overrides or {}))
        result = self.execute(artifact, order)
        return decision, artifact, result
