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
    V27ExperimentalSignals,
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
from symbolu.presentation.p6_lite import (
    P6LiteResolver,
    derive_regime,
    DELIVERY_MODE_TO_REGIME,
)
from symbolu.presentation.p7_lite import (
    P7LiteResolver,
    derive_discourse_act,
    DELIVERY_MODE_TO_DISCOURSE_ACT,
)

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
    "V27ExperimentalSignals",
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
    # P6-Lite Bridge
    "P6LiteResolver",
    "derive_regime",
    "DELIVERY_MODE_TO_REGIME",
    # P7-Lite Bridge
    "P7LiteResolver",
    "derive_discourse_act",
    "DELIVERY_MODE_TO_DISCOURSE_ACT",
]
