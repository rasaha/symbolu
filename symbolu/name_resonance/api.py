"""
Name Resonance System - Public API
===================================

High-level interface for name resonance analysis.

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)

Usage:
    from symbolu.name_resonance import analyze_name

    result = analyze_name("Campbell")
    print(result.summary)
    for domain in result.domain_results:
        print(f"{domain.domain_name}: {domain.classification.value}")
"""

from typing import Tuple, Optional

from symbolu.name_resonance.types import (
    NormalizedInput,
    ExtractedSignals,
    StructuralProfile,
    DomainCompatibilityResult,
    NameResonanceResult,
    CompatibilityLevel,
    DIMENSION_NAMES,
)
from symbolu.name_resonance.extractor import normalize_input, extract_signals
from symbolu.name_resonance.projector import project_to_structural_profile
from symbolu.name_resonance.matcher import match_all_domains, get_compatibility_summary
from symbolu.name_resonance.domains import ALL_DOMAINS
from symbolu.name_resonance.ontological_bridge import (
    get_ontological_vector,
    project_ontological_to_experiential,
    compute_bridged_profile,
)


# =============================================================================
# Mandatory Caveats (Always Included)
# =============================================================================

MANDATORY_CAVEATS: Tuple[str, ...] = (
    "This analysis is based solely on phonetic/structural features of the input.",
    "Domain compatibility reflects structural pattern matching, not individual capability.",
    "Cultural, personal, and contextual factors are not considered.",
    "This is a deterministic projection, not a prediction or personality assessment.",
    "Names do not determine destiny, skill, or success in any field.",
)


# =============================================================================
# Main Analysis Function
# =============================================================================

def analyze_name(
    name: str,
    *,
    domains: Optional[Tuple] = None,
    use_ontological_bridge: bool = False,
    phonetic_weight: float = 0.6,
    ontological_weight: float = 0.4,
) -> NameResonanceResult:
    """
    Analyze a name's structural resonance and domain compatibility.

    This is the main public API for the Name Resonance System.
    Fully deterministic: same name → same result.

    Args:
        name: The name to analyze (single word or full name)
        domains: Optional tuple of DomainPatterns to match against.
                 Defaults to ALL_DOMAINS (careers + sports).
        use_ontological_bridge: If True, use 10D ontological layers (C-S-R logic)
                               bridged to 12D for enhanced analysis.
                               Default False for backward compatibility.
        phonetic_weight: Weight for phonetic 12D component (default 0.6).
                        Only used when use_ontological_bridge=True.
        ontological_weight: Weight for ontological 10D→12D component (default 0.4).
                           Only used when use_ontological_bridge=True.

    Returns:
        NameResonanceResult with full analysis and explanation

    Example:
        >>> result = analyze_name("Campbell")
        >>> print(result.summary)
        >>> for dr in result.domain_results[:3]:
        ...     print(f"{dr.domain_name}: {dr.classification.value}")

        >>> # With ontological bridge (enhanced C-S-R phoneme logic)
        >>> result = analyze_name("Campbell", use_ontological_bridge=True)
    """
    if domains is None:
        domains = ALL_DOMAINS

    # Layer 1: Normalize
    normalized = normalize_input(name)

    # Layer 2: Extract signals
    signals = extract_signals(normalized)

    # Layer 3: Project to structural profile
    phonetic_profile = project_to_structural_profile(signals)

    if use_ontological_bridge:
        # Enhanced: Combine phonetic 12D with ontological 10D→12D
        ontological_vector = get_ontological_vector(name)
        ontological_contribution = project_ontological_to_experiential(ontological_vector)

        # Compute bridged profile
        bridged_dict = compute_bridged_profile(
            phonetic_profile.to_dict(),
            ontological_contribution,
            phonetic_weight=phonetic_weight,
            ontological_weight=ontological_weight,
        )

        # Create new StructuralProfile from bridged values
        profile = StructuralProfile(
            force=bridged_dict["force"],
            stability=bridged_dict["stability"],
            duration=bridged_dict["duration"],
            initiation=bridged_dict["initiation"],
            flow=bridged_dict["flow"],
            termination=bridged_dict["termination"],
            complexity=bridged_dict["complexity"],
            density=bridged_dict["density"],
            balance=bridged_dict["balance"],
            openness=bridged_dict["openness"],
            depth=bridged_dict["depth"],
            connectivity=bridged_dict["connectivity"],
            signal_contributions=phonetic_profile.signal_contributions,
        )
    else:
        # Default: Use phonetic profile only
        profile = phonetic_profile

    # Layer 4: Match domains
    domain_results = match_all_domains(profile, domains)

    # Get summary
    high_compat, low_compat = get_compatibility_summary(domain_results)

    # Generate summary text
    summary = _generate_summary(name, profile, high_compat, low_compat)

    return NameResonanceResult(
        original_input=name,
        normalized_input=normalized,
        signals=signals,
        profile=profile,
        domain_results=domain_results,
        summary=summary,
        high_compatibility=high_compat,
        low_compatibility=low_compat,
        caveats=MANDATORY_CAVEATS,
    )


