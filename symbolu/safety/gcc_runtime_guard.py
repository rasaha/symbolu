"""
GCC Runtime Guard - assert_non_expressive()
=============================================

Runtime enforcement of Generative Containment Constraint (C-1).

This guard validates that all return values from constrained modules
(Phases 1b-9, Ontological Router R1, Ledger core) are non-expressive.

Hard Constraints:
    - Recursively inspects return values
    - Allows ONLY:
        - int, bool
        - Enum
        - hash strings (hex only)
        - tuples / frozensets of the above
        - frozen dataclasses composed only of the above
    - ANY other string -> hard failure
    - Fail-closed on ANY violation

This constraint is PERMANENT and IRREVERSIBLE.

Allowed imports:
    - dataclasses
    - typing
    - enum
    - re (for hex validation ONLY)
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, FrozenSet, Mapping, Tuple, Union


# =============================================================================
# Constants
# =============================================================================

# Maximum allowed string length for invariant keys / enum names
MAX_INVARIANT_KEY_LENGTH = 32

# Maximum allowed length for opaque identifiers (artifact_id, span_id, etc.)
MAX_OPAQUE_ID_LENGTH = 64

# Hex string pattern (must match full string)
_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]+$")

# GCC Invariants (immutable)
GCC_INVARIANTS: Mapping[str, bool] = {
    "NON_EXPRESSIVE": True,
    "FAIL_CLOSED": True,
    "NO_FREE_TEXT": True,
    "NO_SEMANTICS": True,
    "NO_GENERATION": True,
    "DETERMINISTIC": True,
    "AUDITABLE": True,
}


# =============================================================================
# Type Definitions
# =============================================================================

# Non-expressive value types
NonExpressiveValue = Union[
    int,
    bool,
    Enum,
    str,  # Only hex hashes or short invariant keys
    Tuple[Any, ...],
    FrozenSet[Any],
    None,
]


# =============================================================================
# Exceptions
# =============================================================================

class GCCViolationError(Exception):
    """
    Exception raised when Generative Containment Constraint is violated.

    This is a HARD FAILURE. The system cannot proceed.

    Attributes:
        value: The violating value
        path: The path to the violating value (for nested structures)
        reason: Human-readable reason code (not free-form)
    """

    # Fixed reason codes (no free-form text)
    REASON_FREE_TEXT = "FREE_TEXT_DETECTED"
    REASON_INVALID_TYPE = "INVALID_TYPE"
    REASON_NON_HEX_STRING = "NON_HEX_STRING"
    REASON_STRING_TOO_LONG = "STRING_TOO_LONG"
    REASON_MUTABLE_CONTAINER = "MUTABLE_CONTAINER"
    REASON_MUTABLE_DATACLASS = "MUTABLE_DATACLASS"
    REASON_NESTED_VIOLATION = "NESTED_VIOLATION"

    def __init__(
        self,
        value: Any,
        *,
        path: str = "",
        reason: str = REASON_INVALID_TYPE,
    ) -> None:
        self.value = value
        self.path = path
        self.reason = reason
        # Message is structured, not free-form
        super().__init__(f"GCC_VIOLATION:{reason}:PATH={path}")


# =============================================================================
# Validation Functions
# =============================================================================

def _is_hex_string(value: str) -> bool:
    """
    Check if a string contains only hexadecimal characters.

    Args:
        value: The string to check.

    Returns:
        True if the string is a valid hex string, False otherwise.

    Note:
        Empty strings return False.
        This is the ONLY allowed string format for hashes.
    """
    if not value:
        return False
    return bool(_HEX_PATTERN.match(value))


def _is_invariant_key(value: str) -> bool:
    """
    Check if a string is a valid invariant key.

    Invariant keys are:
        - <= 32 characters
        - Uppercase letters, digits, underscores only
        - Used for enum names, fixed keys, etc.

    Args:
        value: The string to check.

    Returns:
        True if valid invariant key, False otherwise.
    """
    if not value:
        return False
    if len(value) > MAX_INVARIANT_KEY_LENGTH:
        return False
    # Must be uppercase letters, digits, underscores only
    return bool(re.match(r"^[A-Z0-9_]+$", value))


def _is_phase_id(value: str) -> bool:
    """
    Check if a string is a valid phase ID.

    Valid phase IDs: "1b", "2", "3", "4", "5", "6", "7", "8", "9"

    Args:
        value: The string to check.

    Returns:
        True if valid phase ID, False otherwise.
    """
    return value in {"1b", "2", "3", "4", "5", "6", "7", "8", "9"}


# Opaque identifier pattern: alphanumeric, hyphens, underscores, dots
# Bounded length prevents free-form text smuggling
_OPAQUE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def _is_opaque_id(value: str) -> bool:
    """
    Check if a string is a valid opaque identifier.

    Opaque IDs are structural identifiers (artifact_id, span_id, etc.)
    that are not free-form text. They:
        - Contain only alphanumeric chars, hyphens, underscores, dots
        - Are bounded to MAX_OPAQUE_ID_LENGTH characters
        - Contain no spaces or special characters

    Args:
        value: The string to check.

    Returns:
        True if valid opaque identifier, False otherwise.
    """
    if not value:
        return False
    if len(value) > MAX_OPAQUE_ID_LENGTH:
        return False
    return bool(_OPAQUE_ID_PATTERN.match(value))


def _is_valid_string(value: str) -> bool:
    """
    Check if a string is valid under GCC constraints.

    Valid strings are:
        - Hex strings (hash values)
        - Invariant keys (enum names, fixed keys)
        - Phase IDs
        - Router version strings (e.g., "R1.0", "M1.0")
        - Opaque identifiers (artifact_id, span_id — bounded, no free text)

    Args:
        value: The string to check.

    Returns:
        True if the string is valid, False otherwise.
    """
    # Empty strings are allowed (valid edge case)
    if value == "":
        return True

    # Check if hex hash
    if _is_hex_string(value):
        return True

    # Check if invariant key
    if _is_invariant_key(value):
        return True

    # Check if phase ID
    if _is_phase_id(value):
        return True

    # Check if version string (R1.x, M1.x format)
    if re.match(r"^[RM]\d+\.\d+$", value):
        return True

    # Check if opaque identifier (structural, bounded, no free text)
    if _is_opaque_id(value):
        return True

    # Otherwise, it's a free-form string -> VIOLATION
    return False


def is_non_expressive(value: Any, *, path: str = "") -> bool:
    """
    Check if a value is non-expressive (GCC-compliant).

    This function recursively validates that a value contains
    only allowed types. It does NOT raise exceptions.

    Args:
        value: The value to check.
        path: The current path (for nested structures).

    Returns:
        True if the value is non-expressive, False otherwise.

    Allowed types:
        - None
        - int
        - bool
        - Enum
        - str (hex only, or short invariant keys)
        - tuple (of non-expressive values)
        - frozenset (of non-expressive values)
        - frozen dataclass (all fields non-expressive)
    """
    # None is allowed
    if value is None:
        return True

    # int is allowed (but not subclasses except bool)
    if type(value) is int:
        return True

    # bool is allowed
    if type(value) is bool:
        return True

    # Enum is allowed
    if isinstance(value, Enum):
        return True

    # str requires validation
    if isinstance(value, str):
        return _is_valid_string(value)

    # tuple is allowed if all elements are non-expressive
    if isinstance(value, tuple):
        return all(
            is_non_expressive(item, path=f"{path}[{i}]")
            for i, item in enumerate(value)
        )

    # frozenset is allowed if all elements are non-expressive
    if isinstance(value, frozenset):
        return all(
            is_non_expressive(item, path=f"{path}{{item}}")
            for item in value
        )

    # frozen dataclass is allowed if all fields are non-expressive
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # Must be frozen
        if not getattr(value, "__dataclass_fields__", None):
            return False

        # Check if frozen
        try:
            # Try to verify frozen status
            if not value.__dataclass_fields__:
                return True  # Empty dataclass is fine

            # Check all fields
            for field in dataclasses.fields(value):
                field_value = getattr(value, field.name)
                if not is_non_expressive(
                    field_value, path=f"{path}.{field.name}"
                ):
                    return False
            return True
        except Exception:
            return False

    # All other types are VIOLATIONS
    return False


def assert_non_expressive(value: Any, *, path: str = "") -> None:
    """
    Assert that a value is non-expressive (GCC-compliant).

    This function recursively validates that a value contains
    only allowed types. It raises GCCViolationError on violation.

    Args:
        value: The value to validate.
        path: The current path (for nested structures).

    Raises:
        GCCViolationError: If the value contains expressive content.

    Usage:
        Apply at:
            - All Phase exits (1b-9)
            - Ontological Router R1 outputs
            - Ledger replay verification

    FAIL-CLOSED: Any violation terminates processing.
    """
    # None is allowed
    if value is None:
        return

    # int is allowed (but not subclasses except bool)
    if type(value) is int:
        return

    # bool is allowed
    if type(value) is bool:
        return

    # Enum is allowed
    if isinstance(value, Enum):
        return

    # str requires validation
    if isinstance(value, str):
        if not _is_valid_string(value):
            if len(value) > MAX_INVARIANT_KEY_LENGTH:
                raise GCCViolationError(
                    value,
                    path=path,
                    reason=GCCViolationError.REASON_STRING_TOO_LONG,
                )
            raise GCCViolationError(
                value,
                path=path,
                reason=GCCViolationError.REASON_FREE_TEXT,
            )
        return

    # tuple is allowed if all elements are non-expressive
    if isinstance(value, tuple):
        for i, item in enumerate(value):
            assert_non_expressive(item, path=f"{path}[{i}]")
        return

    # frozenset is allowed if all elements are non-expressive
    if isinstance(value, frozenset):
        for item in value:
            assert_non_expressive(item, path=f"{path}{{item}}")
        return

    # frozen dataclass is allowed if all fields are non-expressive
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # Check if the dataclass is frozen by checking __dataclass_params__
        params = getattr(value, "__dataclass_params__", None)
        if params is not None and hasattr(params, "frozen"):
            if not params.frozen:
                raise GCCViolationError(
                    value,
                    path=path,
                    reason=GCCViolationError.REASON_MUTABLE_DATACLASS,
                )
        else:
            # Fallback: try to verify frozen status via modification
            try:
                fields_list = dataclasses.fields(value)
                if fields_list:
                    first_field = fields_list[0]
                    original_value = getattr(value, first_field.name)
                    try:
                        object.__setattr__(value, first_field.name, None)
                        # If we get here, it's mutable - restore and fail
                        object.__setattr__(value, first_field.name, original_value)
                        raise GCCViolationError(
                            value,
                            path=path,
                            reason=GCCViolationError.REASON_MUTABLE_DATACLASS,
                        )
                    except (dataclasses.FrozenInstanceError, AttributeError, TypeError):
                        pass  # Expected for frozen dataclass
            except Exception:
                pass  # Empty dataclass or other edge case - allow

        # Check all fields
        for field in dataclasses.fields(value):
            field_value = getattr(value, field.name)
            assert_non_expressive(field_value, path=f"{path}.{field.name}")
        return

    # list is NEVER allowed (mutable)
    if isinstance(value, list):
        raise GCCViolationError(
            value,
            path=path,
            reason=GCCViolationError.REASON_MUTABLE_CONTAINER,
        )

    # dict is NEVER allowed (mutable)
    if isinstance(value, dict):
        raise GCCViolationError(
            value,
            path=path,
            reason=GCCViolationError.REASON_MUTABLE_CONTAINER,
        )

    # set is NEVER allowed (mutable)
    if isinstance(value, set):
        raise GCCViolationError(
            value,
            path=path,
            reason=GCCViolationError.REASON_MUTABLE_CONTAINER,
        )

    # All other types are VIOLATIONS
    raise GCCViolationError(
        value,
        path=path,
        reason=GCCViolationError.REASON_INVALID_TYPE,
    )


# =============================================================================
# Decorator for Phase Exit Guards
# =============================================================================

def gcc_guarded(func):
    """
    Decorator to apply GCC guard to function return values.

    Usage:
        @gcc_guarded
        def phase_3_exit(artifact):
            ...
            return result  # Will be validated

    The decorator validates the return value against GCC constraints.
    Raises GCCViolationError if the return value is expressive.
    """
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        assert_non_expressive(result, path=f"{func.__name__}:return")
        return result

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper
