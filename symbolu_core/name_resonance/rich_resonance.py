"""
Rich Resonance Analysis
=======================

Provides detailed, interpretable resonance reports between names/words.

Combines:
1. Layer-by-layer profile comparison (12D ontological × 12D structural)
2. Orthogonal signal decomposition (magnitude, correlation, phase)
3. Narrative interpretation

Tier: Core/Substrate (Tier 1)
Determinism: FULL
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, List, Optional
from enum import Enum


# =============================================================================
# Layer Correspondence Mapping
# =============================================================================

# The 12 ontological layers mapped to 12 structural dimensions
LAYER_PAIRS: Tuple[Tuple[str, str, str], ...] = (
    ("O1_POTENTIAL", "FORCE", "Latent power before expression"),
    ("O2_IDENTITY", "STABILITY", "Naming creates constancy"),
    ("O3_EXECUTION", "DURATION", "Action unfolds through time"),
    ("O4_STRUCTURE", "INITIATION", "Form must be initiated"),
    ("O5_COGNITION", "FLOW", "Awareness streams continuously"),
    ("O6_AGENCY", "TERMINATION", "Will decides endings"),
    ("O7_REASONING", "COMPLEXITY", "Logic navigates intricacy"),
    ("O8_PURPOSE", "DENSITY", "Meaning concentrates"),
    ("O9_WITNESSES", "BALANCE", "Observer sees equilibrium"),
    ("O10_UNIFYING", "OPENNESS", "Synthesis requires receptivity"),
    ("O11_INTEGRATION", "DEPTH", "Resolution goes deep"),
    ("O12_ABSOLVING", "CONNECTIVITY", "Transcendence unites all"),
)

# Phase definitions (arc segments)
PHASES = (
    ("GENESIS", (0, 4), "Emergence from potential to form"),
    ("OPERATION", (4, 8), "Active engagement with reality"),
    ("RETURN", (8, 12), "Integration back to unity"),
)


class AlignmentType(Enum):
    """Type of layer alignment between two profiles."""
    STRONG = "strong"      # Both high (> 0.6)
    ALIGNED = "aligned"    # Similar values (diff < 0.15)
    PARTIAL = "partial"    # Moderate similarity
    DIVERGENT = "divergent"  # Different directions


class ResonanceMode(Enum):
    """Overall resonance relationship."""
    DUPLICATE = "duplicate"      # High correlation, high magnitude
    COMPLEMENT = "complement"    # Low correlation, high magnitude
    HARMONIC = "harmonic"        # High correlation, moderate magnitude
    DISSONANT = "dissonant"      # Low on both
    POTENTIAL = "potential"      # One high, one low


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(frozen=True)
class LayerAlignment:
    """Alignment analysis for a single layer pair."""
    index: int
    ontological_name: str
    structural_name: str
    description: str
    value_a: float
    value_b: float
    alignment: AlignmentType

    @property
    def diff(self) -> float:
        return abs(self.value_a - self.value_b)

    @property
    def combined(self) -> float:
        return (self.value_a + self.value_b) / 2


@dataclass(frozen=True)
class OrthogonalSignals:
    """Three orthogonal signals from resonance analysis."""
    magnitude_alignment: float   # Do peaks coincide?
    profile_correlation: float   # Do shapes match?
    phase_coherence: float       # Same arc segment?

    @property
    def combined_score(self) -> float:
        """Weighted combination of signals."""
        return (0.4 * self.magnitude_alignment +
                0.3 * (self.profile_correlation + 1) / 2 +  # normalize [-1,1] to [0,1]
                0.3 * self.phase_coherence)


@dataclass(frozen=True)
class PhaseProfile:
    """Phase concentration for a single name/word."""
    name: str
    genesis_energy: float
    operation_energy: float
    return_energy: float
    dominant_phase: str

    @property
    def phase_vector(self) -> Tuple[float, float, float]:
        return (self.genesis_energy, self.operation_energy, self.return_energy)


@dataclass(frozen=True)
class RichResonanceReport:
    """Complete rich resonance analysis between two names/words."""
    name_a: str
    name_b: str
    vector_a: Tuple[float, ...]
    vector_b: Tuple[float, ...]
    overall_score: float
    layer_alignments: Tuple[LayerAlignment, ...]
    signals: OrthogonalSignals
    phase_a: PhaseProfile
    phase_b: PhaseProfile
    resonance_mode: ResonanceMode
    dominant_layer_a: Tuple[str, float]  # (layer_name, value)
    dominant_layer_b: Tuple[str, float]
    narrative: str


# =============================================================================
# Core Computation Functions
# =============================================================================

def _compute_alignment_type(val_a: float, val_b: float) -> AlignmentType:
    """Determine alignment type between two values."""
    diff = abs(val_a - val_b)
    avg = (val_a + val_b) / 2

    if avg > 0.6 and diff < 0.2:
        return AlignmentType.STRONG
    elif diff < 0.15:
        return AlignmentType.ALIGNED
    elif diff < 0.3:
        return AlignmentType.PARTIAL
    else:
        return AlignmentType.DIVERGENT


def _compute_magnitude_alignment(vec_a: Tuple[float, ...],
                                  vec_b: Tuple[float, ...]) -> float:
    """Compute element-wise magnitude alignment (normalized dot product)."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a * mag_b < 1e-9:
        return 0.0
    return dot / (mag_a * mag_b)


