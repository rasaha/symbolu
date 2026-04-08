"""
Phase-7 Targeted Generation - Completeness Validation

Assesses target completeness per the minimal completeness specification.
"""

from typing import List, Tuple

from .types import (
    TargetSpec,
    GenerationConfig,
    CompletenessReport,
    CompletenessLevel,
    PluralityEstimate,
    Constraint,
    ConstraintField,
    ConstraintOperator,
)


def validate_completeness(
    spec: TargetSpec,
    config: GenerationConfig,
) -> CompletenessReport:
    """
    Assess target completeness.

    Args:
        spec: Validated target specification
        config: Generation configuration

    Returns:
        CompletenessReport with level, warnings, metrics
    """
    warnings: List[str] = []

    # Check discrimination
    discriminates, disc_ratio, disc_warnings = check_discrimination(spec)
    warnings.extend(disc_warnings)

    # Check boundedness
    bounded, bound_warnings = check_boundedness(spec, config)
    warnings.extend(bound_warnings)

    # Check triviality
    trivial, triv_warnings = check_triviality(spec)
    warnings.extend(triv_warnings)

    # Estimate plurality
    plurality = estimate_plurality(spec, config)

    # Determine completeness level
    if not spec.constraints:
        level = CompletenessLevel.INVALID
    elif not discriminates or not bounded:
        level = CompletenessLevel.VALID_INCOMPLETE
    elif trivial:
        level = CompletenessLevel.VALID_INCOMPLETE
    elif plurality in (PluralityEstimate.NONE, PluralityEstimate.SINGLE):
        level = CompletenessLevel.MINIMALLY_COMPLETE
    else:
        level = CompletenessLevel.OPTIMALLY_COMPLETE

    return CompletenessReport(
        level=level,
        discrimination_ratio=disc_ratio,
        bounded=bounded,
        trivial=trivial,
        plurality_estimate=plurality,
        warnings=tuple(warnings),
    )


def check_discrimination(spec: TargetSpec) -> Tuple[bool, float, List[str]]:
    """
    Check if target discriminates.

    Returns:
        (discriminates: bool, ratio: float, warnings: List[str])
    """
    warnings = []
    non_discriminating_count = 0

    for constraint in spec.constraints:
        if is_always_true_constraint(constraint):
            non_discriminating_count += 1
            warnings.append(
                f"Constraint '{constraint.field.value}' is always true (Phase-6 invariant)"
            )

    total = len(spec.constraints)
    if total == 0:
        return False, 0.0, warnings

    # Discrimination ratio: fraction of constraints that actually discriminate
    discriminating_count = total - non_discriminating_count
    ratio = discriminating_count / total

    discriminates = discriminating_count > 0

    if not discriminates:
        warnings.append("All constraints are always-true invariants")

    return discriminates, ratio, warnings


def is_always_true_constraint(constraint: Constraint) -> bool:
    """Check if a constraint is always satisfied (Phase-6 invariant)."""

    # steps[0].event == "reset" is always true
    if (constraint.field == ConstraintField.STEP_EVENT and
        constraint.index == 0 and
        constraint.operator == ConstraintOperator.EQ and
        constraint.value == "reset"):
        return True

    # final_magnitude >= 1.0 is always true (or weaker)
    if constraint.field == ConstraintField.FINAL_MAGNITUDE:
        if constraint.operator == ConstraintOperator.GE:
            if isinstance(constraint.value, (int, float)) and constraint.value <= 1.0:
                return True

    # len(steps) >= 1 is always true (or weaker)
    if constraint.field == ConstraintField.LEN_STEPS:
        if constraint.operator == ConstraintOperator.GE:
            if isinstance(constraint.value, int) and constraint.value <= 1:
                return True

    return False


def check_boundedness(
    spec: TargetSpec,
    config: GenerationConfig,
) -> Tuple[bool, List[str]]:
    """
    Check if search space is bounded.

    Returns:
        (bounded: bool, warnings: List[str])
    """
    warnings = []

    # Check for explicit length bound in target
    has_length_bound = False
    for constraint in spec.constraints:
        if constraint.field == ConstraintField.LEN_STEPS:
            if constraint.operator in (ConstraintOperator.LE, ConstraintOperator.LT, ConstraintOperator.EQ):
                has_length_bound = True
                break

    # Check for generation config bound
    has_config_bound = config.max_sequence_length is not None

    bounded = has_length_bound or has_config_bound

    if not bounded:
        warnings.append("No length bound in target or generation config")

    return bounded, warnings


def check_triviality(spec: TargetSpec) -> Tuple[bool, List[str]]:
    """
    Check if target is trivially satisfied by minimal sequence.

    Minimal sequence: single consonant like ["ka"]
    Produces: final_magnitude=1.0, len(steps)=1, steps[0].event="reset"

    Returns:
        (trivial: bool, warnings: List[str])
    """
    warnings = []

    # Check each constraint against minimal sequence properties
    minimal_satisfies_all = True

    for constraint in spec.constraints:
        if not minimal_sequence_satisfies(constraint):
            minimal_satisfies_all = False
            break

    if minimal_satisfies_all:
        # Check if any constraint forces non-minimal
        forces_non_minimal = any(
            constraint_forces_non_minimal(c) for c in spec.constraints
        )
        if not forces_non_minimal:
            warnings.append("Target is satisfied by minimal single-consonant sequence")
            return True, warnings

    return False, warnings


