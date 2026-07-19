"""
Trading authorization artifact, execution order, and audit-safe receipt.

The artifact is **HMAC-authenticated inside a shared trust boundary** — it is an
integrity/authenticity tag verified with a shared secret, NOT an independently
verifiable asymmetric digital signature. A production system would use asymmetric
signing + key custody.

No broker secrets, API keys, or raw strategy internals appear here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Optional, Tuple

# HMAC test key (shared-secret). NOT an asymmetric signature; NOT a real secret.
DEFAULT_HMAC_KEY = b"actiongate-trading-enforcement-test-key"


def _canonical(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def compute_hmac(payload: Dict[str, Any], key: bytes = DEFAULT_HMAC_KEY) -> str:
    """Deterministic HMAC-SHA256 authentication tag over the canonical payload."""
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


class ExecutionStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"


class MismatchCode(str, Enum):
    OK = "OK"
    HMAC_INVALID = "E_HMAC_INVALID"
    EXPIRED = "E_EXPIRED"
    REPLAY = "E_REPLAY_NONCE_USED"
    DUPLICATE_ORDER = "E_DUPLICATE_ORDER"
    APPROVAL_INCOMPLETE = "E_APPROVAL_INCOMPLETE"
    NO_AUTHORIZATION = "E_NO_AUTHORIZATION"
    TENANT_MISMATCH = "E_TENANT_MISMATCH"
    ACCOUNT_MISMATCH = "E_ACCOUNT_MISMATCH"
    ACTOR_MISMATCH = "E_ACTOR_MISMATCH"
    STRATEGY_MISMATCH = "E_STRATEGY_MISMATCH"
    MODEL_MISMATCH = "E_MODEL_VERSION_MISMATCH"
    SYMBOL_MISMATCH = "E_SYMBOL_MISMATCH"
    SIDE_MISMATCH = "E_SIDE_MISMATCH"
    VENUE_MISMATCH = "E_VENUE_MISMATCH"
    ORDER_TYPE_MISMATCH = "E_ORDER_TYPE_MISMATCH"
    QUANTITY_WIDENING = "E_QUANTITY_WIDENING"
    NOTIONAL_WIDENING = "E_NOTIONAL_WIDENING"
    PRICE_OUT_OF_BOUNDS = "E_PRICE_OUT_OF_BOUNDS"
    PRICE_DEVIATION = "E_PRICE_DEVIATION"
    TIF_MISMATCH = "E_TIF_MISMATCH"
    KILL_SWITCH = "E_KILL_SWITCH_ACTIVE"
    ACCOUNT_SUSPENDED = "E_ACCOUNT_SUSPENDED"
    STRATEGY_SUSPENDED = "E_STRATEGY_SUSPENDED"
    STALE_MARKET_DATA = "E_STALE_MARKET_DATA"
    DAILY_LOSS = "E_DAILY_LOSS_BREACHED"
    POLICY_STALE = "E_POLICY_STALE"


_SIGNED_FIELDS = (
    "authorization_id", "tenant_id", "account_id", "portfolio_id", "actor_id",
    "strategy_id", "strategy_version", "model_id", "model_version", "action",
    "side", "symbol", "venue", "permitted_order_types", "max_quantity",
    "max_notional", "min_price", "max_price", "max_price_deviation_pct",
    "time_in_force", "strategy_mandate", "policy_version", "policy_hash",
    "governance_version", "market_data_ref", "freshness_bound_seconds",
    "daily_loss_limit", "issued_at", "expires_at", "nonce", "one_time",
    "final_authority_used", "approval_required",
)


@dataclass(frozen=True)
class TradingAuthorizationArtifact:
    """HMAC-authenticated constraint-bearing trading authorization."""

    authorization_id: str
    tenant_id: str
    account_id: str
    portfolio_id: Optional[str]
    actor_id: str
    strategy_id: Optional[str]
    strategy_version: Optional[str]
    model_id: Optional[str]
    model_version: Optional[str]
    action: str
    side: Optional[str]
    symbol: str
    venue: Optional[str]
    permitted_order_types: Tuple[str, ...]
    max_quantity: float
    max_notional: float
    min_price: Optional[float]
    max_price: Optional[float]
    max_price_deviation_pct: float
    time_in_force: str
    strategy_mandate: Optional[str]
    policy_version: str
    policy_hash: str
    governance_version: str
    market_data_ref: str
    freshness_bound_seconds: float
    daily_loss_limit: float
    issued_at: float
    expires_at: float
    nonce: str
    one_time: bool
    final_authority_used: str
    approval_required: bool
    require_policy_freshness: bool = False
    hmac_tag: str = ""

    def auth_payload(self) -> Dict[str, Any]:
        d = {}
        for f in _SIGNED_FIELDS:
            v = getattr(self, f)
            d[f] = list(v) if isinstance(v, tuple) else v
        d["require_policy_freshness"] = self.require_policy_freshness
        return d

    def authenticated(self, key: bytes = DEFAULT_HMAC_KEY) -> "TradingAuthorizationArtifact":
        return replace(self, hmac_tag=compute_hmac(self.auth_payload(), key))

    def verify(self, key: bytes = DEFAULT_HMAC_KEY) -> bool:
        return hmac.compare_digest(compute_hmac(self.auth_payload(), key), self.hmac_tag)

    def safe_dict(self) -> Dict[str, Any]:
        return self.auth_payload() | {"hmac_present": bool(self.hmac_tag)}


@dataclass(frozen=True)
class ExecutionOrder:
    """The order actually submitted at execution (may be adversarial)."""

    authorization_id: str
    tenant_id: str
    account_id: str
    actor_id: str
    strategy_id: Optional[str]
    strategy_version: Optional[str]
    model_id: Optional[str]
    model_version: Optional[str]
    symbol: str
    side: str
    quantity: float
    order_type: str
    limit_price: Optional[float]
    venue: Optional[str]
    time_in_force: str
    order_id: str
    policy_version: str
    approval_completed: bool = True
    session_id: str = "default-session"

    @staticmethod
    def faithful_from(a: TradingAuthorizationArtifact, *, order_id: str = "ord-1",
                      session_id: str = "default-session",
                      **overrides: Any) -> "ExecutionOrder":
        base = dict(
            authorization_id=a.authorization_id, tenant_id=a.tenant_id,
            account_id=a.account_id, actor_id=a.actor_id, strategy_id=a.strategy_id,
            strategy_version=a.strategy_version, model_id=a.model_id,
            model_version=a.model_version, symbol=a.symbol, side=a.side or "buy",
            quantity=a.max_quantity, order_type=a.permitted_order_types[0],
            limit_price=a.max_price, venue=a.venue,
            time_in_force=a.time_in_force, order_id=order_id,
            policy_version=a.policy_version, approval_completed=True,
            session_id=session_id)
        base.update(overrides)
        return ExecutionOrder(**base)


@dataclass(frozen=True)
class ExecutionReceipt:
    """Audit-safe receipt — no broker secrets / credentials / raw strategy state."""

    authorization_id: str
    order_request_id: str
    execution_status: str
    tenant_ref: str
    account_ref: str
    actor_ref: str
    strategy_ref: Optional[str]
    model_version_ref: Optional[str]
    symbol: str
    side: Optional[str]
    authorized_quantity: float
    submitted_quantity: float
    authorized_order_types: Tuple[str, ...]
    submitted_order_type: Optional[str]
    min_price: Optional[float]
    max_price: Optional[float]
    submitted_limit_price: Optional[float]
    venue: Optional[str]
    policy_version: str
    timestamp: float
    denial_code: Optional[str]
    audit_correlation_id: str
    final_authority_used: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "order_request_id": self.order_request_id,
            "execution_status": self.execution_status,
            "tenant_ref": self.tenant_ref,
            "account_ref": self.account_ref,
            "actor_ref": self.actor_ref,
            "strategy_ref": self.strategy_ref,
            "model_version_ref": self.model_version_ref,
            "symbol": self.symbol,
            "side": self.side,
            "authorized_quantity": self.authorized_quantity,
            "submitted_quantity": self.submitted_quantity,
            "authorized_order_types": list(self.authorized_order_types),
            "submitted_order_type": self.submitted_order_type,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "submitted_limit_price": self.submitted_limit_price,
            "venue": self.venue,
            "policy_version": self.policy_version,
            "timestamp": self.timestamp,
            "denial_code": self.denial_code,
            "audit_correlation_id": self.audit_correlation_id,
            "final_authority_used": self.final_authority_used,
        }


@dataclass(frozen=True)
class ExecutionResult:
    receipt: ExecutionReceipt

    @property
    def submitted(self) -> bool:
        return self.receipt.execution_status == ExecutionStatus.SUBMITTED.value

    @property
    def denial_code(self) -> Optional[str]:
        return self.receipt.denial_code
