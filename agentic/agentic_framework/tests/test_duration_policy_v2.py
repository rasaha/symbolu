"""
Tests for DurationPolicy v2.

Batches covered:
- B1 — approval expiry: policy field, APPROVAL_EXPIRED event, runtime
  wrap of the controller callback (sync + async), trace counters,
  ordering invariants.
- B3 — duration observability metrics: `time_to_first_action_s` and
  `time_to_first_approval_s` derived in `_build_trace` from event
  timestamps; defensive handling of missing anchors and malformed
  ordering.
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
    RUN_STARTED,
    make_event,
)
from agentic.agentic_framework.tracing import TraceCollector, _build_trace


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


# ===================================================================
# B3 — Duration observability metrics
# ===================================================================
#
# Pure trace-derivation tests: build event lists by hand and feed them
# through `_build_trace`. No runtime/event-model changes are exercised
# here — the runtime tests above already cover those.
# ===================================================================


def _evt(event_type: str, *, ts: str, turn_id: int = 0,
         session_id: str = "s", payload=None):
    """Build an AgentRunEvent with an explicit ISO timestamp."""
    e = make_event(event_type, turn_id, session_id, payload or {})
    e.timestamp = ts
    return e


class TestB3DurationMetricsUnit:
    def test_time_to_first_action_basic(self):
        events = [
            _evt(RUN_STARTED, ts="2025-01-01T00:00:00+00:00"),
            _evt(ACTION_STARTED, ts="2025-01-01T00:00:01.500000+00:00"),
            _evt(ACTION_COMPLETED, ts="2025-01-01T00:00:02+00:00"),
            _evt(RUN_COMPLETED, ts="2025-01-01T00:00:03+00:00"),
        ]
        trace = _build_trace(events)
        assert trace.time_to_first_action_s == pytest.approx(1.5)
        # No approval requested -> None
        assert trace.time_to_first_approval_s is None

    def test_time_to_first_approval_basic(self):
        events = [
            _evt(RUN_STARTED, ts="2025-01-01T00:00:00+00:00"),
            _evt(APPROVAL_REQUESTED, ts="2025-01-01T00:00:00.250000+00:00"),
            _evt(RUN_COMPLETED, ts="2025-01-01T00:00:05+00:00"),
        ]
        trace = _build_trace(events)
        assert trace.time_to_first_approval_s == pytest.approx(0.25)
        assert trace.time_to_first_action_s is None

    def test_only_first_action_counts(self):
        events = [
            _evt(RUN_STARTED, ts="2025-01-01T00:00:00+00:00"),
            _evt(ACTION_STARTED, ts="2025-01-01T00:00:01+00:00"),
            _evt(ACTION_COMPLETED, ts="2025-01-01T00:00:02+00:00"),
            _evt(ACTION_STARTED, ts="2025-01-01T00:00:10+00:00"),
            _evt(ACTION_COMPLETED, ts="2025-01-01T00:00:11+00:00"),
        ]
        trace = _build_trace(events)
        assert trace.time_to_first_action_s == pytest.approx(1.0)

    def test_only_first_approval_counts(self):
        events = [
            _evt(RUN_STARTED, ts="2025-01-01T00:00:00+00:00"),
            _evt(APPROVAL_REQUESTED, ts="2025-01-01T00:00:00.500000+00:00"),
            _evt(APPROVAL_RESOLVED, ts="2025-01-01T00:00:01+00:00"),
            _evt(APPROVAL_REQUESTED, ts="2025-01-01T00:00:05+00:00"),
        ]
        trace = _build_trace(events)
        assert trace.time_to_first_approval_s == pytest.approx(0.5)

    def test_missing_run_started_returns_none(self):
        events = [
            _evt(ACTION_STARTED, ts="2025-01-01T00:00:01+00:00"),
            _evt(APPROVAL_REQUESTED, ts="2025-01-01T00:00:02+00:00"),
        ]
        trace = _build_trace(events)
        assert trace.time_to_first_action_s is None
        assert trace.time_to_first_approval_s is None

    def test_missing_target_returns_none(self):
        events = [
            _evt(RUN_STARTED, ts="2025-01-01T00:00:00+00:00"),
            _evt(RUN_COMPLETED, ts="2025-01-01T00:00:03+00:00"),
        ]
        trace = _build_trace(events)
        assert trace.time_to_first_action_s is None
        assert trace.time_to_first_approval_s is None

    def test_empty_event_list_returns_none(self):
        trace = _build_trace([])
        assert trace.time_to_first_action_s is None
        assert trace.time_to_first_approval_s is None

    def test_negative_delta_clamped_to_zero(self):
        # Malformed ordering: ACTION_STARTED stamped before RUN_STARTED.
        # Defensive clamp — surfaces the field rather than swallowing it.
        events = [
            _evt(RUN_STARTED, ts="2025-01-01T00:00:05+00:00"),
            _evt(ACTION_STARTED, ts="2025-01-01T00:00:00+00:00"),
        ]
        trace = _build_trace(events)
        assert trace.time_to_first_action_s == 0.0

    def test_unparseable_timestamp_returns_none(self):
        events = [
            _evt(RUN_STARTED, ts="not-a-real-timestamp"),
            _evt(ACTION_STARTED, ts="2025-01-01T00:00:01+00:00"),
        ]
        trace = _build_trace(events)
        assert trace.time_to_first_action_s is None


class TestB3DurationMetricsTraceSurface:
    def test_to_dict_includes_b3_fields(self):
        agent = _make_agent()
        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        d = collector.build_trace().to_dict()
        json.dumps(d)
        assert "time_to_first_action_s" in d
        assert "time_to_first_approval_s" in d

    def test_summary_includes_b3_fields(self):
        agent = _make_agent()
        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        summary = collector.build_trace().summary
        assert "time_to_first_action_s" in summary
        assert "time_to_first_approval_s" in summary

    def test_no_action_no_approval_defaults_to_none(self):
        # MockLLMAdapter produces a run with no actions and no approvals
        # (fresh agent, no goal_state override) — but the rule-based
        # decompose_goal_simple does inject one action. Use a permissive
        # safety gate that blocks every action so none start.
        from agentic.agentic_framework.safety_contract import (
            SafetyContractEvaluator,
            SafetyGate,
        )
        agent = _make_agent()
        # Force the safety gate to deny all actions so ACTION_STARTED
        # is never emitted.
        agent.safety_gate = SafetyGate(
            evaluator=SafetyContractEvaluator(
                consistency_threshold=2.0,  # impossible
                alignment_threshold=2.0,
                reversal_risk_threshold=-1.0,
                stability_threshold=2.0,
            ),
        )
        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        trace = collector.build_trace()
        # Run completed but with safety_blocked, no actions, no approvals
        assert trace.time_to_first_action_s is None
        assert trace.time_to_first_approval_s is None

    def test_real_run_populates_action_metric(self):
        """A real run with a permissive gate emits ACTION_STARTED, so
        time_to_first_action_s should be a non-negative float."""
        agent = _make_agent()
        agent._decompose_goal = lambda _u: _two_action_goal_state()
        _install_fast_executor(agent)

        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        trace = collector.build_trace()
        assert trace.time_to_first_action_s is not None
        assert trace.time_to_first_action_s >= 0.0
        # No approval was requested in this run.
        assert trace.time_to_first_approval_s is None

    def test_real_run_populates_approval_metric(self):
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
        assert trace.time_to_first_approval_s is not None
        assert trace.time_to_first_approval_s >= 0.0
        # ACTION_STARTED also fired (after approval) so the action
        # metric is populated too.
        assert trace.time_to_first_action_s is not None
        assert trace.time_to_first_action_s >= trace.time_to_first_approval_s
