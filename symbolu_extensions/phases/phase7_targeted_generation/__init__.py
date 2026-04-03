"""
Phase-7 Targeted Generation

A constraint satisfaction engine operating on deterministic simulation results.
Phase-7 receives a mechanical target specification and produces ranked varna
sequences whose Phase-6 simulation results satisfy the target constraints.

Usage:
    from symbolu_extensions.phases.phase7_targeted_generation import execute_phase7

    result = execute_phase7(
        target={"final_magnitude": ">= 1.3", "len(steps)": "<= 5"},
        generation_config={"max_sequence_length": 5, "max_candidates": 1000},
        selection_config={"max_results": 10, "scoring_mode": "binary"},
    )

    for r in result.results:
        print(f"Rank {r.rank}: {r.sequence} -> {r.trajectory.final_magnitude}")
"""

# Primary entry point
from .executor import execute_phase7, derive_template, PrefixCache

# Type exports
from .types import (
    # Enums
    ScoringMode,
    ErrorType,
    CompletenessLevel,
    PluralityEstimate,
    ConstraintField,
    ConstraintOperator,

    # Data classes
    Constraint,
    TargetSpec,
    GenerationConfig,
    SelectionConfig,
    TrajectoryStep,
    TrajectoryResult,
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
    detect_contradictions,
    get_phase6_invariants,
)

# Completeness utilities
from .completeness import (
    validate_completeness,
)

# Generator utilities (for compositional targeting)
from .generator import (
    generate_candidates,
    generate_candidates_filtered,
    generate_candidates_lexicographic,
    count_candidate_space,
    validate_sequence,
)

# Scorer utilities
from .scorer import (
    score_trajectory,
    evaluate_constraint,
    extract_field_value,
)

__all__ = [
    # Main entry point
    "execute_phase7",

    # Enums
    "ScoringMode",
    "ErrorType",
    "CompletenessLevel",
    "PluralityEstimate",
    "ConstraintField",
    "ConstraintOperator",

    # Data classes
    "Constraint",
    "TargetSpec",
    "GenerationConfig",
    "SelectionConfig",
    "TrajectoryStep",
    "TrajectoryResult",
    "RankedResult",
    "ExecutionError",
    "ExecutionMetadata",
    "CompletenessReport",
    "Phase7Result",

    # Validation
    "parse_target_spec",
    "validate_target_spec",
    "detect_contradictions",
    "get_phase6_invariants",

    # Completeness
    "validate_completeness",

    # Generator
    "generate_candidates",
    "generate_candidates_filtered",
    "generate_candidates_lexicographic",
    "count_candidate_space",
    "validate_sequence",

    # Scorer
    "score_trajectory",
    "evaluate_constraint",
    "extract_field_value",

    # Optimization utilities
    "derive_template",
    "PrefixCache",
]
