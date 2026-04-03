"""
P25 - Counterfactual Sandbox Schema Definitions

Defines the immutable data structures for Phase 25: Counterfactual Sandbox.

The counterfactual sandbox answers one question only:
"If certain cognitive inputs were different, how would coherence and stability
respond - hypothetically?"

This phase:
    - Simulates alternative internal states
    - Computes delta-effects on existing truth metrics
    - Never selects, recommends, or predicts outcomes

It is a sandbox, not a planner.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (bitwise), no LLM, no randomness
    - Read-only: Does not modify system behavior
    - Non-invasive: Zero impact on routing, TTOR, MLCR, Fusion, DHA, Renderer
    - Observation-only: Never used for gating, blocking, or behavior modification
    - No prediction: Never implies futures or recommends actions

    MUST NOT:
        - Trigger regime changes
        - Open insight windows
        - Select discourse acts
        - Influence semantics or lexical choice
        - Predict futures
        - Decide actions
        - Import P6-P9 (regime, discourse, semantics, lexical)
        - Import P21 delivery logic
        - Import Renderer, DHA, Persona
        - Use acoustic/phonetic observers

    MAY import (read-only):
        - P10 coherence outputs
        - P12 coherence quality
        - P18 temporal entropy
        - P19 drift fusion
        - P26 UCF
        - Core formula utilities only

Invariants:
    - INV-P25-1: Sandbox outputs are observational only
    - INV-P25-2: No mutation of PipelineContext
    - INV-P25-3: Counterfactuals never imply recommendations
    - INV-P25-4: UCF is recomputed, never overridden
    - INV-P25-5: No forward prediction allowed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# VERSION
# ============================================================================

P25_VERSION = "1.0.0"


# ============================================================================
# CONSTANTS - Delta Bounds
# ============================================================================

# Delta bounds - all deltas must be in [-1.0, +1.0]
DELTA_MIN = -1.0
DELTA_MAX = 1.0

# Risk flag thresholds (rule-based, no heuristics)
STABILITY_DROP_THRESHOLD = -0.15  # stability_band drops by > 15%
ENTROPY_SPIKE_THRESHOLD = 0.20    # entropy increases by > 20%
DRIFT_ACCELERATION_THRESHOLD = 0.20  # drift increases by > 20%
UCF_THRESHOLD_CROSS_STABLE = 0.75     # UCF crosses stable threshold
UCF_THRESHOLD_CROSS_TRANSITIONAL = 0.45  # UCF crosses transitional threshold


# ============================================================================
# DATACLASSES - Input Structures
# ============================================================================


@dataclass(frozen=True)
class CounterfactualScenario:
    """
    Immutable description of a counterfactual scenario.

    A scenario specifies deltas (perturbations) to apply to the baseline
    cognitive state. All deltas are bounded to [-1.0, +1.0].

    This is an input structure - it describes what-if perturbations to simulate.

    Fields:
        scenario_id: Unique identifier for this scenario
        delta_coherence: Change to coherence_v3_quality [-1.0, +1.0]
        delta_entropy: Change to entropy_volatility [-1.0, +1.0]
        delta_drift: Change to drift_fusion_index [-1.0, +1.0]
        delta_schema_stability: Optional change to schema_stability [-1.0, +1.0]

    Invariants:
        - All deltas MUST be in [-1.0, +1.0]
        - scenario_id MUST be non-empty
    """

    scenario_id: str
    delta_coherence: float = 0.0
    delta_entropy: float = 0.0
    delta_drift: float = 0.0
    delta_schema_stability: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate scenario invariants."""
        # Validate scenario_id is non-empty
        if not self.scenario_id or not self.scenario_id.strip():
            raise ValueError(
                "CounterfactualScenario.scenario_id must be non-empty"
            )

        # Validate delta bounds
        _validate_delta_bound(self.delta_coherence, "delta_coherence")
        _validate_delta_bound(self.delta_entropy, "delta_entropy")
        _validate_delta_bound(self.delta_drift, "delta_drift")

        if self.delta_schema_stability is not None:
            _validate_delta_bound(
                self.delta_schema_stability, "delta_schema_stability"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize scenario to dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "delta_coherence": self.delta_coherence,
            "delta_entropy": self.delta_entropy,
            "delta_drift": self.delta_drift,
            "delta_schema_stability": self.delta_schema_stability,
        }

    def is_identity(self) -> bool:
        """Check if this scenario produces no change (all deltas are zero)."""
        return (
            self.delta_coherence == 0.0 and
            self.delta_entropy == 0.0 and
            self.delta_drift == 0.0 and
            (self.delta_schema_stability is None or
             self.delta_schema_stability == 0.0)
        )


# ============================================================================
# DATACLASSES - Output Structures
# ============================================================================


