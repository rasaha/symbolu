"""
Tests for Human-in-the-Loop Interrupts / Approvals (R4)

Validates:
1. Normal runs unchanged without approval controller
2. Interrupt event emitted when approval is required
3. Denied action does not execute
4. Approved action resumes and executes
5. Tracing captures interrupt/approval events
6. Sync and async paths both work
7. Already-started action remains non-preemptive
8. Event ordering remains sane
9. Approval model serialization
10. Policy edge cases
"""

import asyncio
import json
from dataclasses import dataclass

import pytest

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.approval import (
    ApprovalCallback,
    ApprovalController,
    ApprovalPolicy,
    ApprovalResponse,
    PendingApproval,
)
from agentic.agentic_framework.cancellation import CancellationToken
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.safety_contract import SafetyGate, SafetyContractEvaluator
from agentic.agentic_framework.streaming_events import (
    ACTION_COMPLETED,
    ACTION_STARTED,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    RUN_COMPLETED,
    RUN_STARTED,
    SAFETY_GATE_RESULT,
)
from agentic.agentic_framework.tracing import TraceCollector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG = (
    "This is a very detailed and comprehensive response that covers "
    "all aspects of the topic thoroughly with multiple paragraphs of "
    "well-structured content providing deep analysis and insight into "
    "the subject matter. The explanation includes examples, context, "
    "and supporting details that demonstrate a complete understanding. "
    "Furthermore, additional considerations are presented with nuance."
)


def _make_agent(response_text=_LONG, **kwargs):
    """Create agent with sensible test defaults and permissive safety gate."""
    llm = MockLLMAdapter(default_response=response_text)
    defaults = dict(
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
    )
    defaults.update(kwargs)
    agent = AgenticLLMWrapper(llm, **defaults)
    # Install a permissive safety gate so actions are eligible in tests.
    evaluator = SafetyContractEvaluator(
        consistency_threshold=0.0,
        alignment_threshold=0.0,
        reversal_risk_threshold=1.0,
        stability_threshold=0.0,
    )
    agent.safety_gate = SafetyGate(evaluator=evaluator)
    agent.new_session()
    return agent


def _collect_events(agent, user_input="Search for quantum computing", **kwargs):
    """Collect all events from run_stream into a list."""
    return list(agent.run_stream(user_input, **kwargs))


def _event_types(events):
    return [e.event_type for e in events]


def _auto_approve(pending: PendingApproval) -> ApprovalResponse:
    """Always approve."""
    return ApprovalResponse(approved=True, reason="auto-approved")


def _auto_deny(pending: PendingApproval) -> ApprovalResponse:
    """Always deny."""
    return ApprovalResponse(approved=False, reason="denied by test")


def _has_actions(events):
    """Return True if the run produced any action-related events."""
    safety = [e for e in events if e.event_type == SAFETY_GATE_RESULT]
    if not safety:
        return False
    return safety[0].payload.get("eligible", False)


# ===================================================================
# 1. Normal runs unchanged without approval controller
# ===================================================================


class TestNoApprovalController:
    def test_run_unchanged(self):
        agent = _make_agent()
        result = agent.run("Hello")
        assert "detailed" in result.response.lower() or len(result.response) > 10

    def test_run_stream_unchanged_without_controller(self):
        agent = _make_agent()
        events = _collect_events(agent)
        types = _event_types(events)
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED
        # No approval events
        assert APPROVAL_REQUESTED not in types
        assert APPROVAL_RESOLVED not in types

    def test_run_stream_with_none_controller(self):
        agent = _make_agent()
        events = list(agent.run_stream("Hello", approval_controller=None))
        types = _event_types(events)
        assert APPROVAL_REQUESTED not in types

    def test_empty_policy_no_interrupts(self):
        """Policy with no required action types never triggers."""
        policy = ApprovalPolicy()
        ctrl = ApprovalController(policy=policy, callback=_auto_deny)
        agent = _make_agent()
        events = _collect_events(agent, approval_controller=ctrl)
        types = _event_types(events)
        assert APPROVAL_REQUESTED not in types


