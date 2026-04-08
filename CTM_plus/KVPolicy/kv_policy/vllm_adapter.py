"""
vLLM integration adapter for KVCachePolicy.

Provides a thin layer that connects KVCachePolicy to a vLLM-style paged
KV cache lifecycle: block allocation, attention updates, eviction decisions,
and sequence management.

This module does NOT import vLLM. It defines the integration surface so that
a vLLM-based serving engine can call into CTM+ eviction logic.

Usage:
    from CTM_plus.KVPolicy.kv_policy.vllm_adapter import CTMBlockSpaceManager, CTMvLLMConfig

    config = CTMvLLMConfig.for_llm_inference()
    manager = CTMBlockSpaceManager(
        block_size=16,
        num_gpu_blocks=2000,
        num_cpu_blocks=20000,
        watermark=0.1,
        ctm_config=config,
    )

    # Sequence lifecycle
    manager.register_sequence(seq_id=1)
    manager.allocate_block(seq_id=1, page_id=100, positions=[0, 1, ..., 15])

    # Attention (called once per block per decode step)
    manager.on_attention(page_id=100, attention_sum=0.05, seq_id=1, seq_len=512)

    # Eviction under memory pressure
    victim_page = manager.evict()

    # Phase transition
    manager.on_decode_start(seq_id=1)

    # Sequence done
    freed_pages = manager.complete_sequence(seq_id=1)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .attention_evictor import KVCachePolicy, InferencePhase


logger = logging.getLogger("ctm_plus.vllm_adapter")


# =============================================================================
# Instrumentation
# =============================================================================

class EventLogger:
    """
    Lightweight structured event logger for KV cache instrumentation.

    Disabled by default. When enabled, emits structured dicts to either
    a Python logger or a user-supplied callback. Samples periodic events
    (attention snapshots, pressure) at configurable intervals.

    Usage:
        mgr = CTMBlockSpaceManager(..., enable_logging=True)
        mgr.event_logger.snapshot_interval = 20  # every 20 steps
        mgr.event_logger.callback = my_handler   # optional
    """

    __slots__ = (
        "enabled", "snapshot_interval", "top_k", "callback",
        "_event_counts", "_step",
    )

    def __init__(self, enabled: bool = False, snapshot_interval: int = 10,
                 top_k: int = 5):
        self.enabled = enabled
        self.snapshot_interval = snapshot_interval
        self.top_k = top_k
        self.callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self._event_counts: Dict[str, int] = {}
        self._step = 0

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit a structured event."""
        if not self.enabled:
            return
        self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1
        if self.callback is not None:
            self.callback(event_type, data)
        else:
            logger.info("%s %s", event_type, data)

    def tick(self) -> int:
        """Advance step counter. Returns current step."""
        self._step += 1
        return self._step

    def should_snapshot(self) -> bool:
        """True if it's time for a periodic snapshot."""
        return self.enabled and self._step % self.snapshot_interval == 0

    def get_event_counts(self) -> Dict[str, int]:
        return dict(self._event_counts)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class CTMvLLMConfig:
    """Configuration for CTM+ vLLM integration."""

    sink_tokens: int = 4
    recent_window: int = 256
    entity_attention_threshold: float = 0.02
    attention_ema_alpha: float = 0.1
    victim_sample_size: int = 48
    promotion_threshold: float = 0.3

    @classmethod
    def for_llm_inference(cls) -> "CTMvLLMConfig":
        """General-purpose inference."""
        return cls()

    @classmethod
    def for_streaming(cls) -> "CTMvLLMConfig":
        """Streaming / low-latency chat."""
        return cls(recent_window=256, victim_sample_size=32)

    @classmethod
    def for_batch_inference(cls) -> "CTMvLLMConfig":
        """High-throughput batch inference."""
        return cls(recent_window=512, victim_sample_size=64)


# =============================================================================
# Block Space Manager
# =============================================================================

