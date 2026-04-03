"""
OfflineConsolidationCycle: Sleep analog for CG training.

Reduced to two essential operations (no overloaded reconciliation):

    1. Replay — Re-present high-salience deferred samples
    2. Prune — Drop stale, low-salience samples

Plus: trigger identity consolidation (slow loop).

This is NOT a second training system. It is a simple periodic buffer
management mechanism that:
    - Feeds high-salience deferred samples back into the training stream
    - Removes stale/low-value samples to prevent memory bloat
    - Triggers identity EMA integration on the slow timescale

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationConfig:
    """Configuration for offline consolidation cycles.

    Attributes:
        d_model: Model dimension
        num_regions: Number of gatable regions
        replay_fraction: Fraction of buffer to replay (highest salience)
        prune_threshold: Salience below which items are pruned
        consolidation_interval: Steps between consolidation (medium loop)
        identity_interval: Steps between identity consolidation (slow loop)
        min_buffer_depth: Minimum buffer depth to trigger consolidation
        buffer_capacity: Maximum buffer size
        staleness_limit: Max steps an item can stay in buffer before pruning
    """
    d_model: int = 128
    num_regions: int = 12
    replay_fraction: float = 0.5
    prune_threshold: float = 0.2
    consolidation_interval: int = 100
    identity_interval: int = 1000
    min_buffer_depth: int = 8
    buffer_capacity: int = 512
    staleness_limit: int = 500


class ReplayBuffer:
    """Prioritized replay buffer for high-salience deferred samples.

    Items are stored with their salience scores and replayed in
    priority order during consolidation — analogous to how the
    hippocampus replays significant experiences during sleep.
    """

    def __init__(self, capacity: int = 512):
        self.capacity = capacity
        self.buffer: List[Dict] = []

    def add(self, item: Dict) -> None:
        """Add an item to the replay buffer."""
        self.buffer.append(item)
        if len(self.buffer) > self.capacity:
            # Remove lowest-salience item
            self.buffer.sort(key=lambda x: x.get("salience", 0.0))
            self.buffer.pop(0)

    def add_batch(self, items: List[Dict]) -> None:
        """Add a batch of items to the buffer."""
        for item in items:
            self.add(item)

    def sample_top_k(self, k: int) -> List[Dict]:
        """Sample k items with probability proportional to salience.

        Uses softmax over salience scores for stochastic priority sampling,
        ensuring diversity while still favoring high-salience items.
        Falls back to deterministic top-k if all saliences are equal.
        """
        if len(self.buffer) <= k:
            return sorted(
                self.buffer, key=lambda x: x.get("salience", 0.0), reverse=True
            )

        import random
        saliences = [item.get("salience", 0.0) for item in self.buffer]
        min_s = min(saliences)
        max_s = max(saliences)

        if max_s - min_s < 1e-8:
            # Uniform — just shuffle and take k
            indices = list(range(len(self.buffer)))
            random.shuffle(indices)
            return [self.buffer[i] for i in indices[:k]]

        # Probability proportional to salience (shifted to be non-negative)
        weights = [s - min_s + 1e-6 for s in saliences]
        selected = random.choices(range(len(self.buffer)), weights=weights, k=k)
        # Deduplicate while preserving order
        seen = set()
        unique_indices = []
        for idx in selected:
            if idx not in seen:
                seen.add(idx)
                unique_indices.append(idx)
        # If dedup reduced count, fill from remaining highest-salience
        if len(unique_indices) < k:
            remaining = sorted(
                set(range(len(self.buffer))) - seen,
                key=lambda i: saliences[i], reverse=True,
            )
            unique_indices.extend(remaining[:k - len(unique_indices)])

        result = [self.buffer[i] for i in unique_indices]
        return sorted(result, key=lambda x: x.get("salience", 0.0), reverse=True)

    def prune_below(self, threshold: float) -> int:
        """Remove items with salience below threshold. Returns count pruned."""
        before = len(self.buffer)
        self.buffer = [
            item for item in self.buffer
            if item.get("salience", 0.0) >= threshold
        ]
        return before - len(self.buffer)

    def prune_stale(self, current_step: int, staleness_limit: int) -> int:
        """Remove items older than staleness_limit steps."""
        before = len(self.buffer)
        self.buffer = [
            item for item in self.buffer
            if current_step - item.get("step", 0) < staleness_limit
        ]
        return before - len(self.buffer)

    def __len__(self) -> int:
        return len(self.buffer)


class OfflineConsolidationCycle(nn.Module):
    """Simplified offline consolidation: replay + prune.

    Two operations only:
        1. Replay — Select highest-salience deferred samples for re-training
        2. Prune — Drop low-salience and stale items

    Plus: triggers identity consolidation on the slow loop.

    Time scales:
        - Medium loop (consolidation_interval): replay + prune
        - Slow loop (identity_interval): identity EMA integration

    Args:
        config: ConsolidationConfig
    """

    def __init__(self, config: ConsolidationConfig):
        super().__init__()
        self.config = config

        self.replay_buffer = ReplayBuffer(capacity=config.buffer_capacity)

        # Step counter
        self.register_buffer("step_counter", torch.tensor(0, dtype=torch.long))
        self.register_buffer("consolidation_count", torch.tensor(0, dtype=torch.long))

    def should_consolidate(self) -> bool:
        """Check if it's time for a medium-loop consolidation."""
        step = self.step_counter.item()
        return (
            step > 0
            and step % self.config.consolidation_interval == 0
            and len(self.replay_buffer) >= self.config.min_buffer_depth
        )

    def should_consolidate_identity(self) -> bool:
        """Check if it's time for a slow-loop identity consolidation."""
        step = self.step_counter.item()
        return step > 0 and step % self.config.identity_interval == 0

    def ingest(self, deferred_items: List[Dict]) -> int:
        """Ingest deferred items from the resistance gate.

        Args:
            deferred_items: Items from VrittiResistanceGate.drain_deferred_buffer()

        Returns:
            Number of items ingested
        """
        current_step = self.step_counter.item()
        for item in deferred_items:
            item["step"] = current_step
            self.replay_buffer.add(item)
        return len(deferred_items)

    def consolidate(self) -> Dict[str, object]:
        """Run medium-loop consolidation: replay + prune.

        Returns:
            Dict with:
                'replay_items': List of high-salience items for re-training
                'replayed': Count of items selected for replay
                'pruned_low_salience': Count pruned for low salience
                'pruned_stale': Count pruned for staleness
                'buffer_depth_after': Buffer size after pruning
        """
        self.consolidation_count += 1
        current_step = self.step_counter.item()

        # Phase 1: Select top items for replay
        k = max(1, int(len(self.replay_buffer) * self.config.replay_fraction))
        replay_items = self.replay_buffer.sample_top_k(k)

        # Phase 2: Prune low-salience items
        pruned_low = self.replay_buffer.prune_below(self.config.prune_threshold)

        # Phase 3: Prune stale items
        pruned_stale = self.replay_buffer.prune_stale(
            current_step, self.config.staleness_limit
        )

        logger.info(
            f"Consolidation #{self.consolidation_count.item()}: "
            f"replay={len(replay_items)}, "
            f"pruned_low={pruned_low}, pruned_stale={pruned_stale}, "
            f"buffer={len(self.replay_buffer)}"
        )

        return {
            "replay_items": replay_items,
            "replayed": len(replay_items),
            "pruned_low_salience": pruned_low,
            "pruned_stale": pruned_stale,
            "buffer_depth_after": len(self.replay_buffer),
        }

    def step(self) -> None:
        """Increment step counter."""
        self.step_counter += 1

    def get_state(self) -> Dict[str, object]:
        """Get consolidation state for diagnostics."""
        return {
            "step": self.step_counter.item(),
            "consolidation_count": self.consolidation_count.item(),
            "buffer_depth": len(self.replay_buffer),
            "buffer_mean_salience": (
                sum(item.get("salience", 0) for item in self.replay_buffer.buffer)
                / max(len(self.replay_buffer), 1)
            ),
        }
