"""
Goal Stack for Robotics
========================

O8_PURPOSE hierarchy management.

Goals are organized hierarchically with priorities.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable
from enum import Enum
import time


class GoalStatus(Enum):
    """Goal execution status."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    PREEMPTED = "preempted"


@dataclass
class Goal:
    """
    Goal specification for task planning.

    Maps to O8_PURPOSE layer.
    """
    description: str
    priority: float = 1.0
    timeout: float = 60.0  # seconds
    target_position: Optional[tuple] = None  # (x, y, z)
    target_orientation: Optional[tuple] = None  # (roll, pitch, yaw)
    completion_predicate: Optional[Callable[[], bool]] = None
    parent_id: Optional[str] = None

    # Runtime state
    id: str = field(default_factory=lambda: str(time.time()))
    status: GoalStatus = GoalStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    subgoals: List["Goal"] = field(default_factory=list)

    def is_atomic(self) -> bool:
        """Check if goal has no subgoals."""
        return len(self.subgoals) == 0

    def is_completed(self) -> bool:
        return self.status == GoalStatus.COMPLETED

    def is_active(self) -> bool:
        return self.status == GoalStatus.ACTIVE

    def is_timed_out(self) -> bool:
        if self.start_time is None:
            return False
        return (time.time() - self.start_time) > self.timeout

    def activate(self) -> None:
        """Mark goal as active."""
        self.status = GoalStatus.ACTIVE
        self.start_time = time.time()

    def complete(self) -> None:
        """Mark goal as completed."""
        self.status = GoalStatus.COMPLETED
        self.end_time = time.time()

    def fail(self, reason: str = "") -> None:
        """Mark goal as failed."""
        self.status = GoalStatus.FAILED
        self.end_time = time.time()

    def preempt(self) -> None:
        """Preempt goal for higher priority."""
        self.status = GoalStatus.PREEMPTED
        self.end_time = time.time()


class GoalStack:
    """
    LIFO goal stack with priority support.

    Higher priority goals preempt lower priority ones.
    """

    def __init__(self, max_depth: int = 10):
        self._stack: List[Goal] = []
        self._completed: List[Goal] = []
        self.max_depth = max_depth

    def push(self, goal: Goal) -> None:
        """
        Push goal onto stack.

        Preempts lower priority goals if necessary.
        """
        # Preempt lower priority active goals
        if self._stack:
            current = self._stack[-1]
            if current.is_active() and goal.priority > current.priority:
                current.preempt()

        if len(self._stack) >= self.max_depth:
            # Remove oldest completed/failed goal
            self._cleanup()

        self._stack.append(goal)

    def pop(self) -> Optional[Goal]:
        """Pop and return top goal."""
        if self._stack:
            goal = self._stack.pop()
            self._completed.append(goal)
            return goal
        return None

    def peek(self) -> Optional[Goal]:
        """Return top goal without removing."""
        if self._stack:
            return self._stack[-1]
        return None

    def get_active(self) -> Optional[Goal]:
        """Get currently active goal."""
        for goal in reversed(self._stack):
            if goal.is_active():
                return goal
        return None

    def activate_top(self) -> Optional[Goal]:
        """Activate the top goal."""
        if self._stack:
            goal = self._stack[-1]
            if goal.status == GoalStatus.PENDING:
                goal.activate()
            return goal
        return None

    def complete_active(self) -> Optional[Goal]:
        """Complete the active goal."""
        active = self.get_active()
        if active:
            active.complete()
            return self.pop()
        return None

    def is_empty(self) -> bool:
        return len(self._stack) == 0

    def size(self) -> int:
        return len(self._stack)

    def clear(self) -> None:
        """Clear all goals."""
        self._stack.clear()

    def _cleanup(self) -> None:
        """Remove oldest non-active goals."""
        self._stack = [g for g in self._stack
                       if g.status in (GoalStatus.PENDING, GoalStatus.ACTIVE)]

    def get_all(self) -> List[Goal]:
        """Get all goals in stack."""
        return self._stack.copy()

    def get_completed(self) -> List[Goal]:
        """Get completed goals history."""
        return self._completed.copy()

    def compute_purpose_level(self) -> float:
        """
        Compute O8_PURPOSE layer activation.

        Based on stack state and goal priorities.
        """
        if not self._stack:
            return 0.0

        # Average priority of active/pending goals
        active_goals = [g for g in self._stack
                        if g.status in (GoalStatus.PENDING, GoalStatus.ACTIVE)]

        if not active_goals:
            return 0.0

        avg_priority = sum(g.priority for g in active_goals) / len(active_goals)
        depth_factor = min(1.0, len(active_goals) / 3.0)

        return avg_priority * depth_factor
