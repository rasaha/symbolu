PHASE-7 IMPLEMENTATION SPECIFICATION
Version: 1.0
Date: 2025-12-18
Type: Implementation Blueprint

================================================================================
PURPOSE
================================================================================

This document translates the Phase-7 Target Contract into typed interfaces,
function signatures, and module structure. It serves as the blueprint for
implementation.

No implementation code is provided. Only type definitions and signatures.

================================================================================
1. MODULE STRUCTURE
================================================================================

symbolu/
└── phases/
    └── phase7_targeted_generation/
        ├── __init__.py              # Public API exports
        ├── types.py                 # Type definitions (frozen dataclasses, enums)
        ├── constraints.py           # Constraint parsing and validation
        ├── generator.py             # Candidate sequence generation
        ├── scorer.py                # Constraint scoring
        ├── selector.py              # Result ranking and selection
        ├── executor.py              # Main execution orchestrator
        ├── completeness.py          # Completeness validation
        └── errors.py                # Error types

tests/
└── phases/
    └── test_phase7_targeted_generation/
        ├── __init__.py
        ├── test_types.py
        ├── test_constraints.py
        ├── test_generator.py
        ├── test_scorer.py
        ├── test_selector.py
        ├── test_executor.py
        ├── test_completeness.py
        ├── test_invariance.py       # I1-I7 invariance tests
        └── test_integration.py

================================================================================
2. TYPE DEFINITIONS (types.py)
================================================================================

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, FrozenSet, Union, Literal

# Re-export from Phase-6
from symbolu.experiments.composition.composition_types import (
    TrajectoryResult,
    TrajectoryStep,
)

------------------------------------------------------------------------------
ENUMS
------------------------------------------------------------------------------

class ScoringMode(Enum):
    BINARY = "binary"      # 1 = satisfies, 0 = does not
    DISTANCE = "distance"  # Sum of constraint violations (0 = perfect)

class ConstraintOperator(Enum):
    EQ = "=="
    NE = "!="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    IN_RANGE = "in"

class ConstraintField(Enum):
    FINAL_MAGNITUDE = "final_magnitude"
    LEN_STEPS = "len(steps)"
    STEP_MAGNITUDE = "steps[i].magnitude"
    STEP_EVENT = "steps[i].event"
    MONOTONIC_INCREASING = "monotonic_increasing(steps[].magnitude)"
    MONOTONIC_DECREASING = "monotonic_decreasing(steps[].magnitude)"
    COUNT_MAGNITUDE_GT = "count(steps where magnitude > threshold)"
    COUNT_MAGNITUDE_LT = "count(steps where magnitude < threshold)"
    COUNT_EVENT_RESET = "count(steps where event == 'reset')"
    COUNT_EVENT_MODULATE = "count(steps where event == 'modulate')"
    MAGNITUDE_RANGE = "max(steps[].magnitude) - min(steps[].magnitude)"
    STEP_DELTA = "steps[i].magnitude - steps[i-1].magnitude"
    TERMINAL_EVENT = "steps[-1].event"

class ErrorType(Enum):
    INVALID_TARGET_DIMENSION = "INVALID_TARGET_DIMENSION"
    UNKNOWN_TARGET_FIELD = "UNKNOWN_TARGET_FIELD"
    INVALID_CONSTRAINT_PATTERN = "INVALID_CONSTRAINT_PATTERN"
    VACUOUS_TARGET = "VACUOUS_TARGET"
    INVALID_NUMERIC_LITERAL = "INVALID_NUMERIC_LITERAL"
    CONTRADICTORY_TARGET = "CONTRADICTORY_TARGET"
    SIMULATION_FAILURE = "SIMULATION_FAILURE"
    INDEX_OUT_OF_BOUNDS = "INDEX_OUT_OF_BOUNDS"

class CompletenessLevel(Enum):
    INVALID = 0
    VALID_INCOMPLETE = 1
    MINIMALLY_COMPLETE = 2
    OPTIMALLY_COMPLETE = 3

