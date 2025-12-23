"""Presentation Layer Rule Definitions.

Implements: PRESENTATION_LAYER_v1.0.md Part 4

Defines the 8 prioritized presentation rules:
1. Critical Viparyaya (100) - Misperception detection
2. Severe Nidrā (95) - Missing information
3. High Vikalpa (80) - Multiple interpretations
4. Elevated Smṛti (70) - Staleness/repetition
5. Moderate Uncertainty (60) - Hedged delivery
6. Low Confidence (55) - Acknowledge uncertainty
7. High Pramāṇa (50) - Confident delivery
8. Default (0) - Fallback rule
"""

from dataclasses import dataclass
from typing import Callable

from symbolu.presentation.types import (
    DeliveryMode,
    ConfidenceIndicator,
    SuggestedBehaviors,
    PresentationDirective,
)
from symbolu.presentation.signals import SignalBundle
from symbolu.presentation.config import PresentationConfig


@dataclass
class PresentationRule:
    """A single presentation rule.

    Part 4.1: Each rule has a name, priority, condition, and directive factory.

    Rules are evaluated in priority order (highest first). The first rule
    whose condition returns True produces the directive.
    """

    name: str
    priority: int  # Higher = checked first
    condition: Callable[[SignalBundle, PresentationConfig], bool]
    directive: Callable[[SignalBundle, PresentationConfig], PresentationDirective]


def build_rules(config: PresentationConfig) -> list[PresentationRule]:
    """Build the complete rule set for a configuration.

    Part 4.2: Returns rules sorted by priority (descending).

    Args:
        config: The tier-specific configuration

    Returns:
        List of PresentationRule instances, sorted by priority
    """
    rules = [
        _make_critical_viparyaya_rule(config),
        _make_severe_nidra_rule(config),
        _make_high_vikalpa_rule(config),
        _make_elevated_smrti_rule(config),
        _make_moderate_uncertainty_rule(config),
        _make_low_confidence_rule(config),
        _make_high_pramana_rule(config),
        _make_default_rule(config),
    ]
    return sorted(rules, key=lambda r: r.priority, reverse=True)


# === Rule Factories ===


def _make_critical_viparyaya_rule(config: PresentationConfig) -> PresentationRule:
    """Rule 1: Critical Viparyaya (Priority 100).

    Part 4.2: High viparyaya with high confidence = "confidently wrong".

    Condition: viparyaya > threshold OR (viparyaya > threshold*0.6 AND confidence > 0.8)
    """
    threshold = config.viparyaya_critical_threshold

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        # High viparyaya alone, or moderate viparyaya with high confidence
        return (
            s.vritti.viparyaya > threshold
            or (s.vritti.viparyaya > threshold * 0.6 and s.confidence > 0.8)
        )

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.ACKNOWLEDGING,
            confidence=ConfidenceIndicator.LOW,
            behaviors=SuggestedBehaviors(
                show_alternatives=True,
                offer_clarification=True,
                escalate_to_human=cfg.escalate_to_human,
            ),
            explanation="System detected potential misinterpretation",
            triggered_rule="critical_viparyaya",
        )

    return PresentationRule(
        name="critical_viparyaya",
        priority=100,
        condition=condition,
        directive=directive,
    )


def _make_severe_nidra_rule(config: PresentationConfig) -> PresentationRule:
    """Rule 2: Severe Nidrā (Priority 95).

    Part 4.2: Insufficient information to produce meaningful output.

    Condition: nidra > threshold OR layers_present_count < 2
    """
    threshold = config.nidra_severe_threshold

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        return s.vritti.nidra > threshold or s.layers_present_count < 2

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.CLARIFYING,
            confidence=ConfidenceIndicator.UNKNOWN,
            behaviors=SuggestedBehaviors(
                request_repeat=True,
            ),
            explanation="Insufficient information received",
            triggered_rule="severe_nidra",
        )

    return PresentationRule(
        name="severe_nidra",
        priority=95,
        condition=condition,
        directive=directive,
    )


