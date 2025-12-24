"""
Rich Routing Analysis
=====================

Enhanced STL routing with rich signal decomposition.

Provides detailed, interpretable routing reports including:
1. Phase concentration (genesis/operation/return arc)
2. Semantic field coherence (how words resonate together)
3. Layer narrative (what the query is really asking)
4. Word-level contribution analysis

Tier: Core/Substrate (Tier 1)
Determinism: FULL
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional
from enum import Enum

from symbolu.hybrid.router import (
    SemanticRouter,
    RoutingDecision,
    ModelType,
    LAYER_TO_MODEL,
)
from symbolu.resonance import LAYER_NAMES


# =============================================================================
# Phase Mapping (12D layers to 3 arc phases)
# =============================================================================

PHASE_MAPPING = {
    "GENESIS": (0, 4),      # O1-O4: Potential → Structure
    "OPERATION": (4, 8),    # O5-O8: Cognition → Purpose
    "RETURN": (8, 12),      # O9-O12: Witnesses → Absolving
}

PHASE_DESCRIPTIONS = {
    "GENESIS": "emergence, formation, potential manifesting",
    "OPERATION": "active engagement, cognition, purposeful action",
    "RETURN": "integration, witnessing, transcendence",
}


class QueryMode(Enum):
    """Mode of the query based on signal analysis."""
    FOCUSED = "focused"          # Strong single-layer dominance
    DIFFUSE = "diffuse"          # Energy spread across layers
    CLUSTERED = "clustered"      # Multiple related peaks
    TRANSITIONAL = "transitional"  # Between phases


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(frozen=True)
class WordContribution:
    """Contribution of a single word to the routing decision."""
    word: str
    dominant_layer: str
    dominant_score: float
    phase: str
    vector: Tuple[float, ...]


@dataclass(frozen=True)
class PhaseProfile:
    """Phase energy concentration for a query."""
    genesis_energy: float
    operation_energy: float
    return_energy: float
    dominant_phase: str
    phase_clarity: float  # How concentrated in dominant phase

    @property
    def phase_vector(self) -> Tuple[float, float, float]:
        return (self.genesis_energy, self.operation_energy, self.return_energy)


@dataclass(frozen=True)
class SemanticField:
    """Semantic field coherence analysis."""
    coherence_score: float      # How well words resonate together
    field_strength: float       # Overall semantic intensity
    resonant_pairs: Tuple[Tuple[str, str, float], ...]  # Word pairs with high resonance
    dominant_cluster: str       # Main semantic cluster


@dataclass(frozen=True)
class RichRoutingReport:
    """Complete rich routing analysis for a query."""
    query: str
    # Core routing
    model_type: ModelType
    confidence: float
    dominant_layer: str
    # Rich signals
    phase_profile: PhaseProfile
    semantic_field: SemanticField
    query_mode: QueryMode
    word_contributions: Tuple[WordContribution, ...]
    layer_distribution: Tuple[Tuple[str, float], ...]  # All 12 layers normalized
    # Narrative
    routing_narrative: str
    layer_narrative: str


# =============================================================================
# Computation Functions
# =============================================================================

def _compute_phase_profile(layer_totals: List[float]) -> PhaseProfile:
    """Compute phase energy concentration from layer totals."""
    # Normalize first
    total = sum(layer_totals) if sum(layer_totals) > 0 else 1.0
    normalized = [s / total for s in layer_totals]

    genesis = sum(normalized[0:4])
    operation = sum(normalized[4:8])
    return_phase = sum(normalized[8:12])

    phases = {"GENESIS": genesis, "OPERATION": operation, "RETURN": return_phase}
    dominant = max(phases, key=phases.get)

    # Phase clarity: how much of energy is in dominant phase
    clarity = phases[dominant] / (genesis + operation + return_phase + 1e-9)

    return PhaseProfile(
        genesis_energy=round(genesis, 3),
        operation_energy=round(operation, 3),
        return_energy=round(return_phase, 3),
        dominant_phase=dominant,
        phase_clarity=round(clarity, 3),
    )


def _compute_semantic_field(word_vectors: List[Tuple[str, Tuple[float, ...]]]) -> SemanticField:
    """Compute semantic field coherence between words."""
    if len(word_vectors) < 2:
        return SemanticField(
            coherence_score=1.0,
            field_strength=sum(sum(wv[1]) for wv in word_vectors) / max(len(word_vectors), 1),
            resonant_pairs=(),
            dominant_cluster="single-word",
        )

    # Compute pairwise cosine similarities
    resonant_pairs = []
    total_similarity = 0.0
    pair_count = 0

    for i, (word_a, vec_a) in enumerate(word_vectors):
        for j, (word_b, vec_b) in enumerate(word_vectors):
            if i >= j:
                continue

            # Cosine similarity
            dot = sum(a * b for a, b in zip(vec_a, vec_b))
            mag_a = math.sqrt(sum(a * a for a in vec_a))
            mag_b = math.sqrt(sum(b * b for b in vec_b))
            sim = dot / (mag_a * mag_b + 1e-9)

            total_similarity += sim
            pair_count += 1

            if sim > 0.7:  # High resonance threshold
                resonant_pairs.append((word_a, word_b, round(sim, 3)))

    coherence = total_similarity / pair_count if pair_count > 0 else 1.0
    field_strength = sum(sum(wv[1]) for wv in word_vectors) / len(word_vectors)

    # Determine dominant cluster based on layer peaks
    layer_peaks: Dict[str, int] = {}
    for _, vec in word_vectors:
        max_idx = max(range(len(vec)), key=lambda i: vec[i])
        layer = LAYER_NAMES[max_idx]
        layer_peaks[layer] = layer_peaks.get(layer, 0) + 1

    dominant_cluster = max(layer_peaks, key=layer_peaks.get) if layer_peaks else "mixed"

    return SemanticField(
        coherence_score=round(coherence, 3),
        field_strength=round(field_strength, 3),
        resonant_pairs=tuple(sorted(resonant_pairs, key=lambda x: -x[2])[:5]),
        dominant_cluster=dominant_cluster,
    )


def _determine_query_mode(
    phase_profile: PhaseProfile,
    layer_distribution: List[Tuple[str, float]],
    semantic_field: SemanticField,
) -> QueryMode:
    """Determine the query mode from signals."""
    # Check for focused mode (single layer dominance)
    if layer_distribution and layer_distribution[0][1] > 0.25:
        if len(layer_distribution) < 2 or layer_distribution[0][1] > layer_distribution[1][1] * 1.5:
            return QueryMode.FOCUSED

    # Check for clustered mode (related peaks)
    if semantic_field.coherence_score > 0.8 and len(semantic_field.resonant_pairs) > 1:
        return QueryMode.CLUSTERED

    # Check for transitional mode (between phases)
    phases = phase_profile.phase_vector
    if max(phases) < 0.45 and min(phases) > 0.25:
        return QueryMode.TRANSITIONAL

    return QueryMode.DIFFUSE


def _generate_layer_narrative(dominant_layer: str, layer_dist: List[Tuple[str, float]]) -> str:
    """Generate narrative about the layer distribution."""
    layer_descriptions = {
        "O1_POTENTIAL": "latent possibilities and dormant capacity",
        "O2_IDENTITY": "naming, classification, and role definition",
        "O3_EXECUTION": "action, doing, and kinetic expression",
        "O4_STRUCTURE": "form, pattern, and organized structure",
        "O5_COGNITION": "perception, awareness, and understanding",
        "O6_AGENCY": "direction, control, and purposeful will",
        "O7_REASONING": "logic, analysis, and discriminative thinking",
        "O8_PURPOSE": "meaning, motivation, and intentional goals",
        "O9_WITNESSES": "observation, witnessing, and meta-awareness",
        "O10_UNIFYING": "connection, synthesis, and integration",
        "O11_INTEGRATION": "resolution, consolidation, and deep merging",
        "O12_ABSOLVING": "transcendence, dissolution, and ultimate release",
    }

    primary = layer_descriptions.get(dominant_layer, dominant_layer)

    if len(layer_dist) >= 2:
        secondary_layer = layer_dist[1][0]
        secondary = layer_descriptions.get(secondary_layer, secondary_layer)
        return f"This query primarily engages {primary}, with secondary resonance in {secondary}."
    else:
        return f"This query engages {primary}."


def _generate_routing_narrative(
    model_type: ModelType,
    phase_profile: PhaseProfile,
    query_mode: QueryMode,
    semantic_field: SemanticField,
) -> str:
    """Generate comprehensive routing narrative."""
    model_descriptions = {
        ModelType.GENERAL: "general-purpose processing",
        ModelType.RELATIONSHIP: "relational and emotional understanding",
        ModelType.REASONING: "logical analysis and reasoning",
        ModelType.ACTION: "action-oriented procedural handling",
        ModelType.CREATIVE: "creative generation and structural design",
        ModelType.REFLECTIVE: "contemplative and philosophical exploration",
        ModelType.DIRECTIVE: "guidance and direction provision",
        ModelType.TRANSCENDENT: "abstract and spiritual inquiry",
    }

    lines = []

    # Model routing
    model_desc = model_descriptions.get(model_type, str(model_type))
    lines.append(f"Routed to {model_type.value.upper()} for {model_desc}.")

    # Phase insight
    phase_desc = PHASE_DESCRIPTIONS.get(phase_profile.dominant_phase, "")
    lines.append(f"Query operates in the {phase_profile.dominant_phase} arc ({phase_desc}).")

    # Mode insight
    if query_mode == QueryMode.FOCUSED:
        lines.append("Query shows focused, single-intent energy.")
    elif query_mode == QueryMode.CLUSTERED:
        lines.append("Query words form a coherent semantic cluster.")
    elif query_mode == QueryMode.TRANSITIONAL:
        lines.append("Query spans multiple phases - may require nuanced handling.")
    else:
        lines.append("Query energy is diffuse across multiple dimensions.")

    # Semantic field
    if semantic_field.coherence_score > 0.8:
        lines.append("Strong internal coherence - words reinforce each other.")
    elif semantic_field.coherence_score < 0.5:
        lines.append("Low internal coherence - may contain multiple intents.")

    return " ".join(lines)


# =============================================================================
# Main Analysis Function
# =============================================================================

def analyze_routing(query: str, router: Optional[SemanticRouter] = None) -> RichRoutingReport:
    """
    Perform rich routing analysis on a query.

    Args:
        query: The input query to analyze
        router: Optional SemanticRouter instance (creates default if not provided)

    Returns:
        RichRoutingReport with complete analysis
    """
    if router is None:
        router = SemanticRouter()

    # Get base routing decision
    decision = router.route(query)

    # Extract word-level data
    word_vectors: List[Tuple[str, Tuple[float, ...]]] = []
    word_contributions = []

    for word_vec in decision.query_analysis.words:
        word_vectors.append((word_vec.word, word_vec.vector))

        # Determine word's phase
        vec = word_vec.vector
        genesis = sum(vec[0:4])
        operation = sum(vec[4:8])
        return_phase = sum(vec[8:12])
        phases = {"GENESIS": genesis, "OPERATION": operation, "RETURN": return_phase}
        word_phase = max(phases, key=phases.get)

        word_contributions.append(WordContribution(
            word=word_vec.word,
            dominant_layer=word_vec.dominant_layer,
            dominant_score=round(word_vec.dominant_score, 3),
            phase=word_phase,
            vector=word_vec.vector,
        ))

    # Compute layer totals for phase profile
    layer_totals = [0.0] * 12
    for _, vec in word_vectors:
        for i, score in enumerate(vec):
            layer_totals[i] += score

    # Compute rich signals
    phase_profile = _compute_phase_profile(layer_totals)
    semantic_field = _compute_semantic_field(word_vectors)

    # Layer distribution (normalized, sorted)
    total = sum(layer_totals) if sum(layer_totals) > 0 else 1.0
    layer_distribution = sorted(
        [(LAYER_NAMES[i], round(layer_totals[i] / total, 3)) for i in range(12)],
        key=lambda x: -x[1]
    )

    # Determine query mode
    query_mode = _determine_query_mode(phase_profile, layer_distribution, semantic_field)

    # Generate narratives
    layer_narrative = _generate_layer_narrative(decision.dominant_layer, layer_distribution)
    routing_narrative = _generate_routing_narrative(
        decision.model_type, phase_profile, query_mode, semantic_field
    )

    return RichRoutingReport(
        query=query,
        model_type=decision.model_type,
        confidence=round(decision.confidence, 3),
        dominant_layer=decision.dominant_layer,
        phase_profile=phase_profile,
        semantic_field=semantic_field,
        query_mode=query_mode,
        word_contributions=tuple(word_contributions),
        layer_distribution=tuple(layer_distribution),
        routing_narrative=routing_narrative,
        layer_narrative=layer_narrative,
    )


# =============================================================================
# Formatting Functions
# =============================================================================

def format_rich_routing(report: RichRoutingReport, verbose: bool = True) -> str:
    """Format a rich routing report for display."""
    lines = []

    # Header
    lines.append(f"ROUTING ANALYSIS: \"{report.query}\"")
    lines.append("=" * 65)
    lines.append("")

    # Core routing
    lines.append(f"Model: {report.model_type.value.upper()}")
    lines.append(f"Confidence: {report.confidence:.3f}")
    lines.append(f"Dominant Layer: {report.dominant_layer}")
    lines.append(f"Query Mode: {report.query_mode.value}")
    lines.append("")

    # Phase profile
    lines.append("PHASE CONCENTRATION:")
    lines.append("-" * 50)
    pp = report.phase_profile
    lines.append(f"  Genesis:   {'#' * int(pp.genesis_energy * 20):<20} {pp.genesis_energy:.3f}")
    lines.append(f"  Operation: {'#' * int(pp.operation_energy * 20):<20} {pp.operation_energy:.3f}")
    lines.append(f"  Return:    {'#' * int(pp.return_energy * 20):<20} {pp.return_energy:.3f}")
    lines.append(f"  Dominant: {pp.dominant_phase} (clarity: {pp.phase_clarity:.2f})")
    lines.append("")

    # Semantic field
    sf = report.semantic_field
    lines.append("SEMANTIC FIELD:")
    lines.append("-" * 50)
    lines.append(f"  Coherence: {sf.coherence_score:.3f}")
    lines.append(f"  Field Strength: {sf.field_strength:.3f}")
    lines.append(f"  Dominant Cluster: {sf.dominant_cluster}")
    if sf.resonant_pairs:
        lines.append("  Resonant Pairs:")
        for word_a, word_b, sim in sf.resonant_pairs[:3]:
            lines.append(f"    {word_a} <-> {word_b}: {sim:.3f}")
    lines.append("")

    if verbose:
        # Word contributions
        lines.append("WORD CONTRIBUTIONS:")
        lines.append("-" * 60)
        lines.append(f"  {'Word':<15} {'Layer':<18} {'Score':>8} {'Phase':<10}")
        lines.append("-" * 60)
        for wc in report.word_contributions:
            lines.append(f"  {wc.word:<15} {wc.dominant_layer:<18} {wc.dominant_score:>8.3f} {wc.phase:<10}")
        lines.append("")

        # Layer distribution (top 5)
        lines.append("LAYER DISTRIBUTION (top 5):")
        lines.append("-" * 50)
        for layer, score in report.layer_distribution[:5]:
            bar = '#' * int(score * 40)
            lines.append(f"  {layer:<20} {bar:<40} {score:.3f}")
        lines.append("")

    # Narratives
    lines.append("LAYER INSIGHT:")
    lines.append("-" * 50)
    # Word wrap
    words = report.layer_narrative.split()
    current = "  "
    for word in words:
        if len(current) + len(word) + 1 > 60:
            lines.append(current)
            current = "  " + word
        else:
            current += " " + word if current.strip() else "  " + word
    if current.strip():
        lines.append(current)
    lines.append("")

    lines.append("ROUTING DECISION:")
    lines.append("-" * 50)
    words = report.routing_narrative.split()
    current = "  "
    for word in words:
        if len(current) + len(word) + 1 > 60:
            lines.append(current)
            current = "  " + word
        else:
            current += " " + word if current.strip() else "  " + word
    if current.strip():
        lines.append(current)
    lines.append("")
    lines.append("=" * 65)

    return "\n".join(lines)


def print_routing_report(query: str, verbose: bool = True) -> None:
    """Analyze and print routing report for a query."""
    report = analyze_routing(query)
    print(format_rich_routing(report, verbose=verbose))


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Enums
    "QueryMode",
    # Data classes
    "WordContribution",
    "PhaseProfile",
    "SemanticField",
    "RichRoutingReport",
    # Constants
    "PHASE_MAPPING",
    "PHASE_DESCRIPTIONS",
    # Functions
    "analyze_routing",
    "format_rich_routing",
    "print_routing_report",
]