@dataclass(frozen=True)
class CounterfactualResult:
    """
    Immutable result of a single counterfactual scenario simulation.

    This captures what happens to UCF and stability when a scenario's
    deltas are applied to the baseline state.

    Fields:
        scenario_id: ID of the scenario that was simulated
        ucf_delta: Change in UCF score (counterfactual - baseline)
        coherence_delta: Change in adjusted coherence
        stability_band_before: Stability band at baseline
        stability_band_after: Stability band after applying deltas
        risk_flags: List of detected risk conditions

    Invariants:
        - ucf_delta ∈ [-1.0, +1.0]
        - coherence_delta ∈ [-1.0, +1.0]
        - stability_band_before and stability_band_after are valid bands
        - risk_flags contains only valid flag strings
        - observer_only is always True
    """

    scenario_id: str
    ucf_delta: float
    coherence_delta: float
    stability_band_before: str
    stability_band_after: str
    risk_flags: Tuple[str, ...]

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Authority markers - MUST be True
    observer_only: bool = True

    def __post_init__(self) -> None:
        """Validate result invariants."""
        # INV-P25-1: observer_only must always be True
        if not self.observer_only:
            raise ValueError(
                "CounterfactualResult.observer_only must be True. "
                "P25 is observation-only."
            )

        # Validate scenario_id
        if not self.scenario_id or not self.scenario_id.strip():
            raise ValueError(
                "CounterfactualResult.scenario_id must be non-empty"
            )

        # Validate stability bands
        valid_bands = {"stable", "transitional", "unstable"}
        if self.stability_band_before not in valid_bands:
            raise ValueError(
                f"CounterfactualResult.stability_band_before must be one of "
                f"{valid_bands}, got '{self.stability_band_before}'"
            )
        if self.stability_band_after not in valid_bands:
            raise ValueError(
                f"CounterfactualResult.stability_band_after must be one of "
                f"{valid_bands}, got '{self.stability_band_after}'"
            )

    def band_changed(self) -> bool:
        """Check if stability band changed."""
        return self.stability_band_before != self.stability_band_after

    def has_risk_flags(self) -> bool:
        """Check if any risk flags were detected."""
        return len(self.risk_flags) > 0

    def has_flag(self, flag: str) -> bool:
        """Check if a specific risk flag is present."""
        return flag in self.risk_flags

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "ucf_delta": self.ucf_delta,
            "coherence_delta": self.coherence_delta,
            "stability_band_before": self.stability_band_before,
            "stability_band_after": self.stability_band_after,
            "risk_flags": list(self.risk_flags),
            "debug": self.debug,
            "observer_only": self.observer_only,
        }


