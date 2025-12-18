"""
Phase-7 Targeted Generation - Main Executor

Orchestrates the four-stage execution pipeline:
Generate → Simulate → Score → Select

Optimizations:
- H1: Early Termination - stops when max_results satisfying candidates found
- H2: Prefix Memoization - caches trajectory prefixes for efficient extension
"""

from typing import Dict, Any, List, Tuple, Optional, FrozenSet
from collections import OrderedDict

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
from .generator import generate_candidates, generate_candidates_filtered, generate_candidates_lexicographic
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

# Default cache size for prefix memoization
DEFAULT_CACHE_SIZE = 10000


class PrefixCache:
    """
    LRU cache for trajectory prefixes (H2 optimization).

    Stores prefix_tuple → (magnitude, steps) for reuse when simulating
    sequences that share common prefixes.
    """

    def __init__(self, max_size: int = DEFAULT_CACHE_SIZE):
        self.max_size = max_size
        self._cache: OrderedDict[Tuple[str, ...], Tuple[float, Tuple[TrajectoryStep, ...]]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, prefix: Tuple[str, ...]) -> Optional[Tuple[float, Tuple[TrajectoryStep, ...]]]:
        """Get cached result for prefix, or None if not found."""
        if prefix in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(prefix)
            self.hits += 1
            return self._cache[prefix]
        self.misses += 1
        return None

    def put(self, prefix: Tuple[str, ...], magnitude: float, steps: Tuple[TrajectoryStep, ...]) -> None:
        """Store prefix result in cache with LRU eviction."""
        if prefix in self._cache:
            self._cache.move_to_end(prefix)
        else:
            if len(self._cache) >= self.max_size:
                # Evict least recently used
                self._cache.popitem(last=False)
            self._cache[prefix] = (magnitude, steps)

    def find_longest_prefix(self, sequence: Tuple[str, ...]) -> Optional[Tuple[Tuple[str, ...], float, Tuple[TrajectoryStep, ...]]]:
        """
        Find the longest cached prefix of the given sequence.

        Returns:
            (prefix, magnitude, steps) if found, None otherwise
        """
        # Try prefixes from longest to shortest
        for length in range(len(sequence) - 1, 0, -1):
            prefix = sequence[:length]
            cached = self.get(prefix)
            if cached is not None:
                magnitude, steps = cached
                return (prefix, magnitude, steps)
        return None


