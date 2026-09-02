"""§4.1–§4.2 frames, ports and the capture record. Plain JSON-serializable shapes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Protocol, Tuple

from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode, ReasoningMethodRef, TokenUsageSnapshot, UsageAvailabilityToken

from .._canon import digest_of, require_digest, require_member, require_nonblank, require_tzaware, rfc3339_utc, settle_digest
from ..contracts.benchmark import require_count


class CaptureAttemptStatus(str, Enum):
    """Pilot-local; pinned to Context Minimization's AttemptStatus by a test-only import."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    EXCEPTION = "EXCEPTION"


class RunControlFrame(str, Enum):
    RUN_BEGIN = "RUN_BEGIN"
    CASE_BEGIN = "CASE_BEGIN"
    CASE_END = "CASE_END"
    RUN_END = "RUN_END"


@dataclass(frozen=True)
class ProviderResult:
    text: str
    usage: Optional[TokenUsageSnapshot]
    usage_availability: UsageAvailabilityToken
    provider_request_id: Optional[str]
    provider_id: str


class ProviderPort(Protocol):
    def complete(self, prompt: str) -> ProviderResult: ...


@dataclass(frozen=True)
class GatewayRequest:
    manifest_digest: str
    method_id: str
    method_version: str
    run_id: str
    case_digest: str
    sequence: int
    prompt: str


@dataclass(frozen=True)
class GatewayResponse:
    sequence: int
    status: CaptureAttemptStatus
    text: Optional[str]
    error_class: Optional[str]
    usage: Optional[TokenUsageSnapshot]
    usage_availability: UsageAvailabilityToken
    provider_request_id: Optional[str]
    capture_fingerprint: str


@dataclass(frozen=True)
class CaptureRecord:
    manifest_digest: str
    method: ReasoningMethodRef
    run_id: str
    case_digest: str
    sequence: int
    provider_id: str
    attempt_id: str
    status: CaptureAttemptStatus
    provider_invoked: bool
    usage_availability: UsageAvailabilityToken
    usage: Optional[TokenUsageSnapshot]
    prompt_digest: str
    response_digest: str
    captured_at: datetime
    capture_fingerprint: str = ""

    def __post_init__(self) -> None:
        require_digest(self.manifest_digest, "CaptureRecord.manifest_digest")
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "CaptureRecord.method must be a ReasoningMethodRef")
        require_nonblank(self.run_id, "CaptureRecord.run_id")
        require_digest(self.case_digest, "CaptureRecord.case_digest")
        require_count(self.sequence, "CaptureRecord.sequence", positive=True)
        require_nonblank(self.provider_id, "CaptureRecord.provider_id")
        require_nonblank(self.attempt_id, "CaptureRecord.attempt_id")
        require_member(self.status, CaptureAttemptStatus, "CaptureRecord.status", ContractErrorCode.REF_BLANK_FIELD)
        require_member(self.usage_availability, UsageAvailabilityToken, "CaptureRecord.usage_availability", ContractErrorCode.REF_BLANK_FIELD)
        if self.usage is not None and not isinstance(self.usage, TokenUsageSnapshot):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "CaptureRecord.usage must be a TokenUsageSnapshot or None")
        require_digest(self.prompt_digest, "CaptureRecord.prompt_digest")
        require_digest(self.response_digest, "CaptureRecord.response_digest")
        require_tzaware(self.captured_at, "CaptureRecord.captured_at")
        settle_digest(self, "capture_fingerprint", digest_of(self, exclude=("capture_fingerprint",)))

    @property
    def order_key(self) -> Tuple[str, int]:
        return (self.case_digest, self.sequence)


# --------------------------------------------------------------------------- JSON codec
def usage_to_json(u: Optional[TokenUsageSnapshot]) -> Optional[Dict[str, Any]]:
    return None if u is None else asdict(u)


def usage_from_json(d: Optional[Dict[str, Any]]) -> Optional[TokenUsageSnapshot]:
    return None if d is None else TokenUsageSnapshot(**d)


def method_to_json(m: ReasoningMethodRef) -> Dict[str, Any]:
    return {"catalog": {"catalog_id": m.catalog.catalog_id, "catalog_version": m.catalog.catalog_version, "catalog_digest": m.catalog.catalog_digest}, "method_id": m.method_id, "method_version": m.method_version}


def method_from_json(d: Dict[str, Any]) -> ReasoningMethodRef:
    from ugence_reasoning_method_governance.api import ReasoningMethodCatalogRef

    c = d["catalog"]
    return ReasoningMethodRef(ReasoningMethodCatalogRef(c["catalog_id"], c["catalog_version"], c["catalog_digest"]), d["method_id"], d["method_version"])


def capture_to_json(r: CaptureRecord) -> Dict[str, Any]:
    return {
        "manifest_digest": r.manifest_digest, "method": method_to_json(r.method), "run_id": r.run_id, "case_digest": r.case_digest,
        "sequence": r.sequence, "provider_id": r.provider_id, "attempt_id": r.attempt_id, "status": r.status.value,
        "provider_invoked": r.provider_invoked, "usage_availability": r.usage_availability.value, "usage": usage_to_json(r.usage),
        "prompt_digest": r.prompt_digest, "response_digest": r.response_digest, "captured_at": rfc3339_utc(r.captured_at),
        "capture_fingerprint": r.capture_fingerprint,
    }


def capture_from_json(d: Dict[str, Any]) -> CaptureRecord:
    return CaptureRecord(
        d["manifest_digest"], method_from_json(d["method"]), d["run_id"], d["case_digest"], int(d["sequence"]), d["provider_id"], d["attempt_id"],
        CaptureAttemptStatus(d["status"]), bool(d["provider_invoked"]), UsageAvailabilityToken(d["usage_availability"]), usage_from_json(d["usage"]),
        d["prompt_digest"], d["response_digest"], datetime.fromisoformat(d["captured_at"].replace("Z", "+00:00")), d["capture_fingerprint"],
    )


def response_to_json(r: GatewayResponse) -> Dict[str, Any]:
    return {"sequence": r.sequence, "status": r.status.value, "text": r.text, "error_class": r.error_class, "usage": usage_to_json(r.usage),
            "usage_availability": r.usage_availability.value, "provider_request_id": r.provider_request_id, "capture_fingerprint": r.capture_fingerprint}


def response_from_json(d: Dict[str, Any]) -> GatewayResponse:
    return GatewayResponse(int(d["sequence"]), CaptureAttemptStatus(d["status"]), d["text"], d["error_class"], usage_from_json(d["usage"]),
                           UsageAvailabilityToken(d["usage_availability"]), d["provider_request_id"], d["capture_fingerprint"])


__all__ = [
    "CaptureAttemptStatus", "RunControlFrame", "ProviderResult", "ProviderPort", "GatewayRequest", "GatewayResponse", "CaptureRecord",
    "usage_to_json", "usage_from_json", "method_to_json", "method_from_json", "capture_to_json", "capture_from_json", "response_to_json", "response_from_json",
]
