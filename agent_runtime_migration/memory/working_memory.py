"""Working memory — the current run's short-term context (bounded)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class WorkingMemory:
    max_items: int = 32
    _items: List[Dict[str, Any]] = field(default_factory=list)

    def put(self, key: str, value: Any) -> None:
        self._items.append({"key": key, "value": value})
        if len(self._items) > self.max_items:
            self._items = self._items[-self.max_items:]

    def items(self) -> List[Dict[str, Any]]:
        return list(self._items)
