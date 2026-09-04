"""Typed errors. Every one is a programming or configuration fault, never a verdict.

A refused verification is an *answer* and travels as a typed outcome (see
:mod:`.outcomes`). These exceptions are raised only where continuing would mean composing
the wrong thing: a foreign type at the boundary, a reference-grade dependency under the
production factory, or an instant that is not an instant.
"""

from __future__ import annotations

__all__ = [
    "CloudScalingEnvelopeIssuanceError",
    "EnvelopeIssuanceConfigurationError",
    "EnvelopeIssuanceContractError",
    "EnvelopeIssuanceExactTypeError",
    "UpstreamVerifierUnavailableError",
]


class CloudScalingEnvelopeIssuanceError(Exception):
    """Base class for every error this package raises."""


class EnvelopeIssuanceConfigurationError(CloudScalingEnvelopeIssuanceError):
    """The composition root was built over something it may not stand on."""


class EnvelopeIssuanceContractError(CloudScalingEnvelopeIssuanceError):
    """An input violated the contract in a way no outcome can express."""


class EnvelopeIssuanceExactTypeError(EnvelopeIssuanceContractError):
    """An input was not the exact type the boundary admits; subclasses are refused."""


class UpstreamVerifierUnavailableError(CloudScalingEnvelopeIssuanceError):
    """An upstream verifier raised instead of answering.

    Raised out of the verification port so the seam refuses with
    ``VERIFICATION_UNAVAILABLE`` — never a pass — while the port's report still records
    which verifier failed.
    """
