"""
Tests for DurationPolicy (wall-clock governance, v1).

Validates:
1. Unit — frozen dataclass policy semantics
2. Runtime — DEADLINE_EXCEEDED short-circuits the run after generation
3. Runtime — ACTION_TIMEOUT marks one action timed_out and the run continues
4. Trace — deadline_exceeded / action_timeouts / elapsed_s populated
5. Ordering invariants — cancel > budget > deadline > approve > execute
6. Snapshot — duration_policy=None leaves the event stream unchanged
"""

import asyncio
import json
import time

import pytest

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.approval import (
    ApprovalController,
    ApprovalPolicy,
    ApprovalResponse,
)
from agentic.agentic_framework.cancellation import CancellationToken
from agentic.agentic_framework.duration_policy import DurationPolicy, RunClock
from agentic.agentic_framework.goal_decomposition import (
    ActionItem,
    GoalState,
)
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.safety_contract import (
    SafetyContractEvaluator,
    SafetyGate,
)
from agentic.agentic_framework.streaming_events import (
    ACTION_COMPLETED,
    ACTION_STARTED,
    ACTION_TIMEOUT,
    APPROVAL_REQUESTED,
    BUDGET_EXCEEDED,
    DEADLINE_EXCEEDED,
    RUN_CANCELLED,
    RUN_COMPLETED,
    RUN_STARTED,
    USAGE_UPDATED,
)
from agentic.agentic_framework.token_budget import BudgetPolicy
from agentic.agentic_framework.tracing import TraceCollector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_LONG = (
    "This is a comprehensive response covering the topic with adequate "
    "detail to satisfy the rule-based critic without forcing revisions. "
    "It includes multiple sentences and clear structure."
)