def execute_phase7(
    target: Dict[str, Any],
    generation_config: Dict[str, Any],
    selection_config: Dict[str, Any],
    *,
    use_cache: bool = True,
    cache_size: int = DEFAULT_CACHE_SIZE,
    early_termination: bool = True,
) -> Phase7Result:
    """
    Main Phase-7 execution entry point.

    Args:
        target: Raw target specification dictionary
        generation_config: Raw generation configuration dictionary
        selection_config: Raw selection configuration dictionary
        use_cache: Enable prefix memoization (H2 optimization)
        cache_size: Maximum cache entries for prefix memoization
        early_termination: Enable early termination (H1 optimization)

    Returns:
        Complete Phase7Result with results, metadata, errors, completeness

    Notes:
        - This is the primary public API
        - All inputs are validated before processing
        - Execution is fully deterministic
        - No exceptions escape; all errors in result.errors

    Optimizations:
        - H1 (Early Termination): Stops when max_results satisfying candidates found
        - H2 (Prefix Memoization): Caches trajectory prefixes for efficient extension
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

    # Extract pattern constraints for M1/M2
    template_constraints, pattern_exclusions = _extract_pattern_constraints(spec)

    # Initialize prefix cache for H2 optimization
    cache = PrefixCache(max_size=cache_size) if use_cache else None

    # Stage 1-3: GENERATE → SIMULATE → SCORE (with early termination)
    # Process candidates in streaming fashion for H1 optimization
    candidates_generated = 0
    candidates_simulated = 0
    candidates_checked = 0
    satisfying_candidates: List[Tuple[Tuple[str, ...], TrajectoryResult, float]] = []
    early_terminated = False

    # Get candidate iterator
    # Use lexicographic order when early termination is enabled (H1 optimization)
    # This ensures early termination produces same results as exhaustive search
    use_lexicographic = early_termination

    if exclude_sequences or prefix or suffix:
        candidate_iter = generate_candidates_filtered(
            gen_config,
            exclude_sequences=exclude_sequences,
            prefix=prefix,
            suffix=suffix,
            lexicographic=use_lexicographic,
        )
    else:
        if use_lexicographic:
            candidate_iter = generate_candidates_lexicographic(gen_config)
        else:
            candidate_iter = generate_candidates(gen_config)

    # Apply template/pattern filtering during generation (M1/M2)
    if template_constraints or pattern_exclusions:
        candidate_iter = _filter_by_patterns(
            candidate_iter,
            gen_config,
            template_constraints,
            pattern_exclusions,
        )

    # Process candidates with potential early termination
    for seq in candidate_iter:
        candidates_generated += 1
        candidates_checked += 1

        # Stage 2: SIMULATE (with cache)
        try:
            if cache is not None:
                trajectory = _simulate_sequence_cached(seq, gen_config, cache)
            else:
                trajectory = _simulate_sequence(seq, gen_config)
            candidates_simulated += 1
        except Phase7SimulationError as e:
            errors.append(e.to_execution_error())
            continue

        # Stage 3: SCORE
        score = _score_candidate(seq, trajectory, spec, sel_config.scoring_mode)

        # Check if satisfying
        is_satisfying = _is_satisfying(score, sel_config.scoring_mode)
        if is_satisfying:
            satisfying_candidates.append((seq, trajectory, score))

            # H1: Early termination check
            if early_termination and len(satisfying_candidates) >= sel_config.max_results:
                early_terminated = True
                break

    candidates_satisfying = len(satisfying_candidates)

    # Stage 4: SELECT
    # For early termination, we already have exactly max_results satisfying candidates
    # But we still need to rank them properly for determinism
    results = select_results(satisfying_candidates, sel_config)

    # Build metadata with optimization stats
    cache_hits = cache.hits if cache else 0
    cache_misses = cache.misses if cache else 0

    metadata = ExecutionMetadata(
        candidates_generated=candidates_generated,
        candidates_simulated=candidates_simulated,
        candidates_satisfying=candidates_satisfying,
        execution_deterministic=True,
        target_feasible=candidates_satisfying > 0,
        early_terminated=early_terminated,
        candidates_checked=candidates_checked,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )

    return Phase7Result(
        results=results,
        metadata=metadata,
        errors=tuple(errors),
        completeness=completeness,
    )


def _simulate_sequence_cached(
    sequence: Tuple[str, ...],
    config: GenerationConfig,
    cache: PrefixCache,
) -> TrajectoryResult:
    """
    Simulate a sequence using Phase-6 mechanics with prefix caching (H2).

    Attempts to find a cached prefix and extend from there.
    """
    # Try to find cached prefix
    cached_prefix = cache.find_longest_prefix(sequence)

    if cached_prefix is not None:
        prefix, magnitude, prefix_steps = cached_prefix
        start_idx = len(prefix)
        steps = list(prefix_steps)
    else:
        magnitude = 1.0
        start_idx = 0
        steps = []

    # Simulate remaining tokens
    for idx in range(start_idx, len(sequence)):
        token = sequence[idx]
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

        # Cache intermediate results (prefixes)
        # Only cache if we built from scratch or extended significantly
        if len(steps) > 1:
            cache.put(sequence[:len(steps)], magnitude, tuple(steps))

    return TrajectoryResult(
        sequence=sequence,
        steps=tuple(steps),
        final_magnitude=magnitude,
    )


def _score_candidate(
    sequence: Tuple[str, ...],
    trajectory: TrajectoryResult,
    spec: TargetSpec,
    scoring_mode: ScoringMode,
) -> float:
    """Score a candidate against all constraints."""
    score = score_trajectory(trajectory, spec, scoring_mode)

    # Also check sequence-level constraints
    for constraint in spec.constraints:
        if constraint.field in (ConstraintField.SEQUENCE_NOT_IN,
                                ConstraintField.SEQUENCE_STARTS_WITH,
                                ConstraintField.SEQUENCE_ENDS_WITH):
            seq_satisfied, seq_distance = score_sequence_constraint(
                sequence, constraint.field, constraint.value
            )
            if not seq_satisfied:
                if scoring_mode == ScoringMode.BINARY:
                    score = 0.0
                else:
                    score += seq_distance

    return score


def _is_satisfying(score: float, scoring_mode: ScoringMode) -> bool:
    """Check if score indicates a satisfying candidate."""
    if scoring_mode == ScoringMode.BINARY:
        return score >= 1.0
    else:
        return score == 0.0


def _extract_pattern_constraints(spec: TargetSpec) -> Tuple[
    List[Tuple[ConstraintField, Any]],  # template constraints
    List[Tuple[ConstraintField, Any]],  # pattern exclusions
]:
    """
    Extract template and pattern constraints for M1/M2 optimizations.

    Returns:
        (template_constraints, pattern_exclusions)
    """
    template_constraints = []
    pattern_exclusions = []

    for constraint in spec.constraints:
        if constraint.field in (ConstraintField.TEMPLATE,
                                ConstraintField.TEMPLATE_MATCHES,
                                ConstraintField.TEMPLATE_STARTS_WITH,
                                ConstraintField.TEMPLATE_ENDS_WITH):
            template_constraints.append((constraint.field, constraint.value))

        elif constraint.field in (ConstraintField.TEMPLATE_NOT_IN,
                                  ConstraintField.PREFIX_NOT_IN,
                                  ConstraintField.SUFFIX_NOT_IN):
            pattern_exclusions.append((constraint.field, constraint.value))

    return template_constraints, pattern_exclusions


def _filter_by_patterns(
    candidates,
    config: GenerationConfig,
    template_constraints: List[Tuple[ConstraintField, Any]],
    pattern_exclusions: List[Tuple[ConstraintField, Any]],
):
    """
    Filter candidates by template constraints and pattern exclusions (M1/M2).

    Yields only candidates that match template constraints and don't match exclusions.
    """
    for seq in candidates:
        # Check template constraints (M1)
        template = derive_template(seq, config)
        passes_template = True

        for field, value in template_constraints:
            if field == ConstraintField.TEMPLATE:
                # Exact template match: "== CVCCV"
                if isinstance(value, str):
                    # Parse "== PATTERN" format
                    if value.startswith("== "):
                        expected = value[3:].strip()
                        if template != expected:
                            passes_template = False
                            break
                    else:
                        if template != value:
                            passes_template = False
                            break
                elif template != value:
                    passes_template = False
                    break

            elif field == ConstraintField.TEMPLATE_MATCHES:
                # Regex match: "matches C+V+"
                import re
                if isinstance(value, str):
                    pattern = value.replace("matches ", "").strip()
                    if not re.match(f"^{pattern}$", template):
                        passes_template = False
                        break

            elif field == ConstraintField.TEMPLATE_STARTS_WITH:
                # Prefix match: "starts_with CV"
                if isinstance(value, str):
                    prefix = value.replace("starts_with ", "").strip()
                    if not template.startswith(prefix):
                        passes_template = False
                        break

            elif field == ConstraintField.TEMPLATE_ENDS_WITH:
                # Suffix match: "ends_with VC"
                if isinstance(value, str):
                    suffix = value.replace("ends_with ", "").strip()
                    if not template.endswith(suffix):
                        passes_template = False
                        break

        if not passes_template:
            continue

        # Check pattern exclusions (M2)
        excluded = False
        for field, value in pattern_exclusions:
            if field == ConstraintField.TEMPLATE_NOT_IN:
                # Template exclusion
                if isinstance(value, (set, frozenset)):
                    if template in value:
                        excluded = True
                        break
                elif isinstance(value, (list, tuple)):
                    if template in value:
                        excluded = True
                        break

            elif field == ConstraintField.PREFIX_NOT_IN:
                # Prefix exclusion
                if isinstance(value, (set, frozenset)):
                    for prefix in value:
                        prefix_tuple = tuple(prefix) if isinstance(prefix, list) else prefix
                        if len(seq) >= len(prefix_tuple) and seq[:len(prefix_tuple)] == prefix_tuple:
                            excluded = True
                            break
                if excluded:
                    break

            elif field == ConstraintField.SUFFIX_NOT_IN:
                # Suffix exclusion
                if isinstance(value, (set, frozenset)):
                    for suffix in value:
                        suffix_tuple = tuple(suffix) if isinstance(suffix, list) else suffix
                        if len(seq) >= len(suffix_tuple) and seq[-len(suffix_tuple):] == suffix_tuple:
                            excluded = True
                            break
                if excluded:
                    break

        if not excluded:
            yield seq


def derive_template(sequence: Tuple[str, ...], config: GenerationConfig) -> str:
    """
    Derive the C/V template from a sequence.

    Args:
        sequence: Tuple of varna tokens
        config: Generation config with consonant/vowel sets

    Returns:
        Template string (e.g., "CVCVC" for ("ba", "a", "ka", "i", "ta"))
    """
    template = []
    for token in sequence:
        if token in config.consonant_set:
            template.append("C")
        elif token in config.vowel_set:
            template.append("V")
        else:
            template.append("?")  # Unknown token type
    return "".join(template)


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
