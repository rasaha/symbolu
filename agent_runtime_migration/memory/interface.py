"""Memory interface (protocol). No governance state."""
from __future__ import annotations
from typing import Any, Dict, List, Protocol
from ..contracts.observation import Observation


class Memory(Protocol):
    def record(self, observation: Observation) -> None: ...
    def recent(self, n: int = 5) -> List[Observation]: ...
    def snapshot(self) -> Dict[str, Any]: ...
