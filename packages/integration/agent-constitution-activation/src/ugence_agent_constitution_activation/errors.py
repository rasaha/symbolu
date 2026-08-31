"""The activation boundary's failure taxonomy. One root, no disposition.

`[R]` **None of these names, and no message any of them carries, emits a denial,
an abstention, a reserved authority term, a terminal outcome or a candidate
disposition** (`OD-C3=B`, continuing the conformance package's discipline).
They name orchestration and derivation facts only. Every authority refusal —
approval, signing, digest, registry, resolution — is the Policy Authority's or
the conformance resolver's own typed error, raised by that package and never
re-worded here: this package adds errors only for the failures it detects
itself, at its own composition and derivation seams.

The Policy Authority's ``PolicyResolutionReason`` tokens never pass through this
package at all: resolution runs inside the conformance resolver, whose
``ConstitutionUnresolvedError.reason`` attribute is the one channel for them.
"""

from __future__ import annotations

__all__ = [
    "AgentConstitutionActivationError",
    "ActivationCompositionError",
    "ActivationRequestError",
    "ReferenceMapDerivationError",
    "ReferenceMapConflictError",
]


class AgentConstitutionActivationError(Exception):
    """Root of this boundary's error taxonomy.

    Every failure this package detects itself raises one of these. Nothing
    degraded, partial or defaulted is ever returned: a receipt exists only when
    the underlying authority act completed, and a reference map exists only when
    every entry derived lawfully.
    """


class ActivationCompositionError(AgentConstitutionActivationError):
    """A composition dependency is absent or does not implement its seam.

    Raised at construction, before any request is served: an incompletely wired
    root must fail to exist, never quietly compose around a missing verifier.
    """


class ActivationRequestError(AgentConstitutionActivationError):
    """A presented input is absent, of the wrong exact type, or outside its grammar."""


class ReferenceMapDerivationError(AgentConstitutionActivationError):
    """The issued record does not lawfully yield reference-map entries.

    The record's carried artifact is not exactly this family's artifact, or the
    record's signed coordinate does not equal the coordinate derived from that
    artifact. Nothing is derived from such a record.
    """


class ReferenceMapConflictError(AgentConstitutionActivationError):
    """An existing entry already binds this key to a different coordinate.

    Fail closed: a conflicting entry is never overwritten, merged or preferred
    by recency. Removing or replacing an entry is a deliberate reconfiguration,
    not something a population call performs implicitly.
    """