class SlowLLMAdapter(MockLLMAdapter):
    """Mock adapter whose ``call`` sleeps before returning."""

    def __init__(self, sleep_s: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.sleep_s = sleep_s

    def call(self, prompt: str) -> str:
        if self.sleep_s > 0:
            time.sleep(self.sleep_s)
        return super().call(prompt)


def _make_agent(llm=None, **kwargs):
    """Create an agent with permissive defaults for runtime tests."""
    llm = llm or MockLLMAdapter(default_response=_LONG)
    defaults = dict(
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
    )
    defaults.update(kwargs)
    agent = AgenticLLMWrapper(llm, **defaults)
    agent.new_session()
    evaluator = SafetyContractEvaluator(
        consistency_threshold=0.0,
        alignment_threshold=0.0,
        reversal_risk_threshold=1.0,
        stability_threshold=0.0,
    )
    agent.safety_gate = SafetyGate(evaluator=evaluator)
    return agent


def _two_action_goal_state() -> GoalState:
    """A GoalState with two pending actions of types ``slow`` and ``fast``."""
    return GoalState(
        purpose="run two actions",
        purpose_type="task",
        reasoning_strategy="sequential",
        actions=[
            ActionItem(
                action_id="action_slow",
                description="slow action",
                action_type="slow",
            ),
            ActionItem(
                action_id="action_fast",
                description="fast action",
                action_type="fast",
            ),
        ],
        agency_level="FULL",
        requires_confirmation=False,
        complexity_estimate=0.2,
        confidence=0.9,
    )


def _install_action_handlers(agent, slow_sleep: float):
    """Override ``_execute_single_action`` to support ``slow``/``fast``."""

    def _exec(action):
        if action.action_type == "slow":
            time.sleep(slow_sleep)
            action.status = "completed"
            action.result = "slow done"
        elif action.action_type == "fast":
            action.status = "completed"
            action.result = "fast done"
        else:
            action.status = "skipped"

    agent._execute_single_action = _exec


def _collect(agent, user_input="Hello", **kwargs):
    return list(agent.run_stream(user_input, **kwargs))


def _types(events):
    return [e.event_type for e in events]


# ===================================================================
# 1. Unit — DurationPolicy semantics
# ===================================================================


class TestPolicyUnit:
    def test_default_policy_never_exceeds(self):
        p = DurationPolicy()
        assert p.run_exceeded(0.0) is None
        assert p.run_exceeded(1e9) is None
        assert p.action_exceeded(0.0) is None
        assert p.action_exceeded(1e9) is None

    def test_run_exceeded_boundary(self):
        p = DurationPolicy(max_run_duration_s=1.0)
        assert p.run_exceeded(0.0) is None
        assert p.run_exceeded(1.0) is None  # equal -> within
        reason = p.run_exceeded(1.0001)
        assert reason is not None
        assert "exceeds deadline" in reason

    def test_action_exceeded_boundary(self):
        p = DurationPolicy(max_action_duration_s=2.5)
        assert p.action_exceeded(2.5) is None
        reason = p.action_exceeded(2.50001)
        assert reason is not None
        assert "exceeds deadline" in reason

    def test_run_field_independent_of_action_field(self):
        p = DurationPolicy(max_run_duration_s=1.0)
        assert p.action_exceeded(99.0) is None  # no action cap set
        assert p.run_exceeded(2.0) is not None

    def test_to_dict_round_trip(self):
        p = DurationPolicy(max_run_duration_s=30.0, max_action_duration_s=5.0)
        d = p.to_dict()
        json.dumps(d)
        # Assert the v1 fields without forbidding additive v2+ fields.
        assert d["max_run_duration_s"] == 30.0
        assert d["max_action_duration_s"] == 5.0

    def test_policy_frozen(self):
        p = DurationPolicy(max_run_duration_s=10.0)
        with pytest.raises(AttributeError):
            p.max_run_duration_s = 20.0  # type: ignore[misc]

    def test_run_clock_monotonic_elapsed(self):
        clock = RunClock()
        time.sleep(0.01)
        e1 = clock.elapsed_s()
        e2 = clock.elapsed_s()
        assert e1 > 0
        assert e2 >= e1


# ===================================================================
# 2. Runtime — slow generation triggers DEADLINE_EXCEEDED
# ===================================================================


class TestRuntimeRunDeadline:
    def test_slow_generation_emits_deadline_exceeded(self):
        llm = SlowLLMAdapter(sleep_s=0.15, default_response=_LONG)
        agent = _make_agent(llm=llm)
        agent._goal_state_override = _two_action_goal_state()
        # Override the decompose path so a non-trivial action set is present.
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.0)

        policy = DurationPolicy(max_run_duration_s=0.05)
        events = _collect(agent, duration_policy=policy)
        types = _types(events)

        deadline_evts = [e for e in events if e.event_type == DEADLINE_EXCEEDED]
        assert len(deadline_evts) == 1
        assert ACTION_STARTED not in types
        assert RUN_COMPLETED not in types
        assert types[-1] == DEADLINE_EXCEEDED

        payload = deadline_evts[0].payload
        assert payload["max_run_duration_s"] == 0.05
        assert payload["elapsed_s"] >= 0.05
        assert payload["phase"] == "after_generation"
        assert "exceeds deadline" in payload["reason"]

    def test_no_deadline_completes_normally(self):
        agent = _make_agent()
        events = _collect(agent)
        types = _types(events)
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED
        assert DEADLINE_EXCEEDED not in types
        assert ACTION_TIMEOUT not in types

    def test_within_deadline_completes_normally(self):
        agent = _make_agent()
        policy = DurationPolicy(max_run_duration_s=60.0)
        events = _collect(agent, duration_policy=policy)
        types = _types(events)
        assert types[-1] == RUN_COMPLETED
        assert DEADLINE_EXCEEDED not in types


# ===================================================================
# 3. Runtime — slow tool triggers ACTION_TIMEOUT (non-terminal)
# ===================================================================