def _compute_profile_correlation(vec_a: Tuple[float, ...],
                                  vec_b: Tuple[float, ...]) -> float:
    """Compute Pearson correlation between profiles (shape similarity)."""
    n = len(vec_a)
    mean_a = sum(vec_a) / n
    mean_b = sum(vec_b) / n

    numerator = sum((a - mean_a) * (b - mean_b) for a, b in zip(vec_a, vec_b))
    std_a = math.sqrt(sum((a - mean_a) ** 2 for a in vec_a))
    std_b = math.sqrt(sum((b - mean_b) ** 2 for b in vec_b))

    if std_a * std_b < 1e-9:
        return 0.0
    return numerator / (std_a * std_b)


def _compute_phase_profile(name: str, vector: Tuple[float, ...]) -> PhaseProfile:
    """Compute phase energy concentration."""
    genesis = sum(vector[0:4]) / 4
    operation = sum(vector[4:8]) / 4
    return_phase = sum(vector[8:12]) / 4

    phases = {"GENESIS": genesis, "OPERATION": operation, "RETURN": return_phase}
    dominant = max(phases, key=phases.get)

    return PhaseProfile(
        name=name,
        genesis_energy=round(genesis, 3),
        operation_energy=round(operation, 3),
        return_energy=round(return_phase, 3),
        dominant_phase=dominant,
    )


def _compute_phase_coherence(phase_a: PhaseProfile, phase_b: PhaseProfile) -> float:
    """Compute phase coherence between two profiles."""
    if phase_a.dominant_phase == phase_b.dominant_phase:
        return 1.0

    # Partial coherence for adjacent phases
    phase_order = ["GENESIS", "OPERATION", "RETURN"]
    idx_a = phase_order.index(phase_a.dominant_phase)
    idx_b = phase_order.index(phase_b.dominant_phase)

    if abs(idx_a - idx_b) == 1:
        return 0.6  # Adjacent phases
    return 0.3  # Opposite phases


def _determine_resonance_mode(signals: OrthogonalSignals) -> ResonanceMode:
    """Determine overall resonance mode from orthogonal signals."""
    mag = signals.magnitude_alignment
    corr = signals.profile_correlation

    if mag > 0.7 and corr > 0.6:
        return ResonanceMode.DUPLICATE
    elif mag > 0.6 and corr < 0.3:
        return ResonanceMode.COMPLEMENT
    elif corr > 0.5 and mag > 0.4:
        return ResonanceMode.HARMONIC
    elif mag < 0.4 and corr < 0.3:
        return ResonanceMode.DISSONANT
    else:
        return ResonanceMode.POTENTIAL


