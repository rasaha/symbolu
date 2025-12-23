"""Presentation Layer Configuration.

Implements: PRESENTATION_LAYER_v1.0.md Part 5

Defines tier-specific configurations for the 4 engine tiers:
- ENTERPRISE_SEARCH: Strictest, classification-focused
- ENTERPRISE_CHAT: Strict but conversational
- CONSUMER: Tolerant, flow-optimized
- DEVELOPMENT: All features, verbose debugging
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PresentationTier(Enum):
    """Presentation tier aligned with EngineTier.

    Part 5: Each tier has different sensitivity thresholds and behaviors.
    """

    ENTERPRISE_SEARCH = "enterprise_search"  # Classification/tagging
    ENTERPRISE_CHAT = "enterprise_chat"  # Specialized chat
    CONSUMER = "consumer"  # General use
    DEVELOPMENT = "development"  # Testing/debug


@dataclass
class PresentationConfig:
    """Complete presentation configuration for a tier.

    Part 5: Defines thresholds, behaviors, and language for each tier.

    Threshold parameters control rule sensitivity:
    - Higher thresholds = less sensitive (tolerant)
    - Lower thresholds = more sensitive (strict)
    """

    tier: str

    # === Rule Thresholds ===
    # Critical viparyaya: triggers acknowledging mode
    viparyaya_critical_threshold: float = 0.3

    # Severe nidrā: triggers clarifying mode
    nidra_severe_threshold: float = 0.5

    # High vikalpa: triggers showing alternatives
    vikalpa_high_threshold: float = 0.35

    # Elevated smṛti: triggers staleness warning
    smrti_elevated_threshold: float = 0.4

    # Score thresholds for confidence levels
    score_confident_threshold: float = 0.85  # Above = confident
    score_moderate_threshold: float = 0.5  # Above = hedged, below = low

    # Pramāṇa threshold for high confidence
    pramana_high_threshold: float = 0.7

    # Motion threshold for staleness detection
    low_motion_threshold: float = 0.1

    # === Behavioral Flags ===
    allow_silent_mode: bool = False  # Whether SILENT delivery is allowed
    escalate_to_human: bool = True  # Whether escalation is enabled
    show_reasoning_by_default: bool = False  # Show reasoning without request
    include_diagnostics: bool = False  # Include diagnostic info in output

    # === Language Configuration ===
    hedging_phrases: list[str] = field(
        default_factory=lambda: [
            "Based on available information",
            "With moderate confidence",
        ]
    )

    clarifying_phrases: list[str] = field(
        default_factory=lambda: [
            "Please confirm the intended meaning",
            "Could you clarify",
        ]
    )

    acknowledging_phrases: list[str] = field(
        default_factory=lambda: [
            "I'm not entirely certain, but",
            "There may be some uncertainty here",
        ]
    )

    # === Session Configuration ===
    session_history_window: int = 10  # Turns to track in history
    low_score_streak_threshold: int = 3  # Consecutive low scores to flag
    low_motion_streak_threshold: int = 3  # Consecutive low motion to flag


# === Pre-configured Tier Instances ===

ENTERPRISE_SEARCH_CONFIG = PresentationConfig(
    tier="enterprise_search",
    # Thresholds (strictest - classification must be accurate)
    viparyaya_critical_threshold=0.2,  # Very sensitive to misperception
    nidra_severe_threshold=0.4,  # Need complete information
    vikalpa_high_threshold=0.25,  # Ambiguity is costly
    smrti_elevated_threshold=0.3,
    score_confident_threshold=0.9,  # High bar for "confident"
    score_moderate_threshold=0.6,
    pramana_high_threshold=0.8,
    low_motion_threshold=0.15,
    # Behaviors (minimal UX, maximum audit)
    allow_silent_mode=True,  # Suppress uncertain classifications
    escalate_to_human=True,  # Flag for human review
    show_reasoning_by_default=False,  # Keep output clean
    include_diagnostics=True,  # Audit trail required
    # Language (terse)
    hedging_phrases=["[Uncertain]", "[Low confidence]"],
    clarifying_phrases=["[Ambiguous input]", "[Requires clarification]"],
    acknowledging_phrases=["[Potential error]", "[Review recommended]"],
)

ENTERPRISE_CHAT_CONFIG = PresentationConfig(
    tier="enterprise_chat",
    # Thresholds (strict but conversational)
    viparyaya_critical_threshold=0.3,
    nidra_severe_threshold=0.5,
    vikalpa_high_threshold=0.35,
    smrti_elevated_threshold=0.4,
    score_confident_threshold=0.85,
    score_moderate_threshold=0.5,
    pramana_high_threshold=0.75,
    low_motion_threshold=0.1,
    # Behaviors
    allow_silent_mode=False,  # Chat must respond
    escalate_to_human=True,  # Enable escalation
    show_reasoning_by_default=True,  # Transparency
    include_diagnostics=True,  # Audit trail
    # Language (professional)
    hedging_phrases=[
        "Based on available information",
        "With moderate confidence",
        "Subject to verification",
    ],
    clarifying_phrases=[
        "Please confirm the intended meaning",
        "Clarification required",
    ],
    acknowledging_phrases=[
        "I may have misunderstood",
        "There's some uncertainty here",
    ],
)

CONSUMER_CONFIG = PresentationConfig(
    tier="consumer",
    # Thresholds (most tolerant - prioritize flow)
    viparyaya_critical_threshold=0.6,  # Higher = less sensitive
    nidra_severe_threshold=0.8,
    vikalpa_high_threshold=0.5,
    smrti_elevated_threshold=0.6,
    score_confident_threshold=0.7,
    score_moderate_threshold=0.4,
    pramana_high_threshold=0.6,
    low_motion_threshold=0.05,
    # Behaviors (user-friendly)
    allow_silent_mode=False,  # Never suppress output
    escalate_to_human=False,  # Handle internally
    show_reasoning_by_default=False,  # Keep it simple
    include_diagnostics=False,  # No debug info
    # Language (conversational)
    hedging_phrases=["I think", "It seems like", "Possibly"],
    clarifying_phrases=["Did you mean", "Just to confirm"],
    acknowledging_phrases=["I'm not sure, but", "It might be"],
)

DEVELOPMENT_CONFIG = PresentationConfig(
    tier="development",
    # Thresholds (same as Enterprise Search for accuracy testing)
    viparyaya_critical_threshold=0.2,
    nidra_severe_threshold=0.4,
    vikalpa_high_threshold=0.25,
    smrti_elevated_threshold=0.3,
    score_confident_threshold=0.9,
    score_moderate_threshold=0.6,
    pramana_high_threshold=0.8,
    low_motion_threshold=0.1,
    # Behaviors (all enabled for debugging)
    allow_silent_mode=True,
    escalate_to_human=True,
    show_reasoning_by_default=True,
    include_diagnostics=True,  # Always for debugging
    # Language (explicit tags for testing)
    hedging_phrases=["[DEV:HEDGED]", "[DEV:UNCERTAIN]"],
    clarifying_phrases=["[DEV:CLARIFY]", "[DEV:AMBIGUOUS]"],
    acknowledging_phrases=["[DEV:ACKNOWLEDGE]", "[DEV:LOW_CONF]"],
)


# === Tier Lookup ===

_TIER_CONFIGS = {
    PresentationTier.ENTERPRISE_SEARCH: ENTERPRISE_SEARCH_CONFIG,
    PresentationTier.ENTERPRISE_CHAT: ENTERPRISE_CHAT_CONFIG,
    PresentationTier.CONSUMER: CONSUMER_CONFIG,
    PresentationTier.DEVELOPMENT: DEVELOPMENT_CONFIG,
}


def get_config_for_tier(tier: PresentationTier) -> PresentationConfig:
    """Get the pre-configured config for a tier.

    Args:
        tier: The presentation tier

    Returns:
        Corresponding PresentationConfig instance

    Raises:
        KeyError: If tier is not recognized
    """
    if tier not in _TIER_CONFIGS:
        raise KeyError(f"Unknown tier: {tier}")
    return _TIER_CONFIGS[tier]
