"""Refusal reasons. Every one of them is a refusal to make a claim.

The package has exactly one job — serialize a clearance somebody else evaluated,
and say what a reader can check about it — so every error here marks a place where
producing an artifact would have asserted something the platform cannot support.
"""

from __future__ import annotations

__all__ = [
    "ClearanceExportError",
    "ContractViolation",
    "ExportIntegrityError",
    "AuthenticityClaimRefused",
    "IdentityAssuranceClaimRefused",
    "ClassificationClaimRefused",
    "NotAReceivedClearance",
]


class ClearanceExportError(Exception):
    """Base for every refusal this package raises."""


class ContractViolation(ClearanceExportError):
    """A field is missing, blank, or the wrong shape."""


class ExportIntegrityError(ClearanceExportError):
    """The artifact does not re-derive its own fingerprint, or its id does not
    follow from it. The body was altered after it was exported."""


class AuthenticityClaimRefused(ClearanceExportError):
    """Something tried to state an authenticity other than ``UNSIGNED`` (CE-4).

    No signing key and no trust root is configured anywhere in this repository —
    a ``TrustAnchorResolverPort`` exists in ``trusted-evidence-authority`` and is
    unfed — so an artifact claiming to be signed would be claiming a property
    nothing established.
    """


class IdentityAssuranceClaimRefused(ClearanceExportError):
    """Something tried to state an identity assurance other than
    ``PRESENTED_UNPROVEN`` (CE-3).

    Every declarer upstream of a clearance is recorded as presented and unproven.
    A verified assurance would require an enterprise issuer that does not exist,
    and the ceiling must survive serialization rather than evaporating at the
    boundary.
    """


class ClassificationClaimRefused(ClearanceExportError):
    """Something tried to state a classification other than
    ``SYNTHETIC_DEMONSTRATION_ONLY`` (CE-7, ADR §13.1).

    A seeded receipt exercises the export path and the verifier and is evidence
    about nothing else. Stripping the label would let a demonstration reach an
    external runtime looking like a governed clearance.
    """


class NotAReceivedClearance(ClearanceExportError):
    """The input is not a clearance receipt the deployment received (CE-1).

    Compilation establishes what was compiled; a clearance establishes whether a
    consequential action may proceed now and until when. Exporting a compile
    result as a clearance would collapse the two, and an external runtime acting
    on the artifact would be acting on the wrong question.
    """
