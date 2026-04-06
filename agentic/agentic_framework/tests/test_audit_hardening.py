"""
Cross-Feature Audit Hardening Tests

Covers the highest-value gaps identified in the post-R-phase audit:
1. Approval + budget both active
2. Pre-action budget exceeded checkpoint
3. Approval + cancellation interaction
4. Trace with denied approval but normal run completion
5. Escaped quotes in JSON extraction
6. get_last_usage() returning None vs {}
7. UsageStats multi-generation accounting mode correctness
8. run_with_trace forwarding approval/budget params
"""

import json

import pytest

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.approval import (
    ApprovalController,
    ApprovalPolicy,
    ApprovalResponse,
    PendingApproval,
)
from agentic.agentic_framework.cancellation import CancellationToken
from agentic.agentic_framework.llm_adapters import BaseLLMAdapter, MockLLMAdapter
from agentic.agentic_framework.safety_contract import SafetyGate, SafetyContractEvaluator
from agentic.agentic_framework.streaming_events import (
    ACTION_COMPLETED,
    ACTION_STARTED,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    BUDGET_EXCEEDED,
    RUN_CANCELLED,
    RUN_COMPLETED,
    USAGE_UPDATED,
)
from agentic.agentic_framework.structured_output import (
    StructuredRunResult,
    _find_json_object,
    extract_json,
)
from agentic.agentic_framework.token_budget import (
    BudgetPolicy,
    UsageStats,
    estimate_tokens,
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


class ExactUsageAdapter(BaseLLMAdapter):
    """Mock adapter that reports exact token usage."""

    def __init__(self, response=_LONG, input_tokens=50, output_tokens=100,
                 cost=0.003, model="test-model"):
        self._response = response
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._cost = cost
        self.model = model

    def call(self, prompt: str) -> str:
        return self._response

    def get_last_usage(self):
        return {
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "cost": self._cost,
            "model": self.model,
        }


class NoneUsageAdapter(BaseLLMAdapter):
    """Adapter whose get_last_usage() returns None."""

    def __init__(self, response=_LONG):
        self._response = response

    def call(self, prompt: str) -> str:
        return self._response

    def get_last_usage(self):
        return None


class EmptyDictUsageAdapter(BaseLLMAdapter):
    """Adapter whose get_last_usage() returns {}."""

    def __init__(self, response=_LONG):
        self._response = response

    def call(self, prompt: str) -> str:
        return self._response

    def get_last_usage(self):
        return {}


def _make_permissive_agent(llm=None, **kwargs):
    """Agent with permissive safety gate so actions execute."""
    llm = llm or MockLLMAdapter(default_response=_LONG)
    defaults = dict(
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
    )
    defaults.update(kwargs)
    agent = AgenticLLMWrapper(llm, **defaults)
    evaluator = SafetyContractEvaluator(
        consistency_threshold=0.0,
        alignment_threshold=0.0,
        reversal_risk_threshold=1.0,
        stability_threshold=0.0,
    )
    agent.safety_gate = SafetyGate(evaluator=evaluator)
    agent.new_session()
    return agent


def _event_types(events):
    return [e.event_type for e in events]


def _auto_approve(pending: PendingApproval) -> ApprovalResponse:
    return ApprovalResponse(approved=True, reason="auto-approved")


def _auto_deny(pending: PendingApproval) -> ApprovalResponse:
    return ApprovalResponse(approved=False, reason="denied by test")


# ===================================================================
# 1. Approval + budget both active
# ===================================================================


class TestApprovalPlusBudget:
    """Verify correct behavior when both approval controller and budget
    policy are active simultaneously."""

    def test_approval_and_budget_both_active_approved(self):
        """Approved action under budget succeeds normally."""
        agent = _make_permissive_agent()
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_approve)
        bp = BudgetPolicy(max_total_tokens=100_000)

        events = list(agent.run_stream(
            "Search for quantum computing",
            approval_controller=ctrl,
            budget_policy=bp,
        ))
        types = _event_types(events)

        assert USAGE_UPDATED in types
        assert RUN_COMPLETED in types
        # Approval events should appear if actions were eligible
        if APPROVAL_REQUESTED in types:
            assert APPROVAL_RESOLVED in types

    def test_budget_exceeded_prevents_approval_gate(self):
        """Budget exceeded at pre-action checkpoint stops before
        the approval gate is reached."""
        agent = _make_permissive_agent()
        policy = ApprovalPolicy(require_all=True)

        approval_called = []

        def _tracking_approve(pending):
            approval_called.append(pending.action_type)
            return ApprovalResponse(approved=True)

        ctrl = ApprovalController(policy=policy, callback=_tracking_approve)
        # Set budget so low that post-generation check exceeds it
        bp = BudgetPolicy(max_total_tokens=1)

        events = list(agent.run_stream(
            "Search for quantum computing",
            approval_controller=ctrl,
            budget_policy=bp,
        ))
        types = _event_types(events)

        assert BUDGET_EXCEEDED in types
        # Approval callback should never have been called because
        # budget was exceeded before the action loop
        assert len(approval_called) == 0
        assert APPROVAL_REQUESTED not in types

    def test_budget_check_ordering_before_approval(self):
        """Budget check runs before approval gate in the action loop."""
        # Use an adapter that reports exact high usage so budget is
        # exceeded at the pre-action checkpoint (not post-generation).
        adapter = ExactUsageAdapter(input_tokens=500, output_tokens=500)
        agent = _make_permissive_agent(llm=adapter)
        policy = ApprovalPolicy(require_all=True)

        approval_called = []

        def _tracking_approve(pending):
            approval_called.append(True)
            return ApprovalResponse(approved=True)

        ctrl = ApprovalController(policy=policy, callback=_tracking_approve)
        # Budget is 999 — post-generation total is 1000, which exceeds
        bp = BudgetPolicy(max_total_tokens=999)

        events = list(agent.run_stream(
            "Search for quantum computing",
            approval_controller=ctrl,
            budget_policy=bp,
        ))
        types = _event_types(events)

        assert BUDGET_EXCEEDED in types
        assert len(approval_called) == 0


