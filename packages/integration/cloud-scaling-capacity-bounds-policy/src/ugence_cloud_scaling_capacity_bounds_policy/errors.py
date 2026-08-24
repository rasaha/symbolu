"""Typed construction errors for the capacity-bounds policy family.

Every failure is fail-closed: no ``CapacityBoundsPolicy`` is produced. A malformed
artifact never reaches the authority, and one that somehow does is refused again
by the adapter.
"""

from __future__ import annotations

__all__ = [
    "CapacityBoundsPolicyError",
    "CapacityBoundsFieldError",
    "CapacityBoundsOrderingError",
    "CapacityBoundsDuplicateError",
]


class CapacityBoundsPolicyError(Exception):
    """Root of this family's error taxonomy."""


class CapacityBoundsFieldError(CapacityBoundsPolicyError):
    """A field is absent, of the wrong exact type, or outside its admitted domain."""


class CapacityBoundsOrderingError(CapacityBoundsPolicyError):
    """A bound's own maxima are mutually incoherent."""


class CapacityBoundsDuplicateError(CapacityBoundsPolicyError):
    """Two bounds claim the same selector, so the applicable bound is ambiguous."""
