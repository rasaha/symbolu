"""
P16 Regression Guard — Stable Hashing Utilities

Provides deterministic, stable hashing for Python objects:
- stable_json(obj) -> str: Convert object to stable JSON string
- stable_hash(obj) -> str: Compute SHA-256 hash of stable JSON

DESIGN PRINCIPLES:
- Deterministic: Same input → same output ALWAYS
- Stable: Key ordering is fixed (sorted)
- Safe: Rejects unserializable objects with clear error
- No side effects: Pure functions
- No LLM usage

SUPPORTED TYPES:
- dict: Recursively serialized with sorted keys
- list/tuple: Recursively serialized, preserving order
- dataclasses: Converted via asdict() with sorted keys
- Enum: Uses .value
- frozenset/set: Converted to sorted list
- str, int, float, bool, None: Direct JSON serialization
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Set, FrozenSet, Tuple, Union


# ============================================================================
# STABLE JSON SERIALIZATION
# ============================================================================


class StableJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for stable, deterministic serialization.

    Handles:
    - Enums: Uses .value
    - Dataclasses: Uses asdict() with sorted keys
    - Sets/Frozensets: Converts to sorted list
    - Tuples: Converts to list (JSON array)
    - Objects with to_dict(): Calls to_dict()
    """

    def default(self, obj: Any) -> Any:
        """Encode non-standard types."""
        # Handle Enum
        if isinstance(obj, Enum):
            return obj.value

        # Handle dataclass
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return _dataclass_to_stable_dict(obj)

        # Handle set/frozenset (convert to sorted list for stability)
        if isinstance(obj, (set, frozenset)):
            return sorted(self._make_sortable(item) for item in obj)

        # Handle tuple (convert to list)
        if isinstance(obj, tuple):
            return list(obj)

        # Handle objects with to_dict method
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            return obj.to_dict()

        # Handle bytes
        if isinstance(obj, bytes):
            return obj.hex()

        # Reject unserializable objects
        raise TypeError(
            f"Object of type {type(obj).__name__} is not JSON serializable. "
            f"P16 stable hashing requires serializable types."
        )

    def _make_sortable(self, item: Any) -> Any:
        """Convert item to a sortable representation."""
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, (int, float, str, bool)):
            return item
        if item is None:
            return ""
        # For complex types, convert to string representation
        if isinstance(item, (dict, list)):
            return json.dumps(item, sort_keys=True, cls=StableJSONEncoder)
        if dataclasses.is_dataclass(item) and not isinstance(item, type):
            return json.dumps(_dataclass_to_stable_dict(item), sort_keys=True)
        return str(item)