class TestRuntimeActionTimeout:
    def test_slow_action_emits_action_timeout_and_continues(self):
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.5)

        policy = DurationPolicy(max_action_duration_s=0.05)
        events = _collect(agent, duration_policy=policy)
        types = _types(events)

        timeouts = [e for e in events if e.event_type == ACTION_TIMEOUT]
        assert len(timeouts) == 1
        # The slow action timed out
        assert timeouts[0].payload["action_id"] == "action_slow"
        assert timeouts[0].payload["max_action_duration_s"] == 0.05
        assert timeouts[0].payload["elapsed_s"] >= 0.05

        # Two ACTION_STARTED events (slow then fast); run continued.
        starts = [e for e in events if e.event_type == ACTION_STARTED]
        assert len(starts) == 2
        # And the run reached RUN_COMPLETED — ACTION_TIMEOUT is non-terminal.
        assert RUN_COMPLETED in types

        # The slow action's ACTION_COMPLETED carries status="timed_out".
        completions = [e for e in events if e.event_type == ACTION_COMPLETED]
        slow_completion = next(
            c for c in completions
            if c.payload["action_id"] == "action_slow"
        )
        assert slow_completion.payload["status"] == "timed_out"

    def test_async_action_timeout(self):
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.5)

        policy = DurationPolicy(max_action_duration_s=0.05)

        async def _run():
            out = []
            async for evt in agent.run_stream_async(
                "Hello", duration_policy=policy,
            ):
                out.append(evt)
            return out

        events = asyncio.run(_run())
        types = _types(events)
        assert ACTION_TIMEOUT in types
        # Even with a slow action, async run continues to RUN_COMPLETED.
        assert RUN_COMPLETED in types


# ===================================================================
# 4. Trace integration
# ===================================================================


class TestTraceFields:
    def test_trace_deadline_exceeded(self):
        llm = SlowLLMAdapter(sleep_s=0.15, default_response=_LONG)
        agent = _make_agent(llm=llm)
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.0)

        collector = TraceCollector()
        policy = DurationPolicy(max_run_duration_s=0.05)
        _collect(agent, duration_policy=policy, trace_collector=collector)
        trace = collector.build_trace()

        assert trace.deadline_exceeded is True
        assert trace.action_timeouts == 0
        assert trace.elapsed_s >= 0.05
        assert trace.max_run_duration_s == 0.05
        assert trace.status == "deadline_exceeded"

    def test_trace_action_timeouts_count(self):
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.5)

        collector = TraceCollector()
        policy = DurationPolicy(max_action_duration_s=0.05)
        _collect(agent, duration_policy=policy, trace_collector=collector)
        trace = collector.build_trace()

        assert trace.deadline_exceeded is False
        assert trace.action_timeouts == 1
        assert trace.max_action_duration_s == 0.05

    def test_trace_no_policy_defaults(self):
        agent = _make_agent()
        collector = TraceCollector()
        _collect(agent, trace_collector=collector)
        trace = collector.build_trace()

        assert trace.deadline_exceeded is False
        assert trace.action_timeouts == 0
        assert trace.max_run_duration_s is None
        assert trace.max_action_duration_s is None
        # Wall-clock-derived fallback is non-negative.
        assert trace.elapsed_s >= 0.0

    def test_trace_to_dict_includes_duration_fields(self):
        agent = _make_agent()
        collector = TraceCollector()
        _collect(agent, trace_collector=collector)
        trace = collector.build_trace()
        d = trace.to_dict()
        json.dumps(d)
        for k in (
            "deadline_exceeded",
            "action_timeouts",
            "elapsed_s",
            "max_run_duration_s",
            "max_action_duration_s",
        ):
            assert k in d
        # Summary mirrors the same keys (it is to_dict minus events).
        for k in (
            "deadline_exceeded",
            "action_timeouts",
            "elapsed_s",
            "max_run_duration_s",
            "max_action_duration_s",
        ):
            assert k in trace.summary


