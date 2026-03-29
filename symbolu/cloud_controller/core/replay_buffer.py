"""Replay Buffer — priority-weighted incident memory.

Ported from ReplayBuffer (minimal_controller.py:443-487).
Direct port — original was already plain Python.

Key properties:
- Capacity-bounded (default 256)
- TTL-bounded (default 200 cycles — stale entries expire)
- Priority eviction: when full, remove lowest priority (NOT FIFO)
- Priority sampling: probability-proportional without replacement
"""

import random
from typing import Dict, List, Optional


class ReplayBuffer:
    """Stores high-value decision episodes for learning.

    Store trigger: high misalignment + low plasticity
    (system was stressed AND couldn't adapt).
    """

    def __init__(self, capacity: int = 256, ttl: int = 200):
        self.capacity = capacity
        self.ttl = ttl
        self.buffer: List[Dict] = []

    def store(self, item: Dict, step: int) -> None:
        """Store a decision episode.

        Matches minimal_controller.py lines 451-457.

        Args:
            item: Episode dict with at minimum {"priority": float, ...}.
                  Higher priority = more important incident.
            step: Current cycle number (for TTL expiry).
        """
        item["step"] = step
        self.buffer.append(item)
        # When over capacity, evict lowest priority
        if len(self.buffer) > self.capacity:
            self.buffer.sort(key=lambda x: x.get("priority", 0))
            self.buffer.pop(0)

    def sample(self, k: int) -> List[Dict]:
        """Probability-proportional sampling without replacement.

        Matches minimal_controller.py lines 459-475.

        Args:
            k: Number of entries to sample.

        Returns:
            List of sampled episodes (up to k, may be fewer if buffer is small).
        """
        if not self.buffer:
            return []
        k = min(k, len(self.buffer))
        priorities = [item.get("priority", 0.01) for item in self.buffer]
        indices = list(range(len(self.buffer)))
        result = []
        for _ in range(k):
            if not indices:
                break
            weights = [priorities[i] for i in indices]
            selected = random.choices(indices, weights=weights, k=1)[0]
            result.append(self.buffer[selected])
            indices.remove(selected)
        return result

    def prune(self, current_step: int) -> int:
        """Remove stale entries past TTL.

        Matches minimal_controller.py lines 477-484.

        Returns:
            Number of entries removed.
        """
        before = len(self.buffer)
        self.buffer = [
            item for item in self.buffer
            if current_step - item.get("step", 0) < self.ttl
        ]
        return before - len(self.buffer)

    def __len__(self) -> int:
        return len(self.buffer)
