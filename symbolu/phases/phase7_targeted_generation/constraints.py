"""
Phase-7 Targeted Generation - Constraint Parsing and Validation

Validates targets against Phase-7 contract Section 2 (valid dimensions)
and Section 3 (invalid dimensions).
"""

import math
import re
from typing import Dict, Any, Optional, List, FrozenSet, Tuple, Set

from .types import (
    Constraint,
    ConstraintField,
    ConstraintOperator,
    TargetSpec,
    ErrorType,
    ExecutionError,
)
from .errors import (
    Phase7ValidationError,
    Phase7ContradictionError,
    create_error,
)


# Semantic keywords that indicate invalid target dimensions (Section 3)
FORBIDDEN_KEYWORDS = frozenset([
    "meaning", "means", "expressing", "representing", "signification",
    "feels", "evoking", "calming", "energizing", "emotion", "mood", "affect",
    "intended", "causes", "healing", "protective", "purpose", "goal", "effect",
    "symbolizing", "associated", "cultural", "spiritual", "metaphorical",
    "beautiful", "optimal", "good", "appropriate", "better", "best",
    "harmony", "balance", "resonance",
])

# Valid constraint field patterns
VALID_FIELD_PATTERNS = {
    "final_magnitude": ConstraintField.FINAL_MAGNITUDE,
    "len(steps)": ConstraintField.LEN_STEPS,
    r"steps\[-?\d+\]\.magnitude": ConstraintField.STEP_MAGNITUDE,
    r"steps\[-?\d+\]\.event": ConstraintField.STEP_EVENT,
    "steps[-1].event": ConstraintField.TERMINAL_EVENT,
    "monotonic_increasing(steps[].magnitude)": ConstraintField.MONOTONIC_INCREASING,
    "monotonic_decreasing(steps[].magnitude)": ConstraintField.MONOTONIC_DECREASING,
    r"count\(steps where magnitude > .+\)": ConstraintField.COUNT_MAGNITUDE_GT,
    r"count\(steps where magnitude < .+\)": ConstraintField.COUNT_MAGNITUDE_LT,
    "count(steps where event == 'reset')": ConstraintField.COUNT_EVENT_RESET,
    "count(steps where event == 'modulate')": ConstraintField.COUNT_EVENT_MODULATE,
    "max(steps[].magnitude) - min(steps[].magnitude)": ConstraintField.MAGNITUDE_RANGE,
    r"steps\[\d+\]\.magnitude - steps\[\d+\]\.magnitude": ConstraintField.STEP_DELTA,
    # Compositional targeting
    "sequence NOT IN": ConstraintField.SEQUENCE_NOT_IN,
    "sequence STARTS_WITH": ConstraintField.SEQUENCE_STARTS_WITH,
    "sequence ENDS_WITH": ConstraintField.SEQUENCE_ENDS_WITH,
}


def parse_operator(op_str: str) -> ConstraintOperator:
    """Parse operator string to enum."""
    op_map = {
        "==": ConstraintOperator.EQ,
        "!=": ConstraintOperator.NE,
        ">": ConstraintOperator.GT,
        ">=": ConstraintOperator.GE,
        "<": ConstraintOperator.LT,
        "<=": ConstraintOperator.LE,
        "in": ConstraintOperator.IN_RANGE,
    }
    if op_str not in op_map:
        raise Phase7ValidationError(
            ErrorType.INVALID_CONSTRAINT_PATTERN,
            f"Invalid operator: {op_str}",
            field=op_str,
        )
    return op_map[op_str]


def validate_numeric_literal(value: Any, field_name: str) -> None:
    """Validate that a value is a finite numeric literal."""
    if isinstance(value, bool):
        return  # Booleans are valid
    if isinstance(value, str):
        return  # Strings (like event values) are valid
    if isinstance(value, (int, float)):
        if math.isinf(value):
            raise Phase7ValidationError(
                ErrorType.INVALID_NUMERIC_LITERAL,
                f"Infinity not allowed in constraint value",
                field=field_name,
                value=str(value),
            )
        if math.isnan(value):
            raise Phase7ValidationError(
                ErrorType.INVALID_NUMERIC_LITERAL,
                f"NaN not allowed in constraint value",
                field=field_name,
                value=str(value),
            )
        return
    if isinstance(value, (tuple, list, set, frozenset)):
        # Validate each element in collections
        for item in value:
            if isinstance(item, (tuple, list)):
                # Nested sequence (for sequence constraints)
                for elem in item:
                    if isinstance(elem, (int, float)):
                        validate_numeric_literal(elem, field_name)
            elif isinstance(item, (int, float)):
                validate_numeric_literal(item, field_name)
        return


