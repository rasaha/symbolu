"""
Phase-7 Targeted Generation - Main Executor

Orchestrates the four-stage execution pipeline:
Generate → Simulate → Score → Select
"""

from typing import Dict, Any, List, Tuple, Optional, FrozenSet

from .types import (
    TargetSpec,
    GenerationConfig,
    SelectionConfig,
    Phase7Result,
    RankedResult,
    ExecutionMetadata,
    ExecutionError,
    CompletenessReport,
    TrajectoryResult,
    TrajectoryStep,
    ScoringMode,
    ErrorType,
    ConstraintField,
)
from .constraints import (
    parse_target_spec,
    validate_target_spec,
    detect_contradictions,
)
from .generator import generate_candidates, generate_candidates_filtered
from .scorer import score_trajectory, score_sequence_constraint
from .selector import select_results
from .completeness import validate_completeness
from .errors import (
    Phase7Error,
    Phase7ValidationError,
    Phase7SimulationError,
    create_error,
)


# Phase-6 vowel deltas (from Phase-6 implementation)
PHASE6_VOWEL_DELTAS = {
    "a": 0.1,
    "i": 0.2,
    "u": 0.15,
}


def execute_phase7(
    target: Dict[str, Any],
    generation_config: Dict[str, Any],
    selection_config: Dict[str, Any],
) -> Phase7Result:
    """
    Main Phase-7 execution entry point.

    Args:
        target: Raw target specification dictionary
        generation_config: Raw generation configuration dictionary
        selection_config: Raw selection configuration dictionary

    Returns:
        Complete Phase7Result with results, metadata, errors, completeness

    Notes:
        - This is the primary public API
        - All inputs are validated before processing
        - Execution is fully deterministic
        - No exceptions escape; all errors in result.errors
    """
    errors: List[ExecutionError] = []

    # Parse and validate configuration
    try:
        gen_config = _parse_generation_config(generation_config)
        sel_config = _parse_selection_config(selection_config)
    except Phase7ValidationError as e:
        return _error_result(e.to_execution_error())

    # Parse and validate target
    try:
        spec = parse_target_spec(target)
        validate_target_spec(spec)
    except Phase7ValidationError as e:
        return _error_result(e.to_execution_error())

    # Check for contradictions
    contradiction = detect_contradictions(spec)
    if contradiction is not None:
        return _error_result(contradiction)

    # Validate completeness (advisory)
    completeness = validate_completeness(spec, gen_config)

    # Extract sequence-level constraints for filtering
    exclude_sequences, prefix, suffix = _extract_sequence_constraints(spec)

    # Stage 1: GENERATE
    if exclude_sequences or prefix or suffix:
        candidates = tuple(generate_candidates_filtered(
            gen_config,
            exclude_sequences=exclude_sequences,
            prefix=prefix,
            suffix=suffix,
        ))
    else:
        candidates = tuple(generate_candidates(gen_config))

    candidates_generated = len(candidates)

    # Stage 2: SIMULATE
    simulated: List[Tuple[Tuple[str, ...], TrajectoryResult]] = []
    for seq in candidates:
        try:
            trajectory = _simulate_sequence(seq, gen_config)
            simulated.append((seq, trajectory))
        except Phase7SimulationError as e:
            errors.append(e.to_execution_error())

    candidates_simulated = len(simulated)

    # Stage 3: SCORE
    scored: List[Tuple[Tuple[str, ...], TrajectoryResult, float]] = []
    for seq, trajectory in simulated:
        score = score_trajectory(trajectory, spec, sel_config.scoring_mode)

        # Also check sequence-level constraints
        for constraint in spec.constraints:
            if constraint.field in (ConstraintField.SEQUENCE_NOT_IN,
                                    ConstraintField.SEQUENCE_STARTS_WITH,
                                    ConstraintField.SEQUENCE_ENDS_WITH):
                seq_satisfied, seq_distance = score_sequence_constraint(
                    seq, constraint.field, constraint.value
                )
                if not seq_satisfied:
                    if sel_config.scoring_mode == ScoringMode.BINARY:
                        score = 0.0
                    else:
                        score += seq_distance

        scored.append((seq, trajectory, score))

    # Count satisfying candidates
    if sel_config.scoring_mode == ScoringMode.BINARY:
        candidates_satisfying = sum(1 for _, _, s in scored if s >= 1.0)
    else:
        candidates_satisfying = sum(1 for _, _, s in scored if s == 0.0)

    # Stage 4: SELECT
    results = select_results(scored, sel_config)

    # Build metadata
    metadata = ExecutionMetadata(
        candidates_generated=candidates_generated,
        candidates_simulated=candidates_simulated,
        candidates_satisfying=candidates_satisfying,
        execution_deterministic=True,
        target_feasible=candidates_satisfying > 0,
    )

    return Phase7Result(
        results=results,
        metadata=metadata,
        errors=tuple(errors),
        completeness=completeness,
    )


def _parse_generation_config(raw: Dict[str, Any]) -> GenerationConfig:
    """Parse raw generation config dictionary."""
    max_seq_len = raw.get("max_sequence_length")
    if max_seq_len is None or not isinstance(max_seq_len, int) or max_seq_len < 1:
        raise Phase7ValidationError(
            ErrorType.INVALID_CONSTRAINT_PATTERN,
            "generation_config.max_sequence_length must be a positive integer",
            field="max_sequence_length",
        )

    max_candidates = raw.get("max_candidates")
    if max_candidates is not None and (not isinstance(max_candidates, int) or max_candidates < 1):
        raise Phase7ValidationError(
            ErrorType.INVALID_CONSTRAINT_PATTERN,
            "generation_config.max_candidates must be a positive integer or null",
            field="max_candidates",
        )

    vowel_set = raw.get("vowel_set", {"a", "i", "u"})
    if isinstance(vowel_set, (list, tuple)):
        vowel_set = set(vowel_set)
    vowel_set = frozenset(vowel_set)

    consonant_set = raw.get("consonant_set", {"ka", "ga", "ta", "da", "pa", "ba"})
    if isinstance(consonant_set, (list, tuple)):
        consonant_set = set(consonant_set)
    consonant_set = frozenset(consonant_set)

    return GenerationConfig(
        max_sequence_length=max_seq_len,
        max_candidates=max_candidates,
        vowel_set=vowel_set,
        consonant_set=consonant_set,
    )


