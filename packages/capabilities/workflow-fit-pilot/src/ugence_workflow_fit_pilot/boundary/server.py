"""§4.1 boundary server: newline-delimited JSON frames over a local socket, one client at a
time. Holds the provider port, writes capture records, enforces the completeness rule and
issues attestations. Runs only inside the boundary process (entry.py)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ugence_reasoning_method_governance.api import ReasoningMethodCatalogRef, ReasoningMethodRef, UsageAvailabilityToken

from .._canon import digest_of, payload
from ..contracts.manifest import CaptureBoundaryDeclaration
from ..errors import PilotError, PilotErrorCode
from .attestation import canonical_order, issue_attestation, recompute_telemetry
from .frames import CaptureAttemptStatus, CaptureRecord, GatewayResponse, ProviderPort, capture_to_json, method_from_json, response_to_json
from .transport import serve as _serve


def _text_digest(text: str) -> str:
    return digest_of({"text": text})


@dataclass
class _RunState:
    method: ReasoningMethodRef
    records: List[CaptureRecord] = field(default_factory=list)
    open_case: Optional[str] = None
    seen_cases: Dict[str, int] = field(default_factory=dict)   # case_digest -> captured calls at CASE_END
    case_calls: int = 0
    incomplete_reasons: List[str] = field(default_factory=list)
    ended: bool = False


class BoundaryServer:
    def __init__(self, *, manifest_digest: str, provider: ProviderPort, declaration_fields: Dict[str, Any]) -> None:
        self.manifest_digest = manifest_digest
        self.provider = provider
        self.declaration = CaptureBoundaryDeclaration(**declaration_fields)
        self.runs: Dict[str, _RunState] = {}
        self._attempt_counter = 0

    # ---- frames
    def handle(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        kind = frame.get("kind")
        try:
            if kind == "RUN_BEGIN":
                return self._run_begin(frame)
            if kind == "CASE_BEGIN":
                return self._case_begin(frame)
            if kind == "CALL":
                return self._call(frame)
            if kind == "CASE_END":
                return self._case_end(frame)
            if kind == "RUN_END":
                return self._run_end(frame)
            if kind == "ATTEST":
                return self._attest(frame)
            if kind == "PING":
                return {"ok": True}
            raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, f"unknown frame {kind!r}")
        except PilotError as e:
            return {"ok": False, "code": e.code.value, "detail": e.detail}

    def _require_manifest(self, frame: Dict[str, Any]) -> None:
        if frame.get("manifest_digest") != self.manifest_digest:
            raise PilotError(PilotErrorCode.MANIFEST_MISMATCH, "frame carries a manifest digest the boundary was not started with")

    def _run_begin(self, f: Dict[str, Any]) -> Dict[str, Any]:
        self._require_manifest(f)
        run_id = f["run_id"]
        if run_id in self.runs:
            raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "run_id already begun")
        self.runs[run_id] = _RunState(method=method_from_json(f["method"]))
        return {"ok": True}

    def _run(self, f: Dict[str, Any]) -> _RunState:
        run = self.runs.get(f.get("run_id", ""))
        if run is None or run.ended:
            raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "no open run for run_id")
        return run

    def _case_begin(self, f: Dict[str, Any]) -> Dict[str, Any]:
        run = self._run(f)
        case = f["case_digest"]
        if run.open_case is not None:
            run.incomplete_reasons.append("CASE_BEGIN while a case is open")
        if case in run.seen_cases:
            run.incomplete_reasons.append(f"case {case[:12]} begun twice")
        run.open_case, run.case_calls = case, 0
        return {"ok": True}

    def _call(self, f: Dict[str, Any]) -> Dict[str, Any]:
        self._require_manifest(f)
        run = self._run(f)
        case = f["case_digest"]
        if run.open_case != case:
            raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "CALL outside an open case")
        sequence = int(f["sequence"])
        if sequence != run.case_calls + 1:
            run.incomplete_reasons.append(f"sequence gap at {sequence}")
        run.case_calls += 1
        self._attempt_counter += 1
        prompt = f["prompt"]
        status, text, error_class, usage, availability, req_id, provider_id = CaptureAttemptStatus.SUCCEEDED, None, None, None, UsageAvailabilityToken.UNAVAILABLE_UNKNOWN, None, "provider:unknown"
        invoked = False
        try:
            invoked = True
            result = self.provider.complete(prompt)
            text, usage, availability, req_id, provider_id = result.text, result.usage, result.usage_availability, result.provider_request_id, result.provider_id
        except TimeoutError as e:  # noqa: PERF203
            status, error_class, availability = CaptureAttemptStatus.TIMEOUT, type(e).__name__, UsageAvailabilityToken.UNAVAILABLE_PROVIDER_ERROR
        except Exception as e:  # provider failures are capture records, never crashes
            status, error_class, availability = CaptureAttemptStatus.EXCEPTION, type(e).__name__, UsageAvailabilityToken.UNAVAILABLE_PROVIDER_ERROR
        if availability is not UsageAvailabilityToken.AVAILABLE:
            usage = None
        record = CaptureRecord(
            self.manifest_digest, run.method, f["run_id"], case, sequence, provider_id, f"attempt:{self._attempt_counter}", status, invoked,
            availability, usage, _text_digest(prompt), _text_digest(text or ""), datetime.now(timezone.utc),
        )
        run.records.append(record)
        resp = GatewayResponse(sequence, status, text, error_class, usage, availability, req_id, record.capture_fingerprint)
        return {"ok": True, "response": response_to_json(resp)}

    def _case_end(self, f: Dict[str, Any]) -> Dict[str, Any]:
        run = self._run(f)
        case = f["case_digest"]
        if run.open_case != case:
            raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "CASE_END for a case that is not open")
        observed = int(f["harness_observed_calls"])
        if observed != run.case_calls:
            run.incomplete_reasons.append(f"case {case[:12]}: captured {run.case_calls} != harness_observed {observed}")
        run.seen_cases[case] = run.case_calls
        run.open_case = None
        return {"ok": True}

    def _run_end(self, f: Dict[str, Any]) -> Dict[str, Any]:
        run = self._run(f)
        run.ended = True
        expected = list(f["case_digests"])
        if run.open_case is not None:
            run.incomplete_reasons.append("RUN_END while a case is open")
        missing = [c for c in expected if c not in run.seen_cases]
        extra = [c for c in run.seen_cases if c not in expected]
        if missing or extra:
            run.incomplete_reasons.append(f"cases missing {len(missing)} / unexpected {len(extra)}")
        observed = int(f["harness_observed_calls"])
        if observed != len(run.records):
            run.incomplete_reasons.append(f"run: captured {len(run.records)} != harness_observed {observed}")
        if run.incomplete_reasons:
            return {"ok": True, "complete": False, "reasons": list(run.incomplete_reasons), "capture_records": [capture_to_json(r) for r in canonical_order(run.records)]}
        telemetry = recompute_telemetry(self.manifest_digest, run.records)
        return {"ok": True, "complete": True, "telemetry": payload(telemetry), "capture_records": [capture_to_json(r) for r in canonical_order(run.records)]}

    def _attest(self, f: Dict[str, Any]) -> Dict[str, Any]:
        run = self.runs.get(f.get("run_id", ""))
        if run is None or not run.ended or run.incomplete_reasons:
            raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "attestation requires a complete, ended run")
        env = issue_attestation(
            f["record_payload"], canonical_order(run.records), declaration=self.declaration,
            record_issuer_identity=f["record_issuer_identity"], requester_identity=f["requester_identity"], envelope_id=f["envelope_id"],
        )
        return {"ok": True, "envelope": payload(env)}

    # ---- transport
    def serve(self, endpoint: str, *, ready) -> None:
        """Serve frames on the endpoint (Unix socket path or "stdio"); ``ready()`` is called once
        the endpoint accepts frames."""
        _serve(endpoint, self.handle, ready=ready)


__all__ = ["BoundaryServer"]
