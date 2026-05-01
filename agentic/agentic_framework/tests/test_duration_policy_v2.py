"""
Tests for DurationPolicy v2 — Batch B1 (approval expiry).

Validates:
1. Unit — `approval_ttl_s` field + `approval_exceeded()` semantics; back-
   compat round-trip of `to_dict()`; frozen-dataclass invariant.
2. Runtime — slow approval callback under `approval_ttl_s` emits one
   `APPROVAL_EXPIRED` (and no `APPROVAL_RESOLVED`); marks the action
   `denied` with `error="expired"`; the run continues to the next
   action.
3. Sync + async paths both honour the TTL.
4. Trace counters — `approvals_expired` and `max_approval_ttl_s`
   populated; existing `approvals_denied` still includes the expired
   case (it counts denied-status `APPROVAL_RESOLVED` events; expired
   approvals do NOT emit one — see test).
5. Backward compatibility — `approval_ttl_s=None` produces an event
   stream identical to v1's approval flow.
6. Ordering — approval expiry resolves the action only, never
   terminates the run.
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
from agentic.agentic_framework.duration_policy import DurationPolicy
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
    APPROVAL_EXPIRED,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    RUN_COMPLETED,
)
from agentic.agentic_framework.tracing import TraceCollector


_LONG = (
    "This is a comprehensive response covering the topic with adequate "
    "detail to satisfy the rule-based critic without forcing revisions."
)


def _make_agent(**kwargs):
    llm = MockLLMAdapter(default_response=_LONG)
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
    return GoalState(
        purpose="run two actions",
        purpose_type="task",
        reasoning_strategy="sequential",
        actions=[
            ActionItem(
                action_id="action_a",
                description="first action",
                action_type="search",
            ),
            ActionItem(
                action_id="action_b",
                description="second action",
                action_type="search",
            ),
        ],
        agency_level="FULL",
        requires_confirmation=False,
        complexity_estimate=0.2,
        confidence=0.9,
    )


def _install_fast_executor(agent):
    def _exec(action):
        action.status = "completed"
        action.result = "ok"
    agent._execute_single_action = _exec


def _slow_callback(sleep_s: float, approve: bool = True):
    def _cb(_pending):
        time.sleep(sleep_s)
        return ApprovalResponse(approved=approve)
    return _cb


def _types(events):
    return [e.event_type for e in events]


# ===================================================================
# 1. Unit — policy field & predicate
# ===================================================================


class TestApprovalPolicyUnit:
    def test_default_none_never_exceeds(self):
        p = DurationPolicy()
        assert p.approval_ttl_s is None
        assert p.approval_exceeded(0.0) is None
        assert p.approval_exceeded(1e9) is None

    def test_approval_exceeded_boundary(self):
        p = DurationPolicy(approval_ttl_s=2.0)
        assert p.approval_exceeded(2.0) is None  # equal -> within
        reason = p.approval_exceeded(2.0001)
        assert reason is not None
        assert "exceeds TTL" in reason

    def test_to_dict_includes_field(self):
        p = DurationPolicy(
            max_run_duration_s=30.0,
            approval_ttl_s=15.0,
        )
        d = p.to_dict()
        json.dumps(d)
        assert d["approval_ttl_s"] == 15.0
        assert d["max_run_duration_s"] == 30.0
        assert d["max_action_duration_s"] is None

    def test_policy_still_frozen(self):
        p = DurationPolicy(approval_ttl_s=5.0)
        with pytest.raises(AttributeError):
            p.approval_ttl_s = 10.0  # type: ignore[misc]

    def test_independence_from_other_fields(self):
        p = DurationPolicy(approval_ttl_s=1.0)
        # action_exceeded / run_exceeded must NOT fire on the approval
        # field — they are independent caps.
        assert p.action_exceeded(99.0) is None
        assert p.run_exceeded(99.0) is None


# ===================================================================
# 2. Runtime — sync path
# ===================================================================


class TestApprovalExpirySync:
    def test_slow_callback_emits_approval_expired(self):
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_fast_executor(agent)

        controller = ApprovalController(
            policy=ApprovalPolicy(require_all=True),
            callback=_slow_callback(sleep_s=0.5),
        )
        policy = DurationPolicy(approval_ttl_s=0.05)

        events = list(agent.run_stream(
            "Hello",
            approval_controller=controller,
            duration_policy=policy,
        ))
        types = _types(events)

        expired = [e for e in events if e.event_type == APPROVAL_EXPIRED]
        assert len(expired) == 2  # one per action, both expire
        for evt in expired:
            assert evt.payload["approval_ttl_s"] == 0.05
            assert evt.payload["elapsed_s"] >= 0.05
            assert "exceeds TTL" in evt.payload["reason"]
            assert evt.payload["action_id"] in {"action_a", "action_b"}

        # No APPROVAL_RESOLVED for expired approvals.
        assert APPROVAL_RESOLVED not in types

        # Both approvals were requested.
        assert types.count(APPROVAL_REQUESTED) == 2

        # The expired actions never reached ACTION_STARTED (they were
        # denied at the approval gate).
        assert ACTION_STARTED not in types

        # Two ACTION_COMPLETED with status=denied / error=expired.
        completions = [e for e in events if e.event_type == ACTION_COMPLETED]
        assert len(completions) == 2
        for c in completions:
            assert c.payload["status"] == "denied"
            assert c.payload["error"] == "expired"

        # Run continued and reached RUN_COMPLETED — APPROVAL_EXPIRED is
        # non-terminal.
        assert types[-1] == RUN_COMPLETED

    def test_fast_callback_within_ttl_unchanged(self):
        """When the callback returns within the TTL, behaviour is the
        same as v1 — APPROVAL_RESOLVED fires and APPROVAL_EXPIRED does
        not."""
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_fast_executor(agent)

        controller = ApprovalController(
            policy=ApprovalPolicy(require_all=True),
            callback=lambda _p: ApprovalResponse(approved=True),
        )
        policy = DurationPolicy(approval_ttl_s=10.0)  # generous

        events = list(agent.run_stream(
            "Hello",
            approval_controller=controller,
            duration_policy=policy,
        ))
        types = _types(events)
        assert APPROVAL_EXPIRED not in types
        assert types.count(APPROVAL_RESOLVED) == 2
        assert types.count(ACTION_STARTED) == 2
        assert types[-1] == RUN_COMPLETED


# ===================================================================
# 3. Runtime — async path
# ===================================================================


class TestApprovalExpiryAsync:
    def test_async_slow_callback_emits_approval_expired(self):
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_fast_executor(agent)

        controller = ApprovalController(
            policy=ApprovalPolicy(require_all=True),
            callback=_slow_callback(sleep_s=0.5),
        )
        policy = DurationPolicy(approval_ttl_s=0.05)

        async def _run():
            out = []
            async for evt in agent.run_stream_async(
                "Hello",
                approval_controller=controller,
                duration_policy=policy,
            ):
                out.append(evt)
            return out

        events = asyncio.run(_run())
        types = _types(events)
        assert types.count(APPROVAL_EXPIRED) == 2
        assert APPROVAL_RESOLVED not in types
        assert ACTION_STARTED not in types
        assert types[-1] == RUN_COMPLETED


# ===================================================================
# 4. Trace
# ===================================================================


class TestApprovalExpiryTrace:
    def test_trace_counts_expired_approvals(self):
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_fast_executor(agent)

        controller = ApprovalController(
            policy=ApprovalPolicy(require_all=True),
            callback=_slow_callback(sleep_s=0.5),
        )
        policy = DurationPolicy(approval_ttl_s=0.05)
        collector = TraceCollector()

        list(agent.run_stream(
            "Hello",
            approval_controller=controller,
            duration_policy=policy,
            trace_collector=collector,
        ))
        trace = collector.build_trace()

        assert trace.approvals_expired == 2
        assert trace.max_approval_ttl_s == 0.05
        # The existing approvals_denied counter increments off
        # APPROVAL_RESOLVED with approved=False — expired approvals do
        # NOT emit APPROVAL_RESOLVED, so this stays zero. Operators who
        # want a single "did-not-execute-because-of-approval" count add
        # approvals_denied + approvals_expired.
        assert trace.approvals_denied == 0
        # Run still reached completion.
        assert trace.status == "completed"

    def test_trace_no_expiry_defaults(self):
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_fast_executor(agent)

        controller = ApprovalController(
            policy=ApprovalPolicy(require_all=True),
            callback=lambda _p: ApprovalResponse(approved=True),
        )
        collector = TraceCollector()

        list(agent.run_stream(
            "Hello",
            approval_controller=controller,
            trace_collector=collector,
        ))
        trace = collector.build_trace()

        assert trace.approvals_expired == 0
        assert trace.max_approval_ttl_s is None

    def test_trace_to_dict_includes_b1_fields(self):
        agent = _make_agent()
        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        d = collector.build_trace().to_dict()
        json.dumps(d)
        assert "approvals_expired" in d
        assert "max_approval_ttl_s" in d


# ===================================================================
# 5. Backward compatibility — None policy is a no-op
# ===================================================================


class TestApprovalExpiryBackcompat:
    def test_no_ttl_event_stream_unchanged(self):
        """`approval_ttl_s=None` produces the v1 approval flow exactly:
        APPROVAL_REQUESTED -> APPROVAL_RESOLVED, no APPROVAL_EXPIRED."""
        def _build():
            agent = _make_agent()
            agent._decompose_goal = lambda _u: _two_action_goal_state()
            _install_fast_executor(agent)
            return agent

        controller = ApprovalController(
            policy=ApprovalPolicy(require_all=True),
            callback=lambda _p: ApprovalResponse(approved=True),
        )

        baseline = _types(list(
            _build().run_stream("Hello", approval_controller=controller),
        ))
        explicit_none = _types(list(
            _build().run_stream(
                "Hello",
                approval_controller=controller,
                duration_policy=None,
            ),
        ))
        ttl_none = _types(list(
            _build().run_stream(
                "Hello",
                approval_controller=controller,
                duration_policy=DurationPolicy(),  # all fields None
            ),
        ))
        assert baseline == explicit_none == ttl_none
        assert APPROVAL_EXPIRED not in baseline


# ===================================================================
# 6. Ordering — approval expiry is non-terminal
# ===================================================================


class TestApprovalExpiryOrdering:
    def test_first_action_expires_second_action_still_runs(self):
        """Approval expires for action_a; action_b must still get a
        chance — its callback either expires or resolves, but the
        runtime must not terminate the run on the first expiry."""
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_fast_executor(agent)

        # Callback is slow on first call, instant on second.
        call_count = {"n": 0}

        def _flaky(_pending):
            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(0.5)
            return ApprovalResponse(approved=True)

        controller = ApprovalController(
            policy=ApprovalPolicy(require_all=True),
            callback=_flaky,
        )
        policy = DurationPolicy(approval_ttl_s=0.05)

        events = list(agent.run_stream(
            "Hello",
            approval_controller=controller,
            duration_policy=policy,
        ))
        types = _types(events)

        # Exactly one APPROVAL_EXPIRED (the first action).
        assert types.count(APPROVAL_EXPIRED) == 1
        # The second approval resolved cleanly.
        assert types.count(APPROVAL_RESOLVED) == 1
        # The second action started and completed.
        assert types.count(ACTION_STARTED) == 1
        # Run reached RUN_COMPLETED.
        assert types[-1] == RUN_COMPLETED
