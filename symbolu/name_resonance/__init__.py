"""
Name Resonance System
=====================

A deterministic, explainable system for cross-domain name analysis.

This is a Tier 1 (Core/Substrate) module with:
- Zero governance authority
- Deterministic processing
- Full traceability

Usage:
    from symbolu.name_resonance import analyze_name

    result = analyze_name("Campbell")
    print(result.summary)
"""

from symbolu.name_resonance.api import analyze_name, NameResonanceResult

__all__ = ["analyze_name", "NameResonanceResult"]
