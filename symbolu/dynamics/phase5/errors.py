"""
Phase-5 Error Types
===================

Explicit error types for Phase-5 dynamics failures.

Phase-5 errors are fail-fast: they indicate either:
    1. Invalid input (bad varna/layer/config)
    2. Invariant violations (attempts to modify ontology)

Phase-5 NEVER infers, smooths, or compensates.
"""

from typing import Optional, Tuple


class Phase5Error(Exception):
    """
    Base exception for all Phase-5 failures.

    Phase-5 errors are always fatal and indicate
    configuration or invariant issues.
    """

    def __init__(self, message: str, context: Optional[dict] = None):
        self.message = message
        self.context = context or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if not self.context:
            return f"[Phase-5 Error] {self.message}"
        ctx_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
        return f"[Phase-5 Error] {self.message} | Context: {ctx_str}"


class Phase5InvariantViolation(Phase5Error):
    """
    Raised when a critical Phase-5 invariant is violated.

    Invariants:
        - NO_ONTOLOGY_WRITE: Cannot modify ontology files
        - NO_ONTOLOGY_INFERENCE: Cannot invent meanings
        - NO_POLARITY_REINTERPRETATION: Cannot change polarity labels
        - NO_SMOOTHING_FLATNESS: Cannot artificially smooth flat gradients

    These violations indicate a programming error in Phase-5 itself.
    """

    # Defined invariants
    NO_ONTOLOGY_WRITE = "NO_ONTOLOGY_WRITE"
    NO_ONTOLOGY_INFERENCE = "NO_ONTOLOGY_INFERENCE"
    NO_POLARITY_REINTERPRETATION = "NO_POLARITY_REINTERPRETATION"
    NO_SMOOTHING_FLATNESS = "NO_SMOOTHING_FLATNESS"

    VALID_INVARIANTS = frozenset({
        NO_ONTOLOGY_WRITE,
        NO_ONTOLOGY_INFERENCE,
        NO_POLARITY_REINTERPRETATION,
        NO_SMOOTHING_FLATNESS,
    })

    def __init__(self, invariant: str, detail: str = ""):
        if invariant not in self.VALID_INVARIANTS:
            invariant = f"UNKNOWN({invariant})"

        message = f"Invariant violation: {invariant}"
        if detail:
            message += f" — {detail}"

        super().__init__(
            message,
            context={"invariant": invariant, "detail": detail}
        )
        self.invariant = invariant
        self.detail = detail


class Phase5InvalidVarnaError(Phase5Error):
    """
    Raised when a requested varna is invalid.

    Phase-5 validates varnas through Phase-4A.
    This error indicates the varna does not exist in the frozen ontology.
    """

    def __init__(self, varna: str, reason: str = ""):
        message = f"Invalid varna '{varna}'"
        if reason:
            message += f": {reason}"

        super().__init__(
            message,
            context={"varna": varna, "reason": reason}
        )
        self.varna = varna
        self.reason = reason


class Phase5InvalidLayerError(Phase5Error):
    """
    Raised when a requested layer is invalid.

    Valid layers are O1_POTENTIAL through O12_ABSOLVING.
    """

    VALID_LAYERS = (
        "O1_POTENTIAL",
        "O2_IDENTITY",
        "O3_EXECUTION",
        "O4_STRUCTURE",
        "O5_COGNITION",
        "O6_AGENCY",
        "O7_REASONING",
        "O8_PURPOSE",
        "O9_WITNESSES",
        "O10_UNIFYING",
        "O11_INTEGRATION",
        "O12_ABSOLVING",
    )

    def __init__(self, layer: str, reason: str = ""):
        message = f"Invalid layer '{layer}'"
        if reason:
            message += f": {reason}"

        super().__init__(
            message,
            context={
                "layer": layer,
                "reason": reason,
                "valid_layers": self.VALID_LAYERS,
            }
        )
        self.layer = layer
        self.reason = reason


class Phase5InvalidConfigError(Phase5Error):
    """
    Raised when dynamics configuration is invalid.

    Configuration parameters have strict bounds to ensure
    deterministic, meaningful dynamics.
    """

    def __init__(self, param: str, value: object, constraint: str):
        super().__init__(
            f"Invalid config parameter '{param}'={value!r}: {constraint}",
            context={
                "param": param,
                "value": value,
                "constraint": constraint,
            }
        )
        self.param = param
        self.value = value
        self.constraint = constraint


class Phase5OntologyAccessError(Phase5Error):
    """
    Raised when Phase-5 attempts to access ontology directly.

    Phase-5 MUST access ontology ONLY through Phase-4A.
    Direct file access is an invariant violation.
    """

    def __init__(self, attempted_path: str):
        super().__init__(
            f"Direct ontology access forbidden: {attempted_path}",
            context={"attempted_path": attempted_path}
        )
        self.attempted_path = attempted_path


class Phase5TerminationError(Phase5Error):
    """
    Raised when an invalid operation is attempted after termination.

    Once O10_ABSOLVING terminates a trajectory, no further
    evolution is possible without explicit restart.
    """

    def __init__(self, attempted_operation: str):
        super().__init__(
            f"Operation '{attempted_operation}' not allowed after termination",
            context={"attempted_operation": attempted_operation}
        )
        self.attempted_operation = attempted_operation
