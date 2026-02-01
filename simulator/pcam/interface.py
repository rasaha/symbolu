"""
PCAM Interface specification.

Defines the interface between inference systems (like vLLM) and PCAM.
This interface is implemented by both the simulator and eventual hardware.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class PCAMResult:
    """Result from a PCAM operation."""
    success: bool
    latency_ns: float
    bank_conflicts: int = 0
    data: Optional[any] = None


class PCAMInterface(ABC):
    """
    Abstract interface between vLLM and PCAM (simulator or hardware).

    This interface matches the specification in Appendix H.4.3.
    All implementations (software simulator, FPGA, ASIC) must
    implement this interface.
    """

    @abstractmethod
    def attend(
        self,
        query_block_id: int,
        k: int = 64,
        sequence_id: int = 0,
    ) -> Tuple[List[Tuple[int, float]], float, int]:
        """
        Get top-K candidate blocks for this query.

        Args:
            query_block_id: Current query block ID
            k: Number of candidates to return
            sequence_id: Sequence ID for multi-tenant

        Returns:
            Tuple of (candidates, latency_ns, bank_conflicts)
            where candidates is list of (block_id, score) tuples,
            sorted by score descending.

        Latency target: <100ns for hardware, <500ns for software
        """
        pass

    @abstractmethod
    def update(
        self,
        query_block_id: int,
        key_block_id: int,
        weight: float,
        sequence_id: int = 0,
    ) -> Tuple[bool, float]:
        """
        Update attention relationship between blocks.

        Args:
            query_block_id: Query block ID
            key_block_id: Key block ID
            weight: Attention weight
            sequence_id: Sequence ID

        Returns:
            Tuple of (success, latency_ns)

        Latency target: <200ns for hardware, <1us for software
        """
        pass

    @abstractmethod
    def update_batch(
        self,
        sequence_id: int,
        block_ids: List[int],
        weights: List[float],
    ) -> Tuple[int, float]:
        """
        Batch update for efficiency.

        Args:
            sequence_id: Sequence ID
            block_ids: List of key block IDs
            weights: List of attention weights

        Returns:
            Tuple of (num_updated, total_latency_ns)
        """
        pass

    @abstractmethod
    def get_block_scores(
        self,
        sequence_id: int,
        block_ids: List[int],
    ) -> Dict[int, float]:
        """
        Get current attention scores for blocks.

        Args:
            sequence_id: Sequence ID
            block_ids: Blocks to query

        Returns:
            Dict of block_id -> score
        """
        pass

    @abstractmethod
    def decay(
        self,
        rate: float = 0.99,
        sequence_id: Optional[int] = None,
    ) -> None:
        """
        Apply decay to all weights.

        Args:
            rate: Decay multiplier (0.99 = 1% decay)
            sequence_id: If provided, only decay this sequence
        """
        pass

    @abstractmethod
    def allocate_sequence(
        self,
        sequence_id: int,
        max_blocks: int,
    ) -> bool:
        """
        Allocate state for a new sequence.

        Args:
            sequence_id: Unique sequence identifier
            max_blocks: Maximum blocks for this sequence

        Returns:
            True if allocation successful
        """
        pass

    @abstractmethod
    def free_sequence(self, sequence_id: int) -> bool:
        """
        Release sequence state.

        Args:
            sequence_id: Sequence to free

        Returns:
            True if freed successfully
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict:
        """
        Get interface statistics.

        Returns:
            Dict with operational statistics
        """
        pass


class SoftwarePCAMInterface(PCAMInterface):
    """
    Software implementation of PCAM interface.

    Uses the AttentionState class for state management.
    Provides realistic latency modeling based on configuration.
    """

    def __init__(
        self,
        max_sequences: int = 64,
        max_blocks_per_sequence: int = 4096,
        num_banks: int = 64,
    ):
        from .core.state import AttentionState
        from .core.config import PCAMConfig

        self.config = PCAMConfig(
            max_sequences=max_sequences,
            max_blocks_per_sequence=max_blocks_per_sequence,
        )
        self.config.banks.num_banks = num_banks

        self.state = AttentionState(
            max_sequences=max_sequences,
            max_blocks_per_sequence=max_blocks_per_sequence,
            num_banks=num_banks,
        )

        self._step = 0

    def attend(
        self,
        query_block_id: int,
        k: int = 64,
        sequence_id: int = 0,
    ) -> Tuple[List[Tuple[int, float]], float, int]:
        """Perform ATTEND operation with latency modeling."""
        candidates, bank_conflicts = self.state.attend(
            sequence_id=sequence_id,
            query_block_id=query_block_id,
            k=k,
        )

        # Calculate latency
        latency_ns = self.config.calculate_attend_latency(
            num_candidates=k,
            bank_conflicts=bank_conflicts,
        )

        return candidates, latency_ns, bank_conflicts

    def update(
        self,
        query_block_id: int,
        key_block_id: int,
        weight: float,
        sequence_id: int = 0,
    ) -> Tuple[bool, float]:
        """Perform UPDATE operation with latency modeling."""
        success = self.state.update(
            sequence_id=sequence_id,
            query_block_id=query_block_id,
            key_block_id=key_block_id,
            weight=weight,
            step=self._step,
        )

        latency_ns = self.config.calculate_update_latency(coalesced_count=1)

        return success, latency_ns

    def update_batch(
        self,
        sequence_id: int,
        block_ids: List[int],
        weights: List[float],
        query_block_id: Optional[int] = None,
    ) -> Tuple[int, float]:
        """Batch UPDATE with coalesced latency."""
        count = self.state.update_batch(
            sequence_id=sequence_id,
            block_ids=block_ids,
            weights=weights,
            step=self._step,
            query_block_id=query_block_id,
        )

        # Coalesced latency is sublinear
        latency_ns = self.config.calculate_update_latency(
            coalesced_count=max(1, count // 4)  # 4:1 coalescing
        )

        return count, latency_ns

    def get_block_scores(
        self,
        sequence_id: int,
        block_ids: List[int],
    ) -> Dict[int, float]:
        """Get block scores."""
        return self.state.get_block_scores(sequence_id, block_ids)

    def decay(
        self,
        rate: float = 0.99,
        sequence_id: Optional[int] = None,
    ) -> None:
        """Apply decay."""
        self.state.decay(rate, sequence_id)

    def allocate_sequence(
        self,
        sequence_id: int,
        max_blocks: int,
    ) -> bool:
        """Allocate sequence."""
        return self.state.allocate_sequence(sequence_id, max_blocks)

    def free_sequence(self, sequence_id: int) -> bool:
        """Free sequence."""
        return self.state.free_sequence(sequence_id)

    def get_stats(self) -> Dict:
        """Get statistics."""
        return self.state.get_stats()

    def step(self) -> None:
        """Advance step counter."""
        self._step += 1
