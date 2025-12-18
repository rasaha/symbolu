"""
Phase-7 Targeted Generation - Constraint Scoring

Evaluates trajectories against target constraints.
"""

from typing import Tuple, Union, List

from .types import (
    TrajectoryResult,
    TrajectoryStep,
    TargetSpec,
    Constraint,
    ConstraintField,
    ConstraintOperator,
    ScoringMode,
)


def score_trajectory(
    trajectory: TrajectoryResult,
    spec: TargetSpec,
    mode: ScoringMode,
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
    total_distance = 0.0
    all_satisfied = True

    for constraint in spec.constraints:
        satisfied, distance = evaluate_constraint(trajectory, constraint)
        if not satisfied:
            all_satisfied = False
        total_distance += distance

    if mode == ScoringMode.BINARY:
        return 1.0 if all_satisfied else 0.0
    else:  # DISTANCE
        return total_distance


def evaluate_constraint(
    trajectory: TrajectoryResult,
    constraint: Constraint,
) -> Tuple[bool, float]:
    """
    Evaluate single constraint against trajectory.

    Args:
        trajectory: Phase-6 simulation result
        constraint: Constraint to evaluate

    Returns:
        (satisfied: bool, distance: float)
        distance is 0.0 if satisfied, otherwise magnitude of violation
    """
    try:
        actual_value = extract_field_value(
            trajectory,
            constraint.field,
            constraint.index,
            constraint.threshold,
        )
    except (IndexError, KeyError):
        # Index out of bounds or field not found
        return False, 1.0

    return compare_values(actual_value, constraint.operator, constraint.value)


def extract_field_value(
    trajectory: TrajectoryResult,
    field: ConstraintField,
    index: int = None,
    threshold: float = None,
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
    steps = trajectory.steps

    if field == ConstraintField.FINAL_MAGNITUDE:
        return trajectory.final_magnitude

    elif field == ConstraintField.LEN_STEPS:
        return len(steps)

    elif field == ConstraintField.STEP_MAGNITUDE:
        if index is not None:
            # Handle negative indices
            if index < 0:
                actual_index = len(steps) + index
            else:
                actual_index = index
            if actual_index < 0 or actual_index >= len(steps):
                raise IndexError(f"Step index {index} out of bounds for sequence of length {len(steps)}")
            return steps[actual_index].magnitude
        raise ValueError("Index required for step magnitude")

    elif field == ConstraintField.STEP_EVENT:
        if index is not None:
            if index < 0:
                actual_index = len(steps) + index
            else:
                actual_index = index
            if actual_index < 0 or actual_index >= len(steps):
                raise IndexError(f"Step index {index} out of bounds")
            return steps[actual_index].event
        raise ValueError("Index required for step event")

    elif field == ConstraintField.TERMINAL_EVENT:
        if not steps:
            raise IndexError("No steps in trajectory")
        return steps[-1].event

    elif field == ConstraintField.MONOTONIC_INCREASING:
        if len(steps) <= 1:
            return True
        magnitudes = [s.magnitude for s in steps]
        return all(magnitudes[i] <= magnitudes[i + 1] for i in range(len(magnitudes) - 1))

    elif field == ConstraintField.MONOTONIC_DECREASING:
        if len(steps) <= 1:
            return True
        magnitudes = [s.magnitude for s in steps]
        return all(magnitudes[i] >= magnitudes[i + 1] for i in range(len(magnitudes) - 1))

    elif field == ConstraintField.COUNT_MAGNITUDE_GT:
        if threshold is None:
            raise ValueError("Threshold required for count magnitude >")
        return sum(1 for s in steps if s.magnitude > threshold)

    elif field == ConstraintField.COUNT_MAGNITUDE_LT:
        if threshold is None:
            raise ValueError("Threshold required for count magnitude <")
        return sum(1 for s in steps if s.magnitude < threshold)

    elif field == ConstraintField.COUNT_EVENT_RESET:
        return sum(1 for s in steps if s.event == "reset")

    elif field == ConstraintField.COUNT_EVENT_MODULATE:
        return sum(1 for s in steps if s.event == "modulate")

    elif field == ConstraintField.MAGNITUDE_RANGE:
        if not steps:
            return 0.0
        magnitudes = [s.magnitude for s in steps]
        return max(magnitudes) - min(magnitudes)

    elif field == ConstraintField.STEP_DELTA:
        if index is None or index < 1:
            raise ValueError("Valid index required for step delta")
        if index >= len(steps):
            raise IndexError(f"Step index {index} out of bounds")
        return steps[index].magnitude - steps[index - 1].magnitude

    elif field == ConstraintField.SEQUENCE_NOT_IN:
        # Return the sequence for comparison
        return trajectory.sequence

    elif field == ConstraintField.SEQUENCE_STARTS_WITH:
        return trajectory.sequence

    elif field == ConstraintField.SEQUENCE_ENDS_WITH:
        return trajectory.sequence

    else:
        raise ValueError(f"Unknown constraint field: {field}")


def compare_values(
    actual: Union[float, int, bool, str, Tuple],
    operator: ConstraintOperator,
    expected: Union[float, int, bool, str, Tuple],
) -> Tuple[bool, float]:
    """
    Compare actual value against expected using operator.

    Returns:
        (satisfied: bool, distance: float)
    """
    # Handle sequence constraints specially
    if isinstance(actual, tuple) and isinstance(expected, (tuple, list, set, frozenset)):
        return compare_sequence_constraint(actual, operator, expected)

    # Handle boolean comparisons
    if isinstance(actual, bool) and isinstance(expected, bool):
        satisfied = (actual == expected) if operator == ConstraintOperator.EQ else (actual != expected)
        return satisfied, 0.0 if satisfied else 1.0

    # Handle string comparisons (event types)
    if isinstance(actual, str) and isinstance(expected, str):
        if operator == ConstraintOperator.EQ:
            satisfied = actual == expected
        elif operator == ConstraintOperator.NE:
            satisfied = actual != expected
        else:
            satisfied = False
        return satisfied, 0.0 if satisfied else 1.0

    # Handle numeric comparisons
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if operator == ConstraintOperator.EQ:
            satisfied = abs(actual - expected) < 1e-9
            distance = abs(actual - expected) if not satisfied else 0.0
        elif operator == ConstraintOperator.NE:
            satisfied = abs(actual - expected) >= 1e-9
            distance = 0.0 if satisfied else 1.0
        elif operator == ConstraintOperator.GT:
            satisfied = actual > expected
            distance = max(0, expected - actual + 1e-9) if not satisfied else 0.0
        elif operator == ConstraintOperator.GE:
            satisfied = actual >= expected
            distance = max(0, expected - actual) if not satisfied else 0.0
        elif operator == ConstraintOperator.LT:
            satisfied = actual < expected
            distance = max(0, actual - expected + 1e-9) if not satisfied else 0.0
        elif operator == ConstraintOperator.LE:
            satisfied = actual <= expected
            distance = max(0, actual - expected) if not satisfied else 0.0
        elif operator == ConstraintOperator.IN_RANGE:
            if isinstance(expected, tuple) and len(expected) == 2:
                lower, upper = expected
                satisfied = lower <= actual <= upper
                if not satisfied:
                    if actual < lower:
                        distance = lower - actual
                    else:
                        distance = actual - upper
                else:
                    distance = 0.0
            else:
                satisfied = False
                distance = 1.0
        else:
            satisfied = False
            distance = 1.0
        return satisfied, distance

    # Type mismatch
    return False, 1.0


def compare_sequence_constraint(
    actual: Tuple[str, ...],
    operator: ConstraintOperator,
    expected: Union[Tuple, List, set, frozenset],
) -> Tuple[bool, float]:
    """
    Compare sequence against sequence constraints.

    Handles:
    - SEQUENCE_NOT_IN: actual should not be in expected set
    - SEQUENCE_STARTS_WITH: actual should start with expected prefix
    - SEQUENCE_ENDS_WITH: actual should end with expected suffix
    """
    if operator == ConstraintOperator.EQ:
        # For NOT IN, expected is a set of sequences to exclude
        # The constraint is satisfied if actual is NOT in the set
        if isinstance(expected, (set, frozenset)):
            # Exclusion constraint
            satisfied = actual not in expected
            return satisfied, 0.0 if satisfied else 1.0
        elif isinstance(expected, (tuple, list)):
            # Check if it's a prefix/suffix check or exact match
            expected_tuple = tuple(expected)
            if len(expected_tuple) <= len(actual):
                # Could be prefix check
                if actual[:len(expected_tuple)] == expected_tuple:
                    return True, 0.0
                # Could be suffix check
                if actual[-len(expected_tuple):] == expected_tuple:
                    return True, 0.0
                # Exact match check
                if actual == expected_tuple:
                    return True, 0.0
            return False, 1.0

    return False, 1.0


def score_sequence_constraint(
    sequence: Tuple[str, ...],
    field: ConstraintField,
    value: Union[Tuple, set, frozenset],
) -> Tuple[bool, float]:
    """
    Score a sequence against sequence-level constraints.

    Used for compositional targeting constraints.
    """
    if field == ConstraintField.SEQUENCE_NOT_IN:
        # Value is a set of sequences to exclude
        if isinstance(value, (set, frozenset)):
            satisfied = sequence not in value
        else:
            # Convert to set for comparison
            value_set = set(tuple(v) if isinstance(v, list) else v for v in value)
            satisfied = sequence not in value_set
        return satisfied, 0.0 if satisfied else 1.0

    elif field == ConstraintField.SEQUENCE_STARTS_WITH:
        # Value is a prefix tuple
        prefix = tuple(value) if not isinstance(value, tuple) else value
        if len(sequence) < len(prefix):
            return False, len(prefix) - len(sequence)
        satisfied = sequence[:len(prefix)] == prefix
        return satisfied, 0.0 if satisfied else 1.0

    elif field == ConstraintField.SEQUENCE_ENDS_WITH:
        # Value is a suffix tuple
        suffix = tuple(value) if not isinstance(value, tuple) else value
        if len(sequence) < len(suffix):
            return False, len(suffix) - len(sequence)
        satisfied = sequence[-len(suffix):] == suffix
        return satisfied, 0.0 if satisfied else 1.0

    return True, 0.0
