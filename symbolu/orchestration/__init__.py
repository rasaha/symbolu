"""
Symbolu Orchestration Layer

Provides dynamic pipeline routing between:
- Pipeline A: Deterministic constraint satisfaction (current Phase-7)
- Pipeline B: Extended generation with semantic projection

Architecture:
- Inference: Keyword-based parsing (NO LLM)
- Constraint generation: Mechanical mapping (NO LLM)
- Sequence generation: Phase-7 deterministic (NO LLM)
- Output rendering: LLM optional (for presentation only)
"""

from .pipeline_router import (
    PipelineType,
    RequestIntent,
    RoutingDecision,
    UnifiedRequest,
    UnifiedResponse,
    PipelineRouter,
    generate,
)

from .semantic_layer import (
    SemanticDimension,
    SemanticVector,
    ParsedIntent,
    IntentParser,
    ResponseProjector,
    parse_intent,
    intent_to_constraints,
)

from .conversation import (
    MessageRole,
    Message,
    ConversationState,
    ConversationSession,
    ConversationManager,
    get_conversation_manager,
    chat,
)

from .llm_renderer import (
    LLMProvider,
    RenderContext,
    RenderedOutput,
    OutputRenderer,
    render_output,
)

__all__ = [
    # Pipeline routing
    "PipelineType",
    "RequestIntent",
    "RoutingDecision",
    "UnifiedRequest",
    "UnifiedResponse",
    "PipelineRouter",
    "generate",

    # Semantic layer
    "SemanticDimension",
    "SemanticVector",
    "ParsedIntent",
    "IntentParser",
    "ResponseProjector",
    "parse_intent",
    "intent_to_constraints",

    # Conversation
    "MessageRole",
    "Message",
    "ConversationState",
    "ConversationSession",
    "ConversationManager",
    "get_conversation_manager",
    "chat",

    # Rendering
    "LLMProvider",
    "RenderContext",
    "RenderedOutput",
    "OutputRenderer",
    "render_output",
]