class PluralityEstimate(Enum):
    NONE = "none"
    SINGLE = "single"
    FEW = "few"
    MANY = "many"

------------------------------------------------------------------------------
FROZEN DATACLASSES (Immutable)
------------------------------------------------------------------------------

@dataclass(frozen=True)
class Constraint:
    """Single constraint specification."""
    field: ConstraintField
    operator: ConstraintOperator
    value: Union[float, int, bool, str, tuple]  # tuple for IN_RANGE
    index: Optional[int] = None  # For indexed fields like steps[i]
    threshold: Optional[float] = None  # For count conditions

@dataclass(frozen=True)
class TargetSpec:
    """Complete target specification."""
    constraints: FrozenSet[Constraint]
    # Internally normalized to frozen set for determinism

@dataclass(frozen=True)
class GenerationConfig:
    """Configuration for candidate generation."""
    max_sequence_length: int
    max_candidates: Optional[int]  # None = exhaustive
    vowel_set: FrozenSet[str]  # Subset of {"a", "i", "u"}
    consonant_set: FrozenSet[str]  # Subset of Phase-4A consonants

@dataclass(frozen=True)
class SelectionConfig:
    """Configuration for result selection."""
    max_results: int
    score_threshold: Optional[float]  # Filter by score
    scoring_mode: ScoringMode

@dataclass(frozen=True)
class RankedResult:
    """Single result with ranking."""
    sequence: tuple  # Immutable sequence of varna tokens
    trajectory: TrajectoryResult
    score: float
    rank: int

@dataclass(frozen=True)
class ExecutionError:
    """Error encountered during execution."""
    error_type: ErrorType
    message: str
    sequence: Optional[tuple] = None  # For simulation failures
    field: Optional[str] = None  # For field validation errors
    value: Optional[str] = None  # For literal validation errors
    stage: Optional[str] = None  # Which stage failed

@dataclass(frozen=True)
class ExecutionMetadata:
    """Metadata about execution."""
    candidates_generated: int
    candidates_simulated: int
    candidates_satisfying: int
    execution_deterministic: bool  # Always True
    target_feasible: bool

@dataclass(frozen=True)
class CompletenessReport:
    """Report from completeness validation."""
    level: CompletenessLevel
    discrimination_ratio: float  # 0.0 to 1.0
    bounded: bool
    trivial: bool
    plurality_estimate: PluralityEstimate
    warnings: tuple  # Immutable list of warning strings

@dataclass(frozen=True)
class Phase7Result:
    """Complete Phase-7 execution result."""
    results: tuple  # Tuple of RankedResult (immutable)
    metadata: ExecutionMetadata
    errors: tuple  # Tuple of ExecutionError (immutable)
    completeness: CompletenessReport

================================================================================
3. CONSTRAINT MODULE (constraints.py)
================================================================================

def parse_target_spec(raw_spec: dict) -> TargetSpec:
    """
    Parse raw dictionary into validated TargetSpec.

    Args:
        raw_spec: Dictionary with constraint field names and values

    Returns:
        Validated TargetSpec

    Raises:
        Phase7ValidationError: If spec contains invalid fields or patterns
    """
    ...

def validate_constraint(constraint: Constraint) -> None:
    """
    Validate single constraint against whitelist.

    Args:
        constraint: Constraint to validate

    Raises:
        Phase7ValidationError: If constraint is invalid
    """
    ...

def validate_target_spec(spec: TargetSpec) -> None:
    """
    Validate complete target specification.

    Checks:
        - Non-empty (not vacuous)
        - All fields in whitelist
        - All patterns valid
        - All numeric literals finite
        - No semantic content

    Args:
        spec: Target specification to validate

    Raises:
        Phase7ValidationError: With appropriate ErrorType
    """
    ...