def check_semantic_content(field_name: str) -> None:
    """Check if field name contains forbidden semantic keywords."""
    field_lower = field_name.lower()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in field_lower:
            raise Phase7ValidationError(
                ErrorType.INVALID_TARGET_DIMENSION,
                f"Semantic content detected: '{keyword}' in field '{field_name}'",
                field=field_name,
            )


def parse_field(field_name: str) -> Tuple[ConstraintField, Optional[int], Optional[float]]:
    """
    Parse field name to constraint field enum, extracting index and threshold if present.

    Returns: (field_enum, index, threshold)
    """
    # Check for semantic content first
    check_semantic_content(field_name)

    # Direct matches
    if field_name == "final_magnitude":
        return ConstraintField.FINAL_MAGNITUDE, None, None
    if field_name == "len(steps)":
        return ConstraintField.LEN_STEPS, None, None
    if field_name == "steps[-1].event":
        return ConstraintField.TERMINAL_EVENT, None, None
    if field_name == "monotonic_increasing(steps[].magnitude)":
        return ConstraintField.MONOTONIC_INCREASING, None, None
    if field_name == "monotonic_decreasing(steps[].magnitude)":
        return ConstraintField.MONOTONIC_DECREASING, None, None
    if field_name == "count(steps where event == 'reset')":
        return ConstraintField.COUNT_EVENT_RESET, None, None
    if field_name == "count(steps where event == 'modulate')":
        return ConstraintField.COUNT_EVENT_MODULATE, None, None
    if field_name == "max(steps[].magnitude) - min(steps[].magnitude)":
        return ConstraintField.MAGNITUDE_RANGE, None, None
    if field_name == "sequence NOT IN":
        return ConstraintField.SEQUENCE_NOT_IN, None, None
    if field_name == "sequence STARTS_WITH":
        return ConstraintField.SEQUENCE_STARTS_WITH, None, None
    if field_name == "sequence ENDS_WITH":
        return ConstraintField.SEQUENCE_ENDS_WITH, None, None

    # Pattern matches with index extraction
    step_mag_match = re.match(r"steps\[(-?\d+)\]\.magnitude$", field_name)
    if step_mag_match:
        index = int(step_mag_match.group(1))
        return ConstraintField.STEP_MAGNITUDE, index, None

    step_event_match = re.match(r"steps\[(-?\d+)\]\.event$", field_name)
    if step_event_match:
        index = int(step_event_match.group(1))
        return ConstraintField.STEP_EVENT, index, None

    # Count with threshold
    count_mag_gt_match = re.match(r"count\(steps where magnitude > ([\d.]+)\)$", field_name)
    if count_mag_gt_match:
        threshold = float(count_mag_gt_match.group(1))
        return ConstraintField.COUNT_MAGNITUDE_GT, None, threshold

    count_mag_lt_match = re.match(r"count\(steps where magnitude < ([\d.]+)\)$", field_name)
    if count_mag_lt_match:
        threshold = float(count_mag_lt_match.group(1))
        return ConstraintField.COUNT_MAGNITUDE_LT, None, threshold

    # Step delta (only i-1 allowed per contract)
    step_delta_match = re.match(r"steps\[(\d+)\]\.magnitude - steps\[(\d+)\]\.magnitude$", field_name)
    if step_delta_match:
        i = int(step_delta_match.group(1))
        j = int(step_delta_match.group(2))
        if j != i - 1:
            raise Phase7ValidationError(
                ErrorType.INVALID_CONSTRAINT_PATTERN,
                f"Only steps[i].magnitude - steps[i-1].magnitude allowed, got steps[{i}] - steps[{j}]",
                field=field_name,
            )
        return ConstraintField.STEP_DELTA, i, None

    # Unknown field
    raise Phase7ValidationError(
        ErrorType.UNKNOWN_TARGET_FIELD,
        f"Unknown target field: {field_name}",
        field=field_name,
    )