def _generate_summary(
    name: str,
    profile: StructuralProfile,
    high_compat: Tuple[str, ...],
    low_compat: Tuple[str, ...],
) -> str:
    """Generate human-readable summary."""
    parts = [f"Analysis of '{name}':"]

    # Describe structural profile
    high_dims = profile.get_high_dimensions(0.65)
    low_dims = profile.get_low_dimensions(0.35)

    if high_dims:
        high_names = ", ".join(d[0] for d in high_dims[:3])
        parts.append(f"High structural dimensions: {high_names}")
    if low_dims:
        low_names = ", ".join(d[0] for d in low_dims[:3])
        parts.append(f"Low structural dimensions: {low_names}")

    # Domain compatibility
    if high_compat:
        parts.append(f"Strong/Moderate compatibility: {', '.join(high_compat[:4])}")
    if low_compat:
        parts.append(f"Weak compatibility: {', '.join(low_compat[:3])}")

    return " | ".join(parts)


# =============================================================================
# Convenience Functions
# =============================================================================

def get_profile(name: str) -> StructuralProfile:
    """
    Get just the structural profile for a name.

    Args:
        name: The name to analyze

    Returns:
        12D StructuralProfile
    """
    normalized = normalize_input(name)
    signals = extract_signals(normalized)
    return project_to_structural_profile(signals)


def compare_names(name_a: str, name_b: str) -> str:
    """
    Compare two names' structural profiles.

    Args:
        name_a: First name
        name_b: Second name

    Returns:
        Human-readable comparison
    """
    profile_a = get_profile(name_a)
    profile_b = get_profile(name_b)

    lines = [
        f"Comparison: '{name_a}' vs '{name_b}'",
        "",
        "Dimension          | {:<10} | {:<10} | Diff".format(name_a[:10], name_b[:10]),
        "-" * 50,
    ]

    for dim in DIMENSION_NAMES:
        val_a = getattr(profile_a, dim)
        val_b = getattr(profile_b, dim)
        diff = val_a - val_b
        diff_str = f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}"
        lines.append(f"{dim:<18} | {val_a:.2f}      | {val_b:.2f}      | {diff_str}")

    return "\n".join(lines)


def quick_match(name: str, domain_name: str) -> str:
    """
    Quick check of name compatibility with a specific domain.

    Args:
        name: The name to analyze
        domain_name: Domain to check (e.g., "Golf", "Justice / Law Enforcement")

    Returns:
        Human-readable result
    """
    result = analyze_name(name)

    for dr in result.domain_results:
        if domain_name.lower() in dr.domain_name.lower():
            indicator = _get_indicator(dr.classification)
            return (
                f"{indicator} '{name}' → {dr.domain_name}: "
                f"{dr.classification.value.upper()} ({dr.compatibility_score:.2f})"
            )

    return f"Domain '{domain_name}' not found"


def _get_indicator(level: CompatibilityLevel) -> str:
    """Get visual indicator for compatibility level."""
    if level == CompatibilityLevel.STRONG:
        return "[+++]"
    elif level == CompatibilityLevel.MODERATE:
        return "[++ ]"
    elif level == CompatibilityLevel.PARTIAL:
        return "[+  ]"
    else:
        return "[   ]"


# =============================================================================
# Demo Function
# =============================================================================

