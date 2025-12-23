"""Presentation Layer Rule Definitions.

Implements: PRESENTATION_LAYER_v1.0.md Part 4

Defines the prioritized presentation rules:

Core Rules (always active):
1. Critical Viparyaya (100) - Misperception detection
2. Severe Nidrā (95) - Missing information
3. High Vikalpa (80) - Multiple interpretations
4. Elevated Smṛti (70) - Staleness/repetition
5. Moderate Uncertainty (60) - Hedged delivery
6. Low Confidence (55) - Acknowledge uncertainty
7. High Pramāṇa (50) - Confident delivery
8. Default (0) - Fallback rule

V2.7 Experimental Rules (only when v2.7 enabled):
- Unreliable Estimate (98) - Bayesian confidence too low (Bayesian mode only)
- Regressing State (88) - Cognitive state indicates regression
- Concept Unstable (78) - Concept readiness too low
- Low Utility Streak (68) - Prolonged low utility observations
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


def build_rules(config: PresentationConfig, include_v27_rules: bool = True) -> list[PresentationRule]:
    """Build the complete rule set for a configuration.

    Part 4.2: Returns rules sorted by priority (descending).

    Args:
        config: The tier-specific configuration
        include_v27_rules: Whether to include v2.7 experimental rules.
            These rules only fire when v2.7 signals are present in the bundle.

    Returns:
        List of PresentationRule instances, sorted by priority
    """
    # Core rules (always active)
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

    # V2.7 experimental rules (conditionally included)
    if include_v27_rules:
        rules.extend([
            _make_unreliable_estimate_rule(config),  # Priority 98 (Bayesian only)
            _make_regressing_state_rule(config),  # Priority 88
            _make_concept_unstable_rule(config),  # Priority 78
            _make_low_utility_streak_rule(config),  # Priority 68
        ])

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


# =============================================================================
# V2.7 Experimental Rules
# =============================================================================
# These rules only fire when v2.7 signals are present in the bundle.
# They check s.has_v27_signals or s.has_bayesian_signals before firing.


def _make_unreliable_estimate_rule(config: PresentationConfig) -> PresentationRule:
    """V2.7 Rule: Unreliable Estimate (Priority 98).

    Only fires in Bayesian v2.7 mode when bayesian_confidence is too low.

    Condition: has_bayesian_signals AND bayesian_confidence < 0.5
    """

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        # Only fire if Bayesian signals are available
        if not s.has_bayesian_signals:
            return False
        return s.v27.bayesian_confidence < 0.5

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.ACKNOWLEDGING,
            confidence=ConfidenceIndicator.LOW,
            behaviors=SuggestedBehaviors(
                show_reasoning=True,
                offer_clarification=True,
            ),
            explanation=f"Low estimation confidence ({s.v27.bayesian_confidence:.0%})",
            triggered_rule="unreliable_estimate_v27",
        )

    return PresentationRule(
        name="unreliable_estimate_v27",
        priority=98,
        condition=condition,
        directive=directive,
    )


def _make_regressing_state_rule(config: PresentationConfig) -> PresentationRule:
    """V2.7 Rule: Regressing State (Priority 88).

    Fires when cognitive state indicates regression or instability.

    Condition: has_v27_signals AND cognitive_state in {regressing, unstable}
    """

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        if not s.has_v27_signals:
            return False
        return s.v27.is_regressing

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.CLARIFYING,
            confidence=ConfidenceIndicator.LOW,
            behaviors=SuggestedBehaviors(
                offer_clarification=True,
                escalate_to_human=cfg.escalate_to_human,
            ),
            explanation=f"Cognitive state: {s.v27.cognitive_state}",
            triggered_rule="regressing_state_v27",
        )

    return PresentationRule(
        name="regressing_state_v27",
        priority=88,
        condition=condition,
        directive=directive,
    )


def _make_concept_unstable_rule(config: PresentationConfig) -> PresentationRule:
    """V2.7 Rule: Concept Unstable (Priority 78).

    Fires when concept readiness is too low to present confidently.

    Condition: has_v27_signals AND concept_readiness < 0.4
    """

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        if not s.has_v27_signals:
            return False
        return s.v27.concept_readiness < 0.4

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.LOW,
            behaviors=SuggestedBehaviors(
                offer_clarification=True,
            ),
            explanation=f"Concept not yet stable ({s.v27.concept_readiness_level})",
            triggered_rule="concept_unstable_v27",
        )

    return PresentationRule(
        name="concept_unstable_v27",
        priority=78,
        condition=condition,
        directive=directive,
    )


def _make_low_utility_streak_rule(config: PresentationConfig) -> PresentationRule:
    """V2.7 Rule: Low Utility Streak (Priority 68).

    Fires when there's a prolonged streak of low utility observations.

    Condition: has_v27_signals AND low_utility_streak >= 5
    """

    def condition(s: SignalBundle, cfg: PresentationConfig) -> bool:
        if not s.has_v27_signals:
            return False
        return s.v27.low_utility_streak >= 5

    def directive(s: SignalBundle, cfg: PresentationConfig) -> PresentationDirective:
        return PresentationDirective(
            delivery_mode=DeliveryMode.ACKNOWLEDGING,
            confidence=ConfidenceIndicator.MEDIUM,
            behaviors=SuggestedBehaviors(
                offer_clarification=True,
                show_reasoning=cfg.show_reasoning_by_default,
            ),
            explanation=f"System quality below optimal ({s.v27.low_utility_streak} observations)",
            triggered_rule="low_utility_streak_v27",
        )

    return PresentationRule(
        name="low_utility_streak_v27",
        priority=68,
        condition=condition,
        directive=directive,
    )
