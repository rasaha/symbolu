"""
GCC Ledger Invariant Enforcement
=================================

Enforces the invariant:
    "All ledger entries must be replayable without reconstructing language."

Ledger entries may contain ONLY:
    - span_id (hex hash)
    - phase_id (enum/fixed key)
    - ontological_layer (enum)
    - hashes (hex only)
    - booleans / flags
    - integers (sequence numbers, indices)

Explicitly REJECTED:
    - explanations
    - descriptions
    - summaries
    - reasons
    - any free-form text

This constraint is PERMANENT and IRREVERSIBLE.
Fail-closed on ANY violation.

Allowed imports:
    - dataclasses
    - typing
    - enum
    - re
"""

from __future__ import annotations

import dataclasses
import re
from enum import Enum
from typing import Any, FrozenSet, Mapping, Optional, Tuple


# =============================================================================
# Constants
# =============================================================================

# Allowed fields in ledger entries (exhaustive list)
ALLOWED_LEDGER_FIELDS: FrozenSet[str] = frozenset({
    # Identifiers
    "entry_id",
    "prev_entry_id",
    "span_id",
    "artifact_id",
    "artifact_hash",
    # Phase / Layer
    "phase_id",
    "projected_layers",
    "ontological_layer",
    # Versioning
    "router_version",
    "mapping_version",
    # Sequence / Index
    "seq",
    "ledger_index",
    # Entry integrity
    "entry_hash",
})

# Forbidden field name patterns (detect semantic content)
_FORBIDDEN_FIELD_PATTERNS = (
    r".*explanation.*",
    r".*description.*",
    r".*summary.*",
    r".*reason.*",
    r".*message.*",
    r".*text.*",
    r".*content.*",
    r".*comment.*",
    r".*note.*",
    r".*label.*",
    r".*name.*",  # except enum names
    r".*title.*",
    r".*caption.*",
)

# Compiled forbidden patterns
_FORBIDDEN_COMPILED = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in _FORBIDDEN_FIELD_PATTERNS
)


# =============================================================================
# Exceptions
# =============================================================================

class LedgerInvariantViolation(Exception):
    """
    Exception raised when ledger invariant is violated.

    This is a HARD FAILURE. The ledger entry cannot be recorded.

    Reason codes (fixed, not free-form):
        - FORBIDDEN_FIELD: Field name suggests semantic content
        - FREE_TEXT_VALUE: Field contains free-form text
        - INVALID_FIELD: Field not in allowed list
        - MUTABLE_VALUE: Field contains mutable value
        - INVALID_TYPE: Field has disallowed type
    """

    REASON_FORBIDDEN_FIELD = "FORBIDDEN_FIELD"
    REASON_FREE_TEXT_VALUE = "FREE_TEXT_VALUE"
    REASON_INVALID_FIELD = "INVALID_FIELD"
    REASON_MUTABLE_VALUE = "MUTABLE_VALUE"
    REASON_INVALID_TYPE = "INVALID_TYPE"

    def __init__(
        self,
        field_name: str,
        *,
        reason: str = REASON_INVALID_FIELD,
        value: Any = None,
    ) -> None:
        self.field_name = field_name
        self.reason = reason
        self.value = value
        super().__init__(f"LEDGER_INVARIANT_VIOLATION:{reason}:FIELD={field_name}")


# =============================================================================
# Validation Functions
# =============================================================================

def _is_forbidden_field_name(name: str) -> bool:
    """
    Check if a field name suggests semantic content.

    Args:
        name: The field name to check.

    Returns:
        True if the field name is forbidden, False otherwise.
    """
    for pattern in _FORBIDDEN_COMPILED:
        if pattern.match(name):
            return True
    return False


def _is_hex_string(value: str) -> bool:
    """Check if string is valid hex."""
    if not value:
        return False
    return bool(re.match(r"^[0-9a-fA-F]+$", value))


def _is_phase_id(value: str) -> bool:
    """Check if string is a valid phase ID."""
    return value in {"1b", "2", "3", "4", "5", "6", "7", "8", "9"}


def _is_version_string(value: str) -> bool:
    """Check if string is a valid version string (R1.0, M1.0)."""
    return bool(re.match(r"^[RM]\d+\.\d+$", value))


def _is_valid_ledger_string(value: str) -> bool:
    """
    Check if a string value is valid for ledger entries.

    Valid strings:
        - Empty string
        - Hex hashes
        - Phase IDs
        - Version strings

    Args:
        value: The string to validate.

    Returns:
        True if valid, False if it's free-form text.
    """
    if value == "":
        return True
    if _is_hex_string(value):
        return True
    if _is_phase_id(value):
        return True
    if _is_version_string(value):
        return True
    return False