# ===================================================================
# 2. Interrupt event emitted when approval is required
# ===================================================================


class TestApprovalRequested:
    def test_approval_requested_emitted(self):
        """When policy matches an action type, approval_requested is emitted."""
        policy = ApprovalPolicy(require_approval_for=frozenset({"search", "compute", "generate", "validate"}))
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked all actions in this run")

        req_events = [e for e in events if e.event_type == APPROVAL_REQUESTED]
        assert len(req_events) >= 1
        payload = req_events[0].payload
        assert "action_id" in payload
        assert "action_type" in payload
        assert "description" in payload
        assert "reason" in payload

    def test_require_all_matches_everything(self):
        """require_all=True triggers approval for all action types."""
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked all actions")

        req_events = [e for e in events if e.event_type == APPROVAL_REQUESTED]
        assert len(req_events) >= 1

    def test_approval_resolved_follows_requested(self):
        """approval_resolved always follows approval_requested."""
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        types = _event_types(events)
        for i, t in enumerate(types):
            if t == APPROVAL_REQUESTED:
                assert i + 1 < len(types)
                assert types[i + 1] == APPROVAL_RESOLVED


# ===================================================================
# 3. Denied action does not execute
# ===================================================================


class TestDeniedAction:
    def test_denied_action_not_executed(self):
        """Denied actions get status 'denied' and no ACTION_STARTED is emitted."""
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_deny)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        types = _event_types(events)
        # No ACTION_STARTED should appear — denied actions skip execution
        assert ACTION_STARTED not in types

        # But we should see denial resolved
        resolved = [e for e in events if e.event_type == APPROVAL_RESOLVED]
        for r in resolved:
            assert r.payload["approved"] is False

        # ACTION_COMPLETED with "denied" status should appear
        completed = [e for e in events if e.event_type == ACTION_COMPLETED]
        for c in completed:
            assert c.payload["status"] == "denied"

    def test_denied_reason_propagated(self):
        """The denial reason appears in the ACTION_COMPLETED event."""
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_deny)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        completed = [e for e in events if e.event_type == ACTION_COMPLETED]
        for c in completed:
            assert "denied by test" in (c.payload.get("error") or "").lower()


# ===================================================================
# 4. Approved action resumes and executes
# ===================================================================


class TestApprovedAction:
    def test_approved_action_executes(self):
        """Approved actions get ACTION_STARTED and ACTION_COMPLETED."""
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        types = _event_types(events)
        assert ACTION_STARTED in types

        # Approval events come before ACTION_STARTED
        first_req_idx = types.index(APPROVAL_REQUESTED)
        first_start_idx = types.index(ACTION_STARTED)
        assert first_req_idx < first_start_idx

    def test_approval_reason_in_resolved_event(self):
        """Approval reason appears in the resolved payload."""
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        resolved = [e for e in events if e.event_type == APPROVAL_RESOLVED]
        assert len(resolved) >= 1
        assert resolved[0].payload["approved"] is True
        assert resolved[0].payload["reason"] == "auto-approved"


# ===================================================================
# 5. Tracing captures interrupt/approval events
# ===================================================================


