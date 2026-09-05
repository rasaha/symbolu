"""Specification §7 — comparison-engine request and result ports.

These are CONTRACTS. The engine that consumes the request and produces the
result lives in ``ugence-readiness-comparison``; this package never imports it.
The result's ``authority_resolution_basis`` is fixed at ``REQUESTER_ASSERTED``
in slice 1: the request's ``resolved_authorities`` and ``resolved_admissions``
are the requester's assertions, unverified by the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from ugence_governance_contracts.api import MetricClaim

from ..errors import ContractError, ContractErrorCode, RefusalCode
from ._util import digest_of, payload, require_digest, require_member, require_nonblank, require_str_tuple, require_tzaware, settle_digest
from .assessment import QualityResult, ReasoningMethodFitAssessment
from .catalog import ReasoningMethodCatalogRef, ReasoningMethodRef
from .envelopes import AttestationEnvelope, EvidenceStatusView, VerificationEnvelope
from .record import ReasoningMethodExecutionRecord
from .task_class import TaskClassIdentity

COMPARISON_REQUEST_SCHEMA_VERSION = "readiness_comparison.request.v1"
COMPARISON_RESULT_SCHEMA_VERSION = "readiness_comparison.result.v1"
AUTHORITY_RESOLUTION_BASIS_V1 = "REQUESTER_ASSERTED"


@dataclass(frozen=True)
class ResolvedAuthority:
    authority_identity: str
    resolution_ref: str

    def __post_init__(self) -> None:
        require_nonblank(self.authority_identity, "ResolvedAuthority.authority_identity")
        require_nonblank(self.resolution_ref, "ResolvedAuthority.resolution_ref")


@dataclass(frozen=True)
class ResolvedAdmission:
    authority_identity: str
    authority_result_ref: str
    admitted_digest: str

    def __post_init__(self) -> None:
        require_nonblank(self.authority_identity, "ResolvedAdmission.authority_identity")
        require_nonblank(self.authority_result_ref, "ResolvedAdmission.authority_result_ref")
        require_digest(self.admitted_digest, "ResolvedAdmission.admitted_digest")


@dataclass(frozen=True)
class Refusal:
    code: RefusalCode
    detail: str
    method: Optional[ReasoningMethodRef] = None

    def __post_init__(self) -> None:
        require_member(self.code, RefusalCode, "Refusal.code", ContractErrorCode.REF_BLANK_FIELD)
        if not isinstance(self.detail, str):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "Refusal.detail must be a string")
        if self.method is not None and not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "Refusal.method must be a ReasoningMethodRef or None")

    @property
    def sort_key(self) -> Tuple[str, str, str]:
        return (self.code.value, "" if self.method is None else self.method.method_id, self.detail)


@dataclass(frozen=True)
class ReadinessComparisonRequest:
    schema_version: str
    request_id: str
    task_class: TaskClassIdentity
    catalog: ReasoningMethodCatalogRef
    baseline: ReasoningMethodRef
    candidates: Tuple[ReasoningMethodRef, ...]
    records: Tuple[ReasoningMethodExecutionRecord, ...]
    quality_results: Tuple[QualityResult, ...]
    quality_claims: Tuple[MetricClaim, ...]
    attestation_envelopes: Tuple[AttestationEnvelope, ...] = ()
    verification_envelopes: Tuple[VerificationEnvelope, ...] = ()
    resolved_authorities: Tuple[ResolvedAuthority, ...] = ()
    resolved_admissions: Tuple[ResolvedAdmission, ...] = ()
    requester_identity: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ReadinessComparisonRequest.schema_version")
        require_nonblank(self.request_id, "ReadinessComparisonRequest.request_id")
        if not isinstance(self.task_class, TaskClassIdentity):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReadinessComparisonRequest.task_class must be a TaskClassIdentity")
        if not isinstance(self.catalog, ReasoningMethodCatalogRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReadinessComparisonRequest.catalog must be a ReasoningMethodCatalogRef")
        if not isinstance(self.baseline, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReadinessComparisonRequest.baseline must be a ReasoningMethodRef")
        _typed_tuple(self.candidates, ReasoningMethodRef, "candidates")
        if len(set(self.candidates)) != len(self.candidates):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "candidates must be unique")
        _typed_tuple(self.records, ReasoningMethodExecutionRecord, "records")
        _typed_tuple(self.quality_results, QualityResult, "quality_results")
        _typed_tuple(self.quality_claims, MetricClaim, "quality_claims")
        _typed_tuple(self.attestation_envelopes, AttestationEnvelope, "attestation_envelopes")
        _typed_tuple(self.verification_envelopes, VerificationEnvelope, "verification_envelopes")
        _typed_tuple(self.resolved_authorities, ResolvedAuthority, "resolved_authorities")
        _typed_tuple(self.resolved_admissions, ResolvedAdmission, "resolved_admissions")
        if not isinstance(self.requester_identity, str):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "requester_identity must be a string")

    def canonical_digest(self) -> str:
        """Order-normalized digest of the request.

        Input tuples are sorted by their contractual keys before hashing, so two
        requests that differ only in submission order share a digest and the
        result digest that covers it is input-order independent (§7, R51).
        """
        body = payload(self, exclude=("candidates", "records", "quality_results", "quality_claims", "attestation_envelopes", "verification_envelopes", "resolved_authorities", "resolved_admissions"))
        body["candidates"] = [payload(c) for c in sorted(self.candidates, key=lambda c: c.sort_key)]
        body["records"] = [payload(r) for r in sorted(self.records, key=lambda r: r.record_digest)]
        body["quality_results"] = [payload(q) for q in sorted(self.quality_results, key=lambda q: (q.method.sort_key, q.claim_ref))]
        body["quality_claims"] = [payload(c) for c in sorted(self.quality_claims, key=lambda c: c.claim_id)]
        body["attestation_envelopes"] = [payload(e) for e in sorted(self.attestation_envelopes, key=lambda e: e.envelope_digest)]
        body["verification_envelopes"] = [payload(e) for e in sorted(self.verification_envelopes, key=lambda e: e.envelope_digest)]
        body["resolved_authorities"] = [payload(a) for a in sorted(self.resolved_authorities, key=lambda a: (a.authority_identity, a.resolution_ref))]
        body["resolved_admissions"] = [payload(a) for a in sorted(self.resolved_admissions, key=lambda a: (a.authority_identity, a.authority_result_ref, a.admitted_digest))]
        from ugence_jcs import canonical_sha256_hex

        return canonical_sha256_hex(body)


def _typed_tuple(value: object, cls: type, name: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(v, cls) for v in value):
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"ReadinessComparisonRequest.{name} must be a tuple of {cls.__name__}")


@dataclass(frozen=True)
class ReadinessComparisonResult:
    schema_version: str
    request_id: str
    request_digest: str
    assessments: Tuple[ReasoningMethodFitAssessment, ...]
    refusals: Tuple[Refusal, ...]
    evidence_status: Tuple[EvidenceStatusView, ...]
    ignored_envelopes: Tuple[str, ...]
    authority_resolution_basis: str
    engine_identity: str
    engine_version: str
    produced_at: datetime
    result_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ReadinessComparisonResult.schema_version")
        require_nonblank(self.request_id, "ReadinessComparisonResult.request_id")
        require_digest(self.request_digest, "ReadinessComparisonResult.request_digest")
        if not isinstance(self.assessments, tuple) or not all(isinstance(a, ReasoningMethodFitAssessment) for a in self.assessments):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "assessments must be a tuple of ReasoningMethodFitAssessment")
        if not isinstance(self.refusals, tuple) or not all(isinstance(r, Refusal) for r in self.refusals):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "refusals must be a tuple of Refusal")
        if not isinstance(self.evidence_status, tuple) or not all(isinstance(v, EvidenceStatusView) for v in self.evidence_status):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "evidence_status must be a tuple of EvidenceStatusView")
        require_str_tuple(self.ignored_envelopes, "ignored_envelopes")
        if self.authority_resolution_basis != AUTHORITY_RESOLUTION_BASIS_V1:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"authority_resolution_basis is fixed at {AUTHORITY_RESOLUTION_BASIS_V1} in slice 1")
        require_nonblank(self.engine_identity, "engine_identity")
        require_nonblank(self.engine_version, "engine_version")
        require_tzaware(self.produced_at, "produced_at")
        for a in self.assessments:
            if a.assessor_identity != self.engine_identity or a.engine_version != self.engine_version:
                raise ContractError(
                    ContractErrorCode.ASSESSOR_ENGINE_MISMATCH,
                    "every assessment's assessor_identity and engine_version must equal the producing engine's",
                )
        # Output ordering is contractual (§7).
        if [a.method.sort_key for a in self.assessments] != sorted(a.method.sort_key for a in self.assessments):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "assessments must be ordered by (method_id, method_version)")
        if [r.sort_key for r in self.refusals] != sorted(r.sort_key for r in self.refusals):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "refusals must be ordered by (code, method_id, detail)")
        if [v.record_digest for v in self.evidence_status] != sorted(v.record_digest for v in self.evidence_status):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "evidence_status must be ordered by record_digest")
        if list(self.ignored_envelopes) != sorted(self.ignored_envelopes):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ignored_envelopes must be ordered by digest")
        settle_digest(self, "result_digest", self._stable_digest())

    def _stable_digest(self) -> str:
        """Excludes result_digest and produced_at; assessments contribute their
        time-free payload so the digest is a function of the request alone."""
        body = payload(self, exclude=("result_digest", "produced_at", "assessments"))
        body["assessments"] = [a.stable_payload() for a in self.assessments]
        from ugence_jcs import canonical_sha256_hex

        return canonical_sha256_hex(body)


__all__ = [
    "COMPARISON_REQUEST_SCHEMA_VERSION",
    "COMPARISON_RESULT_SCHEMA_VERSION",
    "AUTHORITY_RESOLUTION_BASIS_V1",
    "ResolvedAuthority",
    "ResolvedAdmission",
    "Refusal",
    "ReadinessComparisonRequest",
    "ReadinessComparisonResult",
]