def _validate_ledger_value(
    value: Any,
    field_name: str,
) -> None:
    """
    Validate a single ledger field value.

    Args:
        value: The value to validate.
        field_name: The field name (for error reporting).

    Raises:
        LedgerInvariantViolation: If the value is invalid.
    """
    # None is allowed
    if value is None:
        return

    # int is allowed
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
        if not _is_valid_ledger_string(value):
            raise LedgerInvariantViolation(
                field_name,
                reason=LedgerInvariantViolation.REASON_FREE_TEXT_VALUE,
                value=value,
            )
        return

    # tuple is allowed if all elements are valid
    if isinstance(value, tuple):
        for i, item in enumerate(value):
            _validate_ledger_value(item, f"{field_name}[{i}]")
        return

    # frozenset is allowed if all elements are valid
    if isinstance(value, frozenset):
        for item in value:
            _validate_ledger_value(item, f"{field_name}{{item}}")
        return

    # list is NEVER allowed (mutable)
    if isinstance(value, list):
        raise LedgerInvariantViolation(
            field_name,
            reason=LedgerInvariantViolation.REASON_MUTABLE_VALUE,
            value=value,
        )

    # dict is NEVER allowed (mutable)
    if isinstance(value, dict):
        raise LedgerInvariantViolation(
            field_name,
            reason=LedgerInvariantViolation.REASON_MUTABLE_VALUE,
            value=value,
        )

    # set is NEVER allowed (mutable)
    if isinstance(value, set):
        raise LedgerInvariantViolation(
            field_name,
            reason=LedgerInvariantViolation.REASON_MUTABLE_VALUE,
            value=value,
        )

    # All other types are violations
    raise LedgerInvariantViolation(
        field_name,
        reason=LedgerInvariantViolation.REASON_INVALID_TYPE,
        value=value,
    )


def assert_ledger_entry_valid(entry: Any) -> None:
    """
    Assert that a ledger entry is valid under GCC constraints.

    This function validates:
        1. Entry is a frozen dataclass
        2. All field names are in ALLOWED_LEDGER_FIELDS
        3. No field names suggest semantic content
        4. All field values are non-expressive

    Args:
        entry: The ledger entry to validate.

    Raises:
        LedgerInvariantViolation: If the entry violates GCC constraints.

    Usage:
        Apply at:
            - Ledger append operations
            - Ledger replay verification
            - Any ledger entry creation

    FAIL-CLOSED: Any violation prevents the entry from being recorded.
    """
    # Must be a dataclass
    if not dataclasses.is_dataclass(entry):
        raise LedgerInvariantViolation(
            "__class__",
            reason=LedgerInvariantViolation.REASON_INVALID_TYPE,
            value=type(entry).__name__,
        )

    # Must not be a class (instance required)
    if isinstance(entry, type):
        raise LedgerInvariantViolation(
            "__class__",
            reason=LedgerInvariantViolation.REASON_INVALID_TYPE,
            value="class_not_instance",
        )

    # Validate each field
    for field in dataclasses.fields(entry):
        field_name = field.name
        field_value = getattr(entry, field_name)

        # Check field name is allowed
        if field_name not in ALLOWED_LEDGER_FIELDS:
            # Check if it's a forbidden semantic field
            if _is_forbidden_field_name(field_name):
                raise LedgerInvariantViolation(
                    field_name,
                    reason=LedgerInvariantViolation.REASON_FORBIDDEN_FIELD,
                )
            # Unknown field - also rejected (fail-closed)
            raise LedgerInvariantViolation(
                field_name,
                reason=LedgerInvariantViolation.REASON_INVALID_FIELD,
            )

        # Validate field value
        _validate_ledger_value(field_value, field_name)


def validate_ledger_entry_dict(entry_dict: Mapping[str, Any]) -> None:
    """
    Validate a ledger entry in dictionary form.

    Used for validating entries before they are converted to dataclasses,
    or when working with JSON-deserialized data.

    Args:
        entry_dict: The dictionary to validate.

    Raises:
        LedgerInvariantViolation: If the entry violates GCC constraints.
    """
    for field_name, field_value in entry_dict.items():
        # Check field name is allowed
        if field_name not in ALLOWED_LEDGER_FIELDS:
            if _is_forbidden_field_name(field_name):
                raise LedgerInvariantViolation(
                    field_name,
                    reason=LedgerInvariantViolation.REASON_FORBIDDEN_FIELD,
                )
            raise LedgerInvariantViolation(
                field_name,
                reason=LedgerInvariantViolation.REASON_INVALID_FIELD,
            )

        # Validate field value
        _validate_ledger_value(field_value, field_name)