def detect_contradictions(spec: TargetSpec) -> Optional[ExecutionError]:
    """
    Static analysis for contradictory constraints.

    Checks:
        - Direct contradictions (x > 2 AND x < 1)
        - Phase-6 invariant violations (steps[0].event == modulate)
        - Index bound contradictions (steps[5] with len <= 3)

    Args:
        spec: Target specification to analyze

    Returns:
        ExecutionError if contradiction found, None otherwise
    """
    ...

def import_phase6_invariants() -> FrozenSet[Constraint]:
    """
    Return Phase-6 invariants as implicit constraints.

    Returns:
        Set of constraints that are always true:
        - steps[0].event == "reset"
        - final_magnitude >= 1.0
        - len(steps) >= 1
    """
    ...

================================================================================
4. GENERATOR MODULE (generator.py)
================================================================================

def generate_candidates(
    config: GenerationConfig
) -> Iterator[tuple]:
    """
    Generate candidate varna sequences.

    Produces valid sequences according to Phase-6 grammar:
        - Consonant-initial
        - Only valid varnas
        - Up to max_sequence_length

    Args:
        config: Generation configuration

    Yields:
        Tuples of varna tokens (immutable sequences)

    Notes:
        - Enumeration order is deterministic (lexicographic)
        - If max_candidates is set, stops after that many
        - Does not filter by target (that's scoring's job)
    """
    ...

def count_candidate_space(config: GenerationConfig) -> int:
    """
    Calculate size of candidate space without generating.

    Args:
        config: Generation configuration

    Returns:
        Number of valid sequences in space

    Notes:
        Used for feasibility estimation
    """
    ...

def validate_sequence(sequence: tuple, config: GenerationConfig) -> bool:
    """
    Check if sequence is valid according to Phase-6 grammar.

    Args:
        sequence: Candidate sequence
        config: Generation configuration

    Returns:
        True if valid, False otherwise
    """
    ...

================================================================================
5. SCORER MODULE (scorer.py)
================================================================================

def score_trajectory(
    trajectory: TrajectoryResult,
    spec: TargetSpec,
    mode: ScoringMode
) -> float:
    """
    Score a trajectory against target constraints.

    Args:
        trajectory: Phase-6 simulation result
        spec: Target specification
        mode: Scoring mode (binary or distance)

    Returns:
        Score value:
        - Binary mode: 1.0 = satisfies all, 0.0 = fails any
        - Distance mode: 0.0 = perfect, >0 = sum of violations
    """
    ...

def evaluate_constraint(
    trajectory: TrajectoryResult,
    constraint: Constraint
) -> tuple:
    """
    Evaluate single constraint against trajectory.

    Args:
        trajectory: Phase-6 simulation result
        constraint: Constraint to evaluate

    Returns:
        (satisfied: bool, distance: float)
        distance is 0.0 if satisfied, otherwise magnitude of violation
    """
    ...

def extract_field_value(
    trajectory: TrajectoryResult,
    field: ConstraintField,
    index: Optional[int] = None,
    threshold: Optional[float] = None
) -> Union[float, int, bool, str]:
    """
    Extract field value from trajectory for constraint evaluation.

    Args:
        trajectory: Phase-6 simulation result
        field: Which field to extract
        index: For indexed fields (steps[i])
        threshold: For count conditions

    Returns:
        Extracted value

    Raises:
        IndexError: If index out of bounds
    """
    ...

================================================================================
6. SELECTOR MODULE (selector.py)
================================================================================

def select_results(
    scored_results: List[tuple],  # (sequence, trajectory, score)
    config: SelectionConfig
) -> tuple:
    """
    Rank and select final results.

    Args:
        scored_results: List of (sequence, trajectory, score) tuples
        config: Selection configuration

    Returns:
        Tuple of RankedResult (immutable, ordered)

    Notes:
        - Ordering is deterministic
        - Ties broken by lexicographic sequence order
        - Respects max_results and score_threshold
    """
    ...

