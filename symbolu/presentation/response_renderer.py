"""
Response Renderer: Directive + Synthesis → Natural Text
========================================================

Transforms presentation directives and synthesis results into
fluent, natural language responses that match the user's query energy.

This is the "last mile" of the presentation layer - where all signals
converge into actual text output.

Flow:
    SynthesisResult + PresentationDirective + FluencyGuidance
        ↓
    ResponseRenderer
        ↓
    Natural Language Response

Tier: Presentation Layer (Layer 4)
Determinism: Template-based with dynamic composition
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from symbolu.presentation.types import (
    DeliveryMode,
    ConfidenceIndicator,
    SuggestedBehaviors,
    PresentationDirective,
)
from symbolu.presentation.signal_bridge import (
    FluencyGuidance,
    BridgeResult,
)


# =============================================================================
# Response Structure Templates
# =============================================================================

class ResponseSection(Enum):
    """Sections that can appear in a response."""
    ACKNOWLEDGMENT = "acknowledgment"
    MAIN_INSIGHT = "main_insight"
    SUPPORTING_EVIDENCE = "supporting_evidence"
    CROSS_DOMAIN = "cross_domain"
    ACTIONS = "actions"
    CLARIFICATION = "clarification"
    HEDGE = "hedge"
    CLOSING = "closing"


# Acknowledgment templates by delivery mode
ACKNOWLEDGMENT_TEMPLATES: Dict[DeliveryMode, List[str]] = {
    DeliveryMode.CONFIDENT: [
        "Here's what I found:",
        "Based on the analysis:",
        "The evidence shows:",
    ],
    DeliveryMode.HEDGED: [
        "From what I can tell,",
        "The patterns suggest,",
        "It appears that",
    ],
    DeliveryMode.ACKNOWLEDGING: [
        "I see what you're asking about.",
        "Let me share what emerges from this.",
        "Exploring this further,",
    ],
    DeliveryMode.CLARIFYING: [
        "To make sure I understand,",
        "Let me clarify what you're looking for:",
        "Before I respond fully,",
    ],
    DeliveryMode.SILENT: [],
}

# Confidence hedges
CONFIDENCE_HEDGES: Dict[ConfidenceIndicator, str] = {
    ConfidenceIndicator.HIGH: "",
    ConfidenceIndicator.MEDIUM: "With reasonable confidence, ",
    ConfidenceIndicator.LOW: "While I'm less certain here, ",
    ConfidenceIndicator.UNKNOWN: "This is speculative, but ",
}

# Transition phrases by structure type
STRUCTURE_TRANSITIONS: Dict[str, List[str]] = {
    "single clear point, then support": [
        "The key point is",
        "Most importantly,",
        "At its core,",
    ],
    "acknowledge the cluster, then address": [
        "There are several related aspects here.",
        "This touches on multiple connected ideas.",
        "Let me address the interconnected points:",
    ],
    "bridge between perspectives": [
        "Looking at this from different angles,",
        "Bridging these perspectives,",
        "Connecting these viewpoints,",
    ],
    "clarify intent, then respond": [
        "First, let me understand what you're after.",
        "There are a few directions this could go.",
        "To give you the most relevant response,",
    ],
}

# Action lead-ins by tone
ACTION_LEADINS: Dict[str, str] = {
    "exploratory, open, possibility-oriented": "You might consider:",
    "direct, engaged, action-oriented": "Here's what to do:",
    "reflective, synthesizing, integrative": "Bringing this together, you could:",
}

# Closing phrases
CLOSING_PHRASES: Dict[DeliveryMode, List[str]] = {
    DeliveryMode.CONFIDENT: [
        "",
        "Let me know if you want to explore any aspect further.",
    ],
    DeliveryMode.HEDGED: [
        "Does this align with what you were thinking?",
        "Would you like me to dig deeper into any of these points?",
    ],
    DeliveryMode.ACKNOWLEDGING: [
        "What resonates most with you here?",
        "Which direction would you like to explore?",
    ],
    DeliveryMode.CLARIFYING: [
        "Could you tell me more about what you're looking for?",
        "What aspect is most important to you?",
    ],
    DeliveryMode.SILENT: [],
}


# =============================================================================
# Rendered Response
# =============================================================================

@dataclass
class RenderedResponse:
    """A fully rendered response ready for output."""
    text: str
    sections: List[ResponseSection]
    delivery_mode: DeliveryMode
    confidence: ConfidenceIndicator
    word_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text


# =============================================================================
# Response Renderer
# =============================================================================

class ResponseRenderer:
    """
    Renders presentation directives into natural language responses.

    The renderer uses templates and composition rules to generate
    text that matches the fluency guidance while incorporating
    synthesis results.
    """

    def __init__(self, verbose: bool = False):
        self._verbose = verbose

    def render(
        self,
        directive: PresentationDirective,
        fluency: Optional[FluencyGuidance] = None,
        synthesis: Optional[Dict[str, Any]] = None,
        raw_query: Optional[str] = None,
    ) -> RenderedResponse:
        """
        Render a complete response from directive and context.

        Args:
            directive: Presentation directive with mode/confidence/behaviors
            fluency: Optional fluency guidance for tone/pacing
            synthesis: Optional synthesis result dict with insights/actions
            raw_query: Optional original query for context

        Returns:
            RenderedResponse with formatted text
        """
        sections_used = []
        parts = []

        mode = directive.delivery_mode
        confidence = directive.confidence
        behaviors = directive.behaviors

        # 1. Acknowledgment (if not silent)
        if mode != DeliveryMode.SILENT:
            ack = self._render_acknowledgment(mode, fluency)
            if ack:
                parts.append(ack)
                sections_used.append(ResponseSection.ACKNOWLEDGMENT)

        # 2. Confidence hedge
        hedge = CONFIDENCE_HEDGES.get(confidence, "")
        if hedge:
            parts.append(hedge)
            sections_used.append(ResponseSection.HEDGE)

        # 3. Main insight
        if synthesis and "primary_insight" in synthesis:
            insight = self._render_main_insight(synthesis["primary_insight"], fluency)
            parts.append(insight)
            sections_used.append(ResponseSection.MAIN_INSIGHT)

        # 4. Supporting evidence (if show_reasoning)
        if behaviors.show_reasoning and synthesis:
            supporting = synthesis.get("supporting_insights", [])
            if supporting:
                evidence = self._render_supporting(supporting, fluency)
                parts.append(evidence)
                sections_used.append(ResponseSection.SUPPORTING_EVIDENCE)

        # 5. Cross-domain connections (if available)
        if synthesis and "cross_domain_connections" in synthesis:
            connections = synthesis["cross_domain_connections"]
            if connections:
                cross = self._render_cross_domain(connections, fluency)
                parts.append(cross)
                sections_used.append(ResponseSection.CROSS_DOMAIN)

        # 6. Actions (if available)
        if synthesis and "recommended_actions" in synthesis:
            actions = synthesis["recommended_actions"]
            if actions:
                action_text = self._render_actions(actions, fluency)
                parts.append(action_text)
                sections_used.append(ResponseSection.ACTIONS)

        # 7. Clarification offer (if behavior suggests)
        if behaviors.offer_clarification:
            clarify = self._render_clarification(mode)
            parts.append(clarify)
            sections_used.append(ResponseSection.CLARIFICATION)

        # 8. Closing
        closing = self._render_closing(mode, behaviors)
        if closing:
            parts.append(closing)
            sections_used.append(ResponseSection.CLOSING)

        # Compose final text
        text = self._compose_text(parts, fluency)

        return RenderedResponse(
            text=text,
            sections=sections_used,
            delivery_mode=mode,
            confidence=confidence,
            word_count=len(text.split()),
            metadata={
                "triggered_rule": directive.triggered_rule,
                "explanation": directive.explanation,
            },
        )

    def _render_acknowledgment(
        self,
        mode: DeliveryMode,
        fluency: Optional[FluencyGuidance],
    ) -> str:
        """Render acknowledgment based on mode."""
        templates = ACKNOWLEDGMENT_TEMPLATES.get(mode, [])
        if not templates:
            return ""

        # Choose based on fluency tone if available
        if fluency and "exploratory" in fluency.tone:
            return templates[-1]  # More open
        elif fluency and "direct" in fluency.tone:
            return templates[0]  # More direct
        else:
            return templates[len(templates) // 2]  # Middle ground

    def _render_main_insight(
        self,
        insight: str,
        fluency: Optional[FluencyGuidance],
    ) -> str:
        """Render main insight with appropriate structure."""
        if not fluency:
            return insight

        # Get structure-appropriate transition
        structure = fluency.structure
        transitions = STRUCTURE_TRANSITIONS.get(structure, [""])
        transition = transitions[0] if transitions else ""

        if transition:
            return f"{transition} {insight}"
        return insight

    def _render_supporting(
        self,
        supporting: List[Dict[str, Any]],
        fluency: Optional[FluencyGuidance],
    ) -> str:
        """Render supporting evidence."""
        lines = ["\nThis is supported by:"]
        for item in supporting[:3]:  # Limit to 3
            text = item.get("text", item.get("insight_text", ""))
            domains = item.get("domains", item.get("source_domains", []))
            if text:
                domain_str = f" ({', '.join(domains)})" if domains else ""
                lines.append(f"  - {text}{domain_str}")
        return "\n".join(lines)

    def _render_cross_domain(
        self,
        connections: List[Dict[str, Any]],
        fluency: Optional[FluencyGuidance],
    ) -> str:
        """Render cross-domain connections."""
        lines = ["\nInterestingly, patterns emerge across domains:"]
        for conn in connections[:2]:  # Limit to 2
            domains = conn.get("domains", [])
            explanation = conn.get("explanation", conn.get("shared_pattern", ""))
            if domains and explanation:
                lines.append(f"  - {' and '.join(domains)}: {explanation}")
        return "\n".join(lines)

    def _render_actions(
        self,
        actions: List[Dict[str, Any]],
        fluency: Optional[FluencyGuidance],
    ) -> str:
        """Render recommended actions."""
        # Choose lead-in based on tone
        lead_in = "Consider these steps:"
        if fluency:
            lead_in = ACTION_LEADINS.get(fluency.tone, lead_in)

        lines = [f"\n{lead_in}"]
        for action in actions[:3]:  # Limit to 3
            step = action.get("step", action.get("step_number", ""))
            text = action.get("action", "")
            if text:
                lines.append(f"  {step}. {text}")
        return "\n".join(lines)

    def _render_clarification(self, mode: DeliveryMode) -> str:
        """Render clarification offer."""
        if mode == DeliveryMode.CLARIFYING:
            return "\nCould you help me understand which aspect is most important to you?"
        return "\nWould you like me to clarify any of these points?"

    def _render_closing(
        self,
        mode: DeliveryMode,
        behaviors: SuggestedBehaviors,
    ) -> str:
        """Render closing phrase."""
        if behaviors.show_alternatives:
            return "\nThere are alternative perspectives I can share if helpful."

        closings = CLOSING_PHRASES.get(mode, [])
        if closings:
            return closings[0]
        return ""

    def _compose_text(
        self,
        parts: List[str],
        fluency: Optional[FluencyGuidance],
    ) -> str:
        """Compose final text from parts with appropriate pacing."""
        # Filter empty parts
        parts = [p for p in parts if p and p.strip()]

        if not parts:
            return "I need more information to provide a helpful response."

        # Join with appropriate spacing based on pacing
        if fluency and "slower" in fluency.pacing:
            # More paragraph breaks for slower pacing
            text = "\n\n".join(parts)
        elif fluency and "confident" in fluency.pacing:
            # Tighter for confident pacing
            text = " ".join(parts)
        else:
            # Default: single newlines between major sections
            text = "\n".join(parts)

        return text.strip()


# =============================================================================
# Convenience Functions
# =============================================================================

def render_response(
    directive: PresentationDirective,
    fluency: Optional[FluencyGuidance] = None,
    synthesis: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Convenience function to render a response.

    Args:
        directive: Presentation directive
        fluency: Optional fluency guidance
        synthesis: Optional synthesis result dict

    Returns:
        Rendered response text
    """
    renderer = ResponseRenderer()
    result = renderer.render(directive, fluency, synthesis)
    return result.text


