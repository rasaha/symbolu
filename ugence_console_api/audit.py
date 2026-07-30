"""Audit & Reconstruction — in-memory, correlation-id keyed decision trail.

Every governed-loop run appends its ordered stage records here, keyed by
``correlation_id``, so the console can reconstruct the complete decision chain —
"what did the AI assert, was it supported, who authorized the action, and was it
safe?" — on demand.

This in-memory store is deliberately a prototype seam. The productization gap
(roadmap §2/§3) is a durable, tamper-evident, hash-chained record with real key
custody; the reconstruction API shape here is designed to survive that swap.
"""

from __future__ import annotations

import threading
from typing import Dict, List

from .models import AuditChain, AuditEntry


class AuditStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chains: Dict[str, AuditChain] = {}

    def record(self, chain: AuditChain) -> None:
        with self._lock:
            self._chains[chain.correlation_id] = chain

    def get(self, correlation_id: str) -> AuditChain | None:
        with self._lock:
            return self._chains.get(correlation_id)

    def list_ids(self) -> List[str]:
        with self._lock:
            return list(self._chains.keys())


__all__ = ["AuditStore", "AuditChain", "AuditEntry"]
