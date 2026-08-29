"""Typed construction errors for the capacity-bounds policy family.

Every failure is fail-closed: no ``CapacityBoundsPolicy`` is produced. A malformed
artifact never reaches the authority, and one that somehow does is refused again
by the adapter.

**The refusal is a pair.** ADR Phase 5 §9.1 makes the typed refusal
``(exception class, reason)`` and the message prose. Until
``CapacityBoundsRejectionReason`` existed this family published only the left half —
three leaf classes and no reason vocabulary at all — so fifteen distinct guards
collapsed to one indistinguishable outcome, and a test could only ever show that
*something* was refused. The guard-coverage ADR §3 ruled the pair degenerate and
required this enum before the family's first scored guard sweep. The enum does not
change **which** inputs are refused: every guard fires on exactly the inputs it
fired on before, and the class it raises is unchanged.

The reason travels on the exception rather than in its message, because a message is
prose a caller may not act on. Refusals raised under a *foreign* type — the shared
authority's ``UnsupportedPolicyArtifactError`` and ``PolicyAuthorityRequestError``,
which the adapter must keep raising because the authority's contract names them —
carry the same attribute, attached by :func:`with_rejection_reason`. So
``error.reason`` answers the same question at every refusal site in this package,
whoever defined the class.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, TypeVar

__all__ = [
    "CapacityBoundsRejectionReason",
    "CapacityBoundsPolicyError",
    "CapacityBoundsFieldError",
    "CapacityBoundsOrderingError",
    "CapacityBoundsDuplicateError",
    "rejection_reason_of",
    "with_rejection_reason",
]


class CapacityBoundsRejectionReason(Enum):
    """Why this family refused — the finest-grained discriminator it publishes.

    One member per *decision*, not per field: two guards share a member only when no
    input can distinguish what they decided. ``FIELD_NOT_A_STRING`` covers every
    token-shaped field because one helper makes that decision once for all of them;
    ``SCOPE_UNSUPPORTED`` and ``LIFECYCLE_STATE_UNSUPPORTED`` are separate because
    they are separate decisions over separate domains.

    Values are stable lowercase tokens: they are a published vocabulary, so a rename
    is a deliberate act, and they are not framed into any digest.
    """

    # --- shape of a single field -------------------------------------------------
    FIELD_NOT_A_STRING = "field_not_a_string"
    FIELD_EMPTY = "field_empty"
    CONTENT_DIGEST_MALFORMED = "content_digest_malformed"
    MAGNITUDE_NOT_AN_INT = "magnitude_not_an_int"
    MAGNITUDE_NEGATIVE = "magnitude_negative"
    TIMESTAMP_NOT_A_DATETIME = "timestamp_not_a_datetime"
    TIMESTAMP_NAIVE = "timestamp_naive"

    # --- admitted domains ---------------------------------------------------------
    SCOPE_UNSUPPORTED = "scope_unsupported"
    LIFECYCLE_STATE_UNSUPPORTED = "lifecycle_state_unsupported"

    # --- facts that are one fact, not two -----------------------------------------
    GLOBAL_SCOPE_CARRIES_TENANT = "global_scope_carries_tenant"
    TENANT_SCOPE_NAMES_NO_TENANT = "tenant_scope_names_no_tenant"

    # --- coherence between two admitted values ------------------------------------
    BOUND_ORDERING_INCOHERENT = "bound_ordering_incoherent"
    EFFECTIVE_INTERVAL_EMPTY = "effective_interval_empty"

    # --- shape of the artifact itself ---------------------------------------------
    METADATA_TYPE_MISMATCH = "metadata_type_mismatch"
    BOUNDS_NOT_A_TUPLE = "bounds_not_a_tuple"
    BOUNDS_EMPTY = "bounds_empty"
    BOUND_TYPE_MISMATCH = "bound_type_mismatch"
    DUPLICATE_SELECTOR = "duplicate_selector"

    # --- the adapter boundary ------------------------------------------------------
    # Raised under the authority's own exception types; the reason is this family's.
    ARTIFACT_TYPE_MISMATCH = "artifact_type_mismatch"
    METADATA_ENVELOPE_MISSING = "metadata_envelope_missing"
    COORDINATE_INPUT_TYPE_MISMATCH = "coordinate_input_type_mismatch"
    PROJECTION_DIGEST_DECLARATION_MISSING = "projection_digest_declaration_missing"


class CapacityBoundsPolicyError(Exception):
    """Root of this family's error taxonomy.

    ``reason`` is required rather than defaulted: a refusal that names no reason is
    the defect §3 ruled against, and a default would let one back in silently.
    """

    def __init__(self, message: str, *, reason: CapacityBoundsRejectionReason) -> None:
        super().__init__(message)
        self.reason = reason


class CapacityBoundsFieldError(CapacityBoundsPolicyError):
    """A field is absent, of the wrong exact type, or outside its admitted domain."""


class CapacityBoundsOrderingError(CapacityBoundsPolicyError):
    """A bound's own maxima are mutually incoherent."""


class CapacityBoundsDuplicateError(CapacityBoundsPolicyError):
    """Two bounds claim the same selector, so the applicable bound is ambiguous."""


_E = TypeVar("_E", bound=BaseException)


def with_rejection_reason(
    error: _E, reason: CapacityBoundsRejectionReason
) -> _E:
    """Attach this family's reason to a refusal raised under a foreign type.

    The adapter refuses with the shared authority's ``UnsupportedPolicyArtifactError``
    and ``PolicyAuthorityRequestError`` because those classes *are* the authority's
    contract with an adapter — replacing them with this family's classes would change
    what the authority sees. Attaching the reason keeps the pair whole at those sites
    without touching either the class raised or the inputs that reach it.
    """

    error.reason = reason  # type: ignore[attr-defined]
    return error


def rejection_reason_of(error: BaseException) -> Optional[CapacityBoundsRejectionReason]:
    """The reason carried by a refusal from this package, or ``None``.

    One accessor for both halves of the taxonomy, so a caller never has to know
    whether the class it caught is this family's or the authority's.
    """

    reason = getattr(error, "reason", None)
    return reason if isinstance(reason, CapacityBoundsRejectionReason) else None
