"""
TradingGovernanceService — pre-trade authorization around generic ActionGate.

Flow: proposal → deterministic classification → generic authorize → order-sizing
(constrained envelope) → TradingDecision. The generic engine decides *whether* and
*under which authority*; this layer computes the deterministic order envelope. No
trading rule lives in the generic engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from agentic.agentic_framework.governance_service import GovernanceService
from agentic.agentic_framework.governance_models import AuthorizationRequest
from agentic.agentic_framework.human_policy import HumanPolicyEngine

from agentic.trading.request import TradingActionRequest
from agentic.trading.taxonomy import EXECUTABLE_ORDER_ACTIONS, TraderRole
from agentic.trading.criticality import (
    ApprovedUniverse,
    CriticalityDerivation,
    OrderConstraints,
    TradingLimits,
    compute_order_constraints,
    derive_criticality,
)
from agentic.trading.policy import (
    build_default_limits,
    build_default_universe,
    build_trading_criticality_registry,
    build_trading_forbidden_policy_resolution,
    build_trading_policy_book,
)

_TRADING_TOOL = "trading_oms"


class TradingOutcome(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


@dataclass(frozen=True)
class TradingDecision:
    outcome: TradingOutcome
    governance_decision: str
    order_constraints: Optional[OrderConstraints]
    constraints: Dict[str, Any]
    criticality: str
    criticality_basis: Tuple[str, ...]
    effective_authority_mode: str
    matched_rule_id: str
    human_verdict: Optional[str]
    model_advisory_decision: Optional[str]
    hard_block: bool
    hard_block_provenance: Tuple[str, ...]
    final_authority_used: str
    requires_human_approval: bool
    rationale: str
    policy_version: str
    policy_hash: str
    decision_id: Optional[str]
    generic_response: Any = field(repr=False, default=None)

    def audit_dict(self) -> Dict[str, Any]:
        return {
            "trading_domain": "cash_equity_pretrade",
            "outcome": self.outcome.value,
            "governance_decision": self.governance_decision,
            "constraints": self.constraints,
            "criticality": self.criticality,
            "criticality_basis": list(self.criticality_basis),
            "effective_authority_mode": self.effective_authority_mode,
            "matched_rule_id": self.matched_rule_id,
            "human_verdict": self.human_verdict,
            "model_advisory_decision": self.model_advisory_decision,
            "hard_block": self.hard_block,
            "hard_block_provenance": list(self.hard_block_provenance),
            "final_authority_used": self.final_authority_used,
            "requires_human_approval": self.requires_human_approval,
            "rationale": self.rationale,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "decision_id": self.decision_id,
        }


class TradingGovernanceService:
    def __init__(
        self,
        *,
        governance_service: Optional[GovernanceService] = None,
        limits: Optional[TradingLimits] = None,
        universe: Optional[ApprovedUniverse] = None,
        policy_book=None,
        criticality_registry=None,
    ) -> None:
        self.limits = limits or build_default_limits()
        self.universe = universe or build_default_universe()
        self._book = policy_book or build_trading_policy_book()
        self._registry = criticality_registry or build_trading_criticality_registry()
        self._policy_version = self._book.policy_version()
        self._policy_hash = self._book.content_hash()
        if governance_service is not None:
            self._gov = governance_service
        else:
            self._gov = GovernanceService(
                human_policy_engine=HumanPolicyEngine(
                    self._book, criticality_registry=self._registry),
                policy_resolution=build_trading_forbidden_policy_resolution())

    def _to_authorization_request(
        self, request: TradingActionRequest, derivation: CriticalityDerivation,
    ) -> AuthorizationRequest:
        agency = "FULL"
        if request.actor_role == TraderRole.UNKNOWN_ACTOR or derivation.facts.get(
            "no_actor_identity"
        ):
            agency = "INFORM"
        metadata = {"facts": derivation.facts, "target": request.destination or "",
                    "trading": request.safe_reference()}
        return AuthorizationRequest(
            actor_id=request.actor_id or "__no_actor__",
            action_type=request.action.value,
            tool_name=_TRADING_TOOL,
            capabilities=list(derivation.hard_block_capabilities),
            agency_level=agency,
            quality_score=request.model_quality,
            coherence_score=request.model_coherence,
            internal_consistency=request.model_consistency,
            goal_alignment=request.model_goal_alignment,
            trajectory_confidence=request.model_trajectory_confidence,
            metadata=metadata)

    def authorize(self, request: TradingActionRequest) -> TradingDecision:
        derivation = derive_criticality(request, self.limits, self.universe)
        authz = self._to_authorization_request(request, derivation)
        resp = self._gov.authorize(authz)
        hp = resp.human_policy or {}
        gd = resp.governance_decision.value

        is_order = request.action in EXECUTABLE_ORDER_ACTIONS
        order_constraints: Optional[OrderConstraints] = None
        constraints: Dict[str, Any] = {}
        rationale: List[str] = []

        if gd == "DENY":
            outcome = TradingOutcome.DENY
            rationale.append("Denied by pre-trade governance.")
            if hp.get("hard_block"):
                rationale.append(
                    f"Hard block: {', '.join(hp.get('hard_block_provenance', ()))}.")
        elif gd == "DEFER":
            outcome = TradingOutcome.REQUIRE_APPROVAL
            rationale.append("Escalated for human approval.")
        else:  # ALLOW
            if is_order:
                order_constraints = compute_order_constraints(request, self.limits)
                if order_constraints.max_quantity <= 0:
                    outcome = TradingOutcome.DENY
                    rationale.append(
                        "Denied: no authorized quantity headroom (cash/position/"
                        "limit).")
                    order_constraints = None
                else:
                    constraints = self._build_constraints(request, order_constraints, hp)
                    if order_constraints.resized or hp.get("verdict") == "ALLOW_WITH_CONSTRAINTS":
                        outcome = TradingOutcome.ALLOW_WITH_CONSTRAINTS
                        rationale.append(
                            f"Authorized {order_constraints.max_quantity:g} of "
                            f"{request.requested_quantity:g} requested; "
                            f"{', '.join(order_constraints.permitted_order_types)} only.")
                    else:
                        outcome = TradingOutcome.ALLOW
                        rationale.append("Authorized within approved envelope.")
            else:
                outcome = TradingOutcome.ALLOW
                rationale.append("Authorized (non-executing action).")

        return TradingDecision(
            outcome=outcome,
            governance_decision=gd,
            order_constraints=order_constraints,
            constraints=constraints,
            criticality=hp.get("criticality", derivation.signal),
            criticality_basis=derivation.basis,
            effective_authority_mode=hp.get("effective_mode", "baseline"),
            matched_rule_id=hp.get("matched_rule_id", ""),
            human_verdict=hp.get("verdict"),
            model_advisory_decision=hp.get("model_advisory_decision"),
            hard_block=bool(hp.get("hard_block")),
            hard_block_provenance=tuple(hp.get("hard_block_provenance", ()) or ()),
            final_authority_used=hp.get("final_authority_used", "MODEL"),
            requires_human_approval=outcome == TradingOutcome.REQUIRE_APPROVAL,
            rationale=" ".join(rationale),
            policy_version=self._policy_version,
            policy_hash=self._policy_hash,
            decision_id=resp.audit_reference,
            generic_response=resp)

    def _build_constraints(
        self, request: TradingActionRequest, oc: OrderConstraints, hp: Dict[str, Any],
    ) -> Dict[str, Any]:
        constraints = {
            "max_quantity": oc.max_quantity,
            "max_notional": oc.max_notional,
            "permitted_side": request.side.value if request.side else None,
            "permitted_symbol": request.symbol,
            "permitted_account": request.account_id,
            "permitted_venue": request.destination,
            "permitted_order_types": list(oc.permitted_order_types),
            "min_price": oc.min_price,
            "max_price": oc.max_price,
            "max_price_deviation_pct": oc.max_price_deviation_pct,
            "time_in_force": request.time_in_force.value,
            "no_widening": True,
            "no_onward_delegation": True,
            "strategy_binding": request.strategy_id,
            "strategy_version_binding": request.strategy_version,
            "model_version_binding": request.model_version,
        }
        for k, v in (hp.get("constraints") or {}).items():
            constraints.setdefault(k, v)
        return constraints
