"""Presentation Layer Engine.

Implements: PRESENTATION_LAYER_v1.0.md Part 7.1

The PresentationEngine is the main entry point for computing
presentation directives from signal bundles. It:
- Builds rules from configuration
- Evaluates rules in priority order
- Applies config overrides to directives
- Optionally attaches diagnostic info
"""

import dataclasses
from typing import Optional

from symbolu_core.presentation.types import (
    DeliveryMode,
    ConfidenceIndicator,
    SuggestedBehaviors,
    DiagnosticInfo,
    PresentationDirective,
)
from symbolu_core.presentation.signals import SignalBundle
from symbolu_core.presentation.config import PresentationConfig
from symbolu_core.presentation.rules import PresentationRule, build_rules


class PresentationEngine:
    """Composes presentation directives from signals.

    Part 7.1: Main entry point for the Presentation Layer.

    The engine is stateless — it evaluates rules based solely on
    the input SignalBundle. Session tracking is handled separately
    by SessionStateManager.
    """

    def __init__(self, config: PresentationConfig):
        """Initialize engine with configuration.

        Args:
            config: Tier-specific presentation configuration
        """
        self._config = config
        self._rules = build_rules(config)

    @property
    def config(self) -> PresentationConfig:
        """Current configuration."""
        return self._config

    @property
    def rules(self) -> list[PresentationRule]:
        """Current rule set (sorted by priority)."""
        return self._rules

    def compute(self, signals: SignalBundle) -> PresentationDirective:
        """Compute directive by evaluating rules in priority order.

        Part 7.1: Main computation method.

        Rules are evaluated in descending priority order. The first
        rule whose condition returns True produces the directive.
        Config overrides are then applied.

        Args:
            signals: Complete signal bundle for rule evaluation

        Returns:
            PresentationDirective with applied config overrides
        """
        directive = self._evaluate_rules(signals)
        directive = self._apply_config_overrides(directive)

        if self._config.include_diagnostics:
            directive = self._attach_diagnostic(directive, signals)

        return directive

    def _evaluate_rules(self, signals: SignalBundle) -> PresentationDirective:
        """Evaluate rules and return matching directive.

        Part 7.1: Core rule evaluation loop.
        """
        for rule in self._rules:
            if rule.condition(signals, self._config):
                return rule.directive(signals, self._config)

        # Should never reach here due to default rule with always-true condition
        # But provide fallback for safety
        return PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.MEDIUM,
            behaviors=SuggestedBehaviors(),
            explanation="Fallback directive",
            triggered_rule="fallback",
        )

    def _apply_config_overrides(
        self,
        directive: PresentationDirective,
    ) -> PresentationDirective:
        """Apply tier-specific config overrides.

        Part 7.1: Ensures tier constraints are respected.
        """
        behaviors = directive.behaviors

        # Disable escalation if not allowed by tier
        if not self._config.escalate_to_human and behaviors.escalate_to_human:
            behaviors = dataclasses.replace(
                behaviors,
                escalate_to_human=False,
            )

        # Enable reasoning if default for tier
        if self._config.show_reasoning_by_default and not behaviors.show_reasoning:
            behaviors = dataclasses.replace(
                behaviors,
                show_reasoning=True,
            )

        # Disable silent mode if not allowed by tier
        if not self._config.allow_silent_mode:
            if directive.delivery_mode == DeliveryMode.SILENT:
                return dataclasses.replace(
                    directive,
                    delivery_mode=DeliveryMode.ACKNOWLEDGING,
                    behaviors=behaviors,
                )

        return dataclasses.replace(directive, behaviors=behaviors)

    def _attach_diagnostic(
        self,
        directive: PresentationDirective,
        signals: SignalBundle,
    ) -> PresentationDirective:
        """Attach diagnostic info to directive.

        Part 7.1: For debug/advanced UX tiers.
        """
        # Determine active penalties based on vritti distribution
        active_penalties = []
        if signals.vritti.viparyaya > self._config.viparyaya_critical_threshold:
            active_penalties.append("viparyaya_penalty")
        if signals.vritti.nidra > self._config.nidra_severe_threshold:
            active_penalties.append("nidra_penalty")
        if signals.vritti.vikalpa > self._config.vikalpa_high_threshold:
            active_penalties.append("vikalpa_penalty")
        if signals.vritti.smrti > self._config.smrti_elevated_threshold:
            active_penalties.append("smrti_penalty")

        # Build signal summary
        signal_summary = (
            f"score={signals.score:.2f} "
            f"coherence={signals.coherence:.2f} "
            f"entropy={signals.entropy:.2f} "
            f"layers={signals.layers_present_count}"
        )

        diagnostic = DiagnosticInfo(
            dominant_vritti=signals.dominant_vritti,
            primary_fracture=signals.primary_fracture,
            active_penalties=active_penalties,
            signal_summary=signal_summary,
        )

        return dataclasses.replace(directive, diagnostic=diagnostic)

    def get_rule_by_name(self, name: str) -> Optional[PresentationRule]:
        """Get a rule by name.

        Args:
            name: Rule name

        Returns:
            PresentationRule or None if not found
        """
        for rule in self._rules:
            if rule.name == name:
                return rule
        return None

    def explain_decision(self, signals: SignalBundle) -> str:
        """Explain which rule would fire and why.

        Useful for debugging and transparency.

        Args:
            signals: Signal bundle to evaluate

        Returns:
            Human-readable explanation string
        """
        lines = [
            "Presentation Decision Explanation",
            "=" * 40,
            f"Tier: {self._config.tier}",
            "",
            "Input Signals:",
            f"  score: {signals.score:.3f}",
            f"  coherence: {signals.coherence:.3f}",
            f"  entropy: {signals.entropy:.3f}",
            f"  layers_present: {signals.layers_present_count}",
            "",
            "Vṛtti Distribution:",
            f"  pramāṇa: {signals.vritti.pramana:.3f}",
            f"  viparyaya: {signals.vritti.viparyaya:.3f}",
            f"  vikalpa: {signals.vritti.vikalpa:.3f}",
            f"  smṛti: {signals.vritti.smrti:.3f}",
            f"  nidrā: {signals.vritti.nidra:.3f}",
            "",
            "Rule Evaluation (priority order):",
        ]

        for rule in self._rules:
            matches = rule.condition(signals, self._config)
            status = "✓ MATCH" if matches else "  skip"
            lines.append(f"  [{rule.priority:3d}] {rule.name}: {status}")
            if matches:
                directive = rule.directive(signals, self._config)
                lines.extend(
                    [
                        "",
                        f"Result: {rule.name}",
                        f"  delivery_mode: {directive.delivery_mode.value}",
                        f"  confidence: {directive.confidence.value}",
                        f"  explanation: {directive.explanation}",
                    ]
                )
                break

        return "\n".join(lines)
