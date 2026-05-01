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
- B2 — lazy session TTL: idle and absolute caps; SESSION_EXPIRED event
  emitted before any run lifecycle; consistent enforcement across
  run / run_stream / run_stream_async; non-streaming entry points raise
  SessionExpiredError; recovery via new_session(); no auto-reset.
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
from agentic.agentic_framework.duration_policy import (
    DurationPolicy,
    SessionExpiredError,
)
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
    SESSION_EXPIRED,
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


# ===================================================================
# B2 — Lazy session TTL
# ===================================================================
#
# These tests force expiry by rewinding the agent's monotonic
# session timestamps backwards, rather than sleeping in real time.
# That keeps the test suite fast and deterministic.
# ===================================================================


def _force_idle_seconds(agent, idle_s: float) -> None:
    """Pretend the session was last touched ``idle_s`` seconds ago."""
    assert agent._session_last_touched_monotonic is not None
    agent._session_last_touched_monotonic -= idle_s


def _force_max_seconds(agent, max_s: float) -> None:
    """Pretend the session was started ``max_s`` seconds ago."""
    assert agent._session_started_monotonic is not None
    agent._session_started_monotonic -= max_s
    # Also move last-touched back so the absolute is reachable
    # without idle also tripping (callers can override afterwards).
    agent._session_last_touched_monotonic -= max_s


class TestB2SessionTTLPolicyUnit:
    def test_default_no_expiry(self):
        p = DurationPolicy()
        assert p.session_exceeded(1e9, 1e9) is None

    def test_idle_only_set(self):
        p = DurationPolicy(session_idle_ttl_s=10.0)
        assert p.session_exceeded(5.0, 1000.0) is None  # max not configured
        assert p.session_exceeded(10.0, 0.0) is None  # equal -> within
        assert p.session_exceeded(10.001, 0.0) == "idle"

    def test_max_only_set(self):
        p = DurationPolicy(session_max_ttl_s=60.0)
        assert p.session_exceeded(1e9, 30.0) is None  # idle not configured
        assert p.session_exceeded(0.0, 60.001) == "max"

    def test_both_set_idle_only_hits(self):
        p = DurationPolicy(session_idle_ttl_s=10.0, session_max_ttl_s=60.0)
        assert p.session_exceeded(11.0, 30.0) == "idle"

    def test_both_set_max_only_hits(self):
        p = DurationPolicy(session_idle_ttl_s=10.0, session_max_ttl_s=60.0)
        assert p.session_exceeded(5.0, 61.0) == "max"

    def test_both_set_both_hit(self):
        p = DurationPolicy(session_idle_ttl_s=10.0, session_max_ttl_s=60.0)
        assert p.session_exceeded(11.0, 61.0) == "both"

    def test_to_dict_includes_session_fields(self):
        p = DurationPolicy(session_idle_ttl_s=30.0, session_max_ttl_s=600.0)
        d = p.to_dict()
        json.dumps(d)
        assert d["session_idle_ttl_s"] == 30.0
        assert d["session_max_ttl_s"] == 600.0

    def test_session_expired_error_carries_payload(self):
        payload = {"session_id": "s1", "reason": "idle"}
        err = SessionExpiredError(payload)
        assert err.payload is payload
        assert "idle" in str(err)


class TestB2SessionTTLRunStream:
    def test_idle_expiry_emits_only_session_expired(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)

        events = list(agent.run_stream("Hello", duration_policy=policy))
        types = _types(events)

        # Exactly one event, and it is SESSION_EXPIRED.
        assert types == [SESSION_EXPIRED]
        # No RUN_STARTED, no RUN_COMPLETED, no usage, no actions.
        for forbidden in (RUN_STARTED, RUN_COMPLETED, ACTION_STARTED):
            assert forbidden not in types

        payload = events[0].payload
        assert payload["reason"] == "idle"
        assert payload["session_idle_ttl_s"] == 1.0
        assert payload["session_max_ttl_s"] is None
        assert payload["idle_elapsed_s"] >= 5.0
        assert payload["session_id"] == agent.session_id

    def test_max_expiry_emits_session_expired(self):
        agent = _make_agent()
        _force_max_seconds(agent, 100.0)
        # Reset idle so only "max" fires (not "both"). Set last-touched
        # back to "now" — the rewind in _force_max_seconds moved it too.
        agent._session_last_touched_monotonic = time.monotonic()
        policy = DurationPolicy(session_max_ttl_s=10.0)

        events = list(agent.run_stream("Hello", duration_policy=policy))
        types = _types(events)
        assert types == [SESSION_EXPIRED]
        assert events[0].payload["reason"] == "max"

    def test_both_expiry_reason(self):
        agent = _make_agent()
        _force_max_seconds(agent, 100.0)  # also rewinds last-touched
        policy = DurationPolicy(
            session_idle_ttl_s=1.0,
            session_max_ttl_s=10.0,
        )

        events = list(agent.run_stream("Hello", duration_policy=policy))
        assert _types(events) == [SESSION_EXPIRED]
        assert events[0].payload["reason"] == "both"

    def test_no_expiry_when_ttl_none(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 1e6)  # ancient session
        # Policy with no session-TTL fields — must not expire.
        policy = DurationPolicy(max_run_duration_s=60.0)

        events = list(agent.run_stream("Hello", duration_policy=policy))
        types = _types(events)
        assert SESSION_EXPIRED not in types
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED

    def test_within_ttl_runs_normally(self):
        agent = _make_agent()
        # session is fresh; idle < TTL.
        policy = DurationPolicy(session_idle_ttl_s=60.0)
        events = list(agent.run_stream("Hello", duration_policy=policy))
        assert SESSION_EXPIRED not in _types(events)
        assert _types(events)[-1] == RUN_COMPLETED


