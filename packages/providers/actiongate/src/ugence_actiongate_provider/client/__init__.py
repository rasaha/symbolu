"""ActionGate client abstraction — in-process and remote modes.

The provider talks to ActionGate through a narrow client seam so it supports both
an **in-process** engine and a **remote** service without a hard network
dependency. The remote client is an abstraction only: for deterministic testing
it delegates to an in-process engine while able to simulate transport-level
failures (timeout / unavailable) independently of the engine.

Imports the ActionGate core only — never DGM or the provider framework.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..core import (
    ActionGateDecision,
    ActionGateEngine,
    ActionGateRequest,
    ActionGateTimeout,
    ActionGateUnavailable,
)


@runtime_checkable
class ActionGateClient(Protocol):
    def evaluate(self, request: ActionGateRequest) -> ActionGateDecision: ...
    def ping(self) -> bool: ...
    def policy_version(self) -> str: ...


class InProcessActionGateClient:
    """Runs the ActionGate engine in the current process."""

    mode = "in_process"

    def __init__(self, engine: ActionGateEngine) -> None:
        self._engine = engine

    def evaluate(self, request: ActionGateRequest) -> ActionGateDecision:
        return self._engine.evaluate(request)

    def ping(self) -> bool:
        return self._engine.available

    def policy_version(self) -> str:
        return self._engine.policy_version


class RemoteActionGateClient:
    """A remote-service client abstraction (no real network in tests).

    Delegates to a co-located engine but can simulate a transport failure before
    the engine is reached — proving the remote-mode seam and its error handling.
    """

    mode = "remote"

    def __init__(self, engine: ActionGateEngine, *, transport_fail: Optional[str] = None,
                 endpoint: str = "actiongate://in-memory") -> None:
        self._engine = engine
        self._transport_fail = transport_fail
        self.endpoint = endpoint

    def _transport(self) -> None:
        if self._transport_fail == "timeout":
            raise ActionGateTimeout(f"remote actiongate timed out at {self.endpoint}")
        if self._transport_fail == "unavailable":
            raise ActionGateUnavailable(f"remote actiongate unreachable at {self.endpoint}")

    def evaluate(self, request: ActionGateRequest) -> ActionGateDecision:
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
