"""
Unified Presentation Pipeline
==============================

The main orchestrator that connects all Symbol-U modules into a
coherent response generation pipeline.

Flow:
    User Query
        ↓
    ┌─────────────────────────────────────────────────┐
    │  1. RAG Retrieval (optional)                    │
    │     - index_corpus, run_rag                     │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │  2. Reasoning Synthesis (optional)              │
    │     - ReasoningSynthesizer                      │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │  3. STL Rich Routing                            │
    │     - analyze_routing → RichRoutingReport       │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │  4. Signal Bridge                               │
    │     - bridge_signals_to_presentation            │
    │     - derive_fluency_guidance                   │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │  5. Response Renderer                           │
    │     - render_response → natural text            │
    └─────────────────────────────────────────────────┘
        ↓
    Natural Language Response

Tier: Presentation Layer (Layer 4)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

# STL / Hybrid imports
from symbolu.hybrid.rich_routing import (
    analyze_routing,
    RichRoutingReport,
)

# Presentation imports
from symbolu.presentation.types import (
    DeliveryMode,
    ConfidenceIndicator,
    PresentationDirective,
)
from symbolu.presentation.signal_bridge import (
    bridge_signals_to_presentation,
    derive_fluency_guidance,
    check_response_resonance,
    BridgeResult,
    FluencyGuidance,
)
from symbolu.presentation.response_renderer import (
    ResponseRenderer,
    RenderedResponse,
    render_from_bridge,
)


# =============================================================================
# Pipeline Configuration
# =============================================================================

class PipelineStage(Enum):
    """Stages in the pipeline."""
    RAG_RETRIEVAL = "rag_retrieval"
    SYNTHESIS = "synthesis"
    STL_ROUTING = "stl_routing"
    SIGNAL_BRIDGE = "signal_bridge"
    RESPONSE_RENDER = "response_render"
    RESONANCE_CHECK = "resonance_check"


@dataclass
class PipelineConfig:
    """Configuration for the presentation pipeline."""
    # Which stages to run
    use_rag: bool = True
    use_synthesis: bool = True
    check_resonance: bool = True

    # RAG settings
    rag_corpus: Optional[str] = None
    rag_top_k: int = 5

    # Rendering settings
    verbose: bool = False
    include_diagnostics: bool = True

    # Resonance threshold
    min_resonance_score: float = 0.5


# =============================================================================
# Pipeline Result
# =============================================================================

@dataclass
class PipelineResult:
    """Complete result from the presentation pipeline."""
    # Final output
    response_text: str
    rendered_response: RenderedResponse

    # Intermediate results
    routing_report: RichRoutingReport
    bridge_result: BridgeResult
    fluency_guidance: FluencyGuidance

    # Optional results
    rag_candidates: Optional[List[Dict[str, Any]]] = None
    synthesis_result: Optional[Dict[str, Any]] = None

    # Quality metrics
    resonance_score: Optional[float] = None
    resonance_explanation: Optional[str] = None

    # Metadata
    stages_run: List[PipelineStage] = field(default_factory=list)
    query: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "response_text": self.response_text,
            "query": self.query,
            "delivery_mode": self.rendered_response.delivery_mode.value,
            "confidence": self.rendered_response.confidence.value,
            "word_count": self.rendered_response.word_count,
            "resonance_score": self.resonance_score,
            "resonance_explanation": self.resonance_explanation,
            "stages_run": [s.value for s in self.stages_run],
            "phase": self.routing_report.phase_profile.dominant_phase,
            "coherence": self.routing_report.semantic_field.coherence_score,
            "query_mode": self.routing_report.query_mode.value,
        }


# =============================================================================
# Main Pipeline Class
# =============================================================================

class PresentationPipeline:
    """
    Unified pipeline for generating fluent responses.

    This orchestrator connects all Symbol-U modules to transform
    a user query into a coherent, contextually-appropriate response.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """Initialize pipeline with configuration."""
        self._config = config or PipelineConfig()
        self._renderer = ResponseRenderer(verbose=self._config.verbose)

    @property
    def config(self) -> PipelineConfig:
        """Current configuration."""
        return self._config

    def process(self, query: str) -> PipelineResult:
        """
        Process a query through the full pipeline.

        Args:
            query: User's input query

        Returns:
            PipelineResult with response and all intermediate data
        """
        stages_run = []

        # Stage 1: RAG Retrieval (optional)
        rag_candidates = None
        if self._config.use_rag and self._config.rag_corpus:
            rag_candidates = self._run_rag(query)
            stages_run.append(PipelineStage.RAG_RETRIEVAL)

        # Stage 2: Synthesis (optional)
        synthesis_result = None
        if self._config.use_synthesis and rag_candidates:
            synthesis_result = self._run_synthesis(query, rag_candidates)
            stages_run.append(PipelineStage.SYNTHESIS)

        # Stage 3: STL Rich Routing
        routing_report = analyze_routing(query)
        stages_run.append(PipelineStage.STL_ROUTING)

        # Stage 4: Signal Bridge
        bridge_result = bridge_signals_to_presentation(
            query,
            include_diagnostic=self._config.include_diagnostics,
        )
        fluency = derive_fluency_guidance(routing_report)
        stages_run.append(PipelineStage.SIGNAL_BRIDGE)

        # Stage 5: Response Rendering
        rendered = self._renderer.render(
            directive=bridge_result.directive,
            fluency=fluency,
            synthesis=synthesis_result,
            raw_query=query,
        )
        stages_run.append(PipelineStage.RESPONSE_RENDER)

        # Stage 6: Resonance Check (optional)
        resonance_score = None
        resonance_explanation = None
        if self._config.check_resonance:
            resonance_score, resonance_explanation = check_response_resonance(
                query,
                rendered.text,
            )
            stages_run.append(PipelineStage.RESONANCE_CHECK)

        return PipelineResult(
            response_text=rendered.text,
            rendered_response=rendered,
            routing_report=routing_report,
            bridge_result=bridge_result,
            fluency_guidance=fluency,
            rag_candidates=rag_candidates,
            synthesis_result=synthesis_result,
            resonance_score=resonance_score,
            resonance_explanation=resonance_explanation,
            stages_run=stages_run,
            query=query,
        )

    def _run_rag(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Run RAG retrieval if available."""
        try:
            from symbolu.rag import run_rag
            candidates = run_rag(
                query,
                self._config.rag_corpus,
                top_k=self._config.rag_top_k,
            )
            # Convert to dict format
            return [
                {
                    "content": c.content if hasattr(c, "content") else str(c),
                    "score": c.score if hasattr(c, "score") else 0.5,
                }
                for c in candidates
            ]
        except Exception:
            return None

    def _run_synthesis(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Run synthesis if experientials are available."""
        try:
            # For now, create a simple synthesis from candidates
            # In full implementation, this would use ReasoningSynthesizer
            if not candidates:
                return None

            # Extract insights from top candidates
            insights = []
            for c in candidates[:3]:
                content = c.get("content", "")
                if content:
                    insights.append({
                        "text": content[:200],
                        "domains": ["retrieved"],
                        "confidence": c.get("score", 0.5),
                    })

            return {
                "primary_insight": insights[0]["text"] if insights else "",
                "supporting_insights": insights[1:],
                "cross_domain_connections": [],
                "recommended_actions": [],
                "warnings": [],
            }
        except Exception:
            return None

    def quick_response(self, query: str) -> str:
        """
        Quick response without optional stages.

        Runs only STL routing, signal bridge, and rendering.
        Faster for interactive use cases.

        Args:
            query: User's input query

        Returns:
            Response text string
        """
        # Minimal pipeline: routing → bridge → render
        bridge_result = bridge_signals_to_presentation(query)
        fluency = derive_fluency_guidance(bridge_result.routing_report)

        rendered = self._renderer.render(
            directive=bridge_result.directive,
            fluency=fluency,
        )

        return rendered.text


# =============================================================================
# Convenience Functions
# =============================================================================

def respond(query: str, config: Optional[PipelineConfig] = None) -> str:
    """
    Main entry point for generating a response.

    Args:
        query: User's input query
        config: Optional pipeline configuration

    Returns:
        Generated response text
    """
    pipeline = PresentationPipeline(config)
    result = pipeline.process(query)
    return result.response_text


def quick_respond(query: str) -> str:
    """
    Quick response with minimal processing.

    Uses only STL routing and signal bridge for fast response.

    Args:
        query: User's input query

    Returns:
        Generated response text
    """
    pipeline = PresentationPipeline()
    return pipeline.quick_response(query)


def process_with_details(query: str) -> PipelineResult:
    """
    Process query and return full pipeline result.

    Args:
        query: User's input query

    Returns:
        PipelineResult with all intermediate data
    """
    pipeline = PresentationPipeline()
    return pipeline.process(query)


def format_pipeline_result(result: PipelineResult, verbose: bool = False) -> str:
    """Format pipeline result for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("PRESENTATION PIPELINE RESULT")
    lines.append("=" * 70)
    lines.append("")

    lines.append("QUERY:")
    lines.append(f"  {result.query}")
    lines.append("")

    lines.append("RESPONSE:")
    lines.append("-" * 50)
    lines.append(result.response_text)
    lines.append("-" * 50)
    lines.append("")

    lines.append("DELIVERY:")
    lines.append(f"  Mode: {result.rendered_response.delivery_mode.value.upper()}")
    lines.append(f"  Confidence: {result.rendered_response.confidence.value.upper()}")
    lines.append(f"  Words: {result.rendered_response.word_count}")
    lines.append("")

    if result.resonance_score is not None:
        lines.append("RESONANCE:")
        lines.append(f"  Score: {result.resonance_score:.2f}")
        lines.append(f"  {result.resonance_explanation}")
        lines.append("")

    if verbose:
        lines.append("ROUTING ANALYSIS:")
        rr = result.routing_report
        lines.append(f"  Phase: {rr.phase_profile.dominant_phase}")
        lines.append(f"  Coherence: {rr.semantic_field.coherence_score:.2f}")
        lines.append(f"  Query Mode: {rr.query_mode.value}")
        lines.append("")

        lines.append("FLUENCY GUIDANCE:")
        fg = result.fluency_guidance
        lines.append(f"  Tone: {fg.tone}")
        lines.append(f"  Pacing: {fg.pacing}")
        lines.append(f"  Structure: {fg.structure}")
        lines.append("")

        lines.append("STAGES RUN:")
        for stage in result.stages_run:
            lines.append(f"  - {stage.value}")

    lines.append("=" * 70)

    return "\n".join(lines)


def demo_pipeline(queries: Optional[List[str]] = None) -> None:
    """
    Demo the presentation pipeline with example queries.

    Args:
        queries: Optional list of queries to demo
    """
    if queries is None:
        queries = [
            "How do atoms bond together?",
            "What makes a good leader?",
            "Explain the meaning of life",
            "Help me debug my code",
        ]

    pipeline = PresentationPipeline()

    for query in queries:
        result = pipeline.process(query)
        print(format_pipeline_result(result, verbose=True))
        print("\n")


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Core classes
    "PresentationPipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStage",
    # Main entry points
    "respond",
    "quick_respond",
    "process_with_details",
    # Formatting
    "format_pipeline_result",
    "demo_pipeline",
]
