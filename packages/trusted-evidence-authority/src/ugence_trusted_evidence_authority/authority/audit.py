"""Deterministic audit records for verification and re-verification acts.

ADR §22.12 requires immutable records and §22.13 deterministic reason ordering,
"so digests over results are stable". This module is the immutable, digestible
record of *what was decided, under what configuration, at what instant* — for
admissions and refusals alike, because a refusal that leaves no trace is a
refusal nobody can audit.

Determinism, in the strong sense
--------------------------------
Two audit records built from the same act are byte-identical. The record reads
no clock, holds no ordering that depends on set iteration, and carries no
free-form field: every instant is an explicit input, every reason sequence is
sorted into the ratified declaration order, and the canonical encoder rejects
mappings, so nothing unordered can enter.

An audit record is a record, not a claim
----------------------------------------
It records that an authority reached an outcome. It does not re-establish that
outcome, cannot be substituted for the determination or the signed receipt it
describes, and authorizes nothing (§13.2, E-12). Its digest lives in its own
domain, so an audit digest can never be presented as a receipt digest, an
envelope digest or an evidence digest (§26.6).

It carries digests, never payloads
----------------------------------
§27.5: "receipts should bind digests, not payloads … not a copy of the evidence
and must not become a secondary store of sensitive content". The same rule
applies with more force to an audit trail, which is typically retained longer
and read more widely. This record therefore names the request, the evidence
identity, the receipt payload, the envelope and the trust anchor **by digest**,
and copies none of them. It carries a tenant id, because §27.1 makes tenant
binding mandatory and never inferred, and nothing else that could identify a
subject: `canonical_subject_context_ref` and provenance references stay out
(§27.4, §27.7 / DD-7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..contracts._validation import (
    require_aware_datetime,
    require_canonical_str,
    require_digest,
    require_exact_type,
    require_identifier,
    require_optional_digest,
)
from ..contracts.canonical import canonical_bytes, canonical_digest
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.reasons import TrustedEvidenceRefusalReason
from .envelope import SignedEvidenceVerificationReceipt
from .reverification import ReceiptVerification
from .verification import EvidenceAdmissionOutcome, EvidenceVerificationDetermination

__all__ = [
    "EvidenceVerificationAuditRecord",
    "audit_record_for_determination",
    "audit_record_for_receipt_verification",
]

_R = TrustedEvidenceRefusalReason
_REASON_ORDER = tuple(TrustedEvidenceRefusalReason)


@dataclass(frozen=True)
class EvidenceVerificationAuditRecord:
    """One immutable, deterministic record of one trusted-evidence act.

    ``act`` names which act this is — ``"EVIDENCE_VERIFICATION"`` or
    ``"RECEIPT_REVERIFICATION"`` — so the two can never be read for one another
    even though they share a shape.

    ``outcome`` is the string value of whichever outcome vocabulary applies. It
    is recorded as text rather than as an enum member precisely because the two
    acts use two different closed vocabularies, and collapsing them into one
    enum here would create the third vocabulary this package refuses to mint.
    """

    act: str
    outcome: str
    evaluated_at: datetime
    tenant_id: str
    authority_id: str
    key_id: str
    verification_protocol_id: str
    verification_protocol_version: str
    verification_request_digest: str
    refusal_reasons: tuple = ()
    verified_at: Optional[datetime] = None
    receipt_payload_digest: str = ""
    receipt_envelope_digest: str = ""
    trust_anchor_digest: str = ""

    def __post_init__(self) -> None:
        for name in (
            "act",
            "outcome",
            "tenant_id",
            "authority_id",
            "key_id",
            "verification_protocol_id",
            "verification_protocol_version",
        ):
            require_identifier(
                getattr(self, name), f"EvidenceVerificationAuditRecord.{name}"
            )
        require_digest(
            self.verification_request_digest,
            "EvidenceVerificationAuditRecord.verification_request_digest",
        )
        require_aware_datetime(
            self.evaluated_at, "EvidenceVerificationAuditRecord.evaluated_at"
        )
        if self.verified_at is not None:
            require_aware_datetime(
                self.verified_at, "EvidenceVerificationAuditRecord.verified_at"
            )
        for name in (
            "receipt_payload_digest",
            "receipt_envelope_digest",
            "trust_anchor_digest",
        ):
            require_optional_digest(
                getattr(self, name), f"EvidenceVerificationAuditRecord.{name}"
            )
        require_canonical_str(
            self.outcome, "EvidenceVerificationAuditRecord.outcome", allow_empty=False
        )
        if not isinstance(self.refusal_reasons, (list, tuple, set, frozenset)):
            raise TrustedEvidenceContractError(
                "EvidenceVerificationAuditRecord.refusal_reasons must be a list, "
                f"tuple or set (got {type(self.refusal_reasons).__name__})"
            )
        unique = set()
        for index, reason in enumerate(self.refusal_reasons):
            if type(reason) is not TrustedEvidenceRefusalReason:
                raise TrustedEvidenceContractError(
                    "EvidenceVerificationAuditRecord.refusal_reasons"
                    f"[{index}] must be exactly a TrustedEvidenceRefusalReason "
                    f"(got {type(reason).__name__})"
                )
            unique.add(reason)
        object.__setattr__(
            self,
            "refusal_reasons",
            tuple(r for r in _REASON_ORDER if r in unique),
        )

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over."""

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the complete record, in its own domain."""

        return canonical_digest(self)


def audit_record_for_determination(
    determination: EvidenceVerificationDetermination,
    *,
    tenant_id: str,
    envelope: Optional[SignedEvidenceVerificationReceipt] = None,
) -> EvidenceVerificationAuditRecord:
    """Build the audit record for one verification act, admitted or refused.

    ``tenant_id`` is required and explicit: ADR §27.1 makes tenant binding
    mandatory on every verification result and rules that "it is never inferred
    and never defaulted", so it is a parameter rather than something read out of
    a payload that may not exist on a refusal.

    ``envelope`` is supplied when a receipt was subsequently issued, so the
    record can name it by digest. It is absent for a refusal, and for an
    admission that was not signed — which the record then shows honestly as an
    admission with no envelope, rather than implying one exists.
    """

    require_exact_type(
        determination,
        EvidenceVerificationDetermination,
        "audit_record_for_determination.determination",
    )
    require_identifier(tenant_id, "audit_record_for_determination.tenant_id")
    payload_digest = ""
    if determination.outcome is EvidenceAdmissionOutcome.ADMITTED:
        payload_digest = determination.receipt_payload.canonical_digest()
    envelope_digest = ""
    if envelope is not None:
        require_exact_type(
            envelope,
            SignedEvidenceVerificationReceipt,
            "audit_record_for_determination.envelope",
        )
        if envelope.payload_canonical_digest != payload_digest:
            raise TrustedEvidenceContractError(
                "audit_record_for_determination was given an envelope whose "
                "payload is not the determination's; an audit record may not "
                "associate a receipt with a verification act that did not "
                "produce it"
            )
        envelope_digest = envelope.envelope_digest()
    return EvidenceVerificationAuditRecord(
        act="EVIDENCE_VERIFICATION",
        outcome=determination.outcome.value,
        evaluated_at=determination.evaluated_at,
        tenant_id=tenant_id,
        authority_id=determination.verifier_authority_id,
        key_id=determination.verifier_key_id,
        verification_protocol_id=determination.verification_protocol_id,
        verification_protocol_version=determination.verification_protocol_version,
        verification_request_digest=determination.verification_request_digest,
        refusal_reasons=determination.refusal_reasons,
        verified_at=determination.verified_at,
        receipt_payload_digest=payload_digest,
        receipt_envelope_digest=envelope_digest,
    )


def audit_record_for_receipt_verification(
    verification: ReceiptVerification,
    envelope: SignedEvidenceVerificationReceipt,
    *,
    tenant_id: str,
) -> EvidenceVerificationAuditRecord:
    """Build the audit record for one independent re-verification act.

    Records the evaluation instant the caller supplied, which is what makes a
    later reader able to see *when* trust was asked about — the distinction that
    carries the whole weight of §13.3's revocation rule.
    """

    require_exact_type(
        verification,
        ReceiptVerification,
        "audit_record_for_receipt_verification.verification",
    )
    require_exact_type(
        envelope,
        SignedEvidenceVerificationReceipt,
        "audit_record_for_receipt_verification.envelope",
    )
    require_identifier(tenant_id, "audit_record_for_receipt_verification.tenant_id")
    if verification.envelope_digest != envelope.envelope_digest():
        raise TrustedEvidenceContractError(
            "audit_record_for_receipt_verification was given a verification of a "
            "different envelope; an audit record may not associate an outcome "
            "with an artifact it was not reached over"
        )
    payload = envelope.payload
    reasons = (
        () if verification.refusal_reason is None else (verification.refusal_reason,)
    )
    return EvidenceVerificationAuditRecord(
        act="RECEIPT_REVERIFICATION",
        outcome=verification.outcome.value,
        evaluated_at=verification.evaluated_at,
        tenant_id=tenant_id,
        authority_id=envelope.signer_authority_id,
        key_id=envelope.signing_key_id,
        verification_protocol_id=payload.verification_protocol_id,
        verification_protocol_version=payload.verification_protocol_version,
        verification_request_digest=payload.verification_request_digest,
        refusal_reasons=reasons,
        verified_at=payload.verified_at,
        receipt_payload_digest=verification.payload_canonical_digest,
        receipt_envelope_digest=verification.envelope_digest,
        trust_anchor_digest=verification.trust_anchor_digest,
    )