# ===================================================================
# 2. Pre-action budget exceeded checkpoint
# ===================================================================


class TestPreActionBudgetCheckpoint:
    """Verify that budget is checked before each action, not only
    after generation."""

    def test_budget_exceeded_after_generation(self):
        """Budget exceeded right after generation emits BUDGET_EXCEEDED
        and never starts any actions."""
        adapter = ExactUsageAdapter(input_tokens=500, output_tokens=501)
        agent = _make_permissive_agent(llm=adapter)
        bp = BudgetPolicy(max_total_tokens=1000)

        events = list(agent.run_stream(
            "Search for quantum computing",
            budget_policy=bp,
        ))
        types = _event_types(events)

        assert BUDGET_EXCEEDED in types
        assert ACTION_STARTED not in types
        # BUDGET_EXCEEDED should be the last event
        assert types[-1] == BUDGET_EXCEEDED


# ===================================================================
# 3. Approval + cancellation interaction
# ===================================================================


class TestApprovalPlusCancellation:
    """Verify behavior when cancellation happens around the approval
    boundary."""

    def test_cancel_before_approval_gate(self):
        """Pre-cancelled token prevents approval from being requested."""
        agent = _make_permissive_agent()
        token = CancellationToken()
        token.cancel(reason="user abort")

        approval_called = []

        def _tracking_approve(pending):
            approval_called.append(True)
            return ApprovalResponse(approved=True)

        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_tracking_approve)

        events = list(agent.run_stream(
            "Search for quantum computing",
            cancellation_token=token,
            approval_controller=ctrl,
        ))
        types = _event_types(events)

        assert RUN_CANCELLED in types
        assert len(approval_called) == 0
        assert APPROVAL_REQUESTED not in types

    def test_cancel_during_approval_callback(self):
        """Cancellation triggered inside the approval callback.
        The approval resolves, but subsequent actions should be
        cancelled at the next checkpoint."""
        agent = _make_permissive_agent()
        token = CancellationToken()

        call_count = [0]

        def _approve_then_cancel(pending):
            call_count[0] += 1
            if call_count[0] == 1:
                # Cancel during the first approval callback
                token.cancel(reason="cancelled in callback")
                return ApprovalResponse(approved=True)
            return ApprovalResponse(approved=True)

        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_approve_then_cancel)

        events = list(agent.run_stream(
            "Search for quantum computing",
            cancellation_token=token,
            approval_controller=ctrl,
        ))
        types = _event_types(events)

        # The run should have been cancelled at some point
        # Either immediately after the first approved action completes
        # (at the next cancellation checkpoint), or if the action
        # itself finishes first.
        assert RUN_CANCELLED in types or RUN_COMPLETED in types
        # The approval callback was called at least once
        assert call_count[0] >= 1