def minimal_sequence_satisfies(constraint: Constraint) -> bool:
    """Check if minimal sequence ["ka"] satisfies this constraint."""

    # Minimal sequence properties:
    # final_magnitude = 1.0
    # len(steps) = 1
    # steps[0].event = "reset"
    # steps[0].magnitude = 1.0
    # No modulation events

    if constraint.field == ConstraintField.FINAL_MAGNITUDE:
        val = constraint.value
        if not isinstance(val, (int, float)):
            return False
        if constraint.operator == ConstraintOperator.EQ:
            return abs(val - 1.0) < 1e-9
        elif constraint.operator == ConstraintOperator.GE:
            return 1.0 >= val
        elif constraint.operator == ConstraintOperator.LE:
            return 1.0 <= val
        elif constraint.operator == ConstraintOperator.GT:
            return 1.0 > val
        elif constraint.operator == ConstraintOperator.LT:
            return 1.0 < val

    elif constraint.field == ConstraintField.LEN_STEPS:
        val = constraint.value
        if not isinstance(val, int):
            return False
        if constraint.operator == ConstraintOperator.EQ:
            return val == 1
        elif constraint.operator == ConstraintOperator.GE:
            return 1 >= val
        elif constraint.operator == ConstraintOperator.LE:
            return 1 <= val
        elif constraint.operator == ConstraintOperator.GT:
            return 1 > val
        elif constraint.operator == ConstraintOperator.LT:
            return 1 < val

    elif constraint.field == ConstraintField.STEP_EVENT and constraint.index == 0:
        return constraint.operator == ConstraintOperator.EQ and constraint.value == "reset"

    elif constraint.field == ConstraintField.STEP_MAGNITUDE and constraint.index == 0:
        val = constraint.value
        if not isinstance(val, (int, float)):
            return False
        if constraint.operator == ConstraintOperator.EQ:
            return abs(val - 1.0) < 1e-9
        elif constraint.operator == ConstraintOperator.GE:
            return 1.0 >= val
        elif constraint.operator == ConstraintOperator.LE:
            return 1.0 <= val

    elif constraint.field == ConstraintField.COUNT_EVENT_MODULATE:
        if constraint.operator == ConstraintOperator.EQ:
            return constraint.value == 0
        elif constraint.operator == ConstraintOperator.LE:
            return True  # 0 <= any non-negative
        elif constraint.operator == ConstraintOperator.GE:
            return constraint.value <= 0

    elif constraint.field == ConstraintField.COUNT_EVENT_RESET:
        if constraint.operator == ConstraintOperator.EQ:
            return constraint.value == 1
        elif constraint.operator == ConstraintOperator.GE:
            return 1 >= constraint.value
        elif constraint.operator == ConstraintOperator.LE:
            return 1 <= constraint.value

    # For other constraints, assume minimal doesn't satisfy to be safe
    return True  # Conservative: if unsure, assume satisfied


def constraint_forces_non_minimal(constraint: Constraint) -> bool:
    """Check if constraint requires non-minimal sequence."""

    # final_magnitude > 1.0 requires vowels
    if constraint.field == ConstraintField.FINAL_MAGNITUDE:
        if constraint.operator == ConstraintOperator.GT:
            if isinstance(constraint.value, (int, float)) and constraint.value >= 1.0:
                return True

    # len(steps) > 1 requires multiple tokens
    if constraint.field == ConstraintField.LEN_STEPS:
        if constraint.operator == ConstraintOperator.GT:
            if isinstance(constraint.value, int) and constraint.value >= 1:
                return True
        if constraint.operator == ConstraintOperator.GE:
            if isinstance(constraint.value, int) and constraint.value > 1:
                return True
        if constraint.operator == ConstraintOperator.EQ:
            if isinstance(constraint.value, int) and constraint.value > 1:
                return True

    # count(modulate) > 0 requires vowels
    if constraint.field == ConstraintField.COUNT_EVENT_MODULATE:
        if constraint.operator == ConstraintOperator.GT:
            if isinstance(constraint.value, int) and constraint.value >= 0:
                return True
        if constraint.operator == ConstraintOperator.GE:
            if isinstance(constraint.value, int) and constraint.value > 0:
                return True
        if constraint.operator == ConstraintOperator.EQ:
            if isinstance(constraint.value, int) and constraint.value > 0:
                return True

    return False


def estimate_plurality(
    spec: TargetSpec,
    config: GenerationConfig,
) -> PluralityEstimate:
    """
    Estimate number of satisfying sequences.

    Returns:
        PluralityEstimate enum value
    """
    # Get constraint tightness indicators
    has_exact_magnitude = any(
        c.field == ConstraintField.FINAL_MAGNITUDE and c.operator == ConstraintOperator.EQ
        for c in spec.constraints
    )

    has_exact_length = any(
        c.field == ConstraintField.LEN_STEPS and c.operator == ConstraintOperator.EQ
        for c in spec.constraints
    )

    has_exact_events = any(
        c.field in (ConstraintField.COUNT_EVENT_RESET, ConstraintField.COUNT_EVENT_MODULATE) and
        c.operator == ConstraintOperator.EQ
        for c in spec.constraints
    )

    has_monotonic = any(
        c.field in (ConstraintField.MONOTONIC_INCREASING, ConstraintField.MONOTONIC_DECREASING) and
        c.value is True
        for c in spec.constraints
    )

    # Very tight constraints → few or single solutions
    tightness_score = sum([
        has_exact_magnitude * 3,  # Very restrictive
        has_exact_length * 1,
        has_exact_events * 2,
        has_monotonic * 1,
    ])

    if tightness_score >= 5:
        return PluralityEstimate.SINGLE
    elif tightness_score >= 3:
        return PluralityEstimate.FEW
    else:
        return PluralityEstimate.MANY
