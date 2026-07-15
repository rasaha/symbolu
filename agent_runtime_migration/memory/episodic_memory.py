"""Episodic memory — append-only record of observations (deterministic)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
from ..contracts.observation import Observation


@dataclass
class EpisodicMemory:
    max_items: int = 1000
    _log: List[Observation] = field(default_factory=list)

    def record(self, observation: Observation) -> None:
        self._log.append(observation)
        if len(self._log) > self.max_items:
            self._log = self._log[-self.max_items:]

    def recent(self, n: int = 5) -> List[Observation]:
        return list(self._log[-n:])

    def all(self) -> List[Observation]:
        return list(self._log)

    def snapshot(self) -> Dict[str, Any]:
        return {"count": len(self._log),
                "outcomes": [o.outcome for o in self._log]}
