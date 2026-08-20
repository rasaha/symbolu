"""Typed errors for the Phase 5B-0A producer-authenticity boundary.

Two different failure surfaces, deliberately not merged.

**Contract errors** (this module) are raised when an artifact cannot be *constructed* —
a malformed attestation, a signing input a caller tried to assemble, a verified artifact
that failed revalidation. They are programming/format failures at a construction site.

**Verification refusals** are not exceptions at all. Verification returns a typed
:class:`~.outcomes.ProducerAuthenticityOutcome` inside a
:class:`~.verification.ProducerAuthenticityResult`, because a refusal is an ordinary,
expected answer to "is this producer authentic?" and raising would tempt a caller into
``except: pass``. An exception is never converted into a success anywhere in this package;
the verifier converts an unexpected exception into
:attr:`~.outcomes.ProducerAuthenticityOutcome.VERIFICATION_UNAVAILABLE`, which is a refusal.

Every error below carries the typed outcome it corresponds to, so a caller that does catch
one still branches on a member rather than on a message string.
"""

from __future__ import annotations

from .outcomes import ProducerAuthenticityOutcome

__all__ = [
    "CloudScalingProducerAttestationError",
    "ProducerAttestationContractError",
    "ProducerAttestationExactTypeError",
    "ProducerAttestationCanonicalFieldError",
    "ProducerAttestationSigningBoundaryError",
    "VerifiedArtifactIntegrityError",
    "ProducerAttestationConfigurationError",
]


class CloudScalingProducerAttestationError(Exception):
    """Base class for every Phase 5B-0A failure. Carries the typed outcome."""

    def __init__(
        self,
        message: str,
        outcome: ProducerAuthenticityOutcome = ProducerAuthenticityOutcome.INDETERMINATE,
    ) -> None:
        super().__init__(message)
        self.outcome = outcome


class ProducerAttestationContractError(CloudScalingProducerAttestationError):
    """An attestation, signing input or verified artifact could not be constructed."""


class ProducerAttestationExactTypeError(ProducerAttestationContractError):
    """A value was not the exact required type. Subclasses and look-alikes are refused."""

    def __init__(
        self,
        message: str,
        outcome: ProducerAuthenticityOutcome = (
            ProducerAuthenticityOutcome.UNSUPPORTED_EXACT_TYPE
        ),
    ) -> None:
        super().__init__(message, outcome)


class ProducerAttestationCanonicalFieldError(ProducerAttestationContractError):
    """A field is missing, unknown, malformed, non-NFC or not canonically representable."""

    def __init__(
        self,
        message: str,
        outcome: ProducerAuthenticityOutcome = (
            ProducerAuthenticityOutcome.ATTESTATION_MALFORMED
        ),
    ) -> None:
        super().__init__(message, outcome)


class ProducerAttestationSigningBoundaryError(ProducerAttestationContractError):
    """The signing boundary was approached from outside its one supported route.

    Raised when a caller tries to assemble a signing input directly, or hands a signer an
    input addressed to coordinates it cannot answer for. It never means "the signature was
    invalid" — no signature exists yet at the point this is raised.
    """

    def __init__(
        self,
        message: str,
        outcome: ProducerAuthenticityOutcome = (
            ProducerAuthenticityOutcome.INVARIANT_VIOLATION
        ),
    ) -> None:
        super().__init__(message, outcome)


class VerifiedArtifactIntegrityError(ProducerAttestationContractError):
    """A :class:`~.verified.VerifiedProducerAttestation` failed revalidation.

    Raised at a consumption boundary against a fabricated, bypassed, mutated or duck-typed
    artifact. A frozen dataclass is not a security boundary; this is what makes the
    boundary real.
    """

    def __init__(
        self,
        message: str,
        outcome: ProducerAuthenticityOutcome = (
            ProducerAuthenticityOutcome.INVARIANT_VIOLATION
        ),
    ) -> None:
        super().__init__(message, outcome)


class ProducerAttestationConfigurationError(CloudScalingProducerAttestationError):
    """A composition root wired the boundary in a posture it may not hold.

    Raised at construction, not at verification time: a reference-grade resolver, a
    reference signer or a non-production-authoritative signature verifier installed in
    production mode fails closed when the object is built, so no production path can carry
    a reference component to the point of producing a determination.
    """

    def __init__(
        self,
        message: str,
        outcome: ProducerAuthenticityOutcome = (
            ProducerAuthenticityOutcome.VERIFICATION_UNAVAILABLE
        ),
    ) -> None:
        super().__init__(message, outcome)
