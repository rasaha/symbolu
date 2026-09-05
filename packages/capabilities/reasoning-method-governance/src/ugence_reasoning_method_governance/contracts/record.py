"""Specification §4 — the v1 execution record.

The three evidence axes are CLASS CONSTANTS: OBSERVED / UNATTESTED /
UNVERIFIED. No producer can set them; a constructor keyword naming any of
them is refused with EVIDENCE_AXIS_SET_BY_PRODUCER. Promotion exists only as
separate authority envelopes (§6) that reference ``record_digest``.

Telemetry vocabulary (``CountBasis``, ``UsageAvailabilityToken``,
``TokenUsageSnapshot``) MIRRORS ``context-minimization``'s
``TokenCountBasis``, ``UsageAvailability`` and ``ProviderTokenUsage`` and is
pinned by a test-only import (spec 1.1-B). Nothing here imports that package.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import ClassVar, Optional, Tuple

from ugence_governance_contracts.api import AttestationStatus, SourceBasis, VerificationStatus

from ..errors import ContractError, ContractErrorCode
from ._util import (
    digest_of,
    guard_kwargs,
    require_decimal_string,
    require_digest,
    require_member,
    require_nonblank,
    require_str_tuple,
    require_tzaware,
    settle_digest,
)
from .catalog import ReasoningMethodRef

RECORD_SCHEMA_VERSION = "reasoning_method.execution_record.v1"
RECORD_V1_SOURCE_BASIS = SourceBasis.OBSERVED
RECORD_V1_ATTESTATION_STATUS = AttestationStatus.UNATTESTED
RECORD_V1_VERIFICATION_STATUS = VerificationStatus.UNVERIFIED

EVIDENCE_AXIS_FIELD_NAMES = ("source_basis", "attestation_status", "verification_status")


class ArtifactKind(str, Enum):
    CANDIDATE = "CANDIDATE"
    REVISION = "REVISION"
    DECISION = "DECISION"
    FINAL_OUTPUT = "FINAL_OUTPUT"


@dataclass(frozen=True)
class ArtifactRef:
    kind: ArtifactKind
    ref: str
    digest: str

    def __post_init__(self) -> None:
        require_member(self.kind, ArtifactKind, "ArtifactRef.kind", ContractErrorCode.ARTIFACT_KIND_UNKNOWN)
        require_nonblank(self.ref, "ArtifactRef.ref")
        require_digest(self.digest, "ArtifactRef.digest")


class CountBasis(str, Enum):
    CALLER_SUPPLIED = "CALLER_SUPPLIED"
    INJECTED_COUNTER = "INJECTED_COUNTER"
    DEFAULT_APPROXIMATE = "DEFAULT_APPROXIMATE"
    MIXED = "MIXED"
    PROVIDER_REPORTED = "PROVIDER_REPORTED"
    UNKNOWN = "UNKNOWN"


class UsageAvailabilityToken(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE_NOT_REPORTED = "UNAVAILABLE_NOT_REPORTED"
    UNAVAILABLE_PROVIDER_ERROR = "UNAVAILABLE_PROVIDER_ERROR"
    UNAVAILABLE_UNKNOWN = "UNAVAILABLE_UNKNOWN"


@dataclass(frozen=True)
class TokenUsageSnapshot:
    input_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_write_input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    provider_request_id: Optional[str] = None
    usage_schema: Optional[str] = None
    adapter_id: Optional[str] = None
    adapter_version: Optional[str] = None

    _count_fields: ClassVar[Tuple[str, ...]] = (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    )

    def __post_init__(self) -> None:
        for name in self._count_fields:
            v = getattr(self, name)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
                raise ContractError(ContractErrorCode.TELEMETRY_INVARIANT, f"TokenUsageSnapshot.{name} must be a non-negative int or None")

    @property
    def has_any_count(self) -> bool:
        return any(getattr(self, n) is not None for n in self._count_fields)


@dataclass(frozen=True)
class ExecutionTelemetry:
    llm_calls: Optional[int]
    llm_calls_basis: CountBasis
    token_usage_availability: UsageAvailabilityToken
    token_usage: Optional[TokenUsageSnapshot]
    token_count_basis: CountBasis
    duration_ms: Optional[int]
    capture_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_member(self.llm_calls_basis, CountBasis, "ExecutionTelemetry.llm_calls_basis", ContractErrorCode.TELEMETRY_INVARIANT)
        require_member(self.token_usage_availability, UsageAvailabilityToken, "ExecutionTelemetry.token_usage_availability", ContractErrorCode.TELEMETRY_INVARIANT)
        require_member(self.token_count_basis, CountBasis, "ExecutionTelemetry.token_count_basis", ContractErrorCode.TELEMETRY_INVARIANT)
        if self.llm_calls is not None and (isinstance(self.llm_calls, bool) or not isinstance(self.llm_calls, int) or self.llm_calls < 0):
            raise ContractError(ContractErrorCode.TELEMETRY_INVARIANT, "ExecutionTelemetry.llm_calls must be a non-negative int or None")
        if self.llm_calls is None and self.llm_calls_basis is not CountBasis.UNKNOWN:
            raise ContractError(ContractErrorCode.TELEMETRY_INVARIANT, "llm_calls None requires llm_calls_basis UNKNOWN")
        if self.duration_ms is not None and (isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int) or self.duration_ms < 0):
            raise ContractError(ContractErrorCode.TELEMETRY_INVARIANT, "ExecutionTelemetry.duration_ms must be a non-negative int or None")
        if self.token_usage is not None and not isinstance(self.token_usage, TokenUsageSnapshot):
            raise ContractError(ContractErrorCode.TELEMETRY_INVARIANT, "ExecutionTelemetry.token_usage must be a TokenUsageSnapshot or None")
        if self.token_usage_availability is UsageAvailabilityToken.AVAILABLE:
            if self.token_usage is None or not self.token_usage.has_any_count:
                raise ContractError(ContractErrorCode.TELEMETRY_INVARIANT, "AVAILABLE requires a TokenUsageSnapshot with at least one count")
        elif self.token_usage is not None:
            raise ContractError(ContractErrorCode.TELEMETRY_INVARIANT, "token_usage must be None unless availability is AVAILABLE")
        require_str_tuple(self.capture_refs, "ExecutionTelemetry.capture_refs")

    def resource_value(self, dimension: object) -> Optional[int]:
        """Read a resource dimension; None when unavailable. Duration is never a dimension."""
        name = getattr(dimension, "value", dimension)
        if name == "LLM_CALLS":
            return self.llm_calls
        if name == "TOTAL_TOKENS":
            return None if self.token_usage is None else self.token_usage.total_tokens
        return None


@dataclass(frozen=True)
class BindingRef:
    binding_id: str
    configuration_id: str
    configuration_digest: str
    context_digest: str
    binding_digest: str

    def __post_init__(self) -> None:
        require_nonblank(self.binding_id, "BindingRef.binding_id")
        require_nonblank(self.configuration_id, "BindingRef.configuration_id")
        require_digest(self.configuration_digest, "BindingRef.configuration_digest")
        require_digest(self.context_digest, "BindingRef.context_digest")
        require_digest(self.binding_digest, "BindingRef.binding_digest")


@dataclass(frozen=True)
class ReasoningMethodExecutionRecord:
    schema_version: str
    record_id: str
    tenant_id: str
    subject_id: str
    invocation_id: str
    method: ReasoningMethodRef
    binding: BindingRef
    task_class_ref: str
    task_class_digest: str
    input_digest: str
    model_ref: str
    policy_refs: Tuple[str, ...]
    artifacts: Tuple[ArtifactRef, ...]
    telemetry: ExecutionTelemetry
    self_reported_quality: Optional[str]
    issuer_identity: str
    captured_at: datetime
    parent_record_digest: Optional[str]
    record_digest: str = ""

    # Constants of the v1 schema. Read-only; no producer can set them.
    source_basis: ClassVar[SourceBasis] = RECORD_V1_SOURCE_BASIS
    attestation_status: ClassVar[AttestationStatus] = RECORD_V1_ATTESTATION_STATUS
    verification_status: ClassVar[VerificationStatus] = RECORD_V1_VERIFICATION_STATUS

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ReasoningMethodExecutionRecord.schema_version")
        require_nonblank(self.record_id, "ReasoningMethodExecutionRecord.record_id")
        require_nonblank(self.tenant_id, "ReasoningMethodExecutionRecord.tenant_id")
        require_nonblank(self.subject_id, "ReasoningMethodExecutionRecord.subject_id")
        require_nonblank(self.invocation_id, "ReasoningMethodExecutionRecord.invocation_id")
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReasoningMethodExecutionRecord.method must be a ReasoningMethodRef")
        if not isinstance(self.binding, BindingRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReasoningMethodExecutionRecord.binding must be a BindingRef")
        require_nonblank(self.task_class_ref, "ReasoningMethodExecutionRecord.task_class_ref")
        require_digest(self.task_class_digest, "ReasoningMethodExecutionRecord.task_class_digest")
        require_digest(self.input_digest, "ReasoningMethodExecutionRecord.input_digest")
        require_nonblank(self.model_ref, "ReasoningMethodExecutionRecord.model_ref")
        require_str_tuple(self.policy_refs, "ReasoningMethodExecutionRecord.policy_refs")
        if not isinstance(self.artifacts, tuple):
            raise ContractError(ContractErrorCode.ARTIFACT_KIND_UNKNOWN, "artifacts must be a tuple of ArtifactRef")
        for a in self.artifacts:
            if not isinstance(a, ArtifactRef):
                raise ContractError(ContractErrorCode.ARTIFACT_KIND_UNKNOWN, "artifacts must be ArtifactRef values")
        if not isinstance(self.telemetry, ExecutionTelemetry):
            raise ContractError(ContractErrorCode.TELEMETRY_INVARIANT, "telemetry must be an ExecutionTelemetry")
        if self.self_reported_quality is not None:
            require_decimal_string(self.self_reported_quality, "ReasoningMethodExecutionRecord.self_reported_quality")
        require_nonblank(self.issuer_identity, "ReasoningMethodExecutionRecord.issuer_identity")
        require_tzaware(self.captured_at, "ReasoningMethodExecutionRecord.captured_at")
        if self.parent_record_digest is not None:
            require_digest(self.parent_record_digest, "ReasoningMethodExecutionRecord.parent_record_digest")
            # L-1: an immediate self-referential lineage is refused before the digest is
            # settled, so a hand-built record naming itself as its own parent is caught
            # whether or not its supplied digest is otherwise consistent.
            if self.record_digest and self.parent_record_digest == self.record_digest:
                raise ContractError(ContractErrorCode.LINEAGE_SELF_REFERENCE, "parent_record_digest must not equal this record's own digest")
        computed = digest_of(
            self,
            exclude=("record_digest",),
            extra={
                "source_basis": self.source_basis,
                "attestation_status": self.attestation_status,
                "verification_status": self.verification_status,
            },
        )
        if self.parent_record_digest is not None and self.parent_record_digest == computed:
            raise ContractError(ContractErrorCode.LINEAGE_SELF_REFERENCE, "parent_record_digest must not equal this record's own digest")
        settle_digest(self, "record_digest", computed)
        if self.parent_record_digest is not None and self.parent_record_digest == self.record_digest:
            raise ContractError(ContractErrorCode.LINEAGE_SELF_REFERENCE, "parent_record_digest must not equal this record's own digest")


guard_kwargs(ReasoningMethodExecutionRecord, EVIDENCE_AXIS_FIELD_NAMES, ContractErrorCode.EVIDENCE_AXIS_SET_BY_PRODUCER)

# The evidence axes are ClassVars and must never become instance fields.
assert not any(f.name in EVIDENCE_AXIS_FIELD_NAMES for f in fields(ReasoningMethodExecutionRecord))


__all__ = [
    "RECORD_SCHEMA_VERSION",
    "RECORD_V1_SOURCE_BASIS",
    "RECORD_V1_ATTESTATION_STATUS",
    "RECORD_V1_VERIFICATION_STATUS",
    "EVIDENCE_AXIS_FIELD_NAMES",
    "ArtifactKind",
    "ArtifactRef",
    "CountBasis",
    "UsageAvailabilityToken",
    "TokenUsageSnapshot",
    "ExecutionTelemetry",
    "BindingRef",
    "ReasoningMethodExecutionRecord",
]
