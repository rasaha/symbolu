"""
Phase 48: Macro-Stability Regime Analyzer

Macro-level categorization of long-range stability regimes.

Phase 48 answers:
    "What kind of long-range stability regime is the system currently in?"

This is classification, not prediction, not action, not gating.

Usage:
    from symbolu.mechanical.pipeline.p48_macro_stability import (
        maybe_run_p48,
        run_p48_directly,
        MacroStabilityRegimeReport,
    )

    # In pipeline after P45, P46, P47:
    report = maybe_run_p48(ctx)

    if report is not None:
        print(f"Regime: {report.macro_regime}")
        print(f"Confidence: {report.confidence}")

Invariants:
    INV-P48-1: Classification-only (no numeric synthesis beyond confidence)
    INV-P48-2: No future selection (no path choice, no ranking)
    INV-P48-3: Deterministic (pure rule + arithmetic)
    INV-P48-4: Observer-only (cannot influence authority layers)
    INV-P48-5: Absence-safe (missing input -> None)
"""

from .p48_schema import (
    P48_VERSION,
    MacroRegime,
    MacroStabilityRegimeReport,
    create_macro_stability_report,
    VALID_MACRO_REGIMES,
)

from .p48_regime_analyzer import (
    compute_macro_stability_regime,
    run_p48_directly,
    T_HIGH,
    T_LOW,
    C_HIGH,
    C_MED,
    C_LOW,
    A_HIGH,
    A_MED,
)

from .p48_integration import (
    maybe_run_p48,
    is_p48_disabled,
    has_p48_regime_report,
    get_p48_regime_report,
    get_macro_regime,
    get_regime_confidence,
    get_p48_version,
)


__all__ = [
    # Schema
    "P48_VERSION",
    "MacroRegime",
    "MacroStabilityRegimeReport",
    "create_macro_stability_report",
    "VALID_MACRO_REGIMES",
    # Engine thresholds
    "T_HIGH",
    "T_LOW",
    "C_HIGH",
    "C_MED",
    "C_LOW",
    "A_HIGH",
    "A_MED",
    # Engine
    "compute_macro_stability_regime",
    "run_p48_directly",
    # Integration
    "maybe_run_p48",
    "is_p48_disabled",
    "has_p48_regime_report",
    "get_p48_regime_report",
    "get_macro_regime",
    "get_regime_confidence",
    "get_p48_version",
]
