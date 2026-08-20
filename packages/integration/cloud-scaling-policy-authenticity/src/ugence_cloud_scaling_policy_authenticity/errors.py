"""Typed errors for the Phase 5B-0B policy-authenticity boundary.

Two different failure surfaces, deliberately not merged, following Phase 5B-0A.

**Contract errors** (this module) are raised when an artifact cannot be *constructed* — a
malformed request, a verified artifact that failed revalidation, a composition root wiring
a posture it may not hold. They are programming or configuration failures at a construction
site.

**Verification refusals** are not exceptions at all. Verification returns a typed
:class:`~.outcomes.PolicyAuthenticityOutcome` inside a
:class:`~.verification.PolicyAuthenticityResult`, because "this policy is revoked" is an
ordinary, expected answer to "is this policy authentic and in force?" and raising would
tempt a caller into ``except: pass``. An exception is never converted into a success
anywhere in this package; the verifier converts an unexpected exception into
:attr:`~.outcomes.PolicyAuthenticityOutcome.VERIFICATION_UNAVAILABLE`, which is a refusal.

Every error below carries the typed outcome it corresponds to, so a caller that does catch
one still branches on a member rather than on a message string.
"""

from __future__ import annotations

from .outcomes import PolicyAuthenticityOutcome

__all__ = [
    "CloudScalingPolicyAuthenticityError",
    "PolicyAuthenticityContractError",
    "PolicyAuthenticityExactTypeError",
    "PolicyAuthenticityFieldError",
    "VerifiedPolicyArtifactIntegrityError",
    "PolicyAuthenticityConfigurationError",
]


class CloudScalingPolicyAuthenticityError(Exception):
    """Base class for every Phase 5B-0B failure. Carries the typed outcome."""

    def __init__(
        self,
        message: str,
        outcome: PolicyAuthenticityOutcome = PolicyAuthenticityOutcome.INDETERMINATE,
    ) -> None:
        super().__init__(message)
        self.outcome = outcome


class PolicyAuthenticityContractError(CloudScalingPolicyAuthenticityError):
    """A request or a verified artifact could not be constructed."""


class PolicyAuthenticityExactTypeError(PolicyAuthenticityContractError):
    """A value was not the exact required type. Subclasses and look-alikes are refused."""

    def __init__(
        self,
        message: str,
        outcome: PolicyAuthenticityOutcome = (
            PolicyAuthenticityOutcome.UNSUPPORTED_EXACT_TYPE
        ),
    ) -> None:
        super().__init__(message, outcome)


class PolicyAuthenticityFieldError(PolicyAuthenticityContractError):
    """A field is missing, malformed, non-NFC, naive, or not canonically representable."""

    def __init__(
        self,
        message: str,
        outcome: PolicyAuthenticityOutcome = PolicyAuthenticityOutcome.COORDINATE_MALFORMED,
    ) -> None:
        super().__init__(message, outcome)


class VerifiedPolicyArtifactIntegrityError(PolicyAuthenticityContractError):
    """A :class:`~.verified.VerifiedPolicyAuthenticity` failed revalidation.

    Raised at a consumption boundary against a fabricated, bypassed, mutated or duck-typed
    artifact. A frozen dataclass is not a security boundary; this is what makes the
    boundary real.
    """

    def __init__(
        self,
        message: str,
        outcome: PolicyAuthenticityOutcome = PolicyAuthenticityOutcome.INVARIANT_VIOLATION,
    ) -> None:
        super().__init__(message, outcome)


class PolicyAuthenticityConfigurationError(CloudScalingPolicyAuthenticityError):
    """A composition root wired the boundary in a posture it may not hold.

    Raised at construction, not at verification time: a reference-grade resolution port —
    or a production port standing on the Policy Authority's explicitly reference-grade
    in-memory registry — fails closed when the verifier is built, so no production path can
    carry a reference component to the point of producing a determination.
    """

    def __init__(
        self,
        message: str,
        outcome: PolicyAuthenticityOutcome = (
            PolicyAuthenticityOutcome.VERIFICATION_UNAVAILABLE
        ),
    ) -> None:
        super().__init__(message, outcome)