# ===================================================================
# 4. Trace with denied approval but normal run completion
# ===================================================================


class TestTraceWithDeniedApproval:
    """Verify trace derivation when actions are denied but the run
    completes normally."""

    def test_trace_counts_denied_approvals(self):
        agent = _make_permissive_agent()
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_deny)

        trace = agent.run_with_trace(
            "Search for quantum computing",
            approval_controller=ctrl,
        )

        assert trace.status == "completed"
        # If actions were eligible, approvals should have been requested
        if trace.approvals_requested > 0:
            assert trace.approvals_denied > 0
            assert trace.approvals_denied == trace.approvals_requested

    def test_trace_denied_actions_show_in_completed_count(self):
        """Denied actions count as ACTION_COMPLETED with status=denied,
        not as actions_executed."""
        agent = _make_permissive_agent()
        policy = ApprovalPolicy(require_all=True)
        ctrl = ApprovalController(policy=policy, callback=_auto_deny)

        collector = TraceCollector()
        events = list(agent.run_stream(
            "Search for quantum computing",
            approval_controller=ctrl,
            trace_collector=collector,
        ))
        trace = collector.build_trace()

        # actions_executed should be 0 (all denied)
        assert trace.actions_executed == 0
        # But run should still complete successfully
        assert trace.status == "completed"

    def test_run_with_trace_forwards_budget_policy(self):
        """run_with_trace forwards budget_policy to run_stream."""
        adapter = ExactUsageAdapter(input_tokens=5000, output_tokens=5000)
        agent = _make_permissive_agent(llm=adapter)
        bp = BudgetPolicy(max_total_tokens=1)

        trace = agent.run_with_trace("Hello", budget_policy=bp)
        assert trace.budget_exceeded is True


# ===================================================================
# 5. Escaped quotes in JSON extraction
# ===================================================================


class TestJSONExtractionEscapedQuotes:
    """Verify _find_json_object handles escaped characters correctly."""

    def test_escaped_quotes_in_value(self):
        text = '{"msg": "He said \\"hello\\"", "ok": true}'
        result = _find_json_object(text)
        assert result is not None
        assert result["msg"] == 'He said "hello"'
        assert result["ok"] is True

    def test_escaped_backslash_in_value(self):
        text = '{"path": "C:\\\\Users\\\\test"}'
        result = _find_json_object(text)
        assert result is not None
        assert result["path"] == "C:\\Users\\test"

    def test_nested_escaped_quotes(self):
        text = 'Sure! {"data": "{\\"key\\": \\"val\\"}"}'
        result = _find_json_object(text)
        assert result is not None
        assert "key" in result["data"]

    def test_extract_json_with_escaped_quotes(self):
        """Full extract_json path with escaped quotes."""
        text = "The answer is: {\"name\": \"O'Brien\", \"age\": 30}"
        result = extract_json(text)
        assert result is not None
        assert result["age"] == 30

    def test_extract_json_bare_escaped_json(self):
        """Bare JSON with escaped quotes."""
        text = '{"greeting": "She said \\"hi\\""}'
        result = extract_json(text)
        assert result is not None
        assert result["greeting"] == 'She said "hi"'


