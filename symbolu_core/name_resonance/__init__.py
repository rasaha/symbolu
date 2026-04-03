"""
Name Resonance System
=====================

A deterministic, explainable system for cross-domain name analysis.

This is a Tier 1 (Core/Substrate) module with:
- Zero governance authority
- Deterministic processing
- Full traceability

Usage:
    from symbolu_core.name_resonance import analyze_name, canonical_match

    # Traditional analysis
    result = analyze_name("Campbell")
    print(result.summary)

    # Canonical matching (C × R framework)
    match = canonical_match("king", "queen")
    print(f"Match: {match.match_score} ({match.mode.value})")

    # Rich resonance analysis (new!)
    from symbolu_core.name_resonance import analyze_name_resonance, print_resonance_report
    print_resonance_report("Rakesh", "Golf")

    # Quick helpers
    profile = get_profile("Campbell")
    comparison = compare_names("Campbell", "Erikson")
    match_result = quick_match("Campbell", "Golf")
"""

from symbolu_core.name_resonance.api import (
    analyze_name,
    get_profile,
    compare_names,
    quick_match,
    NameResonanceResult,
)
from symbolu_core.name_resonance.canonical_matcher import (
    canonical_match,
    CanonicalMatchResult,
    MatchMode,
    demo_canonical_matching,
    format_result,
)
from symbolu_core.name_resonance.rich_resonance import (
    analyze_name_resonance,
    print_resonance_report,
    compute_rich_resonance,
    format_rich_report,
    RichResonanceReport,
    OrthogonalSignals,
    PhaseProfile,
    LayerAlignment,
    AlignmentType,
    ResonanceMode,
    LAYER_PAIRS,
    PHASES,
)

__all__ = [
    # Traditional API
    "analyze_name",
    "get_profile",
    "compare_names",
    "quick_match",
    "NameResonanceResult",
    # Canonical matching
    "canonical_match",
    "CanonicalMatchResult",
    "MatchMode",
    "demo_canonical_matching",
    "format_result",
    # Rich resonance (new!)
    "analyze_name_resonance",
    "print_resonance_report",
    "compute_rich_resonance",
    "format_rich_report",
    "RichResonanceReport",
    "OrthogonalSignals",
    "PhaseProfile",
    "LayerAlignment",
    "AlignmentType",
    "ResonanceMode",
    "LAYER_PAIRS",
    "PHASES",
]