def render_from_bridge(
    bridge_result: BridgeResult,
    synthesis: Optional[Dict[str, Any]] = None,
) -> RenderedResponse:
    """
    Render response directly from bridge result.

    Args:
        bridge_result: Result from bridge_signals_to_presentation()
        synthesis: Optional synthesis result dict

    Returns:
        RenderedResponse
    """
    from symbolu.presentation.signal_bridge import derive_fluency_guidance

    # Get fluency from the routing report in the bridge result
    fluency = derive_fluency_guidance(bridge_result.routing_report)

    renderer = ResponseRenderer()
    return renderer.render(
        directive=bridge_result.directive,
        fluency=fluency,
        synthesis=synthesis,
    )


def format_rendered_response(response: RenderedResponse, verbose: bool = False) -> str:
    """Format rendered response for display."""
    lines = []

    lines.append("=" * 60)
    lines.append("RENDERED RESPONSE")
    lines.append("=" * 60)
    lines.append("")
    lines.append(response.text)
    lines.append("")

    if verbose:
        lines.append("-" * 40)
        lines.append(f"Delivery Mode: {response.delivery_mode.value}")
        lines.append(f"Confidence: {response.confidence.value}")
        lines.append(f"Word Count: {response.word_count}")
        lines.append(f"Sections: {[s.value for s in response.sections]}")

    lines.append("=" * 60)

    return "\n".join(lines)


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Core class
    "ResponseRenderer",
    "RenderedResponse",
    "ResponseSection",
    # Convenience functions
    "render_response",
    "render_from_bridge",
    "format_rendered_response",
    # Templates (for customization)
    "ACKNOWLEDGMENT_TEMPLATES",
    "CONFIDENCE_HEDGES",
    "STRUCTURE_TRANSITIONS",
    "ACTION_LEADINS",
    "CLOSING_PHRASES",
]
