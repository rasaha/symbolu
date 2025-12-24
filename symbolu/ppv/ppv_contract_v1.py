"""
PPV Contract v1 - Phonemic Propensity Vector Data Contract
============================================================

Defines the PPV (Phonemic Propensity Vector) contract for Symbol-U.

PPV is a NUMERIC-ONLY structural signal derived from phoneme sequence
and phase metadata. It is NOT "emotion meaning" - it is a deterministic
structural signature.

Hard Constraints (NON-NEGOTIABLE):
    - PPV must be numeric only: ints/bools/tuples; fixed length; no free-form strings
    - PPV must be deterministic and hash-stable
    - PPV must NOT introduce "meaning inference"
    - PPV dimensions use neutral names (no emotion words)
    - All fields immutable after construction

CRITICAL INVARIANTS:
    - Fixed number of dimensions (8)
    - Bounded integer values (0-7)
    - Deterministic hash computation
    - No ML/NLP imports
    - No randomness
    - No time/datetime
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum, unique
from typing import Tuple


# =============================================================================
# Version Constant
# =============================================================================

PPV_CONTRACT_VERSION = "1.0.0"


# =============================================================================
# PPV Dimension Enum (Fixed Axes)
# =============================================================================


@unique
class PPVDim(str, Enum):
    """
    PPV Dimension axes - fixed, neutral names.

    These are structural signal dimensions derived from phoneme sequences.
    They are NOT emotion labels - they are phonetic structural markers.

    CRITICAL:
        - Exactly 8 dimensions (fixed)
        - Neutral names only (no joy/sad/fear etc.)
        - Order is fixed and must not change
    """
    # Edge dynamics
    EDGE_TENSION = "edge_tension"          # Phoneme boundary tension signature
    EDGE_RELEASE = "edge_release"          # Phoneme boundary release signature

    # Onset characteristics
    ONSET_SHARPNESS = "onset_sharpness"    # Onset attack characteristics

    # Sonority profile
    SONORITY_LIFT = "sonority_lift"        # Sonority contour signature

    # Continuity markers
    CONTINUITY = "continuity"              # Flow continuity marker
    DISCONTINUITY = "discontinuity"        # Break/pause marker

    # Rhythmic structure
    RHYTHMIC_IMPULSE = "rhythmic_impulse"  # Rhythmic pulse signature

    # Stability marker
    STABILITY_PRESSURE = "stability_pressure"  # Structural stability marker


# Fixed dimension count and order
PPV_DIM_COUNT = 8
PPV_DIM_ORDER: Tuple[PPVDim, ...] = (
    PPVDim.EDGE_TENSION,
    PPVDim.EDGE_RELEASE,
    PPVDim.ONSET_SHARPNESS,
    PPVDim.SONORITY_LIFT,
    PPVDim.CONTINUITY,
    PPVDim.DISCONTINUITY,
    PPVDim.RHYTHMIC_IMPULSE,
    PPVDim.STABILITY_PRESSURE,
)

# Value bounds
PPV_VALUE_MIN = 0
PPV_VALUE_MAX = 7


# =============================================================================
# PPV Vector (Frozen)
# =============================================================================


@dataclass(frozen=True)
class PPVVector:
    """
    Phonemic Propensity Vector - numeric structural signature.

    This is a FROZEN dataclass - immutable after construction.

    Attributes:
        version: PPV contract version (e.g., "1.0")
        dims: Tuple of PPVDim in fixed order
        values: Tuple of int values (fixed length, bounded 0-7)
        aggregate: Deterministic checksum-like scalar (not random)
        source_unit_span_ids: Hash-only identifiers for source units
        ppv_hash: Hex hash over canonical serialization (64-char)

    Invariants:
        - len(dims) == len(values) == PPV_DIM_COUNT (8)
        - dims in fixed order (PPV_DIM_ORDER)
        - all values in range [PPV_VALUE_MIN, PPV_VALUE_MAX]
        - ppv_hash is deterministic 64-char hex
        - aggregate is deterministic (sum-based checksum)
    """
    version: str
    dims: Tuple[PPVDim, ...]
    values: Tuple[int, ...]
    aggregate: int
    source_unit_span_ids: Tuple[str, ...]
    ppv_hash: str

    def __post_init__(self) -> None:
        """Validate PPVVector invariants (fail-closed)."""
        # Validate version
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError(
                "PPVVector.version must be a non-empty string"
            )

        # Validate dims
        if not isinstance(self.dims, tuple):
            raise ValueError(
                f"PPVVector.dims must be tuple, got {type(self.dims).__name__}"
            )
        if len(self.dims) != PPV_DIM_COUNT:
            raise ValueError(
                f"PPVVector.dims must have exactly {PPV_DIM_COUNT} elements, "
                f"got {len(self.dims)}"
            )
        for i, dim in enumerate(self.dims):
            if not isinstance(dim, PPVDim):
                raise ValueError(
                    f"PPVVector.dims[{i}] must be PPVDim, got {type(dim).__name__}"
                )
            if dim != PPV_DIM_ORDER[i]:
                raise ValueError(
                    f"PPVVector.dims[{i}] must be {PPV_DIM_ORDER[i].value}, "
                    f"got {dim.value}"
                )

        # Validate values
        if not isinstance(self.values, tuple):
            raise ValueError(
                f"PPVVector.values must be tuple, got {type(self.values).__name__}"
            )
        if len(self.values) != PPV_DIM_COUNT:
            raise ValueError(
                f"PPVVector.values must have exactly {PPV_DIM_COUNT} elements, "
                f"got {len(self.values)}"
            )
        for i, val in enumerate(self.values):
            if not isinstance(val, int):
                raise ValueError(
                    f"PPVVector.values[{i}] must be int, got {type(val).__name__}"
                )
            if val < PPV_VALUE_MIN or val > PPV_VALUE_MAX:
                raise ValueError(
                    f"PPVVector.values[{i}] must be in range "
                    f"[{PPV_VALUE_MIN}, {PPV_VALUE_MAX}], got {val}"
                )

        # Validate aggregate
        if not isinstance(self.aggregate, int):
            raise ValueError(
                f"PPVVector.aggregate must be int, got {type(self.aggregate).__name__}"
            )
        # Verify aggregate is deterministic checksum
        expected_aggregate = _compute_aggregate(self.values)
        if self.aggregate != expected_aggregate:
            raise ValueError(
                f"PPVVector.aggregate mismatch: expected {expected_aggregate}, "
                f"got {self.aggregate}"
            )

        # Validate source_unit_span_ids
        if not isinstance(self.source_unit_span_ids, tuple):
            raise ValueError(
                f"PPVVector.source_unit_span_ids must be tuple, "
                f"got {type(self.source_unit_span_ids).__name__}"
            )
        for i, span_id in enumerate(self.source_unit_span_ids):
            if not isinstance(span_id, str):
                raise ValueError(
                    f"PPVVector.source_unit_span_ids[{i}] must be str, "
                    f"got {type(span_id).__name__}"
                )
            # Span IDs must be hex strings (hash-only)
            if span_id and len(span_id) != 16:
                raise ValueError(
                    f"PPVVector.source_unit_span_ids[{i}] must be 16-char hex, "
                    f"got {len(span_id)} chars"
                )
            if span_id:
                try:
                    int(span_id, 16)
                except ValueError:
                    raise ValueError(
                        f"PPVVector.source_unit_span_ids[{i}] must be hex, "
                        f"got '{span_id}'"
                    )

        # Validate ppv_hash
        if not isinstance(self.ppv_hash, str):
            raise ValueError(
                f"PPVVector.ppv_hash must be str, got {type(self.ppv_hash).__name__}"
            )
        if len(self.ppv_hash) != 64:
            raise ValueError(
                f"PPVVector.ppv_hash must be 64 hex chars, "
                f"got {len(self.ppv_hash)} chars"
            )
        try:
            int(self.ppv_hash, 16)
        except ValueError:
            raise ValueError(
                "PPVVector.ppv_hash must contain only hex characters"
            )

        # Verify ppv_hash is correct (deterministic)
        expected_hash = _compute_ppv_hash(
            version=self.version,
            dims=self.dims,
            values=self.values,
            aggregate=self.aggregate,
            source_unit_span_ids=self.source_unit_span_ids,
        )
        if self.ppv_hash != expected_hash:
            raise ValueError(
                f"PPVVector.ppv_hash mismatch: expected {expected_hash}, "
                f"got {self.ppv_hash}"
            )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "dims": tuple(d.value for d in self.dims),
            "values": self.values,
            "aggregate": self.aggregate,
            "source_unit_span_ids": self.source_unit_span_ids,
            "ppv_hash": self.ppv_hash,
        }

    def get_value(self, dim: PPVDim) -> int:
        """Get the value for a specific dimension."""
        idx = PPV_DIM_ORDER.index(dim)
        return self.values[idx]

    def as_summary_tuple(self) -> Tuple[int, ...]:
        """Return values as a summary tuple (for template slots)."""
        return self.values


# =============================================================================
# Helper Functions
# =============================================================================


def _compute_aggregate(values: Tuple[int, ...]) -> int:
    """
    Compute deterministic aggregate checksum from values.

    This is a simple weighted sum checksum - NOT random, NOT semantic.

    Args:
        values: Tuple of int values.

    Returns:
        Deterministic aggregate integer.
    """
    # Weighted sum with position-based weights
    aggregate = 0
    for i, val in enumerate(values):
        # Weight by position (1-indexed) to ensure position sensitivity
        aggregate += val * (i + 1)
    return aggregate


def _compute_ppv_hash(
    version: str,
    dims: Tuple[PPVDim, ...],
    values: Tuple[int, ...],
    aggregate: int,
    source_unit_span_ids: Tuple[str, ...],
) -> str:
    """
    Compute deterministic PPV hash over canonical serialization.

    Args:
        version: PPV version string.
        dims: Tuple of PPVDim.
        values: Tuple of int values.
        aggregate: Aggregate checksum.
        source_unit_span_ids: Source unit span IDs.

    Returns:
        64-char hex hash string.
    """
    # Canonical serialization (deterministic order)
    canonical_parts = [
        f"version:{version}",
        f"dims:{tuple(d.value for d in dims)}",
        f"values:{values}",
        f"aggregate:{aggregate}",
        f"span_ids:{source_unit_span_ids}",
    ]
    canonical_str = "|".join(canonical_parts)

    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


# =============================================================================
# PPV Creation Factory
# =============================================================================


def create_ppv_vector(
    values: Tuple[int, ...],
    source_unit_span_ids: Tuple[str, ...] = (),
    version: str = "1.0",
) -> PPVVector:
    """
    Create a valid PPVVector with computed aggregate and hash.

    This is the canonical factory for creating PPVVector instances.

    Args:
        values: Tuple of 8 int values (bounded 0-7).
        source_unit_span_ids: Optional tuple of source span IDs (16-char hex each).
        version: PPV version string (default "1.0").

    Returns:
        Valid PPVVector instance.

    Raises:
        ValueError: If inputs are invalid.
    """
    # Validate values length
    if len(values) != PPV_DIM_COUNT:
        raise ValueError(
            f"values must have exactly {PPV_DIM_COUNT} elements, got {len(values)}"
        )

    # Validate and clamp values
    validated_values: list[int] = []
    for i, val in enumerate(values):
        if not isinstance(val, int):
            raise ValueError(f"values[{i}] must be int, got {type(val).__name__}")
        if val < PPV_VALUE_MIN or val > PPV_VALUE_MAX:
            raise ValueError(
                f"values[{i}] must be in range [{PPV_VALUE_MIN}, {PPV_VALUE_MAX}], "
                f"got {val}"
            )
        validated_values.append(val)

    values_tuple = tuple(validated_values)

    # Compute aggregate
    aggregate = _compute_aggregate(values_tuple)

    # Compute hash
    ppv_hash = _compute_ppv_hash(
        version=version,
        dims=PPV_DIM_ORDER,
        values=values_tuple,
        aggregate=aggregate,
        source_unit_span_ids=source_unit_span_ids,
    )

    return PPVVector(
        version=version,
        dims=PPV_DIM_ORDER,
        values=values_tuple,
        aggregate=aggregate,
        source_unit_span_ids=source_unit_span_ids,
        ppv_hash=ppv_hash,
    )


# =============================================================================
# Invariant Validation
# =============================================================================


def validate_ppv_invariants_v1(ppv: PPVVector) -> bool:
    """
    Validate all PPV v1 invariants.

    This function performs comprehensive validation of PPV invariants:
        - Fixed length (8 dimensions)
        - Bounded ints (0-7)
        - Dims in fixed order
        - Hashes are hex and deterministic

    Args:
        ppv: The PPVVector to validate.

    Returns:
        True if all invariants hold.

    Raises:
        ValueError: If any invariant is violated.
    """
    # Check version
    if not ppv.version.startswith("1."):
        raise ValueError(f"Expected v1.x, got {ppv.version}")

    # Check dimension count
    if len(ppv.dims) != PPV_DIM_COUNT:
        raise ValueError(
            f"Expected {PPV_DIM_COUNT} dims, got {len(ppv.dims)}"
        )

    # Check dimension order
    for i, (actual, expected) in enumerate(zip(ppv.dims, PPV_DIM_ORDER)):
        if actual != expected:
            raise ValueError(
                f"Dim order mismatch at index {i}: expected {expected}, got {actual}"
            )

    # Check value count
    if len(ppv.values) != PPV_DIM_COUNT:
        raise ValueError(
            f"Expected {PPV_DIM_COUNT} values, got {len(ppv.values)}"
        )

    # Check value bounds
    for i, val in enumerate(ppv.values):
        if not isinstance(val, int):
            raise ValueError(f"values[{i}] must be int")
        if val < PPV_VALUE_MIN or val > PPV_VALUE_MAX:
            raise ValueError(
                f"values[{i}] out of bounds: {val}"
            )

    # Check aggregate is deterministic
    expected_aggregate = _compute_aggregate(ppv.values)
    if ppv.aggregate != expected_aggregate:
        raise ValueError(
            f"Aggregate mismatch: expected {expected_aggregate}, got {ppv.aggregate}"
        )

    # Check hash is hex
    if len(ppv.ppv_hash) != 64:
        raise ValueError(f"ppv_hash must be 64 chars, got {len(ppv.ppv_hash)}")
    try:
        int(ppv.ppv_hash, 16)
    except ValueError:
        raise ValueError("ppv_hash must be hex")

    # Check hash is deterministic
    expected_hash = _compute_ppv_hash(
        version=ppv.version,
        dims=ppv.dims,
        values=ppv.values,
        aggregate=ppv.aggregate,
        source_unit_span_ids=ppv.source_unit_span_ids,
    )
    if ppv.ppv_hash != expected_hash:
        raise ValueError(
            f"ppv_hash mismatch: expected {expected_hash}, got {ppv.ppv_hash}"
        )

    # Check span IDs are hash-only
    for i, span_id in enumerate(ppv.source_unit_span_ids):
        if span_id:
            if len(span_id) != 16:
                raise ValueError(
                    f"span_ids[{i}] must be 16 chars, got {len(span_id)}"
                )
            try:
                int(span_id, 16)
            except ValueError:
                raise ValueError(f"span_ids[{i}] must be hex")

    return True


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PPV_CONTRACT_VERSION",
    # Constants
    "PPV_DIM_COUNT",
    "PPV_DIM_ORDER",
    "PPV_VALUE_MIN",
    "PPV_VALUE_MAX",
    # Enums
    "PPVDim",
    # Dataclasses
    "PPVVector",
    # Functions
    "create_ppv_vector",
    "validate_ppv_invariants_v1",
]
