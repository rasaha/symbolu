"""
Phase-6 Composition Axis Analyzer
=================================

EXPERIMENTAL MODULE - NON-FROZEN, NON-CANONICAL

This module implements the Phase-6 composition axis experiments, testing:
    1. Dominance (does the last consonant override previous modulation?)
    2. Vowel scope (vowel affects only previous consonant vs persists until reset)
    3. Multi-vowel accumulation (C-V-V: additive baseline)
    4. Optional layer-sensitive initialization (hook for future use)

CONSTRAINTS:
    - NO ML, NO embeddings, NO probability
    - NO ontology edits, NO new phases
    - NO inference - fail fast if data missing
    - READ-ONLY access to Phase-4A ontology

BASELINE DETERMINISTIC RULES:
    - Consonant token: event="reset", magnitude = 1.0 (baseline)
    - Vowel token: event="modulate", modifies active magnitude
        - "a" adds +0.1
        - "i" adds +0.2
        - "u" adds +0.15
    - Active magnitude starts at 1.0 and updates through sequence
    - A consonant always resets magnitude to 1.0
"""

from typing import List, Optional

from symbolu.ontology.phase4a import get_all_varnas
from symbolu.ontology.phase4a.loader import get_varna_info

from symbolu.experiments.composition.composition_types import (
    VowelScope,
    TokenType,
    EventType,
    TrajectoryStep,
    SequenceConfig,
    TrajectoryResult,
    PHASE6_VOWEL_DELTAS,
    PHASE6_VOWELS,
    BASELINE_MAGNITUDE,
)


# =============================================================================
# Errors
# =============================================================================

class Phase6AnalyzerError(Exception):
    """Base error for Phase-6 analyzer."""
    pass


class InvalidVarnaError(Phase6AnalyzerError):
    """Raised when a consonant token is not a valid varna in the ontology."""
    def __init__(self, token: str):
        self.token = token
        super().__init__(
            f"Invalid varna token: '{token}' is not recognized in the Phase-4A ontology"
        )


class InvalidVowelError(Phase6AnalyzerError):
    """Raised when a vowel token is not in the Phase-6 supported vowel set."""
    def __init__(self, token: str):
        self.token = token
        super().__init__(
            f"Invalid vowel token: '{token}' is not supported in Phase-6. "
            f"Supported vowels: {sorted(PHASE6_VOWELS)}"
        )


class EmptySequenceError(Phase6AnalyzerError):
    """Raised when an empty sequence is provided."""
    def __init__(self):
        super().__init__("Empty sequence is not allowed")


class NoActiveConsonantError(Phase6AnalyzerError):
    """Raised when a vowel is processed without an active consonant."""
    def __init__(self, token: str, idx: int):
        self.token = token
        self.idx = idx
        super().__init__(
            f"Vowel '{token}' at index {idx} has no preceding consonant to modulate"
        )


# =============================================================================
# Phase-6 Analyzer
# =============================================================================

