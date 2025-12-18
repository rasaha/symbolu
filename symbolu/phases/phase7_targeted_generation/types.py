"""
Phase-7 Targeted Generation - Type Definitions

All types are frozen (immutable) dataclasses.
All collections are immutable (tuple, frozenset).
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, FrozenSet, Union, Tuple


class ScoringMode(Enum):
    """Scoring mode for constraint evaluation."""
    BINARY = "binary"      # 1 = satisfies, 0 = does not
    DISTANCE = "distance"  # Sum of constraint violations (0 = perfect)


class ConstraintOperator(Enum):
    """Operators for constraint comparisons."""
    EQ = "=="
    NE = "!="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    IN_RANGE = "in"


class ConstraintField(Enum):
    """Valid constraint fields from Phase-7 contract Section 2."""
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
    # Compositional targeting additions
    SEQUENCE_NOT_IN = "sequence NOT IN"
    SEQUENCE_STARTS_WITH = "sequence STARTS_WITH"
    SEQUENCE_ENDS_WITH = "sequence ENDS_WITH"


class ErrorType(Enum):
    """Error types from Phase-7 contract Section 6."""
    INVALID_TARGET_DIMENSION = "INVALID_TARGET_DIMENSION"
    UNKNOWN_TARGET_FIELD = "UNKNOWN_TARGET_FIELD"
    INVALID_CONSTRAINT_PATTERN = "INVALID_CONSTRAINT_PATTERN"
    VACUOUS_TARGET = "VACUOUS_TARGET"
    INVALID_NUMERIC_LITERAL = "INVALID_NUMERIC_LITERAL"
    CONTRADICTORY_TARGET = "CONTRADICTORY_TARGET"
    SIMULATION_FAILURE = "SIMULATION_FAILURE"
    INDEX_OUT_OF_BOUNDS = "INDEX_OUT_OF_BOUNDS"


class CompletenessLevel(Enum):
    """Completeness levels from completeness spec."""
    INVALID = 0
    VALID_INCOMPLETE = 1
    MINIMALLY_COMPLETE = 2
    OPTIMALLY_COMPLETE = 3


class PluralityEstimate(Enum):
    """Estimated number of satisfying sequences."""
    NONE = "none"
    SINGLE = "single"
    FEW = "few"
    MANY = "many"


@dataclass(frozen=True)
class Constraint:
    """Single constraint specification."""
    field: ConstraintField
    operator: ConstraintOperator
    value: Union[float, int, bool, str, Tuple]  # Tuple for IN_RANGE or sequence sets
    index: Optional[int] = None  # For indexed fields like steps[i]
    threshold: Optional[float] = None  # For count conditions


@dataclass(frozen=True)
class TargetSpec:
    """Complete target specification."""
    constraints: FrozenSet[Constraint]


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
class TrajectoryStep:
    """Single step in a trajectory (mirrors Phase-6)."""
    idx: int
    token: str
    token_type: str
    magnitude: float
    event: str
    notes: str = ""


@dataclass(frozen=True)
class TrajectoryResult:
    """Result from Phase-6 simulation (mirrors Phase-6)."""
    sequence: Tuple[str, ...]
    steps: Tuple[TrajectoryStep, ...]
    final_magnitude: float


@dataclass(frozen=True)
class RankedResult:
    """Single result with ranking."""
    sequence: Tuple[str, ...]  # Immutable sequence of varna tokens
    trajectory: TrajectoryResult
    score: float
    rank: int


@dataclass(frozen=True)
class ExecutionError:
    """Error encountered during execution."""
    error_type: ErrorType
    message: str
    sequence: Optional[Tuple[str, ...]] = None  # For simulation failures
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
    warnings: Tuple[str, ...]  # Immutable list of warning strings


@dataclass(frozen=True)
class Phase7Result:
    """Complete Phase-7 execution result."""
    results: Tuple[RankedResult, ...]  # Tuple of RankedResult (immutable)
    metadata: ExecutionMetadata
    errors: Tuple[ExecutionError, ...]  # Tuple of ExecutionError (immutable)
    completeness: CompletenessReport
