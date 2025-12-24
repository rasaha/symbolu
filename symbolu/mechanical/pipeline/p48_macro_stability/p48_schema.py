"""
Phase 48: Macro-Stability Regime Analyzer Schema

Frozen dataclass for macro-stability regime classification output.

Phase 48 answers:
    "What kind of long-range stability regime is the system currently in?"

This is classification, not prediction, not action, not gating.

Invariants:
    INV-P48-1: Classification-only (no numeric synthesis beyond confidence)
    INV-P48-2: No future selection (no path choice, no ranking)
    INV-P48-3: Deterministic (pure rule + arithmetic)
    INV-P48-4: Observer-only (cannot influence authority layers)
    INV-P48-5: Absence-safe (missing input -> None)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

# Version identifier for this phase
P48_VERSION = "1.0.0"

# Macro regime classifications
MacroRegime = Literal[
    "stable_convergent",
    "stable_divergent",
    "fragile_convergent",
    "chaotic",
    "indeterminate",
]

# Valid macro regime values (for validation)
VALID_MACRO_REGIMES = frozenset(
    {
        "stable_convergent",
        "stable_divergent",
        "fragile_convergent",
        "chaotic",
        "indeterminate",
    }
)


@dataclass(frozen=True)
class MacroStabilityRegimeReport:
    """
    Immutable macro-stability regime classification report.

    This is an observer-only output that classifies the current
    long-range stability regime without predicting, selecting,
    or influencing any system behavior.

    Invariants:
        - macro_regime in VALID_MACRO_REGIMES
        - confidence in [0.0, 1.0]
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    macro_regime: MacroRegime
    confidence: float
    observer_only: Literal[True]

    # Metadata
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P48_VERSION
    architectural_phase: str = "P48"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P48-4: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P48-4)")

        # Validate macro_regime
        if self.macro_regime not in VALID_MACRO_REGIMES:
            raise ValueError(
                f"Invalid macro_regime: {self.macro_regime}. "
                f"Must be one of {sorted(VALID_MACRO_REGIMES)}"
            )

        # Clamp confidence to [0.0, 1.0]
        if not 0.0 <= self.confidence <= 1.0:
            clamped = max(0.0, min(1.0, self.confidence))
            object.__setattr__(self, "confidence", clamped)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "macro_regime": self.macro_regime,
            "confidence": self.confidence,
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }


def create_macro_stability_report(
    macro_regime: MacroRegime,
    confidence: float,
    debug: Dict[str, Any] | None = None,
) -> MacroStabilityRegimeReport:
    """
    Factory function to create MacroStabilityRegimeReport safely.

    Always sets observer_only=True (enforced by design).

    INV-P48-1: Classification-only - just regime assignment.
    INV-P48-4: Observer-only enforced.

    Args:
        macro_regime: The classified regime
        confidence: Confidence score in [0.0, 1.0]
        debug: Optional debug information

    Returns:
        MacroStabilityRegimeReport
    """
    # Clamp confidence
    clamped_confidence = max(0.0, min(1.0, confidence))

    return MacroStabilityRegimeReport(
        macro_regime=macro_regime,
        confidence=clamped_confidence,
        observer_only=True,
        debug=debug or {},
    )