def parse_constraint(field_name: str, value: Any) -> Constraint:
    """Parse a single constraint from field name and value."""
    # Parse the field
    field_enum, index, threshold = parse_field(field_name)

    # Determine operator and actual value
    if isinstance(value, str):
        # Parse operator from string like ">= 1.5"
        op_match = re.match(r"^(==|!=|>=|<=|>|<|in)\s*(.+)$", value.strip())
        if op_match:
            operator = parse_operator(op_match.group(1))
            val_str = op_match.group(2).strip()

            # Parse the value
            if val_str.lower() == "true":
                actual_value = True
            elif val_str.lower() == "false":
                actual_value = False
            elif val_str.startswith("'") and val_str.endswith("'"):
                actual_value = val_str[1:-1]
            elif val_str.startswith('"') and val_str.endswith('"'):
                actual_value = val_str[1:-1]
            elif val_str.startswith("[") and val_str.endswith("]"):
                # Range like [1.0, 1.5]
                parts = val_str[1:-1].split(",")
                actual_value = tuple(float(p.strip()) for p in parts)
            else:
                try:
                    actual_value = float(val_str)
                    if actual_value == int(actual_value):
                        actual_value = int(actual_value)
                except ValueError:
                    actual_value = val_str
        else:
            # Assume equality for simple values
            operator = ConstraintOperator.EQ
            actual_value = value
    elif isinstance(value, (list, tuple, set, frozenset)):
        # Sequence constraints or range
        operator = ConstraintOperator.EQ
        if isinstance(value, (set, frozenset)):
            actual_value = tuple(sorted(value))
        else:
            actual_value = tuple(value)
    else:
        # Direct value, assume equality
        operator = ConstraintOperator.EQ
        actual_value = value

    # Validate numeric literals
    validate_numeric_literal(actual_value, field_name)

    return Constraint(
        field=field_enum,
        operator=operator,
        value=actual_value,
        index=index,
        threshold=threshold,
    )


def parse_target_spec(raw_spec: Dict[str, Any]) -> TargetSpec:
    """
    Parse raw dictionary into validated TargetSpec.

    Raises:
        Phase7ValidationError: If spec contains invalid fields or patterns
    """
    if not raw_spec:
        raise Phase7ValidationError(
            ErrorType.VACUOUS_TARGET,
            "Empty target specification: at least one constraint required",
        )

    constraints: Set[Constraint] = set()

    for field_name, value in raw_spec.items():
        constraint = parse_constraint(field_name, value)
        constraints.add(constraint)

    return TargetSpec(constraints=frozenset(constraints))


def validate_target_spec(spec: TargetSpec) -> None:
    """
    Validate complete target specification.

    Raises:
        Phase7ValidationError: With appropriate ErrorType
    """
    if not spec.constraints:
        raise Phase7ValidationError(
            ErrorType.VACUOUS_TARGET,
            "Empty target specification: at least one constraint required",
        )

    # All constraints are already validated during parsing
    # Additional cross-constraint validation happens in detect_contradictions


