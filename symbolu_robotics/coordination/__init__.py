"""
Symbolu Robotics Coordination
=============================

Multi-robot coordination using patent formulas.

Formula Integration:
- BCVF (B1-B3): Task bid scoring, conflict resolution
- USE (U1-U4): Multi-robot observation fusion
- SCC (S1-S9): Formation coherence, swarm health

Modules:
- task_allocation: Auction-based task distribution
- formation: Formation control with coherence
- conflict_resolution: Distributed deadlock resolution
- shared_world: Collaborative world model building
"""

from symbolu_robotics.coordination.task_allocation import (
    TaskAllocator,
    TaskBid,
    TaskAuction,
    AllocationResult,
    AuctionConfig,
)
from symbolu_robotics.coordination.formation import (
    FormationController,
    FormationConfig,
    FormationType,
    FormationState,
)
from symbolu_robotics.coordination.conflict_resolution import (
    ConflictResolver,
    Conflict,
    ConflictType,
    ResolutionStrategy,
    ResolutionResult,
)
from symbolu_robotics.coordination.shared_world import (
    SharedWorldModel,
    Observation,
    WorldCell,
    SharedWorldConfig,
)

__all__ = [
    # Task Allocation
    "TaskAllocator",
    "TaskBid",
    "TaskAuction",
    "AllocationResult",
    "AuctionConfig",
    # Formation
    "FormationController",
    "FormationConfig",
    "FormationType",
    "FormationState",
    # Conflict Resolution
    "ConflictResolver",
    "Conflict",
    "ConflictType",
    "ResolutionStrategy",
    "ResolutionResult",
    # Shared World
    "SharedWorldModel",
    "Observation",
    "WorldCell",
    "SharedWorldConfig",
]
