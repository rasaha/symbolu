"""
vLLM integration adapter for PCAM (Phase 2).

A thin, duck-typed wrapper around ``KVCachePolicy`` that exposes the
shape vLLM's block manager and Evictor ABC expect, without taking a
runtime dependency on the ``vllm`` package. The adapter imports
nothing from vllm; it can be instantiated, exercised, and tested in
environments where vllm is not installed.

Why duck-typed instead of subclassing ``vllm.core.evictor.Evictor``
-------------------------------------------------------------------
PCAM is meant to ship as a small, dependency-free Python package.
Importing vllm at module load time would force every PCAM consumer to
install vllm even if they only want the policy library. Duck-typing
the Evictor surface keeps the adapter usable in test, simulation, and
non-serving contexts, while still letting a real vLLM serving stack
plug it in via a ~5-line bridge:

    from vllm.core.evictor import Evictor
    from simulator.pcam.integrations.vllm import PCAMEvictor

    class VLLMPCAMEvictor(Evictor):
        def __init__(self, policy):
            self._adapter = PCAMEvictor(policy)
        def __contains__(self, block_id):
            return block_id in self._adapter
        def evict(self):
            ids = self._adapter.select_victims(1)
            return ids[0] if ids else None
        def add(self, block):
            self._adapter.admit_block(
                block.block_id, block.seq_id,
                block.positions, vllm_block=block,
            )
        # ... and so on for the rest of the Evictor ABC

This bridge belongs in the consumer's code, not in the PCAM package,
because PCAM does not depend on vLLM.

Architectural rules
-------------------
- All scoring / sketch updates / sink pinning / victim selection
  delegate to ``KVCachePolicy``. There is no second policy
  implementation in this module.
- No bridge class between CTM+ and PCAM.
- No new package-root exports — this adapter is only reachable via
  ``simulator.pcam.integrations.vllm``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..config import PCAMConfig
from ..kv_policy import InferencePhase, KVCachePolicy, TierHint


__all__ = ["PCAMEvictor", "make_pcam_evictor"]


class PCAMEvictor:
    """
    vLLM-compatible KV-cache eviction adapter.

    Wraps a ``KVCachePolicy`` and exposes a duck-typed surface that
    can drive (or be driven by) a vLLM-style block manager. Optionally
    tracks one vLLM block object per block_id so eviction calls can
    return either bare integer IDs or the underlying vLLM block
    objects, depending on what the consumer needs.
    """

    def __init__(self, policy: KVCachePolicy) -> None:
        self._policy = policy
        # Optional vLLM block-object map. Block IDs that have no
        # associated vLLM block object are still tracked by the
        # policy; tier hints and bare-int victim selection work
        # regardless.
        self._blocks: Dict[int, Any] = {}

    # ---- Construction helpers ---------------------------------------------

    @classmethod
    def from_config(cls, config: PCAMConfig) -> "PCAMEvictor":
        """Build a fresh ``KVCachePolicy`` from a ``PCAMConfig`` and wrap it."""
        return cls(config.build_policy())

    @property
    def policy(self) -> KVCachePolicy:
        """
        The underlying ``KVCachePolicy``. Exposed so callers can read
        ``get_stats()`` directly or pass it to ``PolicyMetrics``.
        """
        return self._policy

    # ---- Sequence lifecycle -----------------------------------------------

    def register_sequence(
        self,
        seq_id: int,
        phase: Optional[InferencePhase] = None,
    ) -> None:
        """Register a sequence with the policy. ``phase`` is optional —
        if provided, it is set in the same call."""
        self._policy.register_sequence(seq_id)
        if phase is not None:
            self._policy.set_phase(seq_id, phase)

    def set_phase(self, seq_id: int, phase: InferencePhase) -> None:
        self._policy.set_phase(seq_id, phase)

    def complete_sequence(self, seq_id: int) -> List[int]:
        """Complete a sequence and free its blocks. Returns the list of
        freed block_ids; the adapter also drops any tracked vLLM block
        objects for those IDs."""
        freed = self._policy.complete_sequence(seq_id)
        for bid in freed:
            self._blocks.pop(bid, None)
        return freed

    # ---- Block admission and attention ------------------------------------

    def admit_block(
        self,
        block_id: int,
        sequence_id: int,
        positions: List[int],
        vllm_block: Optional[Any] = None,
    ) -> None:
        """
        Admit a block to the policy. If ``vllm_block`` is provided, the
        adapter remembers it so a later ``select_victims_as_blocks`` call
        can return it as a vLLM block object instead of a bare integer.
        """
        self._policy.ensure_block(block_id, sequence_id, positions)
        if vllm_block is not None:
            self._blocks[block_id] = vllm_block

    def on_attention(
        self,
        block_id: int,
        attention_sum: float,
        sequence_id: int,
    ) -> None:
        """Record an attention event against a block."""
        self._policy.on_block_attention(block_id, attention_sum, sequence_id)

    # ---- Eviction ---------------------------------------------------------

    def select_victims(self, count: int) -> List[int]:
        """Bare-int victim selection. Returns up to ``count`` block IDs."""
        return self._policy.select_victims(count)

    def select_victims_as_blocks(self, count: int) -> List[Any]:
        """
        vLLM-shaped victim selection. Returns the tracked vLLM block
        objects for the chosen victim IDs. Victims that have no
        associated vLLM block object are silently skipped — the policy
        still considers them evicted at the bare-int level.
        """
        ids = self._policy.select_victims(count)
        return [self._blocks[bid] for bid in ids if bid in self._blocks]

    def evict_block(self, block_id: int) -> Optional[Any]:
        """
        Mark a single block as evicted. Returns the associated vLLM
        block object if one was tracked, else ``None``. Useful for
        explicit preemption paths in vLLM where the scheduler chooses
        the victim independently of the policy.
        """
        self._policy.evict_block(block_id)
        return self._blocks.pop(block_id, None)

    # ---- Tier placement hints ---------------------------------------------

    def classify_tier(self, block_id: int) -> TierHint:
        return self._policy.classify_tier(block_id)

    def tier_hints(self, block_ids: List[int]) -> Dict[int, TierHint]:
        return self._policy.tier_hints(block_ids)

    # ---- vLLM Evictor duck-type surface -----------------------------------

    def __contains__(self, block_id: int) -> bool:
        """Mirror of ``vllm.core.evictor.Evictor.__contains__``."""
        return block_id in self._policy.gpu_blocks

    def __len__(self) -> int:
        return len(self._policy.gpu_blocks)

    @property
    def num_blocks(self) -> int:
        """Mirror of ``vllm.core.evictor.Evictor.num_blocks``."""
        return len(self._policy.gpu_blocks)


def make_pcam_evictor(config: PCAMConfig) -> PCAMEvictor:
    """
    Convenience factory: build a ``PCAMEvictor`` from a ``PCAMConfig``.
    Equivalent to ``PCAMEvictor.from_config(config)``.
    """
    return PCAMEvictor.from_config(config)
