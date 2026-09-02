"""Runner-side and workflow-side clients for the boundary (§4.1). The workflow-side stub
implements ``call(prompt) -> str`` and holds no credential and no SDK."""

from __future__ import annotations

import json
import socket
from typing import Any, Dict, Optional

from ugence_reasoning_method_governance.api import ReasoningMethodRef

from ..errors import PilotError, PilotErrorCode
from .frames import CaptureAttemptStatus, GatewayResponse, method_to_json, response_from_json


class BoundaryConnection:
    def __init__(self, endpoint: str) -> None:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(endpoint)
        self._stream = self._sock.makefile("rwb")

    def send(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        self._stream.write((json.dumps(frame) + "\n").encode("utf-8"))
        self._stream.flush()
        line = self._stream.readline()
        if not line:
            raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "boundary closed the connection")
        reply = json.loads(line.decode("utf-8"))
        if not reply.get("ok", False):
            raise PilotError(PilotErrorCode(reply.get("code", "CAPTURE_INCOMPLETE")), reply.get("detail", ""))
        return reply

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            self._sock.close()


class GatewayStubClient:
    """The workflow's ONLY client. One instance per (run, method); the runner sets the case."""

    def __init__(self, conn: BoundaryConnection, *, manifest_digest: str, method: ReasoningMethodRef, run_id: str) -> None:
        self._conn = conn
        self._manifest_digest = manifest_digest
        self._method = method
        self._run_id = run_id
        self._case: Optional[str] = None
        self._sequence = 0
        self.calls = 0

    def set_case(self, case_digest: str) -> None:
        self._case, self._sequence = case_digest, 0

    def call(self, prompt: str) -> str:
        if self._case is None:
            raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "call outside an open case")
        self._sequence += 1
        self.calls += 1
        reply = self._conn.send({
            "kind": "CALL", "manifest_digest": self._manifest_digest, "method_id": self._method.method_id, "method_version": self._method.method_version,
            "run_id": self._run_id, "case_digest": self._case, "sequence": self._sequence, "prompt": prompt,
        })
        resp: GatewayResponse = response_from_json(reply["response"])
        if resp.status is not CaptureAttemptStatus.SUCCEEDED or resp.text is None:
            raise RuntimeError(f"provider call failed: {resp.error_class or resp.status.value}")
        return resp.text


__all__ = ["BoundaryConnection", "GatewayStubClient", "method_to_json"]