def _make_high_vikalpa_rule(config: PresentationConfig) -> PresentationRule:
    """Rule 3: High Vikalpa (Priority 80).

    Part 4.2: Multiple valid interpretations exist.

    Condition: vikalpa > threshold AND entropy > 0.5
    """
    threshold = config.vikalpa_high_threshold

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        return s.vritti.vikalpa > threshold and s.entropy > 0.5

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.CLARIFYING,
            confidence=ConfidenceIndicator.MEDIUM,
            behaviors=SuggestedBehaviors(
                show_alternatives=True,
            ),
            explanation="Multiple interpretations possible",
            triggered_rule="high_vikalpa",
        )

    return PresentationRule(
        name="high_vikalpa",
        priority=80,
        condition=condition,
        directive=directive,
    )


def _make_elevated_smrti_rule(config: PresentationConfig) -> PresentationRule:
    """Rule 4: Elevated Smṛti (Priority 70).

    Part 4.2: System may be stuck in a loop.

    Condition: smrti > threshold AND consecutive_low_motion > 3
    """
    threshold = config.smrti_elevated_threshold

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        return (
            s.vritti.smrti > threshold
            and s.session.consecutive_low_motion > cfg.low_motion_streak_threshold
        )

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.ACKNOWLEDGING,
            confidence=ConfidenceIndicator.MEDIUM,
            behaviors=SuggestedBehaviors(
                offer_clarification=True,
            ),
            explanation="Response seems similar to previous",
            triggered_rule="elevated_smrti",
        )

    return PresentationRule(
        name="elevated_smrti",
        priority=70,
        condition=condition,
        directive=directive,
    )


def _make_moderate_uncertainty_rule(config: PresentationConfig) -> PresentationRule:
    """Rule 5: Moderate Uncertainty (Priority 60).

    Part 4.2: Moderate confidence; hedge language but proceed.

    Condition: score_moderate <= score < score_confident
    """

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        return cfg.score_moderate_threshold <= s.score < cfg.score_confident_threshold

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.MEDIUM,
            behaviors=SuggestedBehaviors(),
            explanation="Moderate confidence in interpretation",
            triggered_rule="moderate_uncertainty",
        )

    return PresentationRule(
        name="moderate_uncertainty",
        priority=60,
        condition=condition,
        directive=directive,
    )


def _make_low_confidence_rule(config: PresentationConfig) -> PresentationRule:
    """Rule 6: Low Confidence (Priority 55).

    Part 4.2: Low overall readiness; acknowledge uncertainty.

    Condition: score < score_moderate
    """

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        return s.score < cfg.score_moderate_threshold

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.ACKNOWLEDGING,
            confidence=ConfidenceIndicator.LOW,
            behaviors=SuggestedBehaviors(
                offer_clarification=True,
            ),
            explanation="Low confidence in interpretation",
            triggered_rule="low_confidence",
        )

    return PresentationRule(
        name="low_confidence",
        priority=55,
        condition=condition,
        directive=directive,
    )


def _make_high_pramana_rule(config: PresentationConfig) -> PresentationRule:
    """Rule 7: High Pramāṇa (Priority 50).

    Part 4.2: Strong valid cognition; deliver confidently.

    Condition: pramana > threshold AND score >= score_confident
    """
    threshold = config.pramana_high_threshold

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        return (
            s.vritti.pramana > threshold and s.score >= cfg.score_confident_threshold
        )

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            behaviors=SuggestedBehaviors(),
            explanation="High confidence interpretation",
            triggered_rule="high_pramana",
        )

    return PresentationRule(
        name="high_pramana",
        priority=50,
        condition=condition,
        directive=directive,
    )


def _make_default_rule(config: PresentationConfig) -> PresentationRule:
    """Rule 8: Default Fallback (Priority 0).

    Part 4.2: When no other rule matches, use moderate hedging.

    Condition: Always True (fallback)
    """

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        return True

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.MEDIUM,
            behaviors=SuggestedBehaviors(),
            explanation="Standard interpretation",
            triggered_rule="default",
        )

    return PresentationRule(
        name="default",
        priority=0,
        condition=condition,
        directive=directive,
    )
