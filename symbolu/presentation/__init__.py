"""Presentation Layer - Signal to UX Directive Translation.

Implements: PRESENTATION_LAYER_v1.0.md

This Layer 4 module consumes all system signals and produces
simple, actionable UX directives for frontends.

Design Document Reference:
- Part 1: Architectural Position (Layer 4, External Interfaces)
- Part 2: Signal Inventory (CV + Raw + Session signals)
- Part 3: Presentation Directives (output types)
- Part 4: Rule Definitions (8 prioritized rules)
- Part 5: Tier-Specific Behavior (4 tiers)
- Part 6: Signal Bundle Structure
- Part 7: Composition Engine
"""

from symbolu.presentation.types import (
    DeliveryMode,
    ConfidenceIndicator,
    SuggestedBehaviors,
    DiagnosticInfo,
    PresentationDirective,
)
from symbolu.presentation.signals import (
    VrittiDistribution,
    SessionContext,
    SignalBundle,
)
from symbolu.presentation.config import (
    PresentationConfig,
    PresentationTier,
    ENTERPRISE_SEARCH_CONFIG,
    ENTERPRISE_CHAT_CONFIG,
    CONSUMER_CONFIG,
    DEVELOPMENT_CONFIG,
    get_config_for_tier,
)
from symbolu.presentation.engine import PresentationEngine
from symbolu.presentation.session import SessionStateManager

__all__ = [
    # Types (Part 3)
    "DeliveryMode",
    "ConfidenceIndicator",
    "SuggestedBehaviors",
    "DiagnosticInfo",
    "PresentationDirective",
    # Signals (Part 6)
    "VrittiDistribution",
    "SessionContext",
    "SignalBundle",
    # Config (Part 5)
    "PresentationConfig",
    "PresentationTier",
    "ENTERPRISE_SEARCH_CONFIG",
    "ENTERPRISE_CHAT_CONFIG",
    "CONSUMER_CONFIG",
    "DEVELOPMENT_CONFIG",
    "get_config_for_tier",
    # Engine (Part 7)
    "PresentationEngine",
    "SessionStateManager",
]
