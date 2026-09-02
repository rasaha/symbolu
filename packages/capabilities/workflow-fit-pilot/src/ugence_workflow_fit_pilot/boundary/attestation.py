"""§4.3 telemetry recomputation from capture records and attestation issuance.

The one clock read the package permits outside CaptureRecord.captured_at happens
here, at issuance, for ``attested_at``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence, Tuple

from ugence_reasoning_method_governance.api import (
    ATTESTATION_ENVELOPE_SCHEMA_VERSION,
    RECORD_V1_ATTESTATION_STATUS,
    RECORD_V1_SOURCE_BASIS,
    RECORD_V1_VERIFICATION_STATUS,
    AttestationEnvelope,
    CountBasis,
    ExecutionTelemetry,
    ReasoningMethodExecutionRecord,
    TokenUsageSnapshot,
    UsageAvailabilityToken,
)

from .._canon import digest_of, payload
from ..contracts.manifest import ATTESTABLE_TELEMETRY_FIELDS, LLM_CALLS_FIELD, CaptureBoundaryDeclaration
from ..contracts.observation import capture_boundary_ref_of
from ..errors import PilotError, PilotErrorCode
from .frames import CaptureRecord

_TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_tokens", "total_tokens")


def canonical_order(records: Sequence[CaptureRecord]) -> Tuple[CaptureRecord, ...]:
    return tuple(sorted(records, key=lambda r: r.order_key))


def recompute_telemetry(manifest_digest: str, records: Sequence[CaptureRecord]) -> ExecutionTelemetry:
    """§4.3 step 3: llm_calls = count of capture records (the sum over the case set);
    token fields summed per field only when present in every record."""
    ordered = canonical_order(records)
    if any(r.manifest_digest != manifest_digest for r in ordered):
        raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "capture record from another manifest")
    llm_calls = len(ordered)
    availability = UsageAvailabilityToken.AVAILABLE
    for r in ordered:
        if r.usage_availability is not UsageAvailabilityToken.AVAILABLE:
            availability = r.usage_availability
            break
    usage: Optional[TokenUsageSnapshot] = None
    if ordered and availability is UsageAvailabilityToken.AVAILABLE:
        sums: Dict[str, Optional[int]] = {}
        for f in _TOKEN_FIELDS:
            values = [getattr(r.usage, f) if r.usage is not None else None for r in ordered]
            sums[f] = sum(values) if all(v is not None for v in values) else None
        if any(v is not None for v in sums.values()):
            usage = TokenUsageSnapshot(**sums)
        else:
            availability = UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED
    elif not ordered:
        availability = UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED
    return ExecutionTelemetry(
        llm_calls=llm_calls,
        llm_calls_basis=CountBasis.INJECTED_COUNTER,
        token_usage_availability=availability,
        token_usage=usage,
        token_count_basis=CountBasis.PROVIDER_REPORTED if usage is not None else CountBasis.UNKNOWN,
        duration_ms=None,
        capture_refs=(manifest_digest,) + tuple(r.capture_fingerprint for r in ordered),
    )


def supported_attested_fields(declaration: CaptureBoundaryDeclaration, telemetry: ExecutionTelemetry) -> Tuple[str, ...]:
    out = []
    for f in ATTESTABLE_TELEMETRY_FIELDS:
        if f not in declaration.allowed_attested_fields:
            continue
        if f == LLM_CALLS_FIELD:
            out.append(f)
        elif telemetry.token_usage is not None and getattr(telemetry.token_usage, f.rsplit(".", 1)[1]) is not None:
            out.append(f)
    return tuple(out)


def record_canonical_payload(record: ReasoningMethodExecutionRecord) -> Dict[str, Any]:
    """The exact payload whose digest is record_digest: the record's fields plus Slice 1's
    three evidence-axis constants, which the record contract folds into its digest."""
    body = payload(record)
    body["source_basis"] = RECORD_V1_SOURCE_BASIS.value
    body["attestation_status"] = RECORD_V1_ATTESTATION_STATUS.value
    body["verification_status"] = RECORD_V1_VERIFICATION_STATUS.value
    return body


def envelope_id_for(record_digest: str, boundary_identity: str) -> str:
    return f"att:{record_digest[:16]}:{boundary_identity}"


def issue_attestation(
    record_payload: Dict[str, Any],
    capture_records: Sequence[CaptureRecord],
    *,
    declaration: CaptureBoundaryDeclaration,
    record_issuer_identity: str,
    requester_identity: str,
    envelope_id: str,
) -> AttestationEnvelope:
    """§4.3 step 5. Recomputes the record digest from its canonical payload and the telemetry
    from the capture records, refuses mismatch and self-attestation, and issues the envelope
    over the record digest with the supported subset of the declared fields. ``attested_at``
    is the boundary's own instant, obtained here."""
    if not isinstance(record_payload, dict) or "record_digest" not in record_payload or "telemetry" not in record_payload:
        raise PilotError(PilotErrorCode.TELEMETRY_NOT_RECOMPUTED, "record payload must carry record_digest and telemetry")
    supplied_digest = record_payload["record_digest"]
    body = {k: v for k, v in record_payload.items() if k != "record_digest"}
    if digest_of(body) != supplied_digest:
        raise PilotError(PilotErrorCode.TELEMETRY_NOT_RECOMPUTED, "record_digest is not the digest of the supplied payload")
    manifest_digest = capture_records[0].manifest_digest if capture_records else None
    if manifest_digest is None:
        raise PilotError(PilotErrorCode.TELEMETRY_NOT_RECOMPUTED, "no capture records")
    # Attribution: every capture record must belong to THIS record's method and invocation.
    method = record_payload.get("method") or {}
    run_id = record_payload.get("invocation_id")
    for c in capture_records:
        if c.manifest_digest != manifest_digest or c.run_id != run_id or c.method.method_id != method.get("method_id") or c.method.method_version != method.get("method_version"):
            raise PilotError(PilotErrorCode.ATTESTATION_MISMATCH, "capture records do not belong to this record's method and invocation")
    telemetry_refs = record_payload["telemetry"].get("capture_refs") if isinstance(record_payload.get("telemetry"), dict) else None
    if not telemetry_refs or telemetry_refs[0] != manifest_digest:
        raise PilotError(PilotErrorCode.ATTESTATION_MISMATCH, "record capture_refs do not stamp the capture records' manifest")
    recomputed = payload(recompute_telemetry(manifest_digest, capture_records))
    if recomputed != record_payload["telemetry"]:
        raise PilotError(PilotErrorCode.TELEMETRY_NOT_RECOMPUTED, "record telemetry differs from the boundary's recomputation")
    if declaration.boundary_identity in (record_issuer_identity, requester_identity):
        raise PilotError(PilotErrorCode.SELF_ATTESTATION, "the boundary must differ from the record issuer and the requester")
    expected_id = envelope_id_for(supplied_digest, declaration.boundary_identity)
    if envelope_id != expected_id:
        raise PilotError(PilotErrorCode.ATTESTATION_MISMATCH, f"envelope_id must be {expected_id!r}")
    telemetry = recompute_telemetry(manifest_digest, capture_records)
    return AttestationEnvelope(
        ATTESTATION_ENVELOPE_SCHEMA_VERSION, envelope_id, supplied_digest, declaration.boundary_identity,
        capture_boundary_ref_of(telemetry.capture_refs), supported_attested_fields(declaration, telemetry), datetime.now(timezone.utc),
    )


__all__ = ["canonical_order", "recompute_telemetry", "supported_attested_fields", "record_canonical_payload", "envelope_id_for", "issue_attestation"]