def detect_contradictions(spec: TargetSpec) -> Optional[ExecutionError]:
    """
    Static analysis for contradictory constraints.

    Checks:
        - Direct contradictions (x > 2 AND x < 1)
        - Phase-6 invariant violations (steps[0].event == modulate)
        - Index bound contradictions (steps[5] with len <= 3)

    Returns:
        ExecutionError if contradiction found, None otherwise
    """
    # Collect constraints by field for cross-checking
    magnitude_bounds: List[Tuple[ConstraintOperator, float]] = []
    length_bounds: List[Tuple[ConstraintOperator, int]] = []
    indexed_constraints: List[Tuple[int, str]] = []  # (index, field_name)

    for c in spec.constraints:
        # Check Phase-6 invariants
        if c.field == ConstraintField.STEP_EVENT and c.index == 0:
            if c.value == "modulate" and c.operator == ConstraintOperator.EQ:
                return create_error(
                    ErrorType.CONTRADICTORY_TARGET,
                    "steps[0].event cannot be 'modulate' - Phase-6 invariant: first token must be consonant (reset)",
                )

        if c.field == ConstraintField.FINAL_MAGNITUDE:
            if isinstance(c.value, (int, float)):
                if c.operator == ConstraintOperator.LT and c.value <= 1.0:
                    return create_error(
                        ErrorType.CONTRADICTORY_TARGET,
                        f"final_magnitude < {c.value} is impossible - Phase-6 invariant: minimum magnitude is 1.0",
                    )
                if c.operator == ConstraintOperator.LE and c.value < 1.0:
                    return create_error(
                        ErrorType.CONTRADICTORY_TARGET,
                        f"final_magnitude <= {c.value} is impossible - Phase-6 invariant: minimum magnitude is 1.0",
                    )
                if c.operator == ConstraintOperator.EQ and c.value < 1.0:
                    return create_error(
                        ErrorType.CONTRADICTORY_TARGET,
                        f"final_magnitude == {c.value} is impossible - Phase-6 invariant: minimum magnitude is 1.0",
                    )
                magnitude_bounds.append((c.operator, c.value))

        if c.field == ConstraintField.LEN_STEPS:
            if isinstance(c.value, int):
                if c.operator == ConstraintOperator.EQ and c.value < 1:
                    return create_error(
                        ErrorType.CONTRADICTORY_TARGET,
                        f"len(steps) == {c.value} is impossible - Phase-6 invariant: minimum length is 1",
                    )
                if c.operator == ConstraintOperator.LT and c.value <= 1:
                    return create_error(
                        ErrorType.CONTRADICTORY_TARGET,
                        f"len(steps) < {c.value} is impossible - Phase-6 invariant: minimum length is 1",
                    )
                if c.operator == ConstraintOperator.LE and c.value < 1:
                    return create_error(
                        ErrorType.CONTRADICTORY_TARGET,
                        f"len(steps) <= {c.value} is impossible - Phase-6 invariant: minimum length is 1",
                    )
                length_bounds.append((c.operator, c.value))

        # Track indexed constraints for bound checking
        if c.index is not None and c.index >= 0:
            indexed_constraints.append((c.index, str(c.field.value)))

    # Check magnitude bound contradictions
    if len(magnitude_bounds) >= 2:
        lower = None
        upper = None
        for op, val in magnitude_bounds:
            if op in (ConstraintOperator.GT, ConstraintOperator.GE):
                if lower is None or val > lower:
                    lower = val
            if op in (ConstraintOperator.LT, ConstraintOperator.LE):
                if upper is None or val < upper:
                    upper = val
        if lower is not None and upper is not None and lower >= upper:
            return create_error(
                ErrorType.CONTRADICTORY_TARGET,
                f"Contradictory magnitude bounds: >= {lower} AND < {upper}",
            )

    # Check length bound contradictions
    if len(length_bounds) >= 2:
        lower = None
        upper = None
        exact_values = set()
        for op, val in length_bounds:
            if op == ConstraintOperator.EQ:
                exact_values.add(val)
            if op in (ConstraintOperator.GT, ConstraintOperator.GE):
                if lower is None or val > lower:
                    lower = val
            if op in (ConstraintOperator.LT, ConstraintOperator.LE):
                if upper is None or val < upper:
                    upper = val

        if len(exact_values) > 1:
            return create_error(
                ErrorType.CONTRADICTORY_TARGET,
                f"Contradictory length constraints: len(steps) == {sorted(exact_values)}",
            )

        if lower is not None and upper is not None and lower >= upper:
            return create_error(
                ErrorType.CONTRADICTORY_TARGET,
                f"Contradictory length bounds: >= {lower} AND < {upper}",
            )

    # Check index bounds against length constraints
    if indexed_constraints and length_bounds:
        max_index = max(idx for idx, _ in indexed_constraints)
        for op, val in length_bounds:
            if op == ConstraintOperator.LE and max_index >= val:
                return create_error(
                    ErrorType.CONTRADICTORY_TARGET,
                    f"Index {max_index} unreachable with len(steps) <= {val}",
                )
            if op == ConstraintOperator.LT and max_index >= val - 1:
                return create_error(
                    ErrorType.CONTRADICTORY_TARGET,
                    f"Index {max_index} unreachable with len(steps) < {val}",
                )
            if op == ConstraintOperator.EQ and max_index >= val:
                return create_error(
                    ErrorType.CONTRADICTORY_TARGET,
                    f"Index {max_index} unreachable with len(steps) == {val}",
                )

    # Check monotonic contradictions
    has_increasing = any(c.field == ConstraintField.MONOTONIC_INCREASING and c.value is True
                         for c in spec.constraints)
    has_decreasing = any(c.field == ConstraintField.MONOTONIC_DECREASING and c.value is True
                         for c in spec.constraints)

    if has_increasing and has_decreasing:
        # Check if length allows both (only length 1 can be both)
        has_length_gt_1 = any(
            c.field == ConstraintField.LEN_STEPS and
            c.operator in (ConstraintOperator.GT, ConstraintOperator.GE) and
            c.value >= 2
            for c in spec.constraints
        )
        if has_length_gt_1:
            return create_error(
                ErrorType.CONTRADICTORY_TARGET,
                "Cannot be both monotonically increasing and decreasing with len(steps) > 1",
            )

    return None


def get_phase6_invariants() -> FrozenSet[Constraint]:
    """
    Return Phase-6 invariants as implicit constraints.

    These are always true:
    - steps[0].event == "reset"
    - final_magnitude >= 1.0
    - len(steps) >= 1
    """
    return frozenset([
        Constraint(
            field=ConstraintField.STEP_EVENT,
            operator=ConstraintOperator.EQ,
            value="reset",
            index=0,
        ),
        Constraint(
            field=ConstraintField.FINAL_MAGNITUDE,
            operator=ConstraintOperator.GE,
            value=1.0,
        ),
        Constraint(
            field=ConstraintField.LEN_STEPS,
            operator=ConstraintOperator.GE,
            value=1,
        ),
    ])
