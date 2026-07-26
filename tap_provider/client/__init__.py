"""TAP client abstraction — in-process and remote modes.

The provider talks to TAP through a narrow client seam so it supports both an
**in-process** engine and a **remote** service without a hard network
dependency. The remote client is an abstraction only: for deterministic testing
it delegates to an in-process engine while able to simulate transport-level
failures (timeout / unavailable) independently of the engine. A production
model-backed evaluator would sit behind this same seam.

Imports the TAP core only — never DGM or the provider framework.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..core import (
    TapEngine,
    TapEvaluationRequest,
    TapEvaluationResult,
    TapTimeout,
    TapUnavailable,
)


@runtime_checkable
class TapClient(Protocol):
    def evaluate(self, request: TapEvaluationRequest) -> TapEvaluationResult: ...
    def ping(self) -> bool: ...
    def policy_version(self) -> str: ...


class InProcessTapClient:
    """Runs the TAP engine in the current process."""

    mode = "in_process"

    def __init__(self, engine: TapEngine) -> None:
        self._engine = engine

    def evaluate(self, request: TapEvaluationRequest) -> TapEvaluationResult:
        return self._engine.evaluate(request)

    def ping(self) -> bool:
        return self._engine.available

    def policy_version(self) -> str:
        return self._engine.policy_version


class RemoteTapClient:
    """A remote-service client abstraction (no real network in tests).

    Delegates to a co-located engine but can simulate a transport failure before
    the engine is reached — proving the remote-mode seam and its error handling.
    """

    mode = "remote"

    def __init__(self, engine: TapEngine, *, transport_fail: Optional[str] = None,
                 endpoint: str = "tap://in-memory") -> None:
        self._engine = engine
        self._transport_fail = transport_fail
        self.endpoint = endpoint

    def _transport(self) -> None:
        if self._transport_fail == "timeout":
            raise TapTimeout(f"remote tap timed out at {self.endpoint}")
        if self._transport_fail == "unavailable":
            raise TapUnavailable(f"remote tap unreachable at {self.endpoint}")

    def evaluate(self, request: TapEvaluationRequest) -> TapEvaluationResult:
        self._transport()
        return self._engine.evaluate(request)

    def ping(self) -> bool:
        try:
            self._transport()
        except Exception:
            return False
        return self._engine.available

    def policy_version(self) -> str:
        return self._engine.policy_version
