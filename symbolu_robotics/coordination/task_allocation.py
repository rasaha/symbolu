"""
Task Allocation with BCVF Auction Scoring
==========================================

Auction-based multi-robot task allocation.

Uses BCVF (B1-B3) for bid scoring:
- Forward score (sf): Robot capability/availability
- Backward score (sb): Task-robot fit/efficiency

O10_UNIFYING: Distributed coordination for optimal assignment.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
import time
import numpy as np

from symbolu_robotics.formulas.bcvf import (
    BCVFScorer,
    BCVFConfig,
    ActionScore,
    score_action_candidates,
)
from symbolu_robotics.formulas.scc import SCCMonitor, SCCConfig


class TaskStatus(Enum):
    """Task lifecycle status."""
    PENDING = "pending"
    ANNOUNCED = "announced"
    BIDDING = "bidding"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class AuctionConfig:
    """Configuration for task auctions."""
    # BCVF configuration
    bcvf_config: BCVFConfig = field(default_factory=BCVFConfig)

    # Auction parameters
    bid_timeout_ms: float = 500.0  # Max time to wait for bids
    min_bids: int = 1  # Minimum bids before assignment
    reannounce_on_failure: bool = True

    # Bid scoring weights
    distance_weight: float = 0.3  # Closer = better
    capability_weight: float = 0.3  # More capable = better
    load_weight: float = 0.2  # Less loaded = better
    coherence_weight: float = 0.2  # Higher coherence = better

    # Thresholds
    min_bid_score: float = 0.3  # Reject bids below this
    coherence_threshold: float = 0.4  # Reject low-coherence bids


@dataclass
class TaskBid:
    """Bid from a robot for a task."""
    robot_id: str
    task_id: str
    timestamp: float = field(default_factory=time.time)

    # Bid components
    distance_to_task: float = 0.0  # Lower = better
    capability_match: float = 1.0  # 0-1, higher = better
    current_load: float = 0.0  # 0-1, lower = better
    coherence: float = 1.0  # SCC coherence, higher = better

    # BCVF scores (computed)
    forward_score: float = 0.0  # sf: Can robot do it?
    backward_score: float = 0.0  # sb: Is robot best fit?
    bcvf_score: Optional[ActionScore] = None

    # Metadata
    estimated_time: float = 0.0
    energy_cost: float = 0.0
    priority_bonus: float = 0.0


@dataclass
class TaskAuction:
    """Active auction for a task."""
    task_id: str
    task_data: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.ANNOUNCED

    # Timing
    announced_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None

    # Bids
    bids: List[TaskBid] = field(default_factory=list)
    winning_bid: Optional[TaskBid] = None

    # Requirements
    required_capabilities: List[str] = field(default_factory=list)
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class AllocationResult:
    """Result of task allocation."""
    task_id: str
    success: bool
    assigned_robot: Optional[str] = None
    winning_bid: Optional[TaskBid] = None

    # Diagnostics
    num_bids: int = 0
    best_score: float = 0.0
    allocation_time_ms: float = 0.0
    rejection_reason: Optional[str] = None


class TaskAllocator:
    """
    BCVF-based multi-robot task allocator.

    Uses auction mechanism with BCVF scoring for optimal assignment.

    BCVF Integration:
    - Forward score (sf): Robot's ability to execute task
      - Capability match
      - Energy availability
      - Current load
    - Backward score (sb): Task-robot efficiency
      - Distance to task
      - Estimated completion time
      - Historical performance

    Usage:
        allocator = TaskAllocator(robot_id="robot_1")

        # Announce task
        auction = allocator.announce_task("task_1", {"type": "pickup"})

        # Receive bids from other robots
        allocator.receive_bid(bid_from_robot_2)

        # Close auction and get result
        result = allocator.close_auction("task_1")
        if result.success:
            print(f"Assigned to {result.assigned_robot}")
    """

    def __init__(
        self,
        robot_id: str,
        config: Optional[AuctionConfig] = None,
        scc_monitor: Optional[SCCMonitor] = None,
    ):
        self.robot_id = robot_id
        self.config = config or AuctionConfig()
        self._bcvf_scorer = BCVFScorer(self.config.bcvf_config)
        self._scc_monitor = scc_monitor

        # Active auctions
        self._auctions: Dict[str, TaskAuction] = {}

        # Robot state for bidding
        self._position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._capabilities: List[str] = []
        self._current_load: float = 0.0
        self._current_coherence: float = 1.0

    def set_robot_state(
        self,
        position: Tuple[float, float, float],
        capabilities: List[str],
        load: float = 0.0,
        coherence: float = 1.0,
    ) -> None:
        """Update robot state for bidding."""
        self._position = position
        self._capabilities = capabilities
        self._current_load = np.clip(load, 0.0, 1.0)
        self._current_coherence = np.clip(coherence, 0.0, 1.0)

    def announce_task(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        required_capabilities: Optional[List[str]] = None,
        deadline: Optional[float] = None,
    ) -> TaskAuction:
        """
        Announce a new task for auction.

        Returns TaskAuction that can be used to track bids.
        """
        auction = TaskAuction(
            task_id=task_id,
            task_data=task_data,
            priority=priority,
            position=position,
            required_capabilities=required_capabilities or [],
            deadline=deadline,
            status=TaskStatus.ANNOUNCED,
        )

        self._auctions[task_id] = auction
        return auction

    def create_bid(
        self,
        task_id: str,
        task_position: Tuple[float, float, float],
        required_capabilities: Optional[List[str]] = None,
    ) -> Optional[TaskBid]:
        """
        Create a bid for a task based on current robot state.

        Uses BCVF to compute bid scores.

        Returns None if robot cannot bid (missing capabilities, overloaded).
        """
        required_capabilities = required_capabilities or []

        # Check capability match
        capability_match = self._compute_capability_match(required_capabilities)
        if capability_match < 0.5:
            return None  # Missing required capabilities

        # Check load
        if self._current_load > 0.9:
            return None  # Too busy

        # Compute distance
        distance = self._compute_distance(task_position)

        # Create bid
        bid = TaskBid(
            robot_id=self.robot_id,
            task_id=task_id,
            distance_to_task=distance,
            capability_match=capability_match,
            current_load=self._current_load,
            coherence=self._current_coherence,
        )

        # BCVF scoring
        self._score_bid(bid)

        return bid

    def _score_bid(self, bid: TaskBid) -> None:
        """
        Score bid using BCVF (B1-B3).

        Forward score (sf): Robot's execution capability
        Backward score (sb): Task-robot fit
        """
        # Forward score: Can the robot execute this task?
        # Higher capability, lower load, higher coherence = better
        sf = (
            self.config.capability_weight * bid.capability_match +
            self.config.load_weight * (1.0 - bid.current_load) +
            self.config.coherence_weight * bid.coherence
        )
        # Normalize to account for distance weight not being in forward
        sf = sf / (1.0 - self.config.distance_weight)
        sf = np.clip(sf, 0.0, 1.0)

        # Backward score: How well does this robot fit the task?
        # Closer distance = higher backward score
        max_distance = 10.0  # Normalize distance
        distance_score = 1.0 - min(bid.distance_to_task / max_distance, 1.0)

        sb = (
            self.config.distance_weight * distance_score +
            self.config.capability_weight * bid.capability_match +
            self.config.coherence_weight * bid.coherence
        )
        sb = sb / (1.0 - self.config.load_weight)
        sb = np.clip(sb, 0.0, 1.0)

        bid.forward_score = float(sf)
        bid.backward_score = float(sb)

        # Compute BCVF score
        bid.bcvf_score = self._bcvf_scorer.score(sf, sb)

    def receive_bid(self, bid: TaskBid) -> bool:
        """
        Receive a bid for an active auction.

        Returns True if bid was accepted.
        """
        if bid.task_id not in self._auctions:
            return False

        auction = self._auctions[bid.task_id]

        # Check auction is still open
        if auction.status != TaskStatus.ANNOUNCED:
            return False

        # Validate bid
        if bid.bcvf_score is None:
            self._score_bid(bid)

        if bid.bcvf_score.weight < self.config.min_bid_score:
            return False

        if bid.coherence < self.config.coherence_threshold:
            return False

        auction.bids.append(bid)
        return True

    def close_auction(self, task_id: str) -> AllocationResult:
        """
        Close auction and select winner using BCVF.

        Applies B3 normalization across all bids to select best.
        """
        start_time = time.time()

        if task_id not in self._auctions:
            return AllocationResult(
                task_id=task_id,
                success=False,
                rejection_reason="Auction not found",
            )

        auction = self._auctions[task_id]

        if len(auction.bids) < self.config.min_bids:
            return AllocationResult(
                task_id=task_id,
                success=False,
                num_bids=len(auction.bids),
                rejection_reason=f"Insufficient bids ({len(auction.bids)} < {self.config.min_bids})",
            )

        # Score all bids using BCVF
        forward_scores = [b.forward_score for b in auction.bids]
        backward_scores = [b.backward_score for b in auction.bids]

        bcvf_scores = score_action_candidates(
            forward_scores,
            backward_scores,
            self.config.bcvf_config,
        )

        # Apply priority bonus
        for i, bid in enumerate(auction.bids):
            bonus = auction.priority.value * 0.1
            bcvf_scores[i].normalized_weight *= (1.0 + bonus)

        # Renormalize after bonus
        total = sum(s.normalized_weight for s in bcvf_scores)
        for s in bcvf_scores:
            s.normalized_weight /= total

        # Select winner (highest normalized weight)
        best_idx = max(range(len(bcvf_scores)), key=lambda i: bcvf_scores[i].normalized_weight)
        winning_bid = auction.bids[best_idx]
        winning_bid.bcvf_score = bcvf_scores[best_idx]

        # Update auction
        auction.winning_bid = winning_bid
        auction.status = TaskStatus.ASSIGNED

        elapsed_ms = (time.time() - start_time) * 1000

        return AllocationResult(
            task_id=task_id,
            success=True,
            assigned_robot=winning_bid.robot_id,
            winning_bid=winning_bid,
            num_bids=len(auction.bids),
            best_score=bcvf_scores[best_idx].normalized_weight,
            allocation_time_ms=elapsed_ms,
        )

    def get_auction(self, task_id: str) -> Optional[TaskAuction]:
        """Get auction by task ID."""
        return self._auctions.get(task_id)

    def get_active_auctions(self) -> List[TaskAuction]:
        """Get all active auctions."""
        return [
            a for a in self._auctions.values()
            if a.status in (TaskStatus.ANNOUNCED, TaskStatus.BIDDING)
        ]

    def cleanup_completed(self) -> int:
        """Remove completed/failed auctions. Returns count removed."""
        to_remove = [
            tid for tid, a in self._auctions.items()
            if a.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        ]
        for tid in to_remove:
            del self._auctions[tid]
        return len(to_remove)

    def _compute_distance(
        self,
        target: Tuple[float, float, float],
    ) -> float:
        """Compute distance to target position."""
        dx = target[0] - self._position[0]
        dy = target[1] - self._position[1]
        dz = target[2] - self._position[2]
        return float(np.sqrt(dx**2 + dy**2 + dz**2))

    def _compute_capability_match(
        self,
        required: List[str],
    ) -> float:
        """Compute capability match score (0-1)."""
        if not required:
            return 1.0

        matched = sum(1 for cap in required if cap in self._capabilities)
        return matched / len(required)

    def compute_o10_unifying(self) -> float:
        """
        Compute O10_UNIFYING layer activation.

        Based on:
        - Number of active auctions
        - Average bid coherence
        - Assignment success rate
        """
        if not self._auctions:
            return 0.1

        # Active coordination level
        active = len(self.get_active_auctions())
        activity_score = min(1.0, active / 5.0)

        # Average coherence across bids
        all_bids = []
        for auction in self._auctions.values():
            all_bids.extend(auction.bids)

        if all_bids:
            avg_coherence = sum(b.coherence for b in all_bids) / len(all_bids)
        else:
            avg_coherence = 0.5

        # Success rate
        completed = sum(
            1 for a in self._auctions.values()
            if a.status == TaskStatus.COMPLETED
        )
        total = len(self._auctions)
        success_rate = completed / max(total, 1)

        # Combine
        o10 = 0.3 * activity_score + 0.4 * avg_coherence + 0.3 * success_rate
        return float(np.clip(o10, 0.0, 1.0))
