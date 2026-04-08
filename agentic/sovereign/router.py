"""
Sovereign-1 Router: Dynamic Nexus Selection
============================================

The SovereignRouter implements the "Transmission" of Sovereign-1.
It extends the SemanticRouter to return both:
1. ModelType - for semantic routing (existing behavior)
2. Nexus Position - for Virtual Nexus (4/8, 6/6, or 8/4 mode)

The Nexus Position determines where the PID Governor is inserted:
- Logic-Heavy (O7, O10): Nexus at Layer 4 → 4 Quadratic + 8 Phase
- Creative (O6, O9): Nexus at Layer 6 → 6 Quadratic + 6 Phase (default)
- Memory-Heavy (O4, O5): Nexus at Layer 8 → 8 Quadratic + 4 Phase

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 8
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Dict
from enum import Enum

# Import existing SemanticRouter
try:
    from symbolu_core.hybrid.router import (
        SemanticRouter,
        RoutingDecision,
        ModelType,
        LAYER_TO_MODEL,
        LAYER_NAMES,
    )
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False
    SemanticRouter = object
    RoutingDecision = None
    ModelType = None
    LAYER_TO_MODEL = {}
    LAYER_NAMES = [
        "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION", "O4_STRUCTURE",
        "O5_COGNITION", "O6_AGENCY", "O7_REASONING", "O8_PURPOSE",
        "O9_WITNESSES", "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING"
    ]


class NexusMode(Enum):
    """Virtual Nexus modes for layer topology configuration."""
    MODE_4_8 = 4   # 4 Quadratic + 8 Phase (Logic-Heavy)
    MODE_6_6 = 6   # 6 Quadratic + 6 Phase (Default/Creative)
    MODE_8_4 = 8   # 8 Quadratic + 4 Phase (Memory-Heavy)


@dataclass(frozen=True)
class SovereignRoutingDecision:
    """
    Extended routing decision with Nexus position.

    Attributes:
        model_type: Semantic model type for content generation
        nexus_position: Virtual Nexus position (4, 6, or 8)
        nexus_mode: Human-readable mode description
        confidence: Routing confidence (0.0 to 1.0)
        dominant_layer: The dominant ontological layer
        routing_decision: Original SemanticRouter decision (if available)
    """
    model_type: Optional["ModelType"]
    nexus_position: int
    nexus_mode: str
    confidence: float
    dominant_layer: str
    dominant_ontology: str  # e.g., "O7_REASONING"
    routing_decision: Optional["RoutingDecision"] = None


# Ontology Layer → Nexus Position Mapping
# From SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 8.4
ONTOLOGY_TO_NEXUS: Dict[str, int] = {
    # Logic-Heavy: More phase attention (earlier nexus)
    # These layers require extensive semantic reasoning
    "O7_REASONING": 4,     # Logic, analysis, deduction
    "O10_UNIFYING": 4,     # Synthesis, connection, relationship

    # Balanced: Default creative mode
    # These layers balance context gathering with generation
    "O6_AGENCY": 6,        # Direction, control, guidance
    "O9_WITNESSES": 6,     # Meta-observation, reflection

    # Memory-Heavy: More quadratic attention (later nexus)
    # These layers need deep context retrieval
    "O4_STRUCTURE": 8,     # Form, shape, organization
    "O5_COGNITION": 8,     # Perception, understanding

    # Default positions for other layers
    "O1_POTENTIAL": 6,     # Dormant → default
    "O2_IDENTITY": 6,      # Classification → default
    "O3_EXECUTION": 6,     # Action → default
    "O8_PURPOSE": 6,       # Intent → default
    "O11_INTEGRATION": 6,  # Consolidation → default
    "O12_ABSOLVING": 6,    # Dissolution → default
}


# Mode descriptions for logging
NEXUS_MODE_DESCRIPTIONS: Dict[int, str] = {
    4: "4/8 (Logic-Heavy)",
    6: "6/6 (Balanced)",
    8: "8/4 (Memory-Heavy)",
}


class SovereignRouter(SemanticRouter if ROUTER_AVAILABLE else object):
    """
    Sovereign-1 Router with Virtual Nexus selection.

    Extends SemanticRouter to provide:
    1. Semantic routing (ModelType) - from parent class
    2. Nexus position selection (4, 6, or 8) - new functionality

    The Nexus position determines where the PID Governor intercepts
    the forward pass, enabling dynamic architecture reconfiguration.

    Usage:
        router = SovereignRouter()
        decision = router.route_sovereign("Explain quantum entanglement")
        # decision.nexus_position = 4 (logic-heavy)

        # Pass to transformer
        outputs = transformer(
            tokens,
            nexus_position=decision.nexus_position
        )
    """

    def __init__(
        self,
        default_nexus: int = 6,
        **kwargs
    ):
        """
        Initialize SovereignRouter.

        Args:
            default_nexus: Default nexus position when layer is ambiguous
            **kwargs: Passed to parent SemanticRouter
        """
        if ROUTER_AVAILABLE:
            super().__init__(**kwargs)
        self.default_nexus = default_nexus

    def select_nexus(self, dominant_layer: str) -> int:
        """
        Select nexus position based on dominant ontological layer.

        Args:
            dominant_layer: e.g., "O7_REASONING", "O4_STRUCTURE"

        Returns:
            Nexus position (4, 6, or 8)
        """
        return ONTOLOGY_TO_NEXUS.get(dominant_layer, self.default_nexus)

    def get_nexus_mode_description(self, nexus: int) -> str:
        """Get human-readable description of nexus mode."""
        return NEXUS_MODE_DESCRIPTIONS.get(nexus, f"Custom ({nexus})")

    def route_sovereign(self, query: str) -> SovereignRoutingDecision:
        """
        Route query with Nexus position selection.

        Performs full semantic routing and determines the optimal
        layer topology for the given query.

        Args:
            query: Input query/prompt string

        Returns:
            SovereignRoutingDecision with model_type and nexus_position
        """
        if ROUTER_AVAILABLE:
            # Use parent SemanticRouter for full analysis
            base_decision = self.route(query)

            dominant_layer = base_decision.dominant_layer
            nexus_position = self.select_nexus(dominant_layer)

            return SovereignRoutingDecision(
                model_type=base_decision.model_type,
                nexus_position=nexus_position,
                nexus_mode=self.get_nexus_mode_description(nexus_position),
                confidence=base_decision.confidence,
                dominant_layer=dominant_layer,
                dominant_ontology=dominant_layer,
                routing_decision=base_decision,
            )
        else:
            # Fallback: Simple keyword-based routing
            return self._route_fallback(query)

    def _route_fallback(self, query: str) -> SovereignRoutingDecision:
        """
        Fallback routing when SemanticRouter is unavailable.

        Uses simple keyword matching to determine nexus position.
        """
        query_lower = query.lower()

        # Logic-heavy keywords → Nexus 4
        logic_keywords = {
            "explain", "analyze", "why", "how", "prove", "derive",
            "calculate", "solve", "logic", "reason", "theorem",
            "therefore", "because", "deduce", "infer", "conclude",
            "math", "equation", "formula", "algorithm",
        }

        # Memory-heavy keywords → Nexus 8
        memory_keywords = {
            "remember", "recall", "history", "when", "where",
            "story", "narrative", "describe", "structure",
            "organize", "list", "sequence", "timeline",
            "archive", "database", "record", "document",
        }

        # Check keyword presence
        words = set(query_lower.split())

        logic_score = len(words & logic_keywords)
        memory_score = len(words & memory_keywords)

        if logic_score > memory_score and logic_score > 0:
            nexus_position = 4
            dominant_layer = "O7_REASONING"
        elif memory_score > logic_score and memory_score > 0:
            nexus_position = 8
            dominant_layer = "O4_STRUCTURE"
        else:
            nexus_position = 6
            dominant_layer = "O6_AGENCY"

        return SovereignRoutingDecision(
            model_type=None,  # No ModelType without full router
            nexus_position=nexus_position,
            nexus_mode=self.get_nexus_mode_description(nexus_position),
            confidence=0.5,  # Medium confidence for fallback
            dominant_layer=dominant_layer,
            dominant_ontology=dominant_layer,
            routing_decision=None,
        )

    def route_batch_sovereign(
        self,
        queries: Tuple[str, ...],
    ) -> Tuple[SovereignRoutingDecision, ...]:
        """Route multiple queries with Nexus selection."""
        return tuple(self.route_sovereign(q) for q in queries)


def create_sovereign_router(**kwargs) -> SovereignRouter:
    """Factory function to create a SovereignRouter instance."""
    return SovereignRouter(**kwargs)


# Quick classification functions for common use cases
def is_logic_heavy(query: str) -> bool:
    """Check if query should use logic-heavy mode (Nexus 4)."""
    router = SovereignRouter()
    decision = router.route_sovereign(query)
    return decision.nexus_position == 4


def is_memory_heavy(query: str) -> bool:
    """Check if query should use memory-heavy mode (Nexus 8)."""
    router = SovereignRouter()
    decision = router.route_sovereign(query)
    return decision.nexus_position == 8


def get_optimal_nexus(query: str) -> int:
    """Get the optimal nexus position for a query."""
    router = SovereignRouter()
    decision = router.route_sovereign(query)
    return decision.nexus_position
