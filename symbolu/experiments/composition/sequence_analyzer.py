"""
Varna Sequence Analyzer
=======================

EXPERIMENTAL MODULE - NON-FROZEN, NON-CANONICAL

This module implements a minimal pressure-state analyzer for varna sequences.
It exists solely to test the hypothesis:

    Does positional arrangement of the SAME varnas produce different
    pressure trajectories?

CONSTRAINTS:
    - NO ML, NO embeddings, NO probability
    - NO ontology edits, NO new phases
    - NO inference - fail fast if data missing
    - READ-ONLY access to Phase-4A ontology

RULES:
    - Consonants are pressure initiators
    - Vowels are pressure modulators
    - Pressure state is stateful across steps
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from symbolu.ontology.phase4a import lookup_interaction
from symbolu.ontology.phase4a.loader import get_all_varnas


# =============================================================================
# Constants
# =============================================================================

# Hardcoded vowel set for this experiment (as specified)
EXPERIMENT_VOWELS = frozenset({"a", "i", "u", "e", "o", "ai", "au"})

# The ontological layer used for pressure initialization
FORMING_LAYER = "O4_STRUCTURE"

# Vector mapping from ontology distortion_vector values
# These are the known values from the frozen ontology
VECTOR_MAP = {
    "lateral": "lateral",
    "downward": "downward",
    "upward": "upward",
    # Add fallback for any unexpected values
}

# Default magnitude for pressure initialization
DEFAULT_MAGNITUDE = 1.0

# Vowel modulation factors (deterministic, toy values)
VOWEL_MODULATION = {
    "a": {"magnitude_delta": 0.1, "vector_shift": None},      # Open vowel - slight increase
    "i": {"magnitude_delta": -0.05, "vector_shift": None},    # High front - slight decrease
    "u": {"magnitude_delta": -0.05, "vector_shift": None},    # High back - slight decrease
    "e": {"magnitude_delta": 0.0, "vector_shift": None},      # Mid front - neutral
    "o": {"magnitude_delta": 0.0, "vector_shift": None},      # Mid back - neutral
    "ai": {"magnitude_delta": 0.15, "vector_shift": None},    # Diphthong - larger increase
    "au": {"magnitude_delta": 0.15, "vector_shift": None},    # Diphthong - larger increase
}


# =============================================================================
# Errors
# =============================================================================

class SequenceAnalyzerError(Exception):
    """Base error for sequence analyzer."""
    pass


class InvalidTokenError(SequenceAnalyzerError):
    """Raised when a token is not a valid varna."""
    def __init__(self, token: str):
        self.token = token
        super().__init__(f"Invalid token: '{token}' is not a recognized varna")


class NoActivePressureError(SequenceAnalyzerError):
    """Raised when a vowel is processed without active pressure."""
    def __init__(self, token: str, step: int):
        self.token = token
        self.step = step
        super().__init__(
            f"Cannot modulate pressure at step {step}: vowel '{token}' encountered "
            "but no active pressure exists (no preceding consonant)"
        )


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class PressureState:
    """
    Current pressure state during sequence processing.

    Attributes:
        active_varna: The consonant that initiated current pressure (None if no pressure)
        vector: Direction of pressure ("upward", "downward", "lateral")
        magnitude: Intensity of pressure (toy value, starts at 1.0)
    """
    active_varna: Optional[str] = None
    vector: str = "lateral"  # Default, will be overwritten
    magnitude: float = 0.0

    def is_active(self) -> bool:
        """Check if pressure is currently active."""
        return self.active_varna is not None

    def copy(self) -> "PressureState":
        """Create a copy of the current state."""
        return PressureState(
            active_varna=self.active_varna,
            vector=self.vector,
            magnitude=self.magnitude,
        )


@dataclass
class TraceEntry:
    """
    A single step in the pressure trace.

    Attributes:
        step: Step number (0-indexed)
        token: The varna token processed
        role: "consonant" or "vowel"
        vector: Current pressure vector after this step
        magnitude: Current pressure magnitude after this step
    """
    step: int
    token: str
    role: str  # "consonant" | "vowel"
    vector: str
    magnitude: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict for serialization."""
        return {
            "step": self.step,
            "token": self.token,
            "role": self.role,
            "vector": self.vector,
            "magnitude": self.magnitude,
        }


# =============================================================================
# Sequence Analyzer
# =============================================================================