# ===================================================================
# 5. Ordering invariants — cancel > budget > deadline > approve > execute
# ===================================================================


class TestOrderingInvariants:
    def test_cancel_before_deadline_wins(self):
        llm = SlowLLMAdapter(sleep_s=0.15, default_response=_LONG)
        agent = _make_agent(llm=llm)
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.0)

        token = CancellationToken()
        token.cancel("user requested")
        policy = DurationPolicy(max_run_duration_s=0.05)
        events = _collect(
            agent,
            duration_policy=policy,
            cancellation_token=token,
        )
        types = _types(events)
        assert RUN_CANCELLED in types
        assert DEADLINE_EXCEEDED not in types
        assert types[-1] == RUN_CANCELLED

    def test_budget_wins_over_deadline_on_same_check(self):
        # Tiny budget will fire at the post-generation budget check, which
        # comes BEFORE the deadline check by ordering.  Even if the run
        # also overran the deadline, BUDGET_EXCEEDED must be the terminal
        # event.
        llm = SlowLLMAdapter(sleep_s=0.10, default_response=_LONG)
        agent = _make_agent(llm=llm)
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.0)

        budget = BudgetPolicy(max_total_tokens=1)
        deadline = DurationPolicy(max_run_duration_s=0.01)
        events = _collect(
            agent, budget_policy=budget, duration_policy=deadline,
        )
        types = _types(events)
        assert BUDGET_EXCEEDED in types
        assert DEADLINE_EXCEEDED not in types
        assert types[-1] == BUDGET_EXCEEDED

    def test_deadline_before_approval_no_approval_emitted(self):
        # The deadline fires post-generation; an approval-required action
        # must NEVER raise APPROVAL_REQUESTED for a run already past its
        # deadline.
        llm = SlowLLMAdapter(sleep_s=0.10, default_response=_LONG)
        agent = _make_agent(llm=llm)
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.0)

        approvals_emitted = []
        controller = ApprovalController(
            policy=ApprovalPolicy(require_all=True),
            callback=lambda pending: ApprovalResponse(approved=True),
        )

        policy = DurationPolicy(max_run_duration_s=0.01)
        events = _collect(
            agent,
            duration_policy=policy,
            approval_controller=controller,
        )
        types = _types(events)
        approvals_emitted = [
            e for e in events if e.event_type == APPROVAL_REQUESTED
        ]
        assert DEADLINE_EXCEEDED in types
        assert not approvals_emitted
        assert ACTION_STARTED not in types

    def test_deadline_before_any_action_no_action_started(self):
        llm = SlowLLMAdapter(sleep_s=0.15, default_response=_LONG)
        agent = _make_agent(llm=llm)
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_action_handlers(agent, slow_sleep=0.0)

        policy = DurationPolicy(max_run_duration_s=0.05)
        events = _collect(agent, duration_policy=policy)
        types = _types(events)
        assert ACTION_STARTED not in types
        assert types[-1] == DEADLINE_EXCEEDED


# ===================================================================
# 6. Snapshot — duration_policy=None preserves the existing event stream
# ===================================================================


class TestSnapshotRegression:
    def test_event_stream_unchanged_without_policy(self):
        # Fixed scenario: one fast action, no LLM sleep.  Compare the
        # event-type sequence with and without an unset duration_policy.
        def _build_agent():
            agent = _make_agent()
            agent._decompose_goal = lambda _u: _two_action_goal_state()
            _install_action_handlers(agent, slow_sleep=0.0)
            return agent

        baseline_types = _types(_collect(_build_agent()))
        explicit_none = _types(
            _collect(_build_agent(), duration_policy=None),
        )
        assert baseline_types == explicit_none
        # Sanity: no duration events leaked when policy is absent.
        assert DEADLINE_EXCEEDED not in baseline_types
        assert ACTION_TIMEOUT not in baseline_types
        # And the run reached RUN_COMPLETED.
        assert baseline_types[-1] == RUN_COMPLETED
