"""
Trading policy fixtures — human-curated policy book, criticality registry,
approved universe + limits, and the forbidden-capability PolicyResolution that
routes trading hard blocks through the generic fail-closed layer.

Configuration for the generic engine only. No trading logic lives in
GovernanceService or HumanPolicyEngine.
"""

from __future__ import annotations

from typing import Tuple

from agentic.agentic_framework.human_policy import (
    ActionCriticalityRegistry,
    HumanPolicyBook,
    HumanPolicyMode,
    HumanPolicyRule,
    HumanPolicyVerdict,
    UncertainDisposition,
)
from agentic.agentic_framework.policy_bundle import (
    PolicyBundle,
    PolicyMetadata,
    PolicyResolution,
    SafetyPolicy,
)
from agentic.trading.criticality import (
    ALL_HARD_BLOCK_TOKENS,
    ApprovedUniverse,
    TradingLimits,
)
from agentic.trading.taxonomy import SessionStatus

TRADING_HARD_BLOCK_CAPABILITIES: Tuple[str, ...] = ALL_HARD_BLOCK_TOKENS

_SOT = HumanPolicyMode.SOURCE_OF_TRUTH
_BASE = HumanPolicyMode.BASELINE


def build_default_limits() -> TradingLimits:
    return TradingLimits()


def build_default_universe() -> ApprovedUniverse:
    return ApprovedUniverse(
        accounts=frozenset({"acct-1", "acct-2"}),
        strategies={"strat-momentum": frozenset({"1.0", "1.1"})},
        models={"model-a": frozenset({"2025.1"})},
        exchanges=frozenset({"XNAS", "XNYS"}),
        symbols=frozenset({"AAA", "BBB", "CCC"}),
        venues=frozenset({"sim-broker-1"}),
        permitted_sessions=frozenset({SessionStatus.OPEN}),
    )


def build_trading_criticality_registry() -> ActionCriticalityRegistry:
    return ActionCriticalityRegistry(
        critical_risk_levels=(),
        non_critical_risk_levels=(),
        critical_promoting_facts=("hc_critical", "declared_high_risk"),
        non_critical_facts=("hc_non_critical",),
        uncertain_disposition=UncertainDisposition.REQUIRE_APPROVAL,
    )


def build_trading_policy_book(
    *, name: str = "trading-pretrade", version: str = "1.0.0",
) -> HumanPolicyBook:
    A = HumanPolicyVerdict.ALLOW
    AWC = HumanPolicyVerdict.ALLOW_WITH_CONSTRAINTS
    RA = HumanPolicyVerdict.REQUIRE_APPROVAL

    rules = (
        # ---- Governance-critical actions (SOURCE_OF_TRUTH) -----------------
        HumanPolicyRule(
            rule_id="TR-RISK-LIMIT-CHANGE", verdict=RA, priority=30,
            when_facts=("action:CHANGE_RISK_LIMIT",), authority_mode=_SOT,
            approver_policy="risk_officer",
            description="Risk-limit changes require authorized human approval."),
        HumanPolicyRule(
            rule_id="TR-ACTIVATE-STRATEGY", verdict=RA, priority=30,
            when_facts=("action:ACTIVATE_STRATEGY",), authority_mode=_SOT,
            approver_policy="head_of_trading",
            description="Strategy activation requires approval."),
        HumanPolicyRule(
            rule_id="TR-TRANSFER-FUNDS", verdict=RA, priority=30,
            when_facts=("action:TRANSFER_FUNDS",), authority_mode=_SOT,
            approver_policy="treasury",
            description="Fund transfers require approval (represented, not executed in V1)."),

        # ---- Unapproved universe (SOURCE_OF_TRUTH review) -----------------
        HumanPolicyRule(
            rule_id="TR-UNAPPROVED-ACCOUNT", verdict=RA, priority=24,
            when_facts=("is_order_action",), unless_facts=("account_approved",),
            authority_mode=_SOT, description="Unapproved account requires review."),
        HumanPolicyRule(
            rule_id="TR-UNAPPROVED-STRATEGY", verdict=RA, priority=23,
            when_facts=("is_order_action",), unless_facts=("strategy_approved",),
            authority_mode=_SOT, description="Unapproved strategy requires review."),
        HumanPolicyRule(
            rule_id="TR-UNAPPROVED-MODEL", verdict=RA, priority=22,
            when_facts=("is_order_action",), unless_facts=("model_approved",),
            authority_mode=_SOT, description="Unapproved model version requires review."),

        # ---- Loss / session review ----------------------------------------
        HumanPolicyRule(
            rule_id="TR-DAILY-LOSS-SOFT", verdict=RA, priority=16,
            when_facts=("daily_loss_soft",), authority_mode=_SOT,
            approver_policy="risk_officer",
            description="Trading near the daily-loss threshold requires review."),
        HumanPolicyRule(
            rule_id="TR-SESSION-NOT-OPEN", verdict=RA, priority=14,
            when_facts=("is_order_action",), unless_facts=("session_open",),
            authority_mode=_SOT, description="Trading outside session requires review."),

        # ---- Large / risky-but-resizable orders (constrain) ---------------
        HumanPolicyRule(
            rule_id="TR-CONSTRAIN-LARGE-ORDER", verdict=AWC, priority=12,
            when_facts=("constrainable_order",),
            constraints={"min_necessary": True, "no_widening": True},
            description="Large/risky order reduced to the approved envelope."),

        # ---- Bounded, reversible, in-limits (BASELINE) --------------------
        HumanPolicyRule(
            rule_id="TR-BOUNDED-ALLOW", verdict=A, priority=1,
            when_facts=("hc_non_critical",),
            constraints={"min_necessary": True},
            description="Bounded in-limits action; model governance may tighten."),

        # ---- Conservative catch-all ---------------------------------------
        HumanPolicyRule(
            rule_id="TR-DEFAULT-REVIEW", verdict=RA, priority=0,
            description="Unmatched actions default to review."),
    )
    return HumanPolicyBook(rules=rules, name=name, version=version)


def build_trading_forbidden_policy_resolution() -> PolicyResolution:
    base = SafetyPolicy().forbidden_capabilities
    safety = SafetyPolicy(
        forbidden_capabilities=tuple(base) + TRADING_HARD_BLOCK_CAPABILITIES)
    bundle = PolicyBundle(
        metadata=PolicyMetadata(policy_id="trading-forbidden", version="1.0.0",
                                description="Trading hard-block capabilities."),
        safety=safety)
    return PolicyResolution(
        effective_policy=bundle, base_policy_id="trading-forbidden",
        base_version="1.0.0")