def _find_dominant_layer(vector: Tuple[float, ...]) -> Tuple[str, float]:
    """Find the dominant layer in a vector."""
    max_idx = 0
    max_val = vector[0]
    for i, v in enumerate(vector):
        if v > max_val:
            max_val = v
            max_idx = i

    layer_name = LAYER_PAIRS[max_idx][0]
    return (layer_name, round(max_val, 3))


def _generate_narrative(name_a: str, name_b: str,
                        signals: OrthogonalSignals,
                        phase_a: PhaseProfile,
                        phase_b: PhaseProfile,
                        dominant_a: Tuple[str, float],
                        dominant_b: Tuple[str, float],
                        mode: ResonanceMode) -> str:
    """Generate interpretive narrative for the resonance."""

    # Layer descriptions
    layer_desc = {
        "O1_POTENTIAL": "latent power",
        "O2_IDENTITY": "stable identity",
        "O3_EXECUTION": "kinetic action",
        "O4_STRUCTURE": "formed pattern",
        "O5_COGNITION": "flowing awareness",
        "O6_AGENCY": "directed will",
        "O7_REASONING": "analytical clarity",
        "O8_PURPOSE": "concentrated meaning",
        "O9_WITNESSES": "balanced observation",
        "O10_UNIFYING": "open synthesis",
        "O11_INTEGRATION": "deep resolution",
        "O12_ABSOLVING": "transcendent connection",
    }

    phase_desc = {
        "GENESIS": "emergence and initiation",
        "OPERATION": "active engagement",
        "RETURN": "integration and completion",
    }

    dom_a_desc = layer_desc.get(dominant_a[0], dominant_a[0])
    dom_b_desc = layer_desc.get(dominant_b[0], dominant_b[0])

    lines = []

    # Opening based on mode
    if mode == ResonanceMode.DUPLICATE:
        lines.append(f'"{name_a}" and "{name_b}" carry remarkably similar energetic signatures.')
    elif mode == ResonanceMode.COMPLEMENT:
        lines.append(f'"{name_a}" and "{name_b}" complement each other with distinct but balanced energies.')
    elif mode == ResonanceMode.HARMONIC:
        lines.append(f'"{name_a}" and "{name_b}" harmonize through shared patterns at different intensities.')
    elif mode == ResonanceMode.DISSONANT:
        lines.append(f'"{name_a}" and "{name_b}" express contrasting energetic qualities.')
    else:
        lines.append(f'"{name_a}" and "{name_b}" show potential for resonance through their differences.')

    # Dominant energies
    lines.append(f'"{name_a}" embodies {dom_a_desc} ({dominant_a[1]:.2f}).')
    lines.append(f'"{name_b}" embodies {dom_b_desc} ({dominant_b[1]:.2f}).')

    # Phase insight
    if phase_a.dominant_phase == phase_b.dominant_phase:
        lines.append(f"Both names resonate in the {phase_a.dominant_phase} arc - {phase_desc[phase_a.dominant_phase]}.")
    else:
        lines.append(f'"{name_a}" operates in {phase_a.dominant_phase} ({phase_desc[phase_a.dominant_phase]}),')
        lines.append(f'while "{name_b}" operates in {phase_b.dominant_phase} ({phase_desc[phase_b.dominant_phase]}).')

    # Practical insight
    if mode == ResonanceMode.COMPLEMENT:
        lines.append("Together they provide balanced coverage across the cosmic arc.")
    elif mode == ResonanceMode.DUPLICATE:
        lines.append("They reinforce and amplify each other's inherent qualities.")

    return " ".join(lines)


# =============================================================================
# Main Analysis Function
# =============================================================================