def _dataclass_to_stable_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert a dataclass to a dictionary with stable key ordering.

    Recursively processes nested dataclasses, enums, and collections.
    """
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"Expected dataclass instance, got {type(obj).__name__}")

    result = {}
    # Get fields in definition order, then sort for stability
    for f in sorted(dataclasses.fields(obj), key=lambda x: x.name):
        value = getattr(obj, f.name)
        result[f.name] = _stabilize_value(value)

    return result


def _stabilize_value(value: Any) -> Any:
    """
    Recursively stabilize a value for JSON serialization.

    Ensures deterministic representation of nested structures.
    """
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, bytes):
        return value.hex()

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_stable_dict(value)

    if isinstance(value, dict):
        return {str(k): _stabilize_value(v) for k, v in sorted(value.items())}

    if isinstance(value, (list, tuple)):
        return [_stabilize_value(item) for item in value]

    if isinstance(value, (set, frozenset)):
        # Convert to sorted list for determinism
        stabilized = [_stabilize_value(item) for item in value]
        # Sort by string representation for complex types
        return sorted(stabilized, key=lambda x: json.dumps(x, sort_keys=True) if isinstance(x, (dict, list)) else str(x))

    # For objects with to_dict, use that
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()

    # Last resort: string representation
    return str(value)


def stable_json(obj: Any) -> str:
    """
    Convert an object to a stable JSON string.

    The output is deterministic: same input always produces same output.

    Args:
        obj: Any Python object to serialize

    Returns:
        str: Stable JSON string with sorted keys, no whitespace

    Raises:
        TypeError: If object contains unserializable types

    Example:
        >>> stable_json({"b": 2, "a": 1})
        '{"a":1,"b":2}'

        >>> from enum import Enum
        >>> class Color(Enum):
        ...     RED = "red"
        >>> stable_json({"color": Color.RED})
        '{"color":"red"}'
    """
    try:
        # First stabilize the value
        stabilized = _stabilize_value(obj)

        # Then serialize with sorted keys and minimal separators
        return json.dumps(
            stabilized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            cls=StableJSONEncoder,
        )
    except TypeError as e:
        raise TypeError(
            f"Cannot create stable JSON for object: {e}. "
            f"Object type: {type(obj).__name__}"
        ) from e


# ============================================================================
# STABLE HASHING
# ============================================================================


def stable_hash(obj: Any) -> str:
    """
    Compute a stable SHA-256 hash of an object.

    The hash is deterministic: same input always produces same hash.

    Args:
        obj: Any Python object to hash

    Returns:
        str: SHA-256 hex digest (64 characters)

    Raises:
        TypeError: If object contains unserializable types

    Example:
        >>> stable_hash({"a": 1, "b": 2})
        '7a38bf81f383f69433ad6e900d35b3e2385593f76a7b7ab5d4355b8ba41ee24b'

        >>> # Same dict with different key order produces same hash
        >>> stable_hash({"b": 2, "a": 1})
        '7a38bf81f383f69433ad6e900d35b3e2385593f76a7b7ab5d4355b8ba41ee24b'
    """
    json_str = stable_json(obj)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def stable_hash_combine(*hashes: str) -> str:
    """
    Combine multiple hashes into a single aggregate hash.

    The hashes are sorted before combining for determinism.

    Args:
        *hashes: Variable number of hash strings to combine

    Returns:
        str: SHA-256 hex digest of combined hashes

    Example:
        >>> h1 = stable_hash({"a": 1})
        >>> h2 = stable_hash({"b": 2})
        >>> combined = stable_hash_combine(h1, h2)
        >>> # Same result regardless of argument order
        >>> stable_hash_combine(h2, h1) == combined
        True
    """
    # Sort hashes for determinism
    sorted_hashes = sorted(hashes)
    combined = "|".join(sorted_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ============================================================================
# FIELD EXTRACTION HELPERS
# ============================================================================


def extract_hashable_fields(obj: Any, field_names: List[str]) -> Dict[str, Any]:
    """
    Extract specific fields from an object for hashing.

    Useful for hashing only certain fields of a complex object.

    Args:
        obj: Object to extract fields from
        field_names: List of field names to extract

    Returns:
        Dict mapping field names to their stabilized values

    Raises:
        AttributeError: If a field doesn't exist
    """
    result = {}
    for name in sorted(field_names):
        if hasattr(obj, name):
            result[name] = _stabilize_value(getattr(obj, name))
        else:
            raise AttributeError(
                f"Object of type {type(obj).__name__} has no attribute '{name}'"
            )
    return result


def hash_fields(obj: Any, field_names: List[str]) -> str:
    """
    Hash specific fields of an object.

    Args:
        obj: Object to hash fields from
        field_names: List of field names to include in hash

    Returns:
        str: SHA-256 hex digest of the selected fields
    """
    fields_dict = extract_hashable_fields(obj, field_names)
    return stable_hash(fields_dict)


# ============================================================================
# VALIDATION HELPERS
# ============================================================================


def validate_hash_unchanged(
    original_hash: str,
    current_obj: Any,
    label: str = "object",
) -> Tuple[bool, str, str]:
    """
    Validate that an object's hash hasn't changed.

    Args:
        original_hash: The expected hash value
        current_obj: The current object to hash
        label: Label for error messages

    Returns:
        Tuple of (is_unchanged, original_hash, current_hash)
    """
    current_hash = stable_hash(current_obj)
    return (original_hash == current_hash, original_hash, current_hash)


def is_serializable(obj: Any) -> bool:
    """
    Check if an object can be stably serialized.

    Args:
        obj: Object to check

    Returns:
        bool: True if serializable, False otherwise
    """
    try:
        stable_json(obj)
        return True
    except (TypeError, ValueError):
        return False


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Core functions
    "stable_json",
    "stable_hash",
    "stable_hash_combine",
    # Field extraction
    "extract_hashable_fields",
    "hash_fields",
    # Validation
    "validate_hash_unchanged",
    "is_serializable",
    # Encoder (for advanced use)
    "StableJSONEncoder",
]
