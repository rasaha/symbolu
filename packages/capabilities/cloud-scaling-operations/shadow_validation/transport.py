"""Hard read-only transport barrier.

Only ``GET`` / ``HEAD`` (and read-only ``WATCH`` / ``LIST`` semantics) may reach a
remote endpoint. ``POST`` / ``PUT`` / ``PATCH`` / ``DELETE`` / ``DELETECOLLECTION`` /
``CONNECT`` are rejected *locally, before the underlying transport is invoked* — the
barrier never depends on remote RBAC to stop a write. Every attempt (allowed or blocked)
is recorded in an append-only request-method ledger with redacted endpoints.

The :class:`ReadOnlyHTTPClient` wraps an injected raw transport callable and enforces the
barrier on every call, including calls funneled through Kubernetes scale-subresource
helpers, ArgoCD sync helpers, retry wrappers, or generic request methods — because they
all ultimately go through this one method-checked chokepoint.
"""

from __future__ import annotations

import time
from typing import Callable, List, Optional, Tuple

from .contracts import Destination, LedgerEntry, TransportDecision
from .redaction import redact_url

# Read verbs that may reach a remote endpoint.
ALLOWED_METHODS = frozenset({"GET", "HEAD", "WATCH", "LIST"})
# Write / tunnelling verbs that must be blocked before transmission.
BLOCKED_METHODS = frozenset({
    "POST", "PUT", "PATCH", "DELETE", "DELETECOLLECTION", "CONNECT", "OPTIONS",
})


class ReadOnlyViolation(Exception):
    """Raised when a non-read method is attempted under the shadow barrier."""

    def __init__(self, method: str, redacted_endpoint: str, reason: str):
        super().__init__(reason)
        self.method = method
        self.redacted_endpoint = redacted_endpoint
        self.reason = reason


class RequestMethodLedger:
    """Append-only ledger of every attempted remote call."""

    def __init__(self, fixture_or_real: str = "fixture"):
        self._entries: List[LedgerEntry] = []
        self._fixture_or_real = fixture_or_real

    def record(self, entry: LedgerEntry) -> None:
        self._entries.append(entry)

    @property
    def entries(self) -> Tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    def transmitted_write_methods(self) -> List[str]:
        """Write methods that were *allowed to transmit* — must always be empty."""
        return [e.method for e in self._entries
                if e.allowed and e.method.upper() in BLOCKED_METHODS]

    def counts(self) -> dict:
        out: dict = {}
        for e in self._entries:
            key = e.method.upper()
            bucket = out.setdefault(key, {"attempted": 0, "allowed": 0, "blocked": 0})
            bucket["attempted"] += 1
            bucket["allowed"] += int(e.allowed)
            bucket["blocked"] += int(e.blocked)
        return out

    def to_jsonl(self) -> str:
        import json
        return "\n".join(json.dumps(e.to_dict(), sort_keys=True) for e in self._entries)


class ReadOnlyTransportBarrier:
    """Decides — before any transmission — whether a method may proceed."""

    def __init__(self, ledger: Optional[RequestMethodLedger] = None,
                 clock: Callable[[], float] = time.time,
                 fixture_or_real: str = "fixture"):
        self.ledger = ledger or RequestMethodLedger(fixture_or_real)
        self._clock = clock
        self._fixture_or_real = fixture_or_real

    def evaluate(self, method: str, endpoint: str, *,
                 destination: Destination = Destination.GENERIC,
                 call_site: str = "unknown") -> TransportDecision:
        """Return a decision without transmitting. Records nothing (pure)."""
        m = (method or "").strip().upper()
        red = redact_url(endpoint)
        allowed = m in ALLOWED_METHODS
        reason = None if allowed else (
            f"method {m or '<empty>'} is not read-only; blocked before transmission")
        return TransportDecision(
            method=m, destination_class=destination.value, redacted_endpoint=red,
            allowed=allowed, blocked_reason=reason, call_site=call_site,
            timestamp=self._clock())

    def guard(self, method: str, endpoint: str, *,
              destination: Destination = Destination.GENERIC,
              call_site: str = "unknown",
              response_status: Optional[int] = None,
              duration_ms: Optional[float] = None) -> TransportDecision:
        """Evaluate, record to the ledger, and raise on a blocked method."""
        decision = self.evaluate(method, endpoint, destination=destination,
                                 call_site=call_site)
        self.ledger.record(LedgerEntry(
            timestamp=decision.timestamp,
            destination_class=decision.destination_class,
            redacted_endpoint=decision.redacted_endpoint,
            method=decision.method,
            allowed=decision.allowed,
            blocked=not decision.allowed,
            blocked_reason=decision.blocked_reason,
            call_site=call_site,
            response_status=response_status if decision.allowed else None,
            duration_ms=duration_ms if decision.allowed else None,
            fixture_or_real=self._fixture_or_real,
        ))
        if not decision.allowed:
            raise ReadOnlyViolation(decision.method, decision.redacted_endpoint,
                                    decision.blocked_reason or "blocked")
        return decision


class ReadOnlyHTTPClient:
    """Read-only HTTP wrapper around an injected raw transport.

    ``transport(method, url, headers, timeout) -> (status, body)`` is only ever invoked
    for read verbs that clear the barrier; write verbs raise :class:`ReadOnlyViolation`
    and the raw transport is never called (asserted by the mutation-canary suite).
    """

    def __init__(self, transport: Callable[..., Tuple[int, str]],
                 barrier: ReadOnlyTransportBarrier,
                 destination: Destination = Destination.GENERIC):
        self._transport = transport
        self._barrier = barrier
        self._destination = destination

    def request(self, method: str, url: str, *, headers=None, timeout: float = 10.0,
                call_site: str = "ReadOnlyHTTPClient.request") -> Tuple[int, str]:
        # Barrier first — a blocked method raises before the transport is touched.
        self._barrier.guard(method, url, destination=self._destination,
                             call_site=call_site)
        start = self._barrier._clock()
        status, body = self._transport(method.upper(), url, headers or {}, timeout)
        # Record response metadata by amending the last ledger entry is avoided;
        # the guard already logged the allowed attempt. Return raw result.
        _ = start
        return status, body

    def get(self, url: str, **kw) -> Tuple[int, str]:
        return self.request("GET", url, call_site="ReadOnlyHTTPClient.get", **kw)

    def head(self, url: str, **kw) -> Tuple[int, str]:
        return self.request("HEAD", url, call_site="ReadOnlyHTTPClient.head", **kw)

    # Deliberately NO post/put/patch/delete convenience methods exist.


__all__ = [
    "ALLOWED_METHODS",
    "BLOCKED_METHODS",
    "ReadOnlyViolation",
    "RequestMethodLedger",
    "ReadOnlyTransportBarrier",
    "ReadOnlyHTTPClient",
]
