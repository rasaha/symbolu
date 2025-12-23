"""
Name Resonance System
=====================

A deterministic, explainable system for cross-domain name analysis.

This is a Tier 1 (Core/Substrate) module with:
- Zero governance authority
- Deterministic processing
- Full traceability

Usage:
    from symbolu.name_resonance import analyze_name, canonical_match

    # Traditional analysis
    result = analyze_name("Campbell")
    print(result.summary)

    # Canonical matching (C × R framework)
    match = canonical_match("king", "queen")
    print(f"Match: {match.match_score} ({match.mode.value})")

    # Quick helpers
    profile = get_profile("Campbell")
    comparison = compare_names("Campbell", "Erikson")
    match_result = quick_match("Campbell", "Golf")
"""

from symbolu.name_resonance.api import (
    analyze_name,
    get_profile,
    compare_names,
    quick_match,
    NameResonanceResult,
)
from symbolu.name_resonance.canonical_matcher import (
    canonical_match,
    CanonicalMatchResult,
    MatchMode,
    demo_canonical_matching,
    format_result,
)

__all__ = [
    "analyze_name",
    "get_profile",
    "compare_names",
    "quick_match",
    "NameResonanceResult",
    "canonical_match",
    "CanonicalMatchResult",
    "MatchMode",
    "demo_canonical_matching",
    "format_result",
]