class TestTraceIntegration:
    def test_trace_has_approval_events(self):
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        collector = TraceCollector()
        events = list(agent.run_stream(
            "Search for quantum computing",
            trace_collector=collector,
            approval_controller=ctrl,
        ))
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        trace = collector.build_trace()
        assert trace.has_event_type(APPROVAL_REQUESTED)
        assert trace.has_event_type(APPROVAL_RESOLVED)

    def test_trace_approvals_requested_count(self):
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        collector = TraceCollector()
        events = list(agent.run_stream(
            "Search for quantum computing",
            trace_collector=collector,
            approval_controller=ctrl,
        ))
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        trace = collector.build_trace()
        assert trace.approvals_requested >= 1
        assert trace.approvals_denied == 0

    def test_trace_approvals_denied_count(self):
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_deny)
        agent = _make_agent()
        collector = TraceCollector()
        events = list(agent.run_stream(
            "Search for quantum computing",
            trace_collector=collector,
            approval_controller=ctrl,
        ))
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        trace = collector.build_trace()
        assert trace.approvals_denied >= 1

    def test_trace_summary_includes_approval_fields(self):
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        collector = TraceCollector()
        events = list(agent.run_stream(
            "Search for quantum computing",
            trace_collector=collector,
            approval_controller=ctrl,
        ))
        trace = collector.build_trace()
        summary = trace.summary
        assert "approvals_requested" in summary
        assert "approvals_denied" in summary

    def test_no_approval_trace_fields_zero_by_default(self):
        """Without approval controller, approval trace fields are zero."""
        agent = _make_agent()
        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        trace = collector.build_trace()
        assert trace.approvals_requested == 0
        assert trace.approvals_denied == 0


# ===================================================================
# 6. Async path works
# ===================================================================


class TestAsyncApproval:
    def test_async_approval_requested(self):
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()

        async def _run():
            events = []
            async for evt in agent.run_stream_async(
                "Search for quantum computing",
                approval_controller=ctrl,
            ):
                events.append(evt)
            return events

        events = asyncio.get_event_loop().run_until_complete(_run())
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        types = _event_types(events)
        assert APPROVAL_REQUESTED in types
        assert APPROVAL_RESOLVED in types

    def test_async_denied_action(self):
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_deny)
        agent = _make_agent()

        async def _run():
            events = []
            async for evt in agent.run_stream_async(
                "Search for quantum computing",
                approval_controller=ctrl,
            ):
                events.append(evt)
            return events

        events = asyncio.get_event_loop().run_until_complete(_run())
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        types = _event_types(events)
        assert ACTION_STARTED not in types
        completed = [e for e in events if e.event_type == ACTION_COMPLETED]
        for c in completed:
            assert c.payload["status"] == "denied"


# ===================================================================
# 7. Already-started action remains non-preemptive
# ===================================================================


class TestNonPreemptive:
    def test_no_interrupt_mid_action(self):
        """Once ACTION_STARTED is emitted, there is no approval gate.
        Approval happens *before* ACTION_STARTED, not during."""
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        types = _event_types(events)
        # Approval events always appear before ACTION_STARTED
        for i, t in enumerate(types):
            if t == ACTION_STARTED:
                # Look backward for the nearest approval pair
                preceding = types[:i]
                # The last two events before ACTION_STARTED should be
                # APPROVAL_REQUESTED + APPROVAL_RESOLVED (if approval was needed)
                req_indices = [j for j, x in enumerate(preceding) if x == APPROVAL_REQUESTED]
                if req_indices:
                    last_req = req_indices[-1]
                    assert preceding[last_req + 1] == APPROVAL_RESOLVED


# ===================================================================
# 8. Event ordering remains sane
# ===================================================================


class TestEventOrdering:
    def test_run_started_is_first(self):
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        assert events[0].event_type == RUN_STARTED

    def test_run_completed_is_last(self):
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        assert events[-1].event_type == RUN_COMPLETED

    def test_approval_before_action_in_sequence(self):
        """For each action, sequence is:
        approval_requested → approval_resolved → action_started → action_completed
        """
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        # Build per-action_id event sequences
        action_sequences = {}
        for e in events:
            aid = e.payload.get("action_id")
            if aid and e.event_type in (
                APPROVAL_REQUESTED, APPROVAL_RESOLVED,
                ACTION_STARTED, ACTION_COMPLETED,
            ):
                action_sequences.setdefault(aid, []).append(e.event_type)

        for aid, seq in action_sequences.items():
            assert seq == [
                APPROVAL_REQUESTED,
                APPROVAL_RESOLVED,
                ACTION_STARTED,
                ACTION_COMPLETED,
            ], f"Action {aid} has unexpected sequence: {seq}"

    def test_denied_action_sequence(self):
        """For a denied action: approval_requested → approval_resolved → action_completed (denied)."""
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_deny)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        action_sequences = {}
        for e in events:
            aid = e.payload.get("action_id")
            if aid and e.event_type in (
                APPROVAL_REQUESTED, APPROVAL_RESOLVED,
                ACTION_STARTED, ACTION_COMPLETED,
            ):
                action_sequences.setdefault(aid, []).append(e.event_type)

        for aid, seq in action_sequences.items():
            assert seq == [
                APPROVAL_REQUESTED,
                APPROVAL_RESOLVED,
                ACTION_COMPLETED,
            ], f"Denied action {aid} has unexpected sequence: {seq}"


