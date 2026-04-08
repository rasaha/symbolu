"""
Signal Bridge: Rich STL Signals → Presentation Layer
=====================================================

Bridges the rich phonemic signals from STL routing to presentation
directives, enabling fluent, resonance-based response generation.

Flow:
    User Query
        ↓
    analyze_routing() → RichRoutingReport
        ↓
    signal_bridge() → PresentationDirective
        ↓
    Response Renderer

Tier: Core/Substrate (Tier 1)
Determinism: FULL
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple

from symbolu_core.hybrid.rich_routing import (
    analyze_routing,
    RichRoutingReport,
    PhaseProfile,
    SemanticField,
    QueryMode,
)
from symbolu_core.presentation.types import (
    DeliveryMode,
    ConfidenceIndicator,
    SuggestedBehaviors,
    DiagnosticInfo,
    PresentationDirective,
)


# =============================================================================
# Phase → Delivery Mode Mapping
# =============================================================================

PHASE_TO_DELIVERY: dict[str, DeliveryMode] = {
    "GENESIS": DeliveryMode.ACKNOWLEDGING,    # Still forming → tentative
    "OPERATION": DeliveryMode.CONFIDENT,      # Active engagement → direct
    "RETURN": DeliveryMode.HEDGED,            # Synthesizing → nuanced
}

PHASE_EXPLANATIONS: dict[str, str] = {
    "GENESIS": "Query is in emergence phase - respond with openness to possibilities",
    "OPERATION": "Query is actively engaged - respond with direct clarity",
    "RETURN": "Query seeks synthesis - respond with integrative nuance",
}


# =============================================================================
# Coherence → Confidence Mapping
# =============================================================================

def coherence_to_confidence(coherence: float) -> ConfidenceIndicator:
    """Map semantic field coherence to confidence indicator."""
    if coherence > 0.8:
        return ConfidenceIndicator.HIGH
    elif coherence > 0.5:
        return ConfidenceIndicator.MEDIUM
    elif coherence > 0.2:
        return ConfidenceIndicator.LOW
    else:
        return ConfidenceIndicator.UNKNOWN


# =============================================================================
# Query Mode → Behaviors Mapping
# =============================================================================

def mode_to_behaviors(mode: QueryMode, coherence: float) -> SuggestedBehaviors:
    """Map query mode to suggested behaviors."""
    return SuggestedBehaviors(
        show_alternatives=(mode == QueryMode.TRANSITIONAL),
        request_repeat=(coherence < 0.3),
        offer_clarification=(mode == QueryMode.DIFFUSE),
        show_reasoning=(mode == QueryMode.CLUSTERED),
        delay_response=(mode == QueryMode.TRANSITIONAL and coherence < 0.5),
        escalate_to_human=False,
    )


# =============================================================================
# Diagnostic Generation
# =============================================================================

def build_diagnostic(report: RichRoutingReport) -> DiagnosticInfo:
    """Build diagnostic info from rich routing report."""
    # Format word contributions
    word_summary = ", ".join(
        f"{wc.word}→{wc.dominant_layer.split('_')[1]}"
        for wc in report.word_contributions[:4]
    )

    # Build signal summary
    signal_parts = [
        f"Phase: {report.phase_profile.dominant_phase}",
        f"Coherence: {report.semantic_field.coherence_score:.2f}",
        f"Mode: {report.query_mode.value}",
        f"Words: [{word_summary}]",
    ]

    return DiagnosticInfo(
        dominant_vritti=report.dominant_layer,
        primary_fracture=None,  # No fracture in coherent queries
        active_penalties=[],
        signal_summary=" | ".join(signal_parts),
    )


# =============================================================================
# Main Bridge Function
# =============================================================================

@dataclass
class BridgeResult:
    """Result of signal bridge transformation."""
    directive: PresentationDirective
    routing_report: RichRoutingReport
    phase_explanation: str
    resonance_narrative: str


def bridge_signals_to_presentation(
    query: str,
    include_diagnostic: bool = True,
) -> BridgeResult:
    """
    Bridge rich STL signals to presentation directive.

    This is the main integration point between phonemic analysis
    and presentation layer fluency.

    Args:
        query: User input query
        include_diagnostic: Whether to include diagnostic info

    Returns:
        BridgeResult with directive and supporting context
    """
    # 1. Analyze query with rich signals
    report = analyze_routing(query)

    # 2. Map phase → delivery mode
    phase = report.phase_profile.dominant_phase
    delivery_mode = PHASE_TO_DELIVERY.get(phase, DeliveryMode.CONFIDENT)

    # 3. Map coherence → confidence
    coherence = report.semantic_field.coherence_score
    confidence = coherence_to_confidence(coherence)

    # 4. Map mode → behaviors
    behaviors = mode_to_behaviors(report.query_mode, coherence)

    # 5. Build diagnostic if requested
    diagnostic = build_diagnostic(report) if include_diagnostic else None

    # 6. Build explanation
    phase_explanation = PHASE_EXPLANATIONS.get(phase, "")

    # 7. Build resonance narrative
    resonance_parts = []

    # Describe the semantic field
    if coherence > 0.8:
        resonance_parts.append("Words resonate strongly together")
    elif coherence > 0.5:
        resonance_parts.append("Moderate resonance between words")
    else:
        resonance_parts.append("Scattered resonance - multiple intents possible")

    # Describe the phase energy
    pp = report.phase_profile
    if pp.phase_clarity > 0.4:
        resonance_parts.append(f"Clear {phase.lower()} energy")
    else:
        resonance_parts.append("Energy spans multiple phases")

    # Describe dominant word energies
    if report.word_contributions:
        top_words = report.word_contributions[:2]
        word_desc = " and ".join(
            f'"{w.word}" ({w.dominant_layer.split("_")[1].lower()})'
            for w in top_words
        )
        resonance_parts.append(f"Led by {word_desc}")

    resonance_narrative = ". ".join(resonance_parts) + "."

    # 8. Compose directive
    directive = PresentationDirective(
        delivery_mode=delivery_mode,
        confidence=confidence,
        behaviors=behaviors,
        diagnostic=diagnostic,
        explanation=resonance_narrative,
        triggered_rule=f"phase:{phase}|mode:{report.query_mode.value}",
    )

    return BridgeResult(
        directive=directive,
        routing_report=report,
        phase_explanation=phase_explanation,
        resonance_narrative=resonance_narrative,
    )


# =============================================================================
# Fluency Guidance
# =============================================================================

@dataclass
class FluencyGuidance:
    """Guidance for response generation fluency."""
    tone: str                    # How to sound
    pacing: str                  # How fast/slow
    structure: str               # How to organize
    word_preference: str         # What kinds of words to prefer
    phase_alignment: str         # How to match user's phase


def derive_fluency_guidance(report: RichRoutingReport) -> FluencyGuidance:
    """
    Derive fluency guidance from rich signals.

    This tells the response generator HOW to be fluent
    in a way that resonates with the user's query.
    """
    phase = report.phase_profile.dominant_phase
    mode = report.query_mode
    coherence = report.semantic_field.coherence_score

    # Tone based on phase
    if phase == "GENESIS":
        tone = "exploratory, open, possibility-oriented"
    elif phase == "OPERATION":
        tone = "direct, engaged, action-oriented"
    else:  # RETURN
        tone = "reflective, synthesizing, integrative"

    # Pacing based on coherence
    if coherence > 0.8:
        pacing = "confident, steady rhythm"
    elif coherence > 0.5:
        pacing = "measured, with pauses for clarity"
    else:
        pacing = "slower, checking understanding"

    # Structure based on mode
    if mode == QueryMode.FOCUSED:
        structure = "single clear point, then support"
    elif mode == QueryMode.CLUSTERED:
        structure = "acknowledge the cluster, then address"
    elif mode == QueryMode.TRANSITIONAL:
        structure = "bridge between perspectives"
    else:  # DIFFUSE
        structure = "clarify intent, then respond"

    # Word preference based on dominant layer
    layer = report.dominant_layer
    if "EXECUTION" in layer or "ACTION" in layer:
        word_preference = "verbs, action words, concrete steps"
    elif "COGNITION" in layer or "REASONING" in layer:
        word_preference = "analytical terms, logical connectors"
    elif "UNIFYING" in layer or "INTEGRATION" in layer:
        word_preference = "connecting words, synthesis terms"
    elif "PURPOSE" in layer:
        word_preference = "meaning words, why-oriented language"
    else:
        word_preference = "balanced vocabulary"

    # Phase alignment instruction
    phase_alignment = (
        f"Match the user's {phase.lower()} energy. "
        f"They are in {PHASE_EXPLANATIONS.get(phase, 'active engagement')}."
    )

    return FluencyGuidance(
        tone=tone,
        pacing=pacing,
        structure=structure,
        word_preference=word_preference,
        phase_alignment=phase_alignment,
    )


# =============================================================================
# Response Resonance Check
# =============================================================================

def check_response_resonance(
    query: str,
    response: str,
) -> Tuple[float, str]:
    """
    Check if a response resonates with the query.

    Returns resonance score and explanation.
    """
    query_report = analyze_routing(query)
    response_report = analyze_routing(response)

    # Compare phases
    query_phase = query_report.phase_profile.dominant_phase
    response_phase = response_report.phase_profile.dominant_phase
    phase_match = query_phase == response_phase

    # Compare coherence levels
    query_coherence = query_report.semantic_field.coherence_score
    response_coherence = response_report.semantic_field.coherence_score
    coherence_compatible = abs(query_coherence - response_coherence) < 0.3

    # Compare dominant clusters
    query_cluster = query_report.semantic_field.dominant_cluster
    response_cluster = response_report.semantic_field.dominant_cluster
    cluster_match = query_cluster == response_cluster

    # Calculate resonance score
    score = 0.0
    if phase_match:
        score += 0.4
    elif _adjacent_phases(query_phase, response_phase):
        score += 0.2

    if coherence_compatible:
        score += 0.3

    if cluster_match:
        score += 0.3

    # Build explanation
    parts = []
    if phase_match:
        parts.append(f"phases align ({query_phase})")
    elif _adjacent_phases(query_phase, response_phase):
        parts.append(f"phases adjacent ({query_phase}→{response_phase})")
    else:
        parts.append(f"phase mismatch ({query_phase} vs {response_phase})")

    if coherence_compatible:
        parts.append("coherence levels compatible")
    else:
        parts.append("coherence mismatch")

    if cluster_match:
        parts.append(f"semantic cluster aligned ({query_cluster})")

    explanation = "; ".join(parts)

    return score, explanation


def _adjacent_phases(a: str, b: str) -> bool:
    """Check if two phases are adjacent in the arc."""
    order = ["GENESIS", "OPERATION", "RETURN"]
    try:
        return abs(order.index(a) - order.index(b)) == 1
    except ValueError:
        return False


# =============================================================================
# Formatting
# =============================================================================

def format_bridge_result(result: BridgeResult) -> str:
    """Format bridge result for display."""
    lines = []

    d = result.directive

    lines.append("=" * 60)
    lines.append("SIGNAL BRIDGE RESULT")
    lines.append("=" * 60)
    lines.append("")

    lines.append("PRESENTATION DIRECTIVE:")
    lines.append("-" * 40)
    lines.append(f"  Delivery Mode:  {d.delivery_mode.value.upper()}")
    lines.append(f"  Confidence:     {d.confidence.value.upper()}")
    lines.append("")

    lines.append("BEHAVIORS:")
    lines.append("-" * 40)
    b = d.behaviors
    if b.show_alternatives:
        lines.append("  ✓ show_alternatives")
    if b.offer_clarification:
        lines.append("  ✓ offer_clarification")
    if b.show_reasoning:
        lines.append("  ✓ show_reasoning")
    if b.delay_response:
        lines.append("  ✓ delay_response")
    if not any([b.show_alternatives, b.offer_clarification,
                b.show_reasoning, b.delay_response]):
        lines.append("  (default behaviors)")
    lines.append("")

    lines.append("PHASE GUIDANCE:")
    lines.append("-" * 40)
    lines.append(f"  {result.phase_explanation}")
    lines.append("")

    lines.append("RESONANCE NARRATIVE:")
    lines.append("-" * 40)
    lines.append(f"  {result.resonance_narrative}")
    lines.append("")

    if d.diagnostic:
        lines.append("DIAGNOSTIC:")
        lines.append("-" * 40)
        lines.append(f"  {d.diagnostic.signal_summary}")

    lines.append("=" * 60)

    return "\n".join(lines)


def format_fluency_guidance(guidance: FluencyGuidance) -> str:
    """Format fluency guidance for display."""
    lines = []

    lines.append("FLUENCY GUIDANCE:")
    lines.append("-" * 40)
    lines.append(f"  Tone:       {guidance.tone}")
    lines.append(f"  Pacing:     {guidance.pacing}")
    lines.append(f"  Structure:  {guidance.structure}")
    lines.append(f"  Words:      {guidance.word_preference}")
    lines.append("")
    lines.append(f"  {guidance.phase_alignment}")

    return "\n".join(lines)


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Main bridge
    "bridge_signals_to_presentation",
    "BridgeResult",
    # Fluency
    "derive_fluency_guidance",
    "FluencyGuidance",
    # Resonance check
    "check_response_resonance",
    # Formatting
    "format_bridge_result",
    "format_fluency_guidance",
    # Mappings
    "PHASE_TO_DELIVERY",
    "PHASE_EXPLANATIONS",
]
