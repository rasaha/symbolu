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
from symbolu.presentation.acoustic_chain import (
    AcousticGovernanceChain,
    AcousticChainResult,
    run_acoustic_chain,
    is_acoustically_consistent,
)
from symbolu.presentation.prosodic_renderer import (
    ProsodicRenderer,
    SSMLOutput,
    ProsodyLevel,
    render_ssml,
    render_minimal_ssml,
)
from symbolu.presentation.governed_gate import (
    GovernedGate,
    GateDecision,
    GateMode,
    GateAction,
    evaluate_governed,
    evaluate_open,
    should_block_output,
)
from symbolu.presentation.speech_pipeline import (
    SpeechPipeline,
    SpeechOutput,
    PipelineMode,
    generate_speech,
    generate_ssml,
    is_speech_allowed,
)
from symbolu.presentation.signal_bridge import (
    bridge_signals_to_presentation,
    derive_fluency_guidance,
    check_response_resonance,
    format_bridge_result,
    format_fluency_guidance,
    BridgeResult,
    FluencyGuidance,
    PHASE_TO_DELIVERY,
    PHASE_EXPLANATIONS,
)
from symbolu.presentation.response_renderer import (
    ResponseRenderer,
    RenderedResponse,
    ResponseSection,
    render_response,
    render_from_bridge,
    format_rendered_response,
)
from symbolu.presentation.pipeline import (
    PresentationPipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStage,
    respond,
    quick_respond,
    process_with_details,
    format_pipeline_result,
    demo_pipeline,
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
    # Acoustic Governance Chain
    "AcousticGovernanceChain",
    "AcousticChainResult",
    "run_acoustic_chain",
    "is_acoustically_consistent",
    # Prosodic Renderer
    "ProsodicRenderer",
    "SSMLOutput",
    "ProsodyLevel",
    "render_ssml",
    "render_minimal_ssml",
    # GOVERNED Mode Gate
    "GovernedGate",
    "GateDecision",
    "GateMode",
    "GateAction",
    "evaluate_governed",
    "evaluate_open",
    "should_block_output",
    # Speech Pipeline
    "SpeechPipeline",
    "SpeechOutput",
    "PipelineMode",
    "generate_speech",
    "generate_ssml",
    "is_speech_allowed",
    # Signal Bridge (Rich STL → Presentation)
    "bridge_signals_to_presentation",
    "derive_fluency_guidance",
    "check_response_resonance",
    "format_bridge_result",
    "format_fluency_guidance",
    "BridgeResult",
    "FluencyGuidance",
    "PHASE_TO_DELIVERY",
    "PHASE_EXPLANATIONS",
    # Response Renderer (Directive → Text)
    "ResponseRenderer",
    "RenderedResponse",
    "ResponseSection",
    "render_response",
    "render_from_bridge",
    "format_rendered_response",
    # Unified Pipeline (Full Query → Response)
    "PresentationPipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStage",
    "respond",
    "quick_respond",
    "process_with_details",
    "format_pipeline_result",
    "demo_pipeline",
]