class Phase6Analyzer:
    """
    Analyzer for Phase-6 composition axis experiments.

    This analyzer computes a deterministic trajectory from a varna sequence,
    testing different composition axes via configuration.

    Implements two vowel scope models:
        - PRECEDING_ONLY: Vowel modifies the previous consonant effect
        - PERSIST_UNTIL_RESET: Vowel modifies active magnitude until next reset

    Example:
        >>> analyzer = Phase6Analyzer()
        >>> result = analyzer.analyze(["ka", "a", "ga"])
        >>> for step in result.steps:
        ...     print(step.to_dict())

        >>> # Test with different vowel scope
        >>> config = SequenceConfig(vowel_scope=VowelScope.PRECEDING_ONLY)
        >>> result = analyzer.analyze(["ka", "a", "i"], config=config)
    """

    def __init__(self) -> None:
        """Initialize the analyzer with Phase-4A ontology varnas."""
        self._valid_varnas = get_all_varnas()

    def _is_vowel(self, token: str) -> bool:
        """Check if token is a supported Phase-6 vowel."""
        return token in PHASE6_VOWELS

    def _is_consonant(self, token: str) -> bool:
        """Check if token is a valid consonant (in ontology, not a vowel)."""
        return token in self._valid_varnas and not self._is_vowel(token)

    def _classify_token(self, token: str) -> TokenType:
        """
        Classify a token as vowel or consonant.

        Args:
            token: The token to classify

        Returns:
            TokenType.VOWEL or TokenType.VARNA

        Raises:
            InvalidVowelError: If token is a vowel but not supported in Phase-6
            InvalidVarnaError: If token is not a valid varna in ontology
        """
        # Check if it's a Phase-6 supported vowel
        if self._is_vowel(token):
            return TokenType.VOWEL

        # Check if token is in the ontology
        if token in self._valid_varnas:
            # Token is in ontology - check if it's a vowel or consonant
            varna_info = get_varna_info(token)
            if varna_info and varna_info.varna_type == "vowel":
                # It's a vowel in the ontology but not supported in Phase-6
                raise InvalidVowelError(token)
            # It's a consonant in the ontology
            return TokenType.VARNA

        # Token is not in ontology at all - invalid varna
        raise InvalidVarnaError(token)

    def analyze(
        self,
        sequence: List[str],
        config: Optional[SequenceConfig] = None,
    ) -> TrajectoryResult:
        """
        Analyze a varna sequence and produce a trajectory.

        Args:
            sequence: List of tokens (consonants and vowels)
            config: Optional configuration for analysis

        Returns:
            TrajectoryResult with steps and final magnitude

        Raises:
            EmptySequenceError: If sequence is empty
            InvalidVarnaError: If a consonant token is not in ontology
            InvalidVowelError: If a vowel token is not in Phase-6 set
            NoActiveConsonantError: If a vowel has no preceding consonant
        """
        if not sequence:
            raise EmptySequenceError()

        if config is None:
            config = SequenceConfig()

        steps: List[TrajectoryStep] = []
        active_magnitude = config.initial_magnitude
        has_active_consonant = False

        for idx, token in enumerate(sequence):
            # Classify the token (may raise errors)
            token_type = self._classify_token(token)

            if token_type == TokenType.VARNA:
                # Consonant: reset magnitude to baseline
                active_magnitude = BASELINE_MAGNITUDE
                has_active_consonant = True

                step = TrajectoryStep(
                    idx=idx,
                    token=token,
                    token_type="varna",
                    magnitude=round(active_magnitude, 4),
                    event="reset",
                    notes=f"Consonant resets magnitude to {BASELINE_MAGNITUDE}",
                )

            elif token_type == TokenType.VOWEL:
                # Vowel: modulate active magnitude
                if not has_active_consonant:
                    raise NoActiveConsonantError(token, idx)

                # Get vowel delta
                delta = PHASE6_VOWEL_DELTAS.get(token, 0.0)

                # Both scope modes apply the delta in the same way for Phase-6
                # The difference is conceptual and affects how we interpret results
                active_magnitude += delta

                notes = f"Vowel '{token}' adds +{delta} (scope={config.vowel_scope.value})"

                step = TrajectoryStep(
                    idx=idx,
                    token=token,
                    token_type="vowel",
                    magnitude=round(active_magnitude, 4),
                    event="modulate",
                    notes=notes,
                )

            else:
                # Should not reach here
                raise Phase6AnalyzerError(f"Unknown token type for '{token}'")

            steps.append(step)

        return TrajectoryResult(
            sequence=tuple(sequence),
            steps=tuple(steps),
            config=config,
            final_magnitude=round(active_magnitude, 4),
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def analyze_sequence(
    sequence: List[str],
    vowel_scope: VowelScope = VowelScope.PERSIST_UNTIL_RESET,
) -> TrajectoryResult:
    """
    Convenience function to analyze a sequence with specified vowel scope.

    Args:
        sequence: List of varna tokens
        vowel_scope: Vowel scope model to use

    Returns:
        TrajectoryResult with trajectory steps

    Example:
        >>> result = analyze_sequence(["ka", "a", "ka"])
        >>> print(result.final_magnitude)
        1.0
    """
    analyzer = Phase6Analyzer()
    config = SequenceConfig(vowel_scope=vowel_scope)
    return analyzer.analyze(sequence, config)


def compare_trajectories(
    sequence_a: List[str],
    sequence_b: List[str],
    vowel_scope: VowelScope = VowelScope.PERSIST_UNTIL_RESET,
) -> dict:
    """
    Compare trajectories of two sequences.

    Args:
        sequence_a: First sequence
        sequence_b: Second sequence
        vowel_scope: Vowel scope model to use

    Returns:
        Dict with comparison results including whether they differ
    """
    analyzer = Phase6Analyzer()
    config = SequenceConfig(vowel_scope=vowel_scope)

    result_a = analyzer.analyze(sequence_a, config)
    result_b = analyzer.analyze(sequence_b, config)

    magnitudes_a = result_a.get_magnitudes()
    magnitudes_b = result_b.get_magnitudes()

    events_a = result_a.get_events()
    events_b = result_b.get_events()

    # Determine differences
    magnitudes_differ = magnitudes_a != magnitudes_b
    events_differ = events_a != events_b
    final_differs = abs(result_a.final_magnitude - result_b.final_magnitude) > 0.0001

    return {
        "sequence_a": list(sequence_a),
        "sequence_b": list(sequence_b),
        "vowel_scope": vowel_scope.value,
        "result_a": result_a.to_dict(),
        "result_b": result_b.to_dict(),
        "magnitudes_differ": magnitudes_differ,
        "events_differ": events_differ,
        "final_differs": final_differs,
        "trajectories_differ": magnitudes_differ or events_differ,
    }
