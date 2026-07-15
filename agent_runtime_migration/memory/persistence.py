"""Persistence interface for memory. In-memory default; DB-backed impls plug in here.

No governance state is persisted; this is runtime memory only."""
from __future__ import annotations
from typing import Any, Dict, Protocol
from .episodic_memory import EpisodicMemory


class MemoryPersistence(Protocol):
    def save(self, session_id: str, memory: EpisodicMemory) -> None: ...
    def load(self, session_id: str) -> EpisodicMemory: ...


class InMemoryPersistence:
    def __init__(self) -> None:
        self._store: Dict[str, EpisodicMemory] = {}

    def save(self, session_id: str, memory: EpisodicMemory) -> None:
        self._store[session_id] = memory

    def load(self, session_id: str) -> EpisodicMemory:
        return self._store.get(session_id, EpisodicMemory())
