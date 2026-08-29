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
carry the same attribute, attached by :func:`with_rejection_reason`.

**Scope of that claim, stated exactly.** Every refusal *this package raises* carries a
reason — all 22 of them. It does not follow that every exception escaping this package
carries one, and an audit produced the counterexample: a non-NFC ``action_type`` is
admitted by :func:`_require_token`, and the shared authority then refuses it inside
``to_canonical_obj`` with a ``PolicyCanonicalizationError`` that this package never
raised and cannot annotate. ``rejection_reason_of`` returns ``None`` there, which is the
honest answer — the decision was not this family's. A caller that must distinguish
"this family refused" from "something refused" should test for ``None``, not assume it
away.
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

    One member per *decision a helper makes*, not per call site and not per field.
    ``FIELD_NOT_A_STRING`` covers every token-shaped field because one helper,
    :func:`_require_token`, makes that decision once for all of them — ten call sites
    share it, and an input can certainly tell those ten apart. Discriminating *which call
    site* refused is deliberately not this vocabulary's job: that is what the sweep's
    D-GC-4 helper-admission class measures, one scored site per call, which is why the
    two mechanisms are complementary rather than redundant. What a member does promise is
    that two *distinct decisions* never share one: ``SCOPE_UNSUPPORTED`` and
    ``LIFECYCLE_STATE_UNSUPPORTED`` are separate because they are separate decisions over
    separate domains.

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

    def __reduce__(self):
        """Keep the refusal picklable despite the keyword-only ``reason``.

        ``BaseException.__reduce__`` replays ``args`` *positionally*, so the default
        would call ``__init__(message)`` with no reason and raise ``TypeError`` — turning
        a refusal that crossed a process boundary into a crash. A refusal that cannot be
        carried out of a worker is a refusal a caller cannot act on, so the rebuild is
        explicit rather than inherited.
        """

        return (_rebuild_refusal, (type(self), self.args, self.reason))


class CapacityBoundsFieldError(CapacityBoundsPolicyError):
    """A field is absent, of the wrong exact type, or outside its admitted domain."""


class CapacityBoundsOrderingError(CapacityBoundsPolicyError):
    """A bound's own maxima are mutually incoherent."""


class CapacityBoundsDuplicateError(CapacityBoundsPolicyError):
    """Two bounds claim the same selector, so the applicable bound is ambiguous."""


def _rebuild_refusal(cls, args, reason):
    """Module-level so ``pickle`` can find it; see ``CapacityBoundsPolicyError.__reduce__``."""

    return cls(*args, reason=reason)


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