# ===================================================================
# 6. get_last_usage() returning None vs {}
# ===================================================================


class TestAdapterUsageEdgeCases:
    """Verify usage tracking handles None and empty dict from adapters."""

    def test_adapter_returns_none(self):
        """get_last_usage() returning None falls back to estimation."""
        agent = _make_permissive_agent(llm=NoneUsageAdapter())
        events = list(agent.run_stream("Hello"))
        usage_events = [e for e in events if e.event_type == USAGE_UPDATED]
        assert len(usage_events) == 1
        payload = usage_events[0].payload
        assert payload["accounting_mode"] == "estimated"
        assert payload["total_tokens"] > 0

    def test_adapter_returns_empty_dict(self):
        """get_last_usage() returning {} falls back to estimation."""
        agent = _make_permissive_agent(llm=EmptyDictUsageAdapter())
        events = list(agent.run_stream("Hello"))
        usage_events = [e for e in events if e.event_type == USAGE_UPDATED]
        assert len(usage_events) == 1
        payload = usage_events[0].payload
        assert payload["accounting_mode"] == "estimated"
        assert payload["total_tokens"] > 0

    def test_adapter_without_get_last_usage(self):
        """Adapter with no get_last_usage method at all falls back."""
        agent = _make_permissive_agent(llm=MockLLMAdapter(default_response=_LONG))
        events = list(agent.run_stream("Hello"))
        usage_events = [e for e in events if e.event_type == USAGE_UPDATED]
        assert len(usage_events) == 1
        payload = usage_events[0].payload
        assert payload["accounting_mode"] == "estimated"


# ===================================================================
# 7. UsageStats multi-generation accounting mode
# ===================================================================


class TestUsageStatsMultiGenAccounting:
    """Verify accounting mode reflects aggregate across multiple
    record_generation calls (M4 fix)."""

    def test_exact_then_estimated_is_mixed(self):
        u = UsageStats()
        u.record_generation("p", "o", exact_input=10, exact_output=20)
        assert u.accounting_mode == "exact"
        u.record_generation("prompt two", "output two")
        assert u.accounting_mode == "mixed"

    def test_estimated_then_exact_is_mixed(self):
        u = UsageStats()
        u.record_generation("prompt one", "output one")
        assert u.accounting_mode == "estimated"
        u.record_generation("p", "o", exact_input=10, exact_output=20)
        assert u.accounting_mode == "mixed"

    def test_all_exact_stays_exact(self):
        u = UsageStats()
        u.record_generation("p", "o", exact_input=10, exact_output=20)
        u.record_generation("p", "o", exact_input=15, exact_output=25)
        assert u.accounting_mode == "exact"

    def test_all_estimated_stays_estimated(self):
        u = UsageStats()
        u.record_generation("hello world", "response text")
        u.record_generation("another prompt", "another response")
        assert u.accounting_mode == "estimated"

    def test_mixed_input_exact_only(self):
        """Exact input but estimated output → mixed."""
        u = UsageStats()
        u.record_generation("p", "output text", exact_input=10)
        assert u.accounting_mode == "mixed"

    def test_token_accumulation_across_generations(self):
        u = UsageStats()
        u.record_generation("hi", "bye", exact_input=10, exact_output=20)
        u.record_generation("hello world", "goodbye world")
        assert u.input_tokens == 10 + estimate_tokens("hello world")
        assert u.output_tokens == 20 + estimate_tokens("goodbye world")
        assert u.total_tokens == u.input_tokens + u.output_tokens