def compute_rich_resonance(name_a: str,
                           vector_a: Tuple[float, ...],
                           name_b: str,
                           vector_b: Tuple[float, ...]) -> RichResonanceReport:
    """
    Compute rich resonance analysis between two names/words.

    Args:
        name_a: First name/word
        vector_a: 12D vector for first name (from ontological or structural analysis)
        name_b: Second name/word
        vector_b: 12D vector for second name

    Returns:
        RichResonanceReport with complete analysis
    """
    assert len(vector_a) == 12, f"Vector A must be 12D, got {len(vector_a)}"
    assert len(vector_b) == 12, f"Vector B must be 12D, got {len(vector_b)}"

    # Compute layer-by-layer alignments
    layer_alignments = []
    for i, (onto, struct, desc) in enumerate(LAYER_PAIRS):
        alignment = LayerAlignment(
            index=i,
            ontological_name=onto,
            structural_name=struct,
            description=desc,
            value_a=round(vector_a[i], 3),
            value_b=round(vector_b[i], 3),
            alignment=_compute_alignment_type(vector_a[i], vector_b[i]),
        )
        layer_alignments.append(alignment)

    # Compute orthogonal signals
    magnitude = _compute_magnitude_alignment(vector_a, vector_b)
    correlation = _compute_profile_correlation(vector_a, vector_b)

    phase_a = _compute_phase_profile(name_a, vector_a)
    phase_b = _compute_phase_profile(name_b, vector_b)
    phase_coh = _compute_phase_coherence(phase_a, phase_b)

    signals = OrthogonalSignals(
        magnitude_alignment=round(magnitude, 3),
        profile_correlation=round(correlation, 3),
        phase_coherence=round(phase_coh, 3),
    )

    # Determine resonance mode
    mode = _determine_resonance_mode(signals)

    # Find dominant layers
    dominant_a = _find_dominant_layer(vector_a)
    dominant_b = _find_dominant_layer(vector_b)

    # Generate narrative
    narrative = _generate_narrative(
        name_a, name_b, signals, phase_a, phase_b, dominant_a, dominant_b, mode
    )

    # Overall score
    overall = signals.combined_score

    return RichResonanceReport(
        name_a=name_a,
        name_b=name_b,
        vector_a=vector_a,
        vector_b=vector_b,
        overall_score=round(overall, 3),
        layer_alignments=tuple(layer_alignments),
        signals=signals,
        phase_a=phase_a,
        phase_b=phase_b,
        resonance_mode=mode,
        dominant_layer_a=dominant_a,
        dominant_layer_b=dominant_b,
        narrative=narrative,
    )


# =============================================================================
# Formatting Functions
# =============================================================================