class CTMBlockSpaceManager:
    """
    vLLM-style block space manager backed by KVCachePolicy.

    Maps vLLM page IDs to internal block IDs and delegates all eviction
    scoring to KVCachePolicy. Does not manage physical memory — only
    tracks block metadata and makes eviction decisions.

    Integration points (call these from your serving engine):
        allocate_block   — when a KV page is allocated
        on_attention     — after each attention step (block-level sum)
        evict            — when memory pressure requires freeing a block
        register_sequence / on_decode_start / complete_sequence — lifecycle
    """

    def __init__(
        self,
        block_size: int = 16,
        num_gpu_blocks: int = 1000,
        num_cpu_blocks: int = 10000,
        watermark: float = 0.1,
        ctm_config: Optional[CTMvLLMConfig] = None,
        enable_logging: bool = False,
    ):
        self.block_size = block_size
        self.num_gpu_blocks = num_gpu_blocks
        self.num_cpu_blocks = num_cpu_blocks
        self.watermark = watermark
        self._watermark_blocks = int(num_gpu_blocks * watermark)

        cfg = ctm_config or CTMvLLMConfig()
        self._policy = KVCachePolicy(
            max_blocks=num_gpu_blocks,
            block_size=block_size,
            sink_tokens=cfg.sink_tokens,
            recent_window=cfg.recent_window,
            entity_attention_threshold=cfg.entity_attention_threshold,
            attention_ema_alpha=cfg.attention_ema_alpha,
        )

        # page_id ↔ block_id mapping
        # In vLLM, pages are physical token blocks identified by integer IDs.
        # KVCachePolicy uses its own block_id space. We map between them.
        self._page_to_block: Dict[int, int] = {}
        self._block_to_page: Dict[int, int] = {}
        self._next_block_id: int = 0

        # Track allocated GPU pages
        self._gpu_pages: Set[int] = set()
        self._pinned_pages: Set[int] = set()

        # Track which pages belong to which sequence
        self._seq_pages: Dict[int, Set[int]] = {}

        # Instrumentation
        self.event_logger = EventLogger(enabled=enable_logging)
        self._recompute_total: int = 0
        self._recompute_important: int = 0
        self._recompute_filler: int = 0
        self._evicted_blocks: Dict[int, Dict[str, Any]] = {}  # block_id → metadata at eviction time

    # ---- Instrumentation helpers ----

    def _block_importance(self, block_id: int) -> str:
        """Classify a block as sink/entity/filler from policy state."""
        block = self._policy.blocks.get(block_id)
        if block is None:
            return "unknown"
        if block.is_sink:
            return "sink"
        if block.attention_ema > self._policy._adaptive_threshold:
            return "entity"
        return "filler"

    def _block_meta(self, block_id: int) -> Dict[str, Any]:
        """Snapshot of block metadata for logging."""
        block = self._policy.blocks.get(block_id)
        if block is None:
            return {"block_id": block_id}
        return {
            "block_id": block_id,
            "seq_id": block.sequence_id,
            "importance": self._block_importance(block_id),
            "attention_ema": round(block.attention_ema, 6),
            "access_count": block.access_count,
            "step": self._policy._step,
        }

    # ---- Task 7: Block Mapping ----

    def _map_page(self, page_id: int) -> int:
        """Get or create block_id for a page_id."""
        if page_id in self._page_to_block:
            return self._page_to_block[page_id]
        block_id = self._next_block_id
        self._next_block_id += 1
        self._page_to_block[page_id] = block_id
        self._block_to_page[block_id] = page_id
        return block_id

    def _unmap_page(self, page_id: int) -> Optional[int]:
        """Remove mapping for a page_id. Returns block_id or None."""
        block_id = self._page_to_block.pop(page_id, None)
        if block_id is not None:
            self._block_to_page.pop(block_id, None)
        return block_id

    # ---- Task 2: Block Allocation ----

    def allocate_block(
        self,
        seq_id: int,
        page_id: int,
        positions: List[int],
    ) -> int:
        """
        Register a newly allocated KV page.

        Called when the serving engine allocates a physical token block.
        Forwards to KVCachePolicy.ensure_block().

        Args:
            seq_id: Sequence that owns this block.
            page_id: Physical page ID from the block allocator.
            positions: Token positions stored in this block.

        Returns:
            Internal block_id.
        """
        block_id = self._map_page(page_id)
        self._policy.ensure_block(block_id, seq_id, positions)
        self._gpu_pages.add(page_id)

        if seq_id not in self._seq_pages:
            self._seq_pages[seq_id] = set()
        self._seq_pages[seq_id].add(page_id)

        return block_id

    # ---- Task 3: Attention Hook ----

    def on_attention(
        self,
        page_id: int,
        attention_sum: float,
        seq_id: int,
        seq_len: int,
    ) -> None:
        """
        Record block-level attention from the model.

        Called once per block per decode step with the sum of attention
        weights for all tokens in the block. No per-token calls.

        If the page was previously evicted, records a recompute event.

        Args:
            page_id: Physical page ID.
            attention_sum: Sum of attention weights across tokens in block.
            seq_id: Owning sequence.
            seq_len: Current sequence length.
        """
        block_id = self._page_to_block.get(page_id)
        if block_id is None:
            # Recompute: page was accessed but not present (evicted earlier)
            evict_meta = self._evicted_blocks.pop(page_id, None)
            if evict_meta is not None:
                importance = evict_meta.get("importance", "filler")
                self._recompute_total += 1
                if importance in ("sink", "entity"):
                    self._recompute_important += 1
                else:
                    self._recompute_filler += 1
                self.event_logger.emit("recompute", {
                    "page_id": page_id,
                    "seq_id": seq_id,
                    "importance": importance,
                    "recompute_cost": self.block_size,
                    "recompute_total": self._recompute_total,
                })
            return
        self._policy.on_block_attention(
            block_id=block_id,
            attention_sum=attention_sum,
            sequence_id=seq_id,
            seq_len=seq_len,
        )

        # Sampled attention snapshot + cache pressure
        self.event_logger.tick()
        if self.event_logger.should_snapshot():
            self._emit_attention_snapshot()
            self._emit_pressure()

    def on_attention_batch(
        self,
        block_attention: Dict[int, float],
        seq_id: int,
        seq_len: int,
    ) -> None:
        """
        Record attention for multiple blocks in one call.

        Args:
            block_attention: {page_id: attention_sum} for each block.
            seq_id: Owning sequence.
            seq_len: Current sequence length.
        """
        for page_id, attn_sum in block_attention.items():
            block_id = self._page_to_block.get(page_id)
            if block_id is not None:
                self._policy.on_block_attention(
                    block_id=block_id,
                    attention_sum=attn_sum,
                    sequence_id=seq_id,
                    seq_len=seq_len,
                )

    # ---- Task 4 & 5: Eviction ----

    def evict(self) -> Optional[int]:
        """
        Select one victim block for eviction.

        Returns:
            page_id of the evicted block, or None if nothing can be evicted.
            Caller is responsible for actually freeing the physical page.
        """
        victims = self._policy.select_victims(count=1)
        if not victims:
            return None

        block_id = victims[0]
        page_id = self._block_to_page.get(block_id)
        if page_id is None:
            return None

        # Log eviction before clearing state
        meta = self._block_meta(block_id)
        meta["page_id"] = page_id
        self.event_logger.emit("eviction", meta)
        self._evicted_blocks[page_id] = meta

        # Notify policy of eviction
        self._policy.evict_block(block_id)
        self._gpu_pages.discard(page_id)
        self._pinned_pages.discard(page_id)

        # Remove from sequence tracking
        for pages in self._seq_pages.values():
            pages.discard(page_id)

        self._unmap_page(page_id)
        return page_id

    def evict_n(self, count: int) -> List[int]:
        """
        Select multiple victim blocks for eviction.

        Returns:
            List of page_ids to evict (may be shorter than count).
        """
        victims = self._policy.select_victims(count=count)
        evicted_pages = []
        for block_id in victims:
            page_id = self._block_to_page.get(block_id)
            if page_id is None:
                continue

            meta = self._block_meta(block_id)
            meta["page_id"] = page_id
            self.event_logger.emit("eviction", meta)
            self._evicted_blocks[page_id] = meta

            self._policy.evict_block(block_id)
            self._gpu_pages.discard(page_id)
            self._pinned_pages.discard(page_id)
            for pages in self._seq_pages.values():
                pages.discard(page_id)
            self._unmap_page(page_id)
            evicted_pages.append(page_id)
        return evicted_pages

    # ---- Task 6: Sequence Lifecycle ----

    def register_sequence(self, seq_id: int) -> None:
        """Register a new sequence. Call before allocating blocks."""
        self._policy.register_sequence(seq_id)
        self._seq_pages[seq_id] = set()

    def on_decode_start(self, seq_id: int) -> None:
        """Notify that a sequence has transitioned from prefill to decode."""
        self._policy.set_phase(seq_id, InferencePhase.DECODE)

    def complete_sequence(self, seq_id: int) -> List[int]:
        """
        Mark a sequence as complete. Frees all associated blocks.

        Returns:
            List of page_ids freed.
        """
        freed_block_ids = self._policy.complete_sequence(seq_id)
        freed_pages = []
        for block_id in freed_block_ids:
            page_id = self._block_to_page.get(block_id)
            if page_id is not None:
                self._gpu_pages.discard(page_id)
                self._pinned_pages.discard(page_id)
                self._unmap_page(page_id)
                freed_pages.append(page_id)

        self._seq_pages.pop(seq_id, None)
        return freed_pages

    # ---- Pinning ----

    def pin_page(self, page_id: int) -> None:
        """Pin a page so it cannot be evicted."""
        block_id = self._page_to_block.get(page_id)
        if block_id is not None:
            self._policy.pin_block(block_id)
            self._pinned_pages.add(page_id)

    def unpin_page(self, page_id: int) -> None:
        """Unpin a page so it becomes eviction-eligible."""
        block_id = self._page_to_block.get(page_id)
        if block_id is not None:
            self._policy.unpin_block(block_id)
            self._pinned_pages.discard(page_id)

    # ---- Queries ----

    @property
    def num_free_gpu_blocks(self) -> int:
        """Number of unallocated GPU blocks."""
        return self.num_gpu_blocks - len(self._gpu_pages)

    @property
    def gpu_utilization(self) -> float:
        """Fraction of GPU blocks in use."""
        return len(self._gpu_pages) / max(1, self.num_gpu_blocks)

    def needs_eviction(self) -> bool:
        """True if GPU block usage exceeds watermark threshold."""
        return self.num_free_gpu_blocks <= self._watermark_blocks

    def get_block_score(self, page_id: int) -> float:
        """Score a single page for eviction. Lower = evict first."""
        block_id = self._page_to_block.get(page_id)
        if block_id is None:
            return -1.0
        return self._policy.score_block(block_id)

    # ---- Instrumentation snapshots ----

    def _emit_attention_snapshot(self) -> None:
        """Emit top-k blocks by attention_ema (sampled, not every step)."""
        blocks = self._policy.blocks
        if not blocks:
            return
        top = sorted(
            blocks.values(),
            key=lambda b: b.attention_ema,
            reverse=True,
        )[:self.event_logger.top_k]
        self.event_logger.emit("attention_snapshot", {
            "step": self._policy._step,
            "top_blocks": [
                {
                    "block_id": b.block_id,
                    "page_id": self._block_to_page.get(b.block_id),
                    "seq_id": b.sequence_id,
                    "attention_ema": round(b.attention_ema, 6),
                    "importance": self._block_importance(b.block_id),
                }
                for b in top
            ],
        })

    def _emit_pressure(self) -> None:
        """Emit cache pressure metrics."""
        self.event_logger.emit("cache_pressure", {
            "step": self._policy._step,
            "active_blocks": len(self._gpu_pages),
            "capacity": self.num_gpu_blocks,
            "utilization_pct": round(self.gpu_utilization * 100, 1),
            "pinned": len(self._pinned_pages),
            "free": self.num_free_gpu_blocks,
            "watermark_blocks": self._watermark_blocks,
            "needs_eviction": self.needs_eviction(),
        })

    # ---- Stats ----

    def get_stats(self) -> Dict:
        """Return combined stats from policy, manager, and instrumentation."""
        policy_stats = self._policy.get_stats()
        return {
            **policy_stats,
            "gpu_pages_allocated": len(self._gpu_pages),
            "gpu_pages_total": self.num_gpu_blocks,
            "gpu_utilization": self.gpu_utilization,
            "pinned_pages": len(self._pinned_pages),
            "page_mappings": len(self._page_to_block),
            "active_sequences": len(self._seq_pages),
            "recompute_total": self._recompute_total,
            "recompute_important": self._recompute_important,
            "recompute_filler": self._recompute_filler,
            "event_counts": self.event_logger.get_event_counts(),
        }
