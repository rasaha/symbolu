"""The Agent Runtime loop (proposer).

    Goal → Plan → Select action → (Executor: build CER → submit to control plane →
    if eligible, governed-execute; or run a local fast path) → Observation →
    memory → reflect → continue / stop / replan / request human.

The runtime NEVER makes its own authoritative allow/deny. Governed execution and
the control-plane decision are owned by the injected ``ActionExecutor`` (the
governed executor, Commit D), which the runtime treats as opaque — it consumes the
``ExecutionResult`` and folds it into memory and reflection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

from ..contracts.action import Action
from ..contracts.errors import CancelledError
from ..contracts.goal import Goal
from ..contracts.observation import Observation
from ..contracts.result import ExecutionResult
from ..memory.episodic_memory import EpisodicMemory
from ..observation.result_ingestion import ingest
from ..planning.planner import Planner
from ..reasoning.reflection import CONTINUE, REPLAN, REQUEST_HUMAN, STOP, Reflection, Reflector
from ..tracing import events as ev
from ..tracing.trace import RunTrace
from .budget import BudgetAccountant
from .cancellation import CancellationToken
from . import state as st


class ActionExecutor(Protocol):
    """Executes one action and returns a typed result. The governed executor
    (Commit D) implements this: governed actions go CER → control plane → tool;
    local actions run a policy-permitted fast path. The runtime does not know or
    decide which — it only consumes the result."""
    def execute(self, action: Action) -> ExecutionResult: ...


@dataclass
class RunOutcome:
    state: st.RuntimeState
    trace: RunTrace
    observations: List[Observation] = field(default_factory=list)

    @property
    def status(self) -> str:
        return self.state.status


class AgentRuntime:
    def __init__(self, *, executor: ActionExecutor, planner: Optional[Planner] = None,
                 reflector: Optional[Reflector] = None,
                 memory: Optional[EpisodicMemory] = None,
                 budget: Optional[BudgetAccountant] = None):
        self._executor = executor
        self._planner = planner or Planner()
        self._reflector = reflector or Reflector()
        self._memory = memory or EpisodicMemory()
        self._budget = budget or BudgetAccountant()

    @property
    def memory(self) -> EpisodicMemory:
        return self._memory

    def run(self, goal: Goal, *, run_id: str = "run",
            cancellation: Optional[CancellationToken] = None,
            max_replans: int = 2) -> RunOutcome:
        trace = RunTrace(run_id=run_id)
        state = st.RuntimeState(run_id=run_id, goal=goal)
        trace.emit(ev.RUN_STARTED, goal_id=goal.goal_id, objective=goal.objective)

        replans = 0
        state.plan = self._planner.plan(goal)
        trace.emit(ev.PLANNED, steps=[a.action_id for a in state.plan.steps])

        while True:
            if cancellation is not None and cancellation.cancelled:
                state.status = st.CANCELLED
                trace.emit(ev.RUN_CANCELLED)
                break
            if self._budget.exceeded:
                state.status = st.BUDGET_STOP
                trace.emit(ev.BUDGET_EXCEEDED, steps=self._budget.steps)
                break

            action = state.plan.next_action()
            if action is None:
                state.status = st.COMPLETED
                break

            state.turns += 1
            self._budget.charge(steps=1)
            trace.emit(ev.ACTION_SELECTED, action_id=action.action_id,
                       risk_class=action.risk_class.value, governed=action.is_governed)

            result = self._executor.execute(action)   # opaque: governed or local
            trace.emit(ev.GOVERNANCE_DECISION, action_id=action.action_id,
                       composed=result.combined_outcome, eligible=result.eligible,
                       executed=result.executed)

            observation = ingest(result, self._memory)   # return path -> memory
            state.observations.append(observation)
            trace.emit(ev.OBSERVED, action_id=action.action_id, outcome=observation.outcome)

            reflection = self._reflector.reflect(observation)
            trace.emit(ev.REFLECTED, decision=reflection.decision, rationale=reflection.rationale)

            if reflection.decision == CONTINUE:
                state.plan.mark_done(action.action_id)
                continue
            if reflection.decision == REPLAN:
                replans += 1
                if replans > max_replans:
                    state.status = st.STOPPED
                    break
                # A denied/blocked action is dropped; replanning here marks it done so
                # the loop advances (a real planner would substitute an alternative).
                state.plan.mark_done(action.action_id)
                trace.emit(ev.PLANNED, replan=replans)
                continue
            if reflection.decision == REQUEST_HUMAN:
                state.status = st.AWAITING_HUMAN
                trace.emit(ev.HUMAN_REQUESTED, action_id=action.action_id)
                break
            # STOP
            state.status = st.STOPPED
            break

        trace.emit(ev.RUN_COMPLETED, status=state.status, turns=state.turns)
        return RunOutcome(state=state, trace=trace, observations=list(state.observations))