def demo(name: str = "Campbell") -> str:
    """
    Run a full demonstration of the Name Resonance System.

    Args:
        name: Name to analyze (default: "Campbell")

    Returns:
        Formatted demo output
    """
    result = analyze_name(name)

    lines = [
        "=" * 70,
        "NAME RESONANCE SYSTEM - DEMO",
        "=" * 70,
        "",
        f"INPUT: {result.original_input}",
        f"NORMALIZED: {result.normalized_input.canonical}",
        f"PHONEMES: {' '.join(result.signals.phoneme_sequence)}",
        "",
        "--- STRUCTURAL PROFILE (12D) ---",
        "",
    ]

    # Show all dimensions
    for dim in DIMENSION_NAMES:
        val = getattr(result.profile, dim)
        bar = "#" * int(val * 20)
        lines.append(f"  {dim:<14}: {val:.2f} |{bar:<20}|")

    lines.extend([
        "",
        "--- DOMAIN COMPATIBILITY ---",
        "",
    ])

    # Show domain results
    for dr in result.domain_results:
        indicator = _get_indicator(dr.classification)
        lines.append(
            f"  {indicator} {dr.domain_name:<30} "
            f"{dr.classification.value:<8} ({dr.compatibility_score:.3f})"
        )
        if dr.top_matches:
            lines.append(f"         Strong: {', '.join(dr.top_matches)}")
        if dr.weak_matches:
            lines.append(f"         Weak: {', '.join(dr.weak_matches)}")

    lines.extend([
        "",
        "--- CAVEATS ---",
        "",
    ])

    for caveat in result.caveats:
        lines.append(f"  * {caveat}")

    lines.extend([
        "",
        "=" * 70,
    ])

    return "\n".join(lines)


# =============================================================================
# Detailed Report Function
# =============================================================================

def detailed_report(name: str) -> str:
    """
    Generate a detailed report for a name analysis.

    Args:
        name: Name to analyze

    Returns:
        Detailed formatted report
    """
    result = analyze_name(name)

    lines = [
        "=" * 80,
        f"DETAILED NAME RESONANCE REPORT: {name}",
        "=" * 80,
        "",
        "LAYER 1: INPUT NORMALIZATION",
        "-" * 40,
        f"  Original:   {result.original_input}",
        f"  Canonical:  {result.normalized_input.canonical}",
        f"  Segments:   {result.normalized_input.segments}",
        f"  Script:     {result.normalized_input.script_family.value}",
        "",
        "LAYER 2: SIGNAL EXTRACTION",
        "-" * 40,
        f"  Phonemes:   {' '.join(result.signals.phoneme_sequence)}",
        f"  Categories: {' '.join(result.signals.phoneme_categories)}",
        f"  Syllables:  {result.signals.syllable_count}",
        f"  Stress:     {result.signals.stress_pattern}",
        f"  V/C Ratio:  {result.signals.vowel_consonant_ratio:.2f}",
        f"  Onset:      {result.signals.onset_cluster_size} consonants",
        f"  Coda:       {result.signals.coda_cluster_size} consonants",
        "",
        "  Phoneme Counts:",
        f"    Plosives:   {result.signals.plosive_count}",
        f"    Fricatives: {result.signals.fricative_count}",
        f"    Nasals:     {result.signals.nasal_count}",
        f"    Liquids:    {result.signals.liquid_count}",
        f"    Glides:     {result.signals.glide_count}",
        f"    Vowels:     {result.signals.vowel_count}",
        "",
        "LAYER 3: STRUCTURAL PROFILE (12D)",
        "-" * 40,
    ]

    for dim in DIMENSION_NAMES:
        val = getattr(result.profile, dim)
        bar = "#" * int(val * 30)
        qualifier = _qualify_dimension(val)
        lines.append(f"  {dim:<14}: {val:.3f} [{qualifier:<6}] |{bar:<30}|")

    lines.extend([
        "",
        "LAYER 4: DOMAIN COMPATIBILITY",
        "-" * 40,
    ])

    for dr in result.domain_results:
        indicator = _get_indicator(dr.classification)
        lines.extend([
            "",
            f"  {indicator} {dr.domain_name}",
            f"      Score: {dr.compatibility_score:.3f} ({dr.classification.value})",
            f"      Category: {dr.domain_category}",
        ])
        if dr.top_matches:
            lines.append(f"      Strong dimensions: {', '.join(dr.top_matches)}")
        if dr.weak_matches:
            lines.append(f"      Weak dimensions: {', '.join(dr.weak_matches)}")

    lines.extend([
        "",
        "MANDATORY CAVEATS",
        "-" * 40,
    ])

    for i, caveat in enumerate(result.caveats, 1):
        lines.append(f"  {i}. {caveat}")

    lines.extend([
        "",
        "=" * 80,
    ])

    return "\n".join(lines)


def _qualify_dimension(value: float) -> str:
    """Qualify a dimension value."""
    if value >= 0.75:
        return "HIGH"
    elif value >= 0.55:
        return "MED-HI"
    elif value >= 0.45:
        return "MID"
    elif value >= 0.30:
        return "MED-LO"
    else:
        return "LOW"