def format_rich_report(report: RichResonanceReport, verbose: bool = True) -> str:
    """Format a rich resonance report for display."""
    lines = []

    # Header
    lines.append(f"RESONANCE ANALYSIS: {report.name_a} <-> {report.name_b}")
    lines.append("=" * 60)
    lines.append("")

    # Overall score
    lines.append(f"Overall Match: {report.overall_score:.3f}")
    lines.append(f"Resonance Mode: {report.resonance_mode.value.upper()}")
    lines.append("")

    # Orthogonal signals
    lines.append("ORTHOGONAL SIGNAL DECOMPOSITION:")
    lines.append("-" * 50)
    lines.append(f"  {'Signal':<22} {'Value':>8}   Interpretation")
    lines.append("-" * 50)

    mag = report.signals.magnitude_alignment
    mag_interp = "Strong shared peaks" if mag > 0.7 else "Moderate overlap" if mag > 0.5 else "Distinct peaks"
    lines.append(f"  {'Magnitude Alignment':<22} {mag:>8.3f}   {mag_interp}")

    corr = report.signals.profile_correlation
    corr_interp = "Similar shapes" if corr > 0.6 else "Partial similarity" if corr > 0.3 else "Different shapes"
    lines.append(f"  {'Profile Correlation':<22} {corr:>8.3f}   {corr_interp}")

    phase = report.signals.phase_coherence
    phase_interp = "Same arc segment" if phase > 0.8 else "Adjacent segments" if phase > 0.5 else "Different arcs"
    lines.append(f"  {'Phase Coherence':<22} {phase:>8.3f}   {phase_interp}")
    lines.append("")

    # Phase profiles
    lines.append("PHASE PROFILES:")
    lines.append("-" * 50)
    lines.append(f"  {report.name_a}:")
    lines.append(f"    Genesis:   {'#' * int(report.phase_a.genesis_energy * 10):<10} {report.phase_a.genesis_energy:.3f}")
    lines.append(f"    Operation: {'#' * int(report.phase_a.operation_energy * 10):<10} {report.phase_a.operation_energy:.3f}")
    lines.append(f"    Return:    {'#' * int(report.phase_a.return_energy * 10):<10} {report.phase_a.return_energy:.3f}")
    lines.append(f"    Dominant:  {report.phase_a.dominant_phase}")
    lines.append("")
    lines.append(f"  {report.name_b}:")
    lines.append(f"    Genesis:   {'#' * int(report.phase_b.genesis_energy * 10):<10} {report.phase_b.genesis_energy:.3f}")
    lines.append(f"    Operation: {'#' * int(report.phase_b.operation_energy * 10):<10} {report.phase_b.operation_energy:.3f}")
    lines.append(f"    Return:    {'#' * int(report.phase_b.return_energy * 10):<10} {report.phase_b.return_energy:.3f}")
    lines.append(f"    Dominant:  {report.phase_b.dominant_phase}")
    lines.append("")

    # Dominant energies
    lines.append("DOMINANT ENERGIES:")
    lines.append("-" * 50)
    lines.append(f"  {report.name_a}: {report.dominant_layer_a[0]} ({report.dominant_layer_a[1]:.3f})")
    lines.append(f"  {report.name_b}: {report.dominant_layer_b[0]} ({report.dominant_layer_b[1]:.3f})")
    lines.append("")

    if verbose:
        # Layer-by-layer breakdown
        lines.append("LAYER-BY-LAYER ALIGNMENT:")
        lines.append("-" * 60)
        lines.append(f"  {'Layer':<25} {report.name_a:>8} {report.name_b:>8}  Align")
        lines.append("-" * 60)

        symbols = {
            AlignmentType.STRONG: "[+++]",
            AlignmentType.ALIGNED: "[ + ]",
            AlignmentType.PARTIAL: "[ ~ ]",
            AlignmentType.DIVERGENT: "[ - ]",
        }

        for la in report.layer_alignments:
            layer_label = f"{la.ontological_name}/{la.structural_name}"
            lines.append(f"  {layer_label:<25} {la.value_a:>8.3f} {la.value_b:>8.3f}  {symbols[la.alignment]}")
        lines.append("")

    # Narrative
    lines.append("NARRATIVE:")
    lines.append("-" * 50)
    # Word wrap narrative
    words = report.narrative.split()
    current_line = "  "
    for word in words:
        if len(current_line) + len(word) + 1 > 58:
            lines.append(current_line)
            current_line = "  " + word
        else:
            current_line += " " + word if current_line.strip() else "  " + word
    if current_line.strip():
        lines.append(current_line)
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


# =============================================================================
# High-Level API
# =============================================================================

def analyze_name_resonance(name_a: str, name_b: str) -> RichResonanceReport:
    """
    Analyze resonance between two names using varṇa-based 12D vectors.

    This is the main entry point for name resonance analysis.

    Args:
        name_a: First name
        name_b: Second name

    Returns:
        RichResonanceReport with complete analysis
    """
    from symbolu_core.resonance.analyzer import analyze_word_varna

    # Get 12D vectors for each name
    vec_a = analyze_word_varna(name_a)
    vec_b = analyze_word_varna(name_b)

    return compute_rich_resonance(
        name_a=name_a,
        vector_a=vec_a.vector,
        name_b=name_b,
        vector_b=vec_b.vector,
    )


def print_resonance_report(name_a: str, name_b: str, verbose: bool = True) -> None:
    """Analyze and print resonance report between two names."""
    report = analyze_name_resonance(name_a, name_b)
    print(format_rich_report(report, verbose=verbose))


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Enums
    "AlignmentType",
    "ResonanceMode",
    # Data classes
    "LayerAlignment",
    "OrthogonalSignals",
    "PhaseProfile",
    "RichResonanceReport",
    # Constants
    "LAYER_PAIRS",
    "PHASES",
    # Functions
    "compute_rich_resonance",
    "format_rich_report",
    "analyze_name_resonance",
    "print_resonance_report",
]