def rank_by_score(
    results: List[tuple],
    mode: ScoringMode
) -> List[tuple]:
    """
    Sort results by score.

    Args:
        results: Unordered results
        mode: Scoring mode (determines sort direction)

    Returns:
        Sorted list:
        - Binary mode: descending (1.0 first)
        - Distance mode: ascending (0.0 first)
    """
    ...

def break_ties(
    tied_results: List[tuple]
) -> List[tuple]:
    """
    Deterministically order tied results.

    Args:
        tied_results: Results with equal scores

    Returns:
        Lexicographically ordered results
    """
    ...

================================================================================
7. EXECUTOR MODULE (executor.py)
================================================================================

def execute_phase7(
    target: dict,
    generation_config: dict,
    selection_config: dict
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
    ...

def execute_stage_generate(
    config: GenerationConfig
) -> tuple:
    """
    Execute GENERATE stage.

    Returns:
        Tuple of candidate sequences
    """
    ...

def execute_stage_simulate(
    candidates: tuple,
    errors: List[ExecutionError]
) -> tuple:
    """
    Execute SIMULATE stage.

    Invokes Phase-6 on each candidate.

    Returns:
        Tuple of (sequence, TrajectoryResult) pairs

    Notes:
        - Simulation failures recorded in errors list
        - Failed candidates excluded from output
    """
    ...

def execute_stage_score(
    simulated: tuple,
    spec: TargetSpec,
    mode: ScoringMode
) -> tuple:
    """
    Execute SCORE stage.

    Returns:
        Tuple of (sequence, TrajectoryResult, score) triples
    """
    ...

def execute_stage_select(
    scored: tuple,
    config: SelectionConfig
) -> tuple:
    """
    Execute SELECT stage.

    Returns:
        Tuple of RankedResult
    """
    ...

================================================================================
8. COMPLETENESS MODULE (completeness.py)
================================================================================

def validate_completeness(
    spec: TargetSpec,
    config: GenerationConfig
) -> CompletenessReport:
    """
    Assess target completeness.

    Args:
        spec: Validated target specification
        config: Generation configuration

    Returns:
        CompletenessReport with level, warnings, metrics
    """
    ...

def check_discrimination(spec: TargetSpec) -> tuple:
    """
    Check if target discriminates.

    Returns:
        (discriminates: bool, ratio: float, warnings: List[str])
    """
    ...

def check_boundedness(
    spec: TargetSpec,
    config: GenerationConfig
) -> tuple:
    """
    Check if search space is bounded.

    Returns:
        (bounded: bool, warnings: List[str])
    """
    ...

def check_triviality(spec: TargetSpec) -> tuple:
    """
    Check if target is trivially satisfied by minimal sequence.

    Returns:
        (trivial: bool, warnings: List[str])
    """
    ...

def estimate_plurality(
    spec: TargetSpec,
    config: GenerationConfig
) -> PluralityEstimate:
    """
    Estimate number of satisfying sequences.

    Returns:
        PluralityEstimate enum value
    """
    ...

================================================================================
9. ERRORS MODULE (errors.py)
================================================================================

class Phase7Error(Exception):
    """Base exception for Phase-7 errors."""
    def __init__(self, error_type: ErrorType, message: str, **details):
        self.error_type = error_type
        self.message = message
        self.details = details
        super().__init__(message)

    def to_execution_error(self) -> ExecutionError:
        """Convert to ExecutionError for result."""
        ...

class Phase7ValidationError(Phase7Error):
    """Raised during target/config validation."""
    ...

class Phase7SimulationError(Phase7Error):
    """Raised during Phase-6 simulation."""
    ...

def create_error(
    error_type: ErrorType,
    message: str,
    **details
) -> ExecutionError:
    """
    Factory function for ExecutionError.

    Args:
        error_type: Type of error
        message: Human-readable message
        **details: Additional context (sequence, field, value, stage)

    Returns:
        Immutable ExecutionError
    """
    ...

================================================================================
10. PUBLIC API (__init__.py)
================================================================================

# Primary entry point
from .executor import execute_phase7

# Type exports
from .types import (
    # Enums
    ScoringMode,
    ErrorType,
    CompletenessLevel,

    # Data classes
    TargetSpec,
    GenerationConfig,
    SelectionConfig,
    RankedResult,
    ExecutionError,
    ExecutionMetadata,
    CompletenessReport,
    Phase7Result,
)

# Validation utilities
from .constraints import (
    parse_target_spec,
    validate_target_spec,
)

# Completeness utilities
from .completeness import (
    validate_completeness,
)

__all__ = [
    "execute_phase7",
    "ScoringMode",
    "ErrorType",
    "CompletenessLevel",
    "TargetSpec",
    "GenerationConfig",
    "SelectionConfig",
    "RankedResult",
    "ExecutionError",
    "ExecutionMetadata",
    "CompletenessReport",
    "Phase7Result",
    "parse_target_spec",
    "validate_target_spec",
    "validate_completeness",
]

================================================================================
11. INTEGRATION WITH PHASE-6
================================================================================

Phase-7 imports and uses Phase-6 as follows:

from symbolu.experiments.composition.phase6_analyzer import Phase6Analyzer
from symbolu.experiments.composition.composition_types import (
    TrajectoryResult,
    TrajectoryStep,
    SequenceConfig,
    VowelScope,
)

def simulate_sequence(sequence: tuple) -> TrajectoryResult:
    """
    Invoke Phase-6 on a sequence.

    Args:
        sequence: Tuple of varna tokens

    Returns:
        Phase-6 TrajectoryResult

    Raises:
        Phase7SimulationError: If Phase-6 rejects sequence
    """
    analyzer = Phase6Analyzer()
    config = SequenceConfig(
        vowel_scope=VowelScope.PERSIST_UNTIL_RESET,
        initial_magnitude=1.0,
    )
    try:
        return analyzer.analyze(list(sequence), config)
    except Exception as e:
        raise Phase7SimulationError(
            ErrorType.SIMULATION_FAILURE,
            str(e),
            sequence=sequence,
        )

================================================================================
12. IMPLEMENTATION PRIORITIES
================================================================================

PHASE 1: Core Types and Validation
  - types.py (all type definitions)
  - errors.py (error types and factories)
  - constraints.py (parsing and validation)
  Priority: CRITICAL
  Estimated complexity: LOW

PHASE 2: Generation and Simulation
  - generator.py (candidate enumeration)
  - Integration with Phase-6
  Priority: CRITICAL
  Estimated complexity: MEDIUM

PHASE 3: Scoring and Selection
  - scorer.py (constraint evaluation)
  - selector.py (ranking and filtering)
  Priority: CRITICAL
  Estimated complexity: MEDIUM

PHASE 4: Orchestration
  - executor.py (main entry point)
  - Completeness.py (advisory validation)
  Priority: HIGH
  Estimated complexity: LOW

PHASE 5: Testing
  - All invariance tests (I1-I7)
  - Integration tests
  - Edge case coverage
  Priority: CRITICAL
  Estimated complexity: MEDIUM

================================================================================
13. IMPLEMENTATION CONSTRAINTS
================================================================================

MUST:
  - Use frozen dataclasses for all public types
  - Use tuples instead of lists for immutable sequences
  - Use FrozenSet for constraint collections
  - Ensure all functions are pure (no side effects)
  - Ensure deterministic iteration order (sorted keys, stable sort)
  - Validate all inputs at API boundary
  - Return errors in result, never raise exceptions past API

MUST NOT:
  - Use mutable state in any module
  - Cache results between invocations (unless explicitly configured)
  - Modify Phase-6 configuration
  - Access Phase-4A directly (use Phase-6 as interface)
  - Import any ML/embedding libraries
  - Use randomness
  - Access filesystem, network, or environment

================================================================================
END OF SPECIFICATION
================================================================================