class TestB2SessionTTLAsync:
    def test_async_idle_expiry(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)

        async def _run():
            out = []
            async for evt in agent.run_stream_async(
                "Hello", duration_policy=policy,
            ):
                out.append(evt)
            return out

        events = asyncio.run(_run())
        assert _types(events) == [SESSION_EXPIRED]


class TestB2SessionTTLNonStreaming:
    def test_run_raises_session_expired_error(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)

        with pytest.raises(SessionExpiredError) as exc_info:
            agent.run("Hello", duration_policy=policy)

        payload = exc_info.value.payload
        assert payload["reason"] == "idle"
        assert payload["session_idle_ttl_s"] == 1.0
        assert payload["session_id"] == agent.session_id

    def test_run_no_policy_unchanged(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 1e6)
        # No policy: run() must not check session TTL.
        result = agent.run("Hello")
        assert isinstance(result.response, str)

    def test_run_within_ttl_succeeds(self):
        agent = _make_agent()
        policy = DurationPolicy(session_idle_ttl_s=60.0)
        result = agent.run("Hello", duration_policy=policy)
        assert isinstance(result.response, str)

    def test_touch_session_extends_idle(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)
        # touch_session WITHOUT a policy never raises and resets idle.
        agent.touch_session()
        # Now run_stream should succeed because idle was reset.
        events = list(agent.run_stream("Hello", duration_policy=policy))
        assert SESSION_EXPIRED not in _types(events)
        assert _types(events)[-1] == RUN_COMPLETED

    def test_touch_session_with_policy_raises_on_expiry(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)
        # touch_session WITH a policy enforces expiry.
        with pytest.raises(SessionExpiredError):
            agent.touch_session(duration_policy=policy)


class TestB2SessionTTLNoAutoReset:
    def test_second_call_still_expired_without_new_session(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)

        # First call: expired.
        events1 = list(agent.run_stream("Hello", duration_policy=policy))
        assert _types(events1) == [SESSION_EXPIRED]
        # Internal session_id is preserved (no auto-reset).
        sid_after_expiry = agent.session_id
        assert sid_after_expiry is not None

        # Second call without new_session(): still expired, same session.
        events2 = list(agent.run_stream("Hello", duration_policy=policy))
        assert _types(events2) == [SESSION_EXPIRED]
        assert events2[0].payload["session_id"] == sid_after_expiry

    def test_new_session_recovers(self):
        agent = _make_agent()
        original_sid = agent.session_id
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)

        # Confirm expiry.
        assert _types(list(agent.run_stream(
            "Hello", duration_policy=policy,
        ))) == [SESSION_EXPIRED]

        # Recover.
        new_sid = agent.new_session()
        assert new_sid != original_sid

        # Subsequent call succeeds.
        events = list(agent.run_stream("Hello", duration_policy=policy))
        types = _types(events)
        assert SESSION_EXPIRED not in types
        assert types[-1] == RUN_COMPLETED

    def test_run_recovers_after_new_session(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)
        with pytest.raises(SessionExpiredError):
            agent.run("Hello", duration_policy=policy)
        agent.new_session()
        result = agent.run("Hello", duration_policy=policy)
        assert isinstance(result.response, str)


class TestB2SessionTTLTrace:
    def test_trace_records_session_expiry(self):
        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)
        collector = TraceCollector()

        list(agent.run_stream(
            "Hello",
            duration_policy=policy,
            trace_collector=collector,
        ))
        trace = collector.build_trace()

        assert trace.sessions_expired == 1
        assert trace.session_expired_reason == "idle"
        # Status was promoted to session_expired (no RUN_COMPLETED /
        # RUN_CANCELLED / RUN_ERROR fired).
        assert trace.status == "session_expired"

    def test_trace_no_expiry_defaults(self):
        agent = _make_agent()
        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        trace = collector.build_trace()
        assert trace.sessions_expired == 0
        assert trace.session_expired_reason is None

    def test_trace_to_dict_includes_b2_fields(self):
        agent = _make_agent()
        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        d = collector.build_trace().to_dict()
        json.dumps(d)
        assert "sessions_expired" in d
        assert "session_expired_reason" in d


class TestB2SessionTTLOrdering:
    def test_session_expiry_runs_before_cancel(self):
        """If a session is already expired AND a cancellation token is
        set, SESSION_EXPIRED still wins — session-expiry sits ahead of
        cancel in the v2 invariant."""
        from agentic.agentic_framework.cancellation import CancellationToken

        agent = _make_agent()
        _force_idle_seconds(agent, 5.0)
        policy = DurationPolicy(session_idle_ttl_s=1.0)
        token = CancellationToken()
        token.cancel("user")

        events = list(agent.run_stream(
            "Hello",
            duration_policy=policy,
            cancellation_token=token,
        ))
        types = _types(events)
        assert types == [SESSION_EXPIRED]
        # No RUN_CANCELLED — the session-expiry check happens before
        # any cancellation checkpoint.
        from agentic.agentic_framework.streaming_events import RUN_CANCELLED
        assert RUN_CANCELLED not in types
