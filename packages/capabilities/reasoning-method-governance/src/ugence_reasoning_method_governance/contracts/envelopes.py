"""Specification §6 — attestation and verification envelope SHAPES, and the
evidence-status view the engine computes from them.

Slice 1 issues no envelope. The shapes exist so the engine's status logic is
tested against synthetic envelopes and so a later capture boundary targets a
fixed shape. A string in an envelope promotes nothing by itself; only the
engine, reading envelopes whose issuers the request names as resolved, sets a
view — and the request's resolution is itself requester-asserted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

from ugence_governance_contracts.api import (
    AttestationStatus,
    EvidenceUsageScope,
    SourceBasis,
    VerificationStatus,
)

from ..errors import ContractError, ContractErrorCode
from ._util import digest_of, require_digest, require_member, require_nonblank, require_str_tuple, require_tzaware, settle_digest

ATTESTATION_ENVELOPE_SCHEMA_VERSION = "reasoning_method.attestation_envelope.v1"
VERIFICATION_ENVELOPE_SCHEMA_VERSION = "reasoning_method.verification_envelope.v1"


@dataclass(frozen=True)
class AttestationEnvelope:
    schema_version: str
    envelope_id: str
    record_digest: str
    attester_identity: str
    capture_boundary_ref: str
    attested_fields: Tuple[str, ...]
    attested_at: datetime
    envelope_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "AttestationEnvelope.schema_version")
        require_nonblank(self.envelope_id, "AttestationEnvelope.envelope_id")
        require_digest(self.record_digest, "AttestationEnvelope.record_digest")
        require_nonblank(self.attester_identity, "AttestationEnvelope.attester_identity")
        require_nonblank(self.capture_boundary_ref, "AttestationEnvelope.capture_boundary_ref")
        require_str_tuple(self.attested_fields, "AttestationEnvelope.attested_fields")
        require_tzaware(self.attested_at, "AttestationEnvelope.attested_at")
        settle_digest(self, "envelope_digest", digest_of(self, exclude=("envelope_digest",)))


@dataclass(frozen=True)
class VerificationEnvelope:
    schema_version: str
    envelope_id: str
    record_digest: str
    attestation_envelope_digest: str
    verifier_identity: str
    verification_ref: str
    verified_fields: Tuple[str, ...]
    verified_at: datetime
    envelope_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "VerificationEnvelope.schema_version")
        require_nonblank(self.envelope_id, "VerificationEnvelope.envelope_id")
        require_digest(self.record_digest, "VerificationEnvelope.record_digest")
        require_digest(self.attestation_envelope_digest, "VerificationEnvelope.attestation_envelope_digest")
        require_nonblank(self.verifier_identity, "VerificationEnvelope.verifier_identity")
        require_nonblank(self.verification_ref, "VerificationEnvelope.verification_ref")
        require_str_tuple(self.verified_fields, "VerificationEnvelope.verified_fields")
        require_tzaware(self.verified_at, "VerificationEnvelope.verified_at")
        settle_digest(self, "envelope_digest", digest_of(self, exclude=("envelope_digest",)))


@dataclass(frozen=True)
class EvidenceStatusView:
    """A projection of one record's evidence axes.

    It carries ``usage_scope`` because a basis-only projection cannot preserve
    D-9: the view can represent ``SourceBasis.SYNTHETIC``, and synthetic evidence
    is restricted to pre-deployment evaluation wherever it appears. Dropping the
    scope would make this a lossy projection of a constraint the platform relies
    on, which the 2026-09-09 §26.8 ruling declined to ratify. The pairing is
    enforced here, structurally, in the same terms as ``MetricClaim``.
    """

    record_digest: str
    source_basis: SourceBasis
    attestation_status: AttestationStatus
    verification_status: VerificationStatus
    attested_fields: Tuple[str, ...]
    verified_fields: Tuple[str, ...]
    #: Required, deliberately without a default. The ruling forbids silently
    #: defaulting a missing scope, and a default of GENERAL would be exactly that
    #: — it would let a SYNTHETIC view be built by omission and then refused, or
    #: worse, let a caller who never considered scope emit GENERAL as if stated.
    usage_scope: EvidenceUsageScope

    def __post_init__(self) -> None:
        require_digest(self.record_digest, "EvidenceStatusView.record_digest")
        require_member(self.source_basis, SourceBasis, "EvidenceStatusView.source_basis", ContractErrorCode.REF_BLANK_FIELD)
        require_member(self.usage_scope, EvidenceUsageScope, "EvidenceStatusView.usage_scope", ContractErrorCode.REF_BLANK_FIELD)
        require_member(self.attestation_status, AttestationStatus, "EvidenceStatusView.attestation_status", ContractErrorCode.REF_BLANK_FIELD)
        require_member(self.verification_status, VerificationStatus, "EvidenceStatusView.verification_status", ContractErrorCode.REF_BLANK_FIELD)
        require_str_tuple(self.attested_fields, "EvidenceStatusView.attested_fields")
        require_str_tuple(self.verified_fields, "EvidenceStatusView.verified_fields")
        if self.verification_status is VerificationStatus.VERIFIED and self.attestation_status is not AttestationStatus.ATTESTED:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "a VERIFIED view requires ATTESTED (verification presupposes attestation)")
        if self.source_basis is SourceBasis.SYNTHETIC and self.usage_scope is not EvidenceUsageScope.EVALUATION_ONLY:
            raise ContractError(
                ContractErrorCode.REF_BLANK_FIELD,
                "a SYNTHETIC view requires usage_scope=EVALUATION_ONLY (UVI ADR D-9, §26.8)",
            )


__all__ = [
    "ATTESTATION_ENVELOPE_SCHEMA_VERSION",
    "VERIFICATION_ENVELOPE_SCHEMA_VERSION",
    "AttestationEnvelope",
    "VerificationEnvelope",
    "EvidenceStatusView",
]
