"""
Enterprise Policy Engine
========================

"Policies as code" that turn explainability signals into runtime control.

Enterprises don't just want explanations — they want guardrails:
    - If query is compliance/legal → require quad_ratio >= 0.35 and stability GREEN
    - If drift is high → force verify mode
    - If action is irreversible → require confirmation
    - If coherence drops below threshold → block tool execution

This module implements a rule-based policy evaluator that reads from
ExplanationTelemetry and produces enforcement decisions.

Usage:
    engine = EnterprisePolicyEngine()
    engine.add_rule(PolicyRule(
        name="compliance_grounding",
        description="Compliance queries must use structured retrieval",
        condition=lambda t: t.routing.quad_ratio < 0.35,
        action=PolicyAction.VERIFY,
        domains=["compliance", "legal", "finance"],
    ))

    result = engine.evaluate(telemetry, context={"domain": "compliance"})
    if result.blocked:
        # Don't execute, escalate to human
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from symbolu.mechanical.logging.telemetry_schema import (
    ExplanationTelemetry,
    PolicyOutcome,
    StabilityBadge,
)


class PolicyAction(str, Enum):
    """What the engine does when a rule triggers."""
    ALLOW = "allow"           # No intervention
    WARN = "warn"             # Log warning, continue
    VERIFY = "verify"         # Require human confirmation
    BLOCK = "block"           # Refuse to proceed
    ESCALATE = "escalate"     # Forward to Sentinel / supervisor


@dataclass
class PolicyRule:
    """
    A single policy rule.

    condition: Callable that takes ExplanationTelemetry and returns True
               when the rule TRIGGERS (i.e., when the condition is violated).
    action: What to do when triggered.
    domains: If non-empty, rule only applies when context.domain is in this list.
    tags: Arbitrary tags for grouping / filtering rules.
    """
    name: str
    description: str
    condition: Callable[[ExplanationTelemetry], bool]
    action: PolicyAction = PolicyAction.WARN
    domains: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class PolicyViolation:
    """Record of a single rule violation."""
    rule_name: str
    rule_description: str
    action: PolicyAction
    telemetry_summary: str


@dataclass
class PolicyResult:
    """
    Result of evaluating all policies against a telemetry record.

    The effective outcome is the MOST RESTRICTIVE action across all
    triggered rules (block > escalate > verify > warn > allow).
    """
    outcome: PolicyAction = PolicyAction.ALLOW
    violations: List[PolicyViolation] = field(default_factory=list)
    rules_evaluated: int = 0
    rules_triggered: int = 0

    @property
    def blocked(self) -> bool:
        return self.outcome == PolicyAction.BLOCK

    @property
    def needs_verification(self) -> bool:
        return self.outcome in (PolicyAction.VERIFY, PolicyAction.ESCALATE)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "violations": [
                {
                    "rule": v.rule_name,
                    "description": v.rule_description,
                    "action": v.action.value,
                }
                for v in self.violations
            ],
            "rules_evaluated": self.rules_evaluated,
            "rules_triggered": self.rules_triggered,
        }


# Severity ordering for "most restrictive wins"
_ACTION_SEVERITY = {
    PolicyAction.ALLOW: 0,
    PolicyAction.WARN: 1,
    PolicyAction.VERIFY: 2,
    PolicyAction.ESCALATE: 3,
    PolicyAction.BLOCK: 4,
}


class EnterprisePolicyEngine:
    """
    Rule-based policy evaluator for Phase Quad telemetry.

    Evaluates a set of PolicyRules against each ExplanationTelemetry record
    and returns the most restrictive outcome.

    Ships with sensible default rules for common enterprise use cases.
    Enterprises can add, remove, or override rules.
    """

    def __init__(self, load_defaults: bool = True):
        """
        Args:
            load_defaults: If True, load the built-in default rules.
        """
        self._rules: List[PolicyRule] = []
        if load_defaults:
            self._load_default_rules()

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a policy rule."""
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name. Returns True if found."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def enable_rule(self, name: str) -> None:
        """Enable a rule by name."""
        for r in self._rules:
            if r.name == name:
                r.enabled = True

    def disable_rule(self, name: str) -> None:
        """Disable a rule by name."""
        for r in self._rules:
            if r.name == name:
                r.enabled = False

    @property
    def rules(self) -> List[PolicyRule]:
        """Read-only access to rules."""
        return list(self._rules)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        telemetry: ExplanationTelemetry,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyResult:
        """
        Evaluate all rules against a telemetry record.

        Args:
            telemetry: The explanation telemetry to evaluate.
            context: Optional context dict with keys like "domain", "user_role",
                     "action_type", "is_irreversible", etc.

        Returns:
            PolicyResult with the most restrictive outcome.
        """
        ctx = context or {}
        domain = ctx.get("domain", "")

        result = PolicyResult()

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Domain filter: skip if rule has domain restrictions and
            # current domain doesn't match
            if rule.domains and domain not in rule.domains:
                continue

            result.rules_evaluated += 1

            try:
                triggered = rule.condition(telemetry)
            except Exception:
                continue  # Never let rule errors break inference

            if triggered:
                result.rules_triggered += 1
                result.violations.append(PolicyViolation(
                    rule_name=rule.name,
                    rule_description=rule.description,
                    action=rule.action,
                    telemetry_summary=telemetry.summary(),
                ))

                # Most restrictive wins
                if _ACTION_SEVERITY[rule.action] > _ACTION_SEVERITY[result.outcome]:
                    result.outcome = rule.action

        return result

    # ------------------------------------------------------------------
    # Default Rules
    # ------------------------------------------------------------------

    def _load_default_rules(self) -> None:
        """
        Load built-in default rules covering the five enterprise use case
        classes identified in the Phase Quad explainability analysis.
        """

        # --- Class 1: Regulated Industries ---

        self.add_rule(PolicyRule(
            name="regulated_grounding",
            description=(
                "Regulated queries must rely on structured retrieval (Quad), "
                "not just local context"
            ),
            condition=lambda t: t.routing.quad_ratio < 0.20,
            action=PolicyAction.VERIFY,
            domains=["compliance", "legal", "finance", "healthcare"],
            tags=["regulated", "grounding"],
        ))

        self.add_rule(PolicyRule(
            name="regulated_stability",
            description=(
                "Regulated queries require GREEN stability badge"
            ),
            condition=lambda t: t.stability.stability_badge != StabilityBadge.GREEN,
            action=PolicyAction.VERIFY,
            domains=["compliance", "legal", "finance", "healthcare"],
            tags=["regulated", "stability"],
        ))

        # --- Class 2: Customer Support ---

        self.add_rule(PolicyRule(
            name="support_old_context_warning",
            description=(
                "Warn if answer relies heavily on distant context "
                "without recent local grounding"
            ),
            condition=lambda t: (
                t.routing.quad_ratio > 0.7 and t.routing.local_ratio < 0.15
            ),
            action=PolicyAction.WARN,
            domains=["support", "customer_service"],
            tags=["support", "recency"],
        ))

        # --- Class 3: Knowledge Work / Enterprise Search ---

        self.add_rule(PolicyRule(
            name="search_low_grounding",
            description=(
                "Knowledge queries with low quad attribution should not "
                "answer confidently"
            ),
            condition=lambda t: (
                t.routing.quad_ratio < 0.15
                and t.policy.confidence_score > 0.7
            ),
            action=PolicyAction.WARN,
            tags=["search", "grounding"],
        ))

        # --- Class 4: Engineering / DevOps ---

        self.add_rule(PolicyRule(
            name="code_high_hallucination_risk",
            description=(
                "Code suggestions with high drift or low anchoring "
                "have elevated hallucination risk"
            ),
            condition=lambda t: (
                t.stability.phase_drift_mean > 0.3
                and t.routing.quad_ratio < 0.2
            ),
            action=PolicyAction.WARN,
            domains=["engineering", "devops", "code"],
            tags=["code", "hallucination"],
        ))

        # --- Class 5: Security / Adversarial ---

        self.add_rule(PolicyRule(
            name="adversarial_drift",
            description=(
                "Adversarial drift detected — unusual gate volatility "
                "or routing shift"
            ),
            condition=lambda t: t.policy.adversarial_drift_detected,
            action=PolicyAction.BLOCK,
            tags=["security", "adversarial"],
        ))

        self.add_rule(PolicyRule(
            name="prompt_injection",
            description="Prompt injection pattern detected",
            condition=lambda t: t.policy.prompt_injection_detected,
            action=PolicyAction.BLOCK,
            tags=["security", "injection"],
        ))

        # --- Universal Rules ---

        self.add_rule(PolicyRule(
            name="stability_red_block",
            description=(
                "Phase collapse or extreme instability — block all actions"
            ),
            condition=lambda t: t.stability.stability_badge == StabilityBadge.RED,
            action=PolicyAction.VERIFY,
            tags=["universal", "stability"],
        ))

        self.add_rule(PolicyRule(
            name="high_reversal_risk",
            description=(
                "High reversal risk — earlier tokens may contradict later ones"
            ),
            condition=lambda t: t.stability.reversal_risk > 0.6,
            action=PolicyAction.VERIFY,
            tags=["universal", "reversal"],
        ))

        self.add_rule(PolicyRule(
            name="low_coherence_block",
            description="Very low coherence — reasoning may be unreliable",
            condition=lambda t: t.policy.coherence_score < 0.3,
            action=PolicyAction.BLOCK,
            tags=["universal", "coherence"],
        ))

        self.add_rule(PolicyRule(
            name="cache_redundancy_warning",
            description=(
                "Cache keys are too similar — memory slots collapsing, "
                "retrieval diversity degraded"
            ),
            condition=lambda t: t.provenance.cache_key_cosine_max > 0.95,
            action=PolicyAction.WARN,
            tags=["universal", "cache_health"],
        ))


__all__ = [
    "PolicyAction",
    "PolicyRule",
    "PolicyViolation",
    "PolicyResult",
    "EnterprisePolicyEngine",
]
