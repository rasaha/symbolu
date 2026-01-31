"""
CTM+ Block Space Manager for vLLM.

Drop-in replacement for vLLM's BlockSpaceManager that uses
CTM+ for intelligent block eviction decisions.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import deque
import logging

from .evictor import CTMEvictionPolicy
from .config import CTMvLLMConfig

logger = logging.getLogger(__name__)


class PhysicalBlock:
    """Represents a physical block of KV cache memory."""

    def __init__(
        self,
        block_id: int,
        block_size: int,
        device: str = "gpu",
    ):
        self.block_id = block_id
        self.block_size = block_size
        self.device = device
        self.ref_count = 0
        self.sequence_ids: Set[int] = set()

    def is_free(self) -> bool:
        return self.ref_count == 0


class BlockTable:
    """Maps logical blocks to physical blocks for a sequence."""

    def __init__(self, sequence_id: int):
        self.sequence_id = sequence_id
        self.blocks: List[int] = []  # Physical block IDs

    def append(self, block_id: int) -> None:
        self.blocks.append(block_id)

    def __len__(self) -> int:
        return len(self.blocks)

    def __getitem__(self, idx: int) -> int:
        return self.blocks[idx]


class CTMBlockSpaceManager:
    """
    CTM+ enabled Block Space Manager for vLLM.

    Manages physical blocks across GPU and CPU memory,
    using CTM+ for intelligent eviction decisions.

    Usage:
        manager = CTMBlockSpaceManager(
            block_size=16,
            num_gpu_blocks=1000,
            num_cpu_blocks=10000,
        )

        # Allocate blocks for a sequence
        manager.allocate(sequence_id=1, num_blocks=10)

        # Access blocks (triggers CTM+ tracking)
        manager.access(sequence_id=1, block_indices=[0, 1, 2])

        # Free blocks when sequence completes
        manager.free(sequence_id=1)
    """

    def __init__(
        self,
        block_size: int,
        num_gpu_blocks: int,
        num_cpu_blocks: int,
        watermark: float = 0.1,
        ctm_config: Optional[CTMvLLMConfig] = None,
    ):
        """
        Initialize block space manager.

        Args:
            block_size: Number of tokens per block.
            num_gpu_blocks: Total GPU blocks available.
            num_cpu_blocks: Total CPU blocks available.
            watermark: Fraction of GPU blocks to keep free.
            ctm_config: CTM+ configuration.
        """
        self.block_size = block_size
        self.num_gpu_blocks = num_gpu_blocks
        self.num_cpu_blocks = num_cpu_blocks
        self.watermark = watermark

        # CTM+ eviction policy
        self.ctm = CTMEvictionPolicy(ctm_config)

        # Physical blocks
        self.gpu_blocks: Dict[int, PhysicalBlock] = {
            i: PhysicalBlock(i, block_size, "gpu")
            for i in range(num_gpu_blocks)
        }
        self.cpu_blocks: Dict[int, PhysicalBlock] = {
            i + num_gpu_blocks: PhysicalBlock(i + num_gpu_blocks, block_size, "cpu")
            for i in range(num_cpu_blocks)
        }

        # Free block pools
        self.free_gpu_blocks: deque = deque(range(num_gpu_blocks))
        self.free_cpu_blocks: deque = deque(
            range(num_gpu_blocks, num_gpu_blocks + num_cpu_blocks)
        )

        # Sequence to block table mapping
        self.block_tables: Dict[int, BlockTable] = {}

        # Statistics
        self.num_evictions = 0
        self.num_promotions = 0

    def can_allocate(self, num_blocks: int) -> bool:
        """Check if we can allocate num_blocks on GPU."""
        available = len(self.free_gpu_blocks)
        watermark_blocks = int(self.num_gpu_blocks * self.watermark)
        return available - watermark_blocks >= num_blocks

    def allocate(
        self,
        sequence_id: int,
        num_blocks: int,
    ) -> List[int]:
        """
        Allocate blocks for a sequence.

        Args:
            sequence_id: Sequence identifier.
            num_blocks: Number of blocks to allocate.

        Returns:
            List of allocated physical block IDs.
        """
        if sequence_id not in self.block_tables:
            self.block_tables[sequence_id] = BlockTable(sequence_id)

        allocated = []
        for _ in range(num_blocks):
            block_id = self._allocate_block(sequence_id)
            if block_id is not None:
                self.block_tables[sequence_id].append(block_id)
                allocated.append(block_id)
            else:
                logger.warning(f"Failed to allocate block for sequence {sequence_id}")
                break

        return allocated

    def _allocate_block(self, sequence_id: int) -> Optional[int]:
        """Allocate a single block, evicting if necessary."""
        # Try to get a free GPU block
        if self.free_gpu_blocks:
            block_id = self.free_gpu_blocks.popleft()
            block = self.gpu_blocks[block_id]
            block.ref_count = 1
            block.sequence_ids.add(sequence_id)

            # Register with CTM+
            self.ctm.on_block_access(block_id, sequence_id)
            return block_id

        # Need to evict
        victim_id = self.ctm.select_victim()
        if victim_id is None:
            return None

        # Evict victim to CPU
        self._evict_to_cpu(victim_id)

        # Now allocate the freed block
        if self.free_gpu_blocks:
            block_id = self.free_gpu_blocks.popleft()
            block = self.gpu_blocks[block_id]
            block.ref_count = 1
            block.sequence_ids.add(sequence_id)
            self.ctm.on_block_access(block_id, sequence_id)
            return block_id

        return None

    def _evict_to_cpu(self, block_id: int) -> bool:
        """Evict a GPU block to CPU."""
        if block_id not in self.gpu_blocks:
            return False

        if not self.free_cpu_blocks:
            logger.error("No free CPU blocks for eviction")
            return False

        gpu_block = self.gpu_blocks[block_id]

        # Get a CPU block
        cpu_block_id = self.free_cpu_blocks.popleft()
        cpu_block = self.cpu_blocks[cpu_block_id]

        # Transfer metadata
        cpu_block.ref_count = gpu_block.ref_count
        cpu_block.sequence_ids = gpu_block.sequence_ids.copy()

        # Update block tables
        for seq_id in gpu_block.sequence_ids:
            if seq_id in self.block_tables:
                table = self.block_tables[seq_id]
                for i, bid in enumerate(table.blocks):
                    if bid == block_id:
                        table.blocks[i] = cpu_block_id

        # Free GPU block
        gpu_block.ref_count = 0
        gpu_block.sequence_ids.clear()
        self.free_gpu_blocks.append(block_id)

        # Update CTM+
        self.ctm.evict_block(block_id)
        self.num_evictions += 1

        return True

    def access(
        self,
        sequence_id: int,
        block_indices: Optional[List[int]] = None,
    ) -> List[int]:
        """
        Access blocks for a sequence (triggers CTM+ tracking).

        Args:
            sequence_id: Sequence identifier.
            block_indices: Specific block indices to access (or all if None).

        Returns:
            List of promoted block IDs (if any).
        """
        if sequence_id not in self.block_tables:
            return []

        table = self.block_tables[sequence_id]
        promoted = []

        indices = block_indices if block_indices else range(len(table))

        for idx in indices:
            if idx >= len(table):
                continue

            block_id = table[idx]
            is_promotion, needs_eviction = self.ctm.on_block_access(
                block_id, sequence_id
            )

            if is_promotion and block_id in self.cpu_blocks:
                # Promote from CPU to GPU
                if needs_eviction and not self.free_gpu_blocks:
                    # Evict first
                    victim = self.ctm.select_victim()
                    if victim:
                        self._evict_to_cpu(victim)

                if self._promote_to_gpu(block_id, sequence_id):
                    promoted.append(block_id)

        return promoted

    def _promote_to_gpu(self, cpu_block_id: int, sequence_id: int) -> bool:
        """Promote a CPU block to GPU."""
        if cpu_block_id not in self.cpu_blocks:
            return False

        if not self.free_gpu_blocks:
            return False

        cpu_block = self.cpu_blocks[cpu_block_id]

        # Get a GPU block
        gpu_block_id = self.free_gpu_blocks.popleft()
        gpu_block = self.gpu_blocks[gpu_block_id]

        # Transfer metadata
        gpu_block.ref_count = cpu_block.ref_count
        gpu_block.sequence_ids = cpu_block.sequence_ids.copy()

        # Update block tables
        for seq_id in cpu_block.sequence_ids:
            if seq_id in self.block_tables:
                table = self.block_tables[seq_id]
                for i, bid in enumerate(table.blocks):
                    if bid == cpu_block_id:
                        table.blocks[i] = gpu_block_id

        # Free CPU block
        cpu_block.ref_count = 0
        cpu_block.sequence_ids.clear()
        self.free_cpu_blocks.append(cpu_block_id)

        # Update CTM+
        self.ctm.promote_block(gpu_block_id)
        self.num_promotions += 1

        return True

    def free(self, sequence_id: int) -> None:
        """Free all blocks for a sequence."""
        if sequence_id not in self.block_tables:
            return

        table = self.block_tables[sequence_id]

        for block_id in table.blocks:
            if block_id in self.gpu_blocks:
                block = self.gpu_blocks[block_id]
                block.sequence_ids.discard(sequence_id)
                block.ref_count = max(0, block.ref_count - 1)
                if block.is_free():
                    self.free_gpu_blocks.append(block_id)
                    self.ctm.free_block(block_id)

            elif block_id in self.cpu_blocks:
                block = self.cpu_blocks[block_id]
                block.sequence_ids.discard(sequence_id)
                block.ref_count = max(0, block.ref_count - 1)
                if block.is_free():
                    self.free_cpu_blocks.append(block_id)
                    self.ctm.free_block(block_id)

        del self.block_tables[sequence_id]

    def get_num_free_gpu_blocks(self) -> int:
        """Get number of free GPU blocks."""
        return len(self.free_gpu_blocks)

    def get_num_free_cpu_blocks(self) -> int:
        """Get number of free CPU blocks."""
        return len(self.free_cpu_blocks)

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        ctm_stats = self.ctm.get_stats()
        return {
            "num_gpu_blocks": self.num_gpu_blocks,
            "num_cpu_blocks": self.num_cpu_blocks,
            "free_gpu_blocks": len(self.free_gpu_blocks),
            "free_cpu_blocks": len(self.free_cpu_blocks),
            "active_sequences": len(self.block_tables),
            "num_evictions": self.num_evictions,
            "num_promotions": self.num_promotions,
            **ctm_stats,
        }

    def pin_sequence(self, sequence_id: int) -> None:
        """Pin all blocks for a sequence (prevent eviction)."""
        if sequence_id not in self.block_tables:
            return

        for block_id in self.block_tables[sequence_id].blocks:
            self.ctm.pin_block(block_id)

    def unpin_sequence(self, sequence_id: int) -> None:
        """Unpin all blocks for a sequence."""
        if sequence_id not in self.block_tables:
            return

        for block_id in self.block_tables[sequence_id].blocks:
            self.ctm.unpin_block(block_id)
