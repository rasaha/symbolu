"""
Hierarchical Task Network (HTN) Planner
=======================================

Hierarchical decomposition of complex tasks into executable primitives.

Integrates with Symbolu ontology:
- O8_PURPOSE: Goal hierarchy management
- O7_REASONING: Task decomposition logic
- BCVF (B1-B3): Method selection scoring
- SCC: Coherence monitoring during execution

Key Features:
- Task decomposition via methods
- Precondition/effect reasoning
- Dynamic replanning on failure
- Integration with action primitives

Implementation: Pure Python HTN planner (similar to pyhop)
No external planning libraries required.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Callable, Any, Tuple
from enum import Enum
import copy
import logging

from symbolu_robotics.core.types import Layer12D

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task in the HTN."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ConditionType(Enum):
    """Type of condition for preconditions/effects."""
    STATE = "state"  # World state condition
    LAYER = "layer"  # 12D layer condition
    COHERENCE = "coherence"  # SCC coherence condition
    CUSTOM = "custom"  # Custom predicate


@dataclass
class Condition:
    """Condition for preconditions and effects."""
    type: ConditionType
    name: str
    value: Any = True
    comparator: str = "=="  # ==, !=, <, >, <=, >=

    def evaluate(self, state: Dict[str, Any], layer_12d: Optional[Layer12D] = None) -> bool:
        """Evaluate condition against current state."""
        if self.type == ConditionType.STATE:
            actual = state.get(self.name)
            return self._compare(actual, self.value)

        elif self.type == ConditionType.LAYER and layer_12d is not None:
            # Layer index encoded in name: "O3_EXECUTION" -> index 2
            layer_map = {
                "O1_POTENTIAL": 0, "O2_IDENTITY": 1, "O3_EXECUTION": 2,
                "O4_STRUCTURE": 3, "O5_COGNITION": 4, "O6_AGENCY": 5,
                "O7_REASONING": 6, "O8_PURPOSE": 7, "O9_WITNESSES": 8,
                "O10_UNIFYING": 9, "O11_INTEGRATION": 10, "O12_ABSOLVING": 11,
            }
            idx = layer_map.get(self.name, -1)
            if idx >= 0:
                actual = layer_12d[idx]
                return self._compare(actual, self.value)

        elif self.type == ConditionType.COHERENCE:
            coherence = state.get("coherence", 0.0)
            return self._compare(coherence, self.value)

        elif self.type == ConditionType.CUSTOM:
            predicate = state.get(f"predicate_{self.name}")
            if callable(predicate):
                return predicate() == self.value
            return False

        return False

    def _compare(self, actual: Any, expected: Any) -> bool:
        """Compare actual value to expected."""
        if actual is None:
            return False
        if self.comparator == "==":
            return actual == expected
        elif self.comparator == "!=":
            return actual != expected
        elif self.comparator == "<":
            return actual < expected
        elif self.comparator == ">":
            return actual > expected
        elif self.comparator == "<=":
            return actual <= expected
        elif self.comparator == ">=":
            return actual >= expected
        return False


@dataclass
class Task:
    """
    A task in the HTN hierarchy.

    Can be:
    - Primitive: Directly executable action
    - Compound: Decomposes into subtasks via methods
    """
    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_primitive: bool = False
    status: TaskStatus = TaskStatus.PENDING

    # Preconditions and effects
    preconditions: List[Condition] = field(default_factory=list)
    effects: List[Condition] = field(default_factory=list)

    # For compound tasks: available decomposition methods
    method_names: List[str] = field(default_factory=list)

    # Execution
    action_name: str = ""  # For primitives: name of action to execute
    subtasks: List["Task"] = field(default_factory=list)

    # BCVF scores for method selection
    forward_score: float = 0.0
    backward_score: float = 0.0

    def is_ready(self, state: Dict[str, Any], layer_12d: Optional[Layer12D] = None) -> bool:
        """Check if all preconditions are satisfied."""
        return all(cond.evaluate(state, layer_12d) for cond in self.preconditions)


@dataclass
class Method:
    """
    Decomposition method for compound tasks.

    A method specifies how to decompose a task into subtasks.
    Multiple methods may be applicable; BCVF selects the best.
    """
    name: str
    task_name: str  # The compound task this method decomposes

    # Applicability conditions (beyond task preconditions)
    conditions: List[Condition] = field(default_factory=list)

    # Subtasks produced by this method (ordered)
    subtask_templates: List[Task] = field(default_factory=list)

    # BCVF scoring factors
    estimated_cost: float = 1.0
    success_probability: float = 0.8

    def is_applicable(self, state: Dict[str, Any], layer_12d: Optional[Layer12D] = None) -> bool:
        """Check if method is applicable in current state."""
        return all(cond.evaluate(state, layer_12d) for cond in self.conditions)

    def decompose(self, task: Task) -> List[Task]:
        """Create subtasks from templates, binding parameters."""
        subtasks = []
        for template in self.subtask_templates:
            subtask = copy.deepcopy(template)
            # Bind parameters from parent task
            for key, value in task.parameters.items():
                if key in subtask.parameters:
                    subtask.parameters[key] = value
            subtasks.append(subtask)
        return subtasks


@dataclass
class HTNConfig:
    """Configuration for HTN planner."""
    max_depth: int = 10  # Maximum decomposition depth
    max_backtracks: int = 5  # Maximum replanning attempts

    # BCVF integration
    use_bcvf_selection: bool = True
    bcvf_beta: float = 2.0  # Selection sharpness

    # Coherence requirements
    min_coherence_for_execution: float = 0.3
    require_coherence_check: bool = True

    # Replanning triggers
    replan_on_failure: bool = True
    replan_on_low_coherence: bool = True
    coherence_replan_threshold: float = 0.4


class HTNPlanner:
    """
    Hierarchical Task Network planner.

    Features:
    - Task decomposition via methods
    - BCVF-based method selection
    - Precondition/effect reasoning
    - Dynamic replanning
    - Coherence-aware execution

    Skeleton Implementation:
    - Core HTN algorithm defined
    - Integration points for BCVF and SCC
    - Action execution delegated to primitives
    """

    def __init__(self, config: Optional[HTNConfig] = None):
        self._config = config or HTNConfig()

        # Task and method library
        self._tasks: Dict[str, Task] = {}
        self._methods: Dict[str, List[Method]] = {}  # task_name -> methods

        # Action executors (primitive name -> executor function)
        self._executors: Dict[str, Callable] = {}

        # Current plan
        self._current_plan: List[Task] = []
        self._plan_index: int = 0

        # State
        self._world_state: Dict[str, Any] = {}
        self._last_layer_12d: Optional[Layer12D] = None

        # BCVF scorer (optional)
        self._bcvf_scorer = None

        # Metrics
        self._decomposition_count = 0
        self._backtrack_count = 0

    def register_task(self, task: Task) -> None:
        """Register a task template."""
        self._tasks[task.name] = task

    def register_method(self, method: Method) -> None:
        """Register a decomposition method."""
        if method.task_name not in self._methods:
            self._methods[method.task_name] = []
        self._methods[method.task_name].append(method)

    def register_executor(self, action_name: str, executor: Callable) -> None:
        """Register executor for primitive action."""
        self._executors[action_name] = executor

    def set_bcvf_scorer(self, scorer) -> None:
        """Set BCVF scorer for method selection."""
        self._bcvf_scorer = scorer

    def update_state(
        self,
        world_state: Optional[Dict[str, Any]] = None,
        layer_12d: Optional[Layer12D] = None,
    ) -> None:
        """Update world state and 12D layer."""
        if world_state is not None:
            self._world_state.update(world_state)
        if layer_12d is not None:
            self._last_layer_12d = layer_12d.copy()

    def plan(
        self,
        goal_task: Task,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> List[Task]:
        """
        Create plan to achieve goal task.

        Uses HTN decomposition with BCVF method selection.
        """
        if initial_state is not None:
            self._world_state.update(initial_state)

        # Reset metrics
        self._decomposition_count = 0
        self._backtrack_count = 0

        # Decompose recursively
        plan = self._decompose(goal_task, depth=0)

        if plan is None:
            return []

        self._current_plan = plan
        self._plan_index = 0

        return plan

    def _decompose(
        self,
        task: Task,
        depth: int,
    ) -> Optional[List[Task]]:
        """Recursively decompose task into primitives."""
        if depth > self._config.max_depth:
            return None

        self._decomposition_count += 1

        # Check preconditions
        if not task.is_ready(self._world_state, self._last_layer_12d):
            return None

        # If primitive, return as-is
        if task.is_primitive:
            return [task]

        # Get applicable methods
        methods = self._get_applicable_methods(task)
        if not methods:
            return None

        # Select best method using BCVF
        best_method = self._select_method(methods, task)
        if best_method is None:
            return None

        # Decompose into subtasks
        subtasks = best_method.decompose(task)

        # Recursively decompose each subtask
        plan = []
        for subtask in subtasks:
            sub_plan = self._decompose(subtask, depth + 1)
            if sub_plan is None:
                # Backtrack: try different method
                self._backtrack_count += 1
                if self._backtrack_count > self._config.max_backtracks:
                    return None
                # Remove this method and retry
                methods.remove(best_method)
                if not methods:
                    return None
                best_method = self._select_method(methods, task)
                if best_method is None:
                    return None
                subtasks = best_method.decompose(task)
                return self._decompose(task, depth)  # Retry

            plan.extend(sub_plan)

        return plan

    def _get_applicable_methods(self, task: Task) -> List[Method]:
        """Get all applicable methods for task."""
        methods = self._methods.get(task.name, [])
        return [
            m for m in methods
            if m.is_applicable(self._world_state, self._last_layer_12d)
        ]

    def _select_method(
        self,
        methods: List[Method],
        task: Task,
    ) -> Optional[Method]:
        """Select best method using BCVF."""
        if not methods:
            return None

        if len(methods) == 1:
            return methods[0]

        if self._config.use_bcvf_selection and self._bcvf_scorer:
            # Use BCVF for selection
            forward_scores = [1.0 / (1.0 + m.estimated_cost) for m in methods]
            backward_scores = [m.success_probability for m in methods]

            scores = self._bcvf_scorer.score_candidates(
                forward_scores, backward_scores
            )

            best_idx = max(range(len(scores)), key=lambda i: scores[i].normalized_weight)
            return methods[best_idx]
        else:
            # Simple heuristic: prefer higher success probability, lower cost
            return max(
                methods,
                key=lambda m: m.success_probability / (1.0 + m.estimated_cost)
            )

    def execute_step(self, layer_12d: Optional[Layer12D] = None) -> Tuple[bool, Optional[Task]]:
        """
        Execute next step in current plan.

        Returns:
            (success, executed_task)
        """
        if layer_12d is not None:
            self._last_layer_12d = layer_12d

        # Check coherence
        if self._config.require_coherence_check:
            coherence = self._world_state.get("coherence", 1.0)
            if coherence < self._config.min_coherence_for_execution:
                return False, None

        # Get next task
        if self._plan_index >= len(self._current_plan):
            return True, None  # Plan complete

        task = self._current_plan[self._plan_index]

        # Check preconditions
        if not task.is_ready(self._world_state, self._last_layer_12d):
            if self._config.replan_on_failure:
                return self._trigger_replan(), task
            task.status = TaskStatus.BLOCKED
            return False, task

        # Execute primitive
        task.status = TaskStatus.ACTIVE
        success = self._execute_primitive(task)

        if success:
            task.status = TaskStatus.COMPLETED
            self._apply_effects(task)
            self._plan_index += 1
        else:
            task.status = TaskStatus.FAILED
            if self._config.replan_on_failure:
                return self._trigger_replan(), task

        return success, task

    def _execute_primitive(self, task: Task) -> bool:
        """Execute a primitive task."""
        executor = self._executors.get(task.action_name)
        if executor is None:
            return False

        try:
            result = executor(task.parameters, self._last_layer_12d)
            return bool(result)
        except Exception:
            return False

    def _apply_effects(self, task: Task) -> None:
        """Apply task effects to world state."""
        for effect in task.effects:
            if effect.type == ConditionType.STATE:
                self._world_state[effect.name] = effect.value

    def _trigger_replan(self) -> bool:
        """Trigger replanning from current state."""
        if not self._current_plan:
            return False

        # Get remaining goal (last task in original plan)
        remaining_tasks = self._current_plan[self._plan_index:]
        if not remaining_tasks:
            return True

        # Find original goal task
        goal_task_name = self._current_plan[-1].name if self._current_plan else None
        if goal_task_name and goal_task_name in self._tasks:
            goal_template = self._tasks[goal_task_name]
            new_plan = self.plan(goal_template)
            return len(new_plan) > 0

        return False

    def get_current_task(self) -> Optional[Task]:
        """Get current task being executed."""
        if self._plan_index < len(self._current_plan):
            return self._current_plan[self._plan_index]
        return None

    def get_plan_progress(self) -> Tuple[int, int]:
        """Get (completed_steps, total_steps)."""
        return self._plan_index, len(self._current_plan)

    def is_plan_complete(self) -> bool:
        """Check if current plan is complete."""
        return self._plan_index >= len(self._current_plan)

    def get_metrics(self) -> Dict[str, Any]:
        """Get planning metrics."""
        return {
            "decomposition_count": self._decomposition_count,
            "backtrack_count": self._backtrack_count,
            "plan_length": len(self._current_plan),
            "plan_progress": self._plan_index,
        }

    def reset(self) -> None:
        """Reset planner state."""
        self._current_plan = []
        self._plan_index = 0
        self._decomposition_count = 0
        self._backtrack_count = 0


# Convenience function to create common tasks
def create_pick_and_place_htn() -> Tuple[Dict[str, Task], Dict[str, List[Method]]]:
    """
    Create standard pick-and-place HTN domain.

    Returns tasks and methods dictionaries.
    """
    tasks = {}
    methods = {}

    # Primitive tasks
    tasks["move_to"] = Task(
        name="move_to",
        is_primitive=True,
        action_name="move_to",
        preconditions=[
            Condition(ConditionType.LAYER, "O6_AGENCY", 0.3, ">="),
        ],
        effects=[
            Condition(ConditionType.STATE, "at_location", True),
        ],
    )

    tasks["grasp"] = Task(
        name="grasp",
        is_primitive=True,
        action_name="grasp",
        preconditions=[
            Condition(ConditionType.STATE, "at_location", True),
            Condition(ConditionType.STATE, "holding", False),
        ],
        effects=[
            Condition(ConditionType.STATE, "holding", True),
        ],
    )

    tasks["release"] = Task(
        name="release",
        is_primitive=True,
        action_name="release",
        preconditions=[
            Condition(ConditionType.STATE, "holding", True),
        ],
        effects=[
            Condition(ConditionType.STATE, "holding", False),
        ],
    )

    # Compound tasks
    tasks["pick_and_place"] = Task(
        name="pick_and_place",
        is_primitive=False,
        method_names=["standard_pick_place"],
    )

    # Methods
    methods["pick_and_place"] = [
        Method(
            name="standard_pick_place",
            task_name="pick_and_place",
            conditions=[
                Condition(ConditionType.COHERENCE, "coherence", 0.3, ">="),
            ],
            subtask_templates=[
                Task(name="move_to", is_primitive=True, action_name="move_to",
                     parameters={"target": "pick_location"}),
                Task(name="grasp", is_primitive=True, action_name="grasp"),
                Task(name="move_to", is_primitive=True, action_name="move_to",
                     parameters={"target": "place_location"}),
                Task(name="release", is_primitive=True, action_name="release"),
            ],
            estimated_cost=4.0,
            success_probability=0.85,
        ),
    ]

    return tasks, methods
