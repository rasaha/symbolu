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
"""

from symbolu.name_resonance.api import analyze_name, NameResonanceResult
from symbolu.name_resonance.canonical_matcher import (
    canonical_match,
    CanonicalMatchResult,
    MatchMode,
    demo_canonical_matching,
    format_result,
)

__all__ = [
    "analyze_name",
    "NameResonanceResult",
    "canonical_match",
    "CanonicalMatchResult",
    "MatchMode",
    "demo_canonical_matching",
    "format_result",
]
