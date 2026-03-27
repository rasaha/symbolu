"""
OfflineConsolidationCycle: Sleep analog for CG training.

Current training is continuous forward-pass and backprop with no offline phase.
Experiential learning requires mandatory consolidation cycles where:

    1. High-loss events are replayed (REM reprocessing analog)
    2. Contradictory updates from the same session are reconciled
    3. Low-salience memories are pruned, high-salience deepened
    4. Cross-layer coherence is enforced after training noise settles

This is NOT periodic checkpointing. It is active reorganization during
stillness — the system doing meaningful work when not processing new input.

Consolidation Phases:
    Phase 1 — Replay: High-salience queued items are re-presented
    Phase 2 — Reconciliation: Contradictory gradients are resolved
    Phase 3 — Pruning: Low-salience items are forgotten
    Phase 4 — Deepening: Surviving items are consolidated into identity

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import torch
import torch.nn as nn
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationConfig:
    """Configuration for offline consolidation cycles.

    Attributes:
        d_model: Model dimension
        num_regions: Number of gatable regions
        replay_fraction: Fraction of queued items to replay (highest salience)
        prune_threshold: Salience below which items are pruned
        deepen_threshold: Salience above which items are deepened
        coherence_weight: Weight for cross-layer coherence enforcement
        reconciliation_temperature: Temperature for contradiction resolution
        max_replay_steps: Maximum replay steps per consolidation cycle
        consolidation_interval: Steps between consolidation cycles
        min_queue_depth: Minimum queue depth to trigger consolidation
    """
    d_model: int = 128
    num_regions: int = 12
    replay_fraction: float = 0.5
    prune_threshold: float = 0.2
    deepen_threshold: float = 0.7
    coherence_weight: float = 0.3
    reconciliation_temperature: float = 1.0
    max_replay_steps: int = 32
    consolidation_interval: int = 100
    min_queue_depth: int = 8


class ReplayBuffer:
    """Prioritized replay buffer for high-salience experiences.

    Items are stored with their salience scores and replayed in
    priority order during consolidation — analogous to how the
    hippocampus replays significant experiences during sleep.
    """

    def __init__(self, capacity: int = 1024):
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
        """Sample top-k items by salience."""
        sorted_items = sorted(
            self.buffer, key=lambda x: x.get("salience", 0.0), reverse=True
        )
        return sorted_items[:k]

    def prune_below(self, threshold: float) -> int:
        """Remove items with salience below threshold. Returns count pruned."""
        before = len(self.buffer)
        self.buffer = [
            item for item in self.buffer
            if item.get("salience", 0.0) >= threshold
        ]
        return before - len(self.buffer)

    def __len__(self) -> int:
        return len(self.buffer)


class ContradictionDetector(nn.Module):
    """Detects contradictory gradient signals in the consolidation queue.

    Two updates are contradictory when they push the same region in
    opposing directions. This must be reconciled — the system cannot
    simultaneously move left and right.

    Detection: cosine similarity between queued error signals for the
    same region. Negative similarity = contradiction.
    """

    def __init__(self, d_model: int):
        super().__init__()
        self.reconciliation_proj = nn.Sequential(
            nn.Linear(d_model * 2, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )

    def detect_contradictions(
        self, errors: List[torch.Tensor], region_ids: List[torch.Tensor]
    ) -> List[Tuple[int, int, float]]:
        """Find contradictory error pairs for the same regions.

        Args:
            errors: List of [num_blocked, D] error tensors
            region_ids: List of [num_blocked] region indices

        Returns:
            List of (idx_i, idx_j, contradiction_score) tuples
        """
        contradictions = []
        for i in range(len(errors)):
            for j in range(i + 1, len(errors)):
                # Find overlapping regions
                regions_i = set(region_ids[i].tolist())
                regions_j = set(region_ids[j].tolist())
                overlap = regions_i & regions_j

                if overlap:
                    # Compute cosine similarity on overlapping regions
                    for r in overlap:
                        mask_i = (region_ids[i] == r).nonzero(as_tuple=True)[0]
                        mask_j = (region_ids[j] == r).nonzero(as_tuple=True)[0]
                        if len(mask_i) > 0 and len(mask_j) > 0:
                            e_i = errors[i][mask_i[0]]
                            e_j = errors[j][mask_j[0]]
                            cos_sim = torch.cosine_similarity(
                                e_i.unsqueeze(0), e_j.unsqueeze(0)
                            ).item()
                            if cos_sim < -0.3:  # Contradictory
                                contradictions.append((i, j, cos_sim))
        return contradictions

    def reconcile(
        self, error_a: torch.Tensor, error_b: torch.Tensor,
        stakes_a: float, stakes_b: float,
    ) -> torch.Tensor:
        """Reconcile two contradictory error signals.

        Resolution strategy: weight by stakes (higher stakes wins more),
        then project through reconciliation network to produce a
        unified update direction.

        Args:
            error_a: [D] first error signal
            error_b: [D] second error signal
            stakes_a: Stakes weight for first signal
            stakes_b: Stakes weight for second signal

        Returns:
            [D] reconciled error signal
        """
        total_stakes = stakes_a + stakes_b + 1e-8
        w_a = stakes_a / total_stakes
        w_b = stakes_b / total_stakes

        # Stakes-weighted blend
        blended = w_a * error_a + w_b * error_b

        # Project through reconciliation network
        combined = torch.cat([blended, error_a - error_b], dim=-1)
        reconciled = self.reconciliation_proj(combined.unsqueeze(0)).squeeze(0)

        return reconciled


class CrossLayerCoherenceEnforcer(nn.Module):
    """Enforces coherence across model layers after training noise.

    During active training, different layers may drift apart. During
    consolidation, we enforce that adjacent layers maintain coherent
    representations — analogous to how sleep restores neural coherence.

    L_coherence = Σ_l ||norm(h_l) - norm(h_{l+1})||^2
    """

    def __init__(self, d_model: int, num_layers: int):
        super().__init__()
        self.layer_norm_projs = nn.ModuleList([
            nn.LayerNorm(d_model) for _ in range(num_layers)
        ])

    def forward(
        self, layer_states: List[torch.Tensor]
    ) -> torch.Tensor:
        """Compute cross-layer coherence loss.

        Args:
            layer_states: List of [B, T, D] hidden states per layer

        Returns:
            Scalar coherence loss
        """
        if len(layer_states) < 2:
            return torch.tensor(0.0, device=layer_states[0].device)

        coherence_loss = torch.tensor(0.0, device=layer_states[0].device)
        for i in range(len(layer_states) - 1):
            norm_i = self.layer_norm_projs[min(i, len(self.layer_norm_projs) - 1)](
                layer_states[i]
            )
            norm_j = self.layer_norm_projs[min(i + 1, len(self.layer_norm_projs) - 1)](
                layer_states[i + 1]
            )
            coherence_loss = coherence_loss + (norm_i - norm_j).pow(2).mean()

        return coherence_loss / max(len(layer_states) - 1, 1)


class OfflineConsolidationCycle(nn.Module):
    """Complete offline consolidation cycle (sleep analog).

    Orchestrates the four phases of consolidation:
        1. Replay — Re-present high-salience queued items
        2. Reconcile — Resolve contradictory gradients
        3. Prune — Forget low-salience items
        4. Deepen — Consolidate surviving items

    Called periodically during training (not every step). The system
    must pause forward processing to consolidate — this mandatory
    stillness is structurally analogous to sleep.

    Args:
        config: ConsolidationConfig
    """

    def __init__(self, config: ConsolidationConfig):
        super().__init__()
        self.config = config

        self.replay_buffer = ReplayBuffer(capacity=config.max_replay_steps * 4)
        self.contradiction_detector = ContradictionDetector(config.d_model)
        self.coherence_enforcer = CrossLayerCoherenceEnforcer(
            config.d_model, config.num_regions
        )

        # Deepening projection: high-salience items get stronger encoding
        self.deepening_proj = nn.Sequential(
            nn.Linear(config.d_model, config.d_model),
            nn.GELU(),
            nn.Linear(config.d_model, config.d_model),
        )

        # Step counter
        self.register_buffer("step_counter", torch.tensor(0, dtype=torch.long))
        self.register_buffer("consolidation_count", torch.tensor(0, dtype=torch.long))

    def should_consolidate(self) -> bool:
        """Check if it's time for a consolidation cycle."""
        step = self.step_counter.item()
        queue_depth = len(self.replay_buffer)
        return (
            step > 0
            and step % self.config.consolidation_interval == 0
            and queue_depth >= self.config.min_queue_depth
        )

    def ingest_queue(self, queued_items: List[Dict]) -> int:
        """Ingest items from the vritti gate's consolidation queue.

        Args:
            queued_items: Items that failed to pass the resistance gate

        Returns:
            Number of items ingested
        """
        for item in queued_items:
            salience = item.get("stakes", torch.tensor(0.0)).mean().item()
            self.replay_buffer.add({
                "error": item["error"],
                "regions": item["regions"],
                "stakes": item.get("stakes", torch.tensor(0.0)),
                "resistance": item.get("resistance", torch.tensor(0.5)),
                "salience": salience,
            })
        return len(queued_items)

    def consolidate(
        self,
        layer_states: Optional[List[torch.Tensor]] = None,
    ) -> Dict[str, object]:
        """Run a full consolidation cycle.

        Args:
            layer_states: Optional list of current layer hidden states
                          for cross-layer coherence enforcement

        Returns:
            Dict with consolidation metrics:
                'replayed': Number of items replayed
                'contradictions_found': Number of contradictions detected
                'pruned': Number of low-salience items pruned
                'deepened': Number of high-salience items deepened
                'coherence_loss': Cross-layer coherence loss (if layer_states provided)
                'consolidated_errors': List of reconciled error signals for replay
        """
        self.consolidation_count += 1
        metrics: Dict[str, object] = {}

        # Phase 1: Replay — select highest-salience items
        k = max(1, int(len(self.replay_buffer) * self.config.replay_fraction))
        replay_items = self.replay_buffer.sample_top_k(k)
        metrics["replayed"] = len(replay_items)

        # Phase 2: Reconciliation — detect and resolve contradictions
        if len(replay_items) >= 2:
            errors = [item["error"] for item in replay_items]
            region_ids = [item["regions"] for item in replay_items]
            contradictions = self.contradiction_detector.detect_contradictions(
                errors, region_ids
            )
            metrics["contradictions_found"] = len(contradictions)

            # Reconcile detected contradictions
            reconciled_errors = []
            reconciled_pairs = set()
            for idx_i, idx_j, score in contradictions:
                if idx_i not in reconciled_pairs and idx_j not in reconciled_pairs:
                    stakes_i = replay_items[idx_i].get("stakes", torch.tensor(0.5)).mean().item()
                    stakes_j = replay_items[idx_j].get("stakes", torch.tensor(0.5)).mean().item()
                    reconciled = self.contradiction_detector.reconcile(
                        replay_items[idx_i]["error"].mean(dim=0),
                        replay_items[idx_j]["error"].mean(dim=0),
                        stakes_i, stakes_j,
                    )
                    reconciled_errors.append(reconciled)
                    reconciled_pairs.add(idx_i)
                    reconciled_pairs.add(idx_j)
            metrics["consolidated_errors"] = reconciled_errors
        else:
            metrics["contradictions_found"] = 0
            metrics["consolidated_errors"] = []

        # Phase 3: Pruning — forget low-salience items
        pruned = self.replay_buffer.prune_below(self.config.prune_threshold)
        metrics["pruned"] = pruned

        # Phase 4: Deepening — strengthen high-salience items
        deepened = 0
        for item in self.replay_buffer.buffer:
            if item.get("salience", 0.0) >= self.config.deepen_threshold:
                # Apply deepening projection to increase salience further
                with torch.no_grad():
                    device = next(self.deepening_proj.parameters()).device
                    error_on_device = item["error"].to(device)
                    deepened_error = self.deepening_proj(error_on_device)
                    item["error"] = deepened_error.cpu()
                    item["salience"] = min(item["salience"] * 1.1, 1.0)
                deepened += 1
        metrics["deepened"] = deepened

        # Phase 5: Cross-layer coherence (if states provided)
        if layer_states is not None and len(layer_states) >= 2:
            coherence_loss = self.coherence_enforcer(layer_states)
            metrics["coherence_loss"] = coherence_loss
        else:
            metrics["coherence_loss"] = torch.tensor(0.0)

        logger.info(
            f"Consolidation cycle {self.consolidation_count.item()}: "
            f"replayed={metrics['replayed']}, "
            f"contradictions={metrics['contradictions_found']}, "
            f"pruned={metrics['pruned']}, deepened={metrics['deepened']}"
        )

        return metrics

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
