"""Typed outcomes: the status of each binding, and the report the port hands back.

The seam speaks one word, ``VERIFIED``; everything else it treats as a refusal and quotes
back in its detail. This module keeps that vocabulary honest on this side of the seam: a
binding reports :data:`VERIFIED` only after the upstream artifact revalidated, named this
exact candidate, and recorded this exact instant — and otherwise reports *why not*, as a
closed enum rather than a free string.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from risk_authority.api import VERIFIED, VerifiedArtifactBinding

from .identifiers import COMPOSITION_PROFILE, COMPOSITION_PROFILE_VERSION

__all__ = [
    "ArtifactBindingStatus",
    "CloudScalingVerificationReport",
    "REFUSING_STATUSES",
]


class ArtifactBindingStatus(str, Enum):
    """What one binding's ``outcome`` says. Exactly one value is a pass."""

    #: The seam's own token; the only value the seam admits.
    VERIFIED = VERIFIED
    #: The candidate did not re-derive its own digests at this boundary.
    CANDIDATE_NOT_REDERIVED = "CANDIDATE_NOT_REDERIVED"
    #: The 5B-0A verifier refused; the report carries its outcome.
    PRODUCER_ATTESTATION_REFUSED = "PRODUCER_ATTESTATION_REFUSED"
    #: The 5B-0B verifier refused; the report carries its outcome.
    POLICY_AUTHENTICITY_REFUSED = "POLICY_AUTHENTICITY_REFUSED"
    #: The verifier answered, but its artifact failed its own revalidation.
    ARTIFACT_INTEGRITY_FAILED = "ARTIFACT_INTEGRITY_FAILED"
    #: The verified artifact names another candidate than the one being issued for.
    ARTIFACT_NOT_BOUND_TO_CANDIDATE = "ARTIFACT_NOT_BOUND_TO_CANDIDATE"
    #: The verified artifact recorded another instant than the seam's (5B-2 D-4).
    ARTIFACT_INSTANT_MISMATCH = "ARTIFACT_INSTANT_MISMATCH"
    #: The verifier raised instead of answering.
    VERIFIER_UNAVAILABLE = "VERIFIER_UNAVAILABLE"


#: Every status that is not a pass. Kept as a set so a test can prove the partition.
REFUSING_STATUSES: frozenset = frozenset(
    s for s in ArtifactBindingStatus if s is not ArtifactBindingStatus.VERIFIED
)


@dataclass(frozen=True)
class CloudScalingVerificationReport:
    """What the port did for one act, at one instant. Non-authoritative bookkeeping.

    ``bindings`` is exactly what the port returned to the seam. ``producer_outcome`` and
    ``policy_outcome`` are the upstream verifiers' own outcome tokens, so an auditor reading
    a refusal sees the neighbour's word for it, not this package's paraphrase.
    """

    as_of: datetime
    bindings: tuple[VerifiedArtifactBinding, ...]
    producer_outcome: Optional[str]
    policy_outcome: Optional[str]
    detail: str = ""
    composition_profile: str = COMPOSITION_PROFILE
    composition_profile_version: str = COMPOSITION_PROFILE_VERSION

    @property
    def all_verified(self) -> bool:
        """``True`` iff every binding reported the seam's one admitted token."""

        return bool(self.bindings) and all(b.outcome == VERIFIED for b in self.bindings)

    def status_of(self, kind: str) -> Optional[str]:
        for binding in self.bindings:
            if binding.kind == kind:
                return binding.outcome
        return None
