"""Idempotency / replay protection.

The in-memory reference store is NOT sufficient for multi-process production
deployment; the interface allows a durable implementation later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class IdempotencyRecord:
    idempotency_key: str
    authorization_id: str
    target: str
    action: str
    request_digest: str
    completed: bool
    receipt_hash: str
    first_seen: float


@runtime_checkable
class IdempotencyStore(Protocol):
    def get(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        ...

    def put(self, record: IdempotencyRecord) -> None:
        ...


class InMemoryIdempotencyStore:
    """Process-local idempotency store (reference / testing only)."""

    def __init__(self):
        self._store: Dict[str, IdempotencyRecord] = {}

    def get(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        return self._store.get(idempotency_key)

    def put(self, record: IdempotencyRecord) -> None:
        self._store[record.idempotency_key] = record

    def reset(self) -> None:
        self._store.clear()


__all__ = ["IdempotencyRecord", "IdempotencyStore", "InMemoryIdempotencyStore"]
