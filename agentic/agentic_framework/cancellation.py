"""
Cancellation Token — Lightweight cooperative cancellation (R2)

A minimal cancellation primitive for in-flight agent runs.
The token is passed through the orchestration flow; each pipeline
stage checks ``is_cancelled`` at its boundary before proceeding.

Cancellation is *cooperative* — it does not forcibly interrupt a
running LLM call or an already-dispatched MCP tool handler.  Those
complete naturally; cancellation prevents the *next* pipeline stage
from starting.

Usage:
    token = CancellationToken()

    # In another thread / callback:
    token.cancel(reason="user requested stop")

    # In the pipeline:
    if token.is_cancelled:
        ...  # emit terminal event and stop
"""

from __future__ import annotations

import threading
from typing import Optional


class CancellationToken:
    """Lightweight cooperative cancellation signal.

    Thread-safe: ``cancel()`` can be called from any thread.
    """

    __slots__ = ("_cancelled", "_reason", "_lock")

    def __init__(self) -> None:
        self._cancelled = False
        self._reason: Optional[str] = None
        self._lock = threading.Lock()

    def cancel(self, reason: Optional[str] = None) -> None:
        """Request cancellation.  Idempotent — subsequent calls are no-ops."""
        with self._lock:
            if not self._cancelled:
                self._cancelled = True
                self._reason = reason

    @property
    def is_cancelled(self) -> bool:
        """Check whether cancellation has been requested."""
        return self._cancelled

    @property
    def reason(self) -> Optional[str]:
        """Optional human-readable reason supplied to ``cancel()``."""
        return self._reason

    def __repr__(self) -> str:
        state = "cancelled" if self._cancelled else "active"
        return f"CancellationToken({state})"