@dataclass(frozen=True)
class CounterfactualSandboxReport:
    """
    Immutable report from the counterfactual sandbox.

    This is the primary output of Phase 25, containing baseline metrics
    and results from all simulated scenarios.

    Fields:
        baseline_ucf: UCF score at baseline (before any counterfactual)
        baseline_stability_band: Stability band at baseline
        results: List of CounterfactualResult for each scenario
        max_negative_delta: Largest negative UCF change across all scenarios
        max_positive_delta: Largest positive UCF change across all scenarios
        notes: Optional observational notes

    Invariants:
        - baseline_ucf ∈ [0.0, 1.0]
        - baseline_stability_band is valid
        - results is immutable tuple
        - observer_only is always True
        - architectural_phase is always "P25"
    """

    baseline_ucf: float
    baseline_stability_band: str
    results: Tuple[CounterfactualResult, ...]
    max_negative_delta: float
    max_positive_delta: float
    notes: Optional[str] = None

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Authority markers - MUST be True
    observer_only: bool = True
    architectural_phase: str = "P25"
    version: str = P25_VERSION

    def __post_init__(self) -> None:
        """Validate report invariants."""
        # INV-P25-1: observer_only must always be True
        if not self.observer_only:
            raise ValueError(
                "CounterfactualSandboxReport.observer_only must be True. "
                "P25 is observation-only."
            )

        # Validate baseline_ucf
        if not 0.0 <= self.baseline_ucf <= 1.0:
            raise ValueError(
                f"CounterfactualSandboxReport.baseline_ucf must be in "
                f"[0.0, 1.0], got {self.baseline_ucf}"
            )

        # Validate stability band
        valid_bands = {"stable", "transitional", "unstable"}
        if self.baseline_stability_band not in valid_bands:
            raise ValueError(
                f"CounterfactualSandboxReport.baseline_stability_band must be "
                f"one of {valid_bands}, got '{self.baseline_stability_band}'"
            )

        # Validate results is a tuple
        if not isinstance(self.results, tuple):
            raise ValueError(
                "CounterfactualSandboxReport.results must be a tuple"
            )

    def scenario_count(self) -> int:
        """Return the number of scenarios simulated."""
        return len(self.results)

    def get_result(self, scenario_id: str) -> Optional[CounterfactualResult]:
        """Get result for a specific scenario by ID."""
        for result in self.results:
            if result.scenario_id == scenario_id:
                return result
        return None

    def get_flagged_results(self) -> List[CounterfactualResult]:
        """Get all results that have risk flags."""
        return [r for r in self.results if r.has_risk_flags()]

    def get_band_change_results(self) -> List[CounterfactualResult]:
        """Get all results where stability band changed."""
        return [r for r in self.results if r.band_changed()]

    def has_any_flags(self) -> bool:
        """Check if any scenario produced risk flags."""
        return any(r.has_risk_flags() for r in self.results)

    def has_any_band_changes(self) -> bool:
        """Check if any scenario caused a stability band change."""
        return any(r.band_changed() for r in self.results)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary."""
        return {
            "baseline_ucf": self.baseline_ucf,
            "baseline_stability_band": self.baseline_stability_band,
            "results": [r.to_dict() for r in self.results],
            "max_negative_delta": self.max_negative_delta,
            "max_positive_delta": self.max_positive_delta,
            "notes": self.notes,
            "debug": self.debug,
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _validate_delta_bound(value: float, name: str) -> None:
    """
    Validate a delta value is within bounds.

    Args:
        value: Delta value to validate
        name: Name of the field for error messages

    Raises:
        ValueError: If value is outside [-1.0, +1.0]
    """
    if not DELTA_MIN <= value <= DELTA_MAX:
        raise ValueError(
            f"{name} must be in [{DELTA_MIN}, {DELTA_MAX}], got {value}"
        )


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] range.

    This is a pure function with no side effects.

    Args:
        value: Value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def create_scenario(
    scenario_id: str,
    delta_coherence: float = 0.0,
    delta_entropy: float = 0.0,
    delta_drift: float = 0.0,
    delta_schema_stability: Optional[float] = None,
) -> CounterfactualScenario:
    """
    Factory function to create a CounterfactualScenario.

    Args:
        scenario_id: Unique identifier for this scenario
        delta_coherence: Change to coherence_v3_quality [-1.0, +1.0]
        delta_entropy: Change to entropy_volatility [-1.0, +1.0]
        delta_drift: Change to drift_fusion_index [-1.0, +1.0]
        delta_schema_stability: Optional change to schema_stability [-1.0, +1.0]

    Returns:
        A validated CounterfactualScenario instance
    """
    return CounterfactualScenario(
        scenario_id=scenario_id,
        delta_coherence=clamp(delta_coherence, DELTA_MIN, DELTA_MAX),
        delta_entropy=clamp(delta_entropy, DELTA_MIN, DELTA_MAX),
        delta_drift=clamp(delta_drift, DELTA_MIN, DELTA_MAX),
        delta_schema_stability=(
            clamp(delta_schema_stability, DELTA_MIN, DELTA_MAX)
            if delta_schema_stability is not None else None
        ),
    )


def create_result(
    scenario_id: str,
    ucf_delta: float,
    coherence_delta: float,
    stability_band_before: str,
    stability_band_after: str,
    risk_flags: List[str],
    debug: Optional[Dict[str, Any]] = None,
) -> CounterfactualResult:
    """
    Factory function to create a CounterfactualResult.

    Args:
        scenario_id: ID of the scenario that was simulated
        ucf_delta: Change in UCF score
        coherence_delta: Change in adjusted coherence
        stability_band_before: Stability band at baseline
        stability_band_after: Stability band after applying deltas
        risk_flags: List of detected risk conditions
        debug: Optional debug dictionary

    Returns:
        A validated CounterfactualResult instance
    """
    return CounterfactualResult(
        scenario_id=scenario_id,
        ucf_delta=ucf_delta,
        coherence_delta=coherence_delta,
        stability_band_before=stability_band_before,
        stability_band_after=stability_band_after,
        risk_flags=tuple(risk_flags),
        debug=debug or {},
        observer_only=True,
    )


def create_report(
    baseline_ucf: float,
    baseline_stability_band: str,
    results: List[CounterfactualResult],
    notes: Optional[str] = None,
    debug: Optional[Dict[str, Any]] = None,
) -> CounterfactualSandboxReport:
    """
    Factory function to create a CounterfactualSandboxReport.

    Args:
        baseline_ucf: UCF score at baseline
        baseline_stability_band: Stability band at baseline
        results: List of CounterfactualResult for each scenario
        notes: Optional observational notes
        debug: Optional debug dictionary

    Returns:
        A validated CounterfactualSandboxReport instance
    """
    # Compute max deltas
    ucf_deltas = [r.ucf_delta for r in results] if results else [0.0]
    max_negative_delta = min(ucf_deltas)
    max_positive_delta = max(ucf_deltas)

    return CounterfactualSandboxReport(
        baseline_ucf=baseline_ucf,
        baseline_stability_band=baseline_stability_band,
        results=tuple(results),
        max_negative_delta=max_negative_delta,
        max_positive_delta=max_positive_delta,
        notes=notes,
        debug=debug or {},
        observer_only=True,
    )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Version
    "P25_VERSION",
    # Constants
    "DELTA_MIN",
    "DELTA_MAX",
    "STABILITY_DROP_THRESHOLD",
    "ENTROPY_SPIKE_THRESHOLD",
    "DRIFT_ACCELERATION_THRESHOLD",
    "UCF_THRESHOLD_CROSS_STABLE",
    "UCF_THRESHOLD_CROSS_TRANSITIONAL",
    # Dataclasses
    "CounterfactualScenario",
    "CounterfactualResult",
    "CounterfactualSandboxReport",
    # Helpers
    "clamp",
    "create_scenario",
    "create_result",
    "create_report",
]