def _parse_selection_config(raw: Dict[str, Any]) -> SelectionConfig:
    """Parse raw selection config dictionary."""
    max_results = raw.get("max_results", 100)
    if not isinstance(max_results, int) or max_results < 1:
        raise Phase7ValidationError(
            ErrorType.INVALID_CONSTRAINT_PATTERN,
            "selection_config.max_results must be a positive integer",
            field="max_results",
        )

    score_threshold = raw.get("score_threshold")

    scoring_mode_str = raw.get("scoring_mode", "binary")
    if scoring_mode_str == "binary":
        scoring_mode = ScoringMode.BINARY
    elif scoring_mode_str == "distance":
        scoring_mode = ScoringMode.DISTANCE
    else:
        raise Phase7ValidationError(
            ErrorType.INVALID_CONSTRAINT_PATTERN,
            f"Invalid scoring_mode: {scoring_mode_str}",
            field="scoring_mode",
        )

    return SelectionConfig(
        max_results=max_results,
        score_threshold=score_threshold,
        scoring_mode=scoring_mode,
    )


def _extract_sequence_constraints(spec: TargetSpec) -> Tuple[
    Optional[FrozenSet[Tuple[str, ...]]],
    Optional[Tuple[str, ...]],
    Optional[Tuple[str, ...]],
]:
    """
    Extract sequence-level constraints for generation filtering.

    Returns:
        (exclude_sequences, prefix, suffix)
    """
    exclude_sequences = None
    prefix = None
    suffix = None

    for constraint in spec.constraints:
        if constraint.field == ConstraintField.SEQUENCE_NOT_IN:
            if isinstance(constraint.value, (set, frozenset)):
                exclude_sequences = frozenset(
                    tuple(s) if isinstance(s, list) else s
                    for s in constraint.value
                )
            elif isinstance(constraint.value, (list, tuple)):
                exclude_sequences = frozenset(
                    tuple(s) if isinstance(s, list) else s
                    for s in constraint.value
                )

        elif constraint.field == ConstraintField.SEQUENCE_STARTS_WITH:
            if isinstance(constraint.value, (list, tuple)):
                prefix = tuple(constraint.value)

        elif constraint.field == ConstraintField.SEQUENCE_ENDS_WITH:
            if isinstance(constraint.value, (list, tuple)):
                suffix = tuple(constraint.value)

    return exclude_sequences, prefix, suffix


def _simulate_sequence(
    sequence: Tuple[str, ...],
    config: GenerationConfig,
) -> TrajectoryResult:
    """
    Simulate a sequence using Phase-6 mechanics.

    This is a local implementation of Phase-6 trajectory analysis
    to avoid circular dependencies.
    """
    steps: List[TrajectoryStep] = []
    magnitude = 1.0

    for idx, token in enumerate(sequence):
        if token in config.consonant_set:
            # Consonant: RESET
            magnitude = 1.0
            step = TrajectoryStep(
                idx=idx,
                token=token,
                token_type="consonant",
                magnitude=magnitude,
                event="reset",
            )
        elif token in config.vowel_set:
            # Vowel: MODULATE
            delta = PHASE6_VOWEL_DELTAS.get(token, 0.1)
            magnitude += delta
            step = TrajectoryStep(
                idx=idx,
                token=token,
                token_type="vowel",
                magnitude=magnitude,
                event="modulate",
            )
        else:
            raise Phase7SimulationError(
                ErrorType.SIMULATION_FAILURE,
                f"Invalid token: {token}",
                sequence=sequence,
            )

        steps.append(step)

    return TrajectoryResult(
        sequence=sequence,
        steps=tuple(steps),
        final_magnitude=magnitude,
    )


def _error_result(error: ExecutionError) -> Phase7Result:
    """Create an error result with no results."""
    return Phase7Result(
        results=tuple(),
        metadata=ExecutionMetadata(
            candidates_generated=0,
            candidates_simulated=0,
            candidates_satisfying=0,
            execution_deterministic=True,
            target_feasible=False,
        ),
        errors=(error,),
        completeness=CompletenessReport(
            level=CompletenessReport.__class__,  # This will be overwritten
            discrimination_ratio=0.0,
            bounded=False,
            trivial=False,
            plurality_estimate=None,
            warnings=tuple(),
        ),
    )


# Re-define error result with proper completeness
def _error_result(error: ExecutionError) -> Phase7Result:
    """Create an error result with no results."""
    from .types import CompletenessLevel, PluralityEstimate

    return Phase7Result(
        results=tuple(),
        metadata=ExecutionMetadata(
            candidates_generated=0,
            candidates_simulated=0,
            candidates_satisfying=0,
            execution_deterministic=True,
            target_feasible=False,
        ),
        errors=(error,),
        completeness=CompletenessReport(
            level=CompletenessLevel.INVALID,
            discrimination_ratio=0.0,
            bounded=False,
            trivial=False,
            plurality_estimate=PluralityEstimate.NONE,
            warnings=tuple(),
        ),
    )