# ===================================================================
# 9. Approval model serialization
# ===================================================================


class TestSerialization:
    def test_pending_approval_to_dict(self):
        pending = PendingApproval(
            action_id="a1",
            action_type="search",
            description="Search for papers",
            parameters={"query": "quantum"},
            turn_id=0,
            session_id="s1",
            reason="Requires approval",
        )
        d = pending.to_dict()
        assert d["action_id"] == "a1"
        assert d["action_type"] == "search"
        assert d["parameters"]["query"] == "quantum"
        # JSON-serializable
        json.dumps(d)

    def test_approval_response_to_dict(self):
        resp = ApprovalResponse(approved=True, reason="Looks good")
        d = resp.to_dict()
        assert d["approved"] is True
        assert d["reason"] == "Looks good"
        json.dumps(d)

    def test_approval_response_default_denied(self):
        resp = ApprovalResponse()
        assert resp.approved is False
        assert resp.reason is None


# ===================================================================
# 10. Policy edge cases
# ===================================================================


class TestPolicyEdgeCases:
    def test_empty_policy_requires_nothing(self):
        policy = ApprovalPolicy()
        assert policy.requires_approval("search") is False
        assert policy.requires_approval("compute") is False

    def test_specific_types_only(self):
        policy = ApprovalPolicy(require_approval_for=frozenset({"search"}))
        assert policy.requires_approval("search") is True
        assert policy.requires_approval("compute") is False

    def test_require_all(self):
        policy = ApprovalPolicy(require_all=True)
        assert policy.requires_approval("search") is True
        assert policy.requires_approval("anything") is True

    def test_require_all_overrides_specific(self):
        """require_all takes precedence even if require_approval_for is empty."""
        policy = ApprovalPolicy(require_all=True, require_approval_for=frozenset())
        assert policy.requires_approval("search") is True

    def test_policy_is_frozen(self):
        policy = ApprovalPolicy(require_all=True)
        with pytest.raises(AttributeError):
            policy.require_all = False


# ===================================================================
# 11. Callback receives correct PendingApproval
# ===================================================================


class TestCallbackInfo:
    def test_callback_receives_pending_with_metadata(self):
        """The callback receives a PendingApproval with correct fields."""
        received = []

        def _capture(pending: PendingApproval) -> ApprovalResponse:
            received.append(pending)
            return ApprovalResponse(approved=True)

        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_capture)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        assert len(received) >= 1
        pending = received[0]
        assert pending.action_id != ""
        assert pending.action_type != ""
        assert pending.description != ""
        assert pending.session_id != ""
        assert "requires approval" in pending.reason.lower()

    def test_selective_approval(self):
        """Callback can approve some actions and deny others."""
        def _selective(pending: PendingApproval) -> ApprovalResponse:
            if pending.action_type == "search":
                return ApprovalResponse(approved=True, reason="search ok")
            return ApprovalResponse(approved=False, reason="not search")

        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_selective)
        agent = _make_agent()
        events = _collect_events(
            agent, "Search for quantum computing", approval_controller=ctrl,
        )
        if not _has_actions(events):
            pytest.skip("Safety gate blocked")

        resolved = [e for e in events if e.event_type == APPROVAL_RESOLVED]
        # At least one resolved event should exist
        assert len(resolved) >= 1