class SequenceAnalyzer:
    """
    Analyzes varna sequences for pressure trajectories.

    EXPERIMENTAL - This class exists solely to test positional non-commutativity.

    Rules:
        - Consonants initialize/reassert pressure using O4_STRUCTURE ontology data
        - Vowels modulate existing pressure (magnitude and/or vector)
        - Vowels cannot introduce new pressure by themselves
        - State is tracked across the entire sequence

    Example:
        >>> analyzer = SequenceAnalyzer()
        >>> trace = analyzer.analyze(["ka", "a", "ka"])
        >>> for entry in trace:
        ...     print(entry.to_dict())
    """

    def __init__(self) -> None:
        """Initialize the analyzer."""
        self._valid_varnas = get_all_varnas()

    def _is_vowel(self, token: str) -> bool:
        """Check if token is a vowel (using hardcoded experiment set)."""
        return token in EXPERIMENT_VOWELS

    def _is_consonant(self, token: str) -> bool:
        """Check if token is a consonant (in ontology and not a vowel)."""
        return token in self._valid_varnas and not self._is_vowel(token)

    def _validate_token(self, token: str) -> None:
        """
        Validate that a token is a recognized varna.

        Args:
            token: The token to validate

        Raises:
            InvalidTokenError: If token is not in ontology and not an experiment vowel
        """
        # Accept if it's an experiment vowel (may not be in ontology)
        if token in EXPERIMENT_VOWELS:
            return
        # Accept if it's in the ontology
        if token in self._valid_varnas:
            return
        # Reject unknown tokens
        raise InvalidTokenError(token)

    def _get_consonant_vector(self, token: str) -> str:
        """
        Get the pressure vector for a consonant from O4_STRUCTURE layer.

        Args:
            token: The consonant token

        Returns:
            The distortion_vector from the ontology

        Raises:
            Phase4A errors if lookup fails
        """
        interaction = lookup_interaction(token, FORMING_LAYER)
        vector = interaction.distortion_vector
        return VECTOR_MAP.get(vector, vector)

    def _process_consonant(
        self,
        token: str,
        state: PressureState,
    ) -> PressureState:
        """
        Process a consonant token - initialize or reassert pressure.

        Args:
            token: The consonant token
            state: Current pressure state

        Returns:
            New pressure state after processing
        """
        new_state = state.copy()
        new_state.active_varna = token
        new_state.vector = self._get_consonant_vector(token)
        new_state.magnitude = DEFAULT_MAGNITUDE
        return new_state

    def _process_vowel(
        self,
        token: str,
        state: PressureState,
        step: int,
    ) -> PressureState:
        """
        Process a vowel token - modulate existing pressure.

        Args:
            token: The vowel token
            state: Current pressure state
            step: Current step number (for error messages)

        Returns:
            New pressure state after modulation

        Raises:
            NoActivePressureError: If no active pressure exists
        """
        if not state.is_active():
            raise NoActivePressureError(token, step)

        new_state = state.copy()

        # Apply vowel modulation
        modulation = VOWEL_MODULATION.get(token, {"magnitude_delta": 0.0, "vector_shift": None})
        new_state.magnitude += modulation["magnitude_delta"]

        # Vector shift if specified (not used in basic experiment)
        if modulation.get("vector_shift"):
            new_state.vector = modulation["vector_shift"]

        return new_state

    def analyze(self, sequence: List[str]) -> List[TraceEntry]:
        """
        Analyze a varna sequence and produce a pressure trace.

        Args:
            sequence: List of varna tokens (e.g., ["ka", "a", "ka"])

        Returns:
            List of TraceEntry objects recording each step

        Raises:
            InvalidTokenError: If any token is not recognized
            NoActivePressureError: If a vowel has no preceding consonant
        """
        if not sequence:
            return []

        trace: List[TraceEntry] = []
        state = PressureState()

        for step, token in enumerate(sequence):
            # Validate token
            self._validate_token(token)

            # Determine role and process
            if self._is_vowel(token):
                role = "vowel"
                state = self._process_vowel(token, state, step)
            else:
                role = "consonant"
                state = self._process_consonant(token, state)

            # Record trace entry
            entry = TraceEntry(
                step=step,
                token=token,
                role=role,
                vector=state.vector,
                magnitude=round(state.magnitude, 4),  # Avoid floating point noise
            )
            trace.append(entry)

        return trace


# =============================================================================
# Convenience Function
# =============================================================================

def analyze_sequence(sequence: List[str]) -> List[Dict[str, Any]]:
    """
    Convenience function to analyze a sequence and return dict traces.

    Args:
        sequence: List of varna tokens

    Returns:
        List of trace entry dicts

    Example:
        >>> trace = analyze_sequence(["ka", "a", "ka"])
        >>> print(trace[0])
        {'step': 0, 'token': 'ka', 'role': 'consonant', 'vector': 'lateral', 'magnitude': 1.0}
    """
    analyzer = SequenceAnalyzer()
    trace = analyzer.analyze(sequence)
    return [entry.to_dict() for entry in trace]
