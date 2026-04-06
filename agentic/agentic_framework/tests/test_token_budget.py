"""
Tests for Token / Cost Budget Tracking (R9)

Validates:
1. Usage metadata collected into traces
2. Estimated accounting works when exact data unavailable
3. Exact adapter-provided accounting respected
4. Budget-exceeded stops further action execution
5. Budget-exceeded event appears in stream/trace
6. Non-budgeted runs behave unchanged
7. Sync and async paths both work
8. Serialization stable / JSON-safe
"""

import asyncio
import json

import pytest

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.llm_adapters import BaseLLMAdapter, MockLLMAdapter
from agentic.agentic_framework.safety_contract import SafetyGate, SafetyContractEvaluator
from agentic.agentic_framework.streaming_events import (
    BUDGET_EXCEEDED,
    GENERATION_COMPLETED,
    RUN_COMPLETED,
    RUN_STARTED,
    USAGE_UPDATED,
    ACTION_STARTED,
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

    def __init__(self, response: str = _LONG, input_tokens: int = 50,
                 output_tokens: int = 100, cost: float = 0.003,
                 model: str = "test-model"):
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


def _make_agent(llm=None, **kwargs):
    """Create agent with sensible test defaults."""
    llm = llm or MockLLMAdapter(default_response=_LONG)
    defaults = dict(
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
    )
    defaults.update(kwargs)
    agent = AgenticLLMWrapper(llm, **defaults)
    agent.new_session()
    return agent


def _make_permissive_agent(llm=None, **kwargs):
    """Create agent with permissive safety gate so actions execute."""
    agent = _make_agent(llm=llm, **kwargs)
    evaluator = SafetyContractEvaluator(
        consistency_threshold=0.0,
        alignment_threshold=0.0,
        reversal_risk_threshold=1.0,
        stability_threshold=0.0,
    )
    agent.safety_gate = SafetyGate(evaluator=evaluator)
    return agent


def _collect_events(agent, user_input="Hello", **kwargs):
    return list(agent.run_stream(user_input, **kwargs))


def _event_types(events):
    return [e.event_type for e in events]


# ===================================================================
# 1. Usage metadata collected into traces
# ===================================================================


class TestUsageInTrace:
    def test_usage_updated_event_emitted(self):
        agent = _make_agent()
        events = _collect_events(agent)
        types = _event_types(events)
        assert USAGE_UPDATED in types

    def test_usage_event_has_token_fields(self):
        agent = _make_agent()
        events = _collect_events(agent)
        usage_events = [e for e in events if e.event_type == USAGE_UPDATED]
        assert len(usage_events) == 1
        p = usage_events[0].payload
        assert "input_tokens" in p
        assert "output_tokens" in p
        assert "total_tokens" in p
        assert "accounting_mode" in p

    def test_trace_has_usage_fields(self):
        agent = _make_agent()
        collector = TraceCollector()
        _collect_events(agent, trace_collector=collector)
        trace = collector.build_trace()
        assert trace.total_tokens > 0
        assert trace.input_tokens > 0
        assert trace.output_tokens > 0

    def test_trace_summary_has_usage(self):
        agent = _make_agent()
        collector = TraceCollector()
        _collect_events(agent, trace_collector=collector)
        trace = collector.build_trace()
        summary = trace.summary
        assert "total_tokens" in summary
        assert "input_tokens" in summary
        assert "estimated_cost" in summary
        assert "accounting_mode" in summary


# ===================================================================
# 2. Estimated accounting when exact data unavailable
# ===================================================================


class TestEstimatedAccounting:
    def test_mock_adapter_uses_estimation(self):
        agent = _make_agent()
        events = _collect_events(agent)
        usage = [e for e in events if e.event_type == USAGE_UPDATED][0]
        assert usage.payload["accounting_mode"] == "estimated"

    def test_estimated_tokens_reasonable(self):
        text = "Hello world, this is a test prompt"
        estimated = estimate_tokens(text)
        # ~34 chars / 4 ≈ 8 tokens
        assert 5 <= estimated <= 15

    def test_empty_text_gives_zero(self):
        assert estimate_tokens("") == 0

    def test_trace_accounting_mode_estimated(self):
        agent = _make_agent()
        collector = TraceCollector()
        _collect_events(agent, trace_collector=collector)
        trace = collector.build_trace()
        assert trace.accounting_mode == "estimated"


# ===================================================================
# 3. Exact adapter-provided accounting respected
# ===================================================================


class TestExactAccounting:
    def test_exact_tokens_from_adapter(self):
        llm = ExactUsageAdapter(
            response=_LONG, input_tokens=42, output_tokens=99,
        )
        agent = _make_agent(llm=llm)
        events = _collect_events(agent)
        usage = [e for e in events if e.event_type == USAGE_UPDATED][0]
        assert usage.payload["input_tokens"] == 42
        assert usage.payload["output_tokens"] == 99
        assert usage.payload["total_tokens"] == 141

    def test_exact_cost_from_adapter(self):
        llm = ExactUsageAdapter(response=_LONG, cost=0.0075)
        agent = _make_agent(llm=llm)
        events = _collect_events(agent)
        usage = [e for e in events if e.event_type == USAGE_UPDATED][0]
        assert usage.payload["estimated_cost"] == 0.0075

    def test_exact_model_from_adapter(self):
        llm = ExactUsageAdapter(response=_LONG, model="gpt-4o")
        agent = _make_agent(llm=llm)
        events = _collect_events(agent)
        usage = [e for e in events if e.event_type == USAGE_UPDATED][0]
        assert usage.payload["model"] == "gpt-4o"

    def test_exact_accounting_mode(self):
        llm = ExactUsageAdapter(response=_LONG)
        agent = _make_agent(llm=llm)
        collector = TraceCollector()
        _collect_events(agent, trace_collector=collector)
        trace = collector.build_trace()
        assert trace.accounting_mode == "exact"


# ===================================================================
# 4. Budget-exceeded stops further action execution
# ===================================================================


class TestBudgetExceeded:
    def test_budget_exceeded_stops_before_actions(self):
        """A tiny budget should stop the run after generation."""
        policy = BudgetPolicy(max_total_tokens=1)  # impossibly small
        agent = _make_permissive_agent()
        events = _collect_events(
            agent, "Search for quantum computing", budget_policy=policy,
        )
        types = _event_types(events)
        assert BUDGET_EXCEEDED in types
        assert ACTION_STARTED not in types
        # Run should NOT have RUN_COMPLETED
        assert RUN_COMPLETED not in types

    def test_budget_exceeded_is_terminal(self):
        policy = BudgetPolicy(max_total_tokens=1)
        agent = _make_agent()
        events = _collect_events(agent, budget_policy=policy)
        types = _event_types(events)
        assert types[-1] == BUDGET_EXCEEDED

    def test_budget_exceeded_event_has_reason(self):
        policy = BudgetPolicy(max_total_tokens=1)
        agent = _make_agent()
        events = _collect_events(agent, budget_policy=policy)
        exceeded = [e for e in events if e.event_type == BUDGET_EXCEEDED][0]
        assert "reason" in exceeded.payload
        assert "exceed" in exceeded.payload["reason"].lower()

    def test_budget_by_cost(self):
        llm = ExactUsageAdapter(response=_LONG, cost=0.10)
        policy = BudgetPolicy(max_cost=0.05)
        agent = _make_agent(llm=llm)
        events = _collect_events(agent, budget_policy=policy)
        types = _event_types(events)
        assert BUDGET_EXCEEDED in types

    def test_budget_by_input_tokens(self):
        llm = ExactUsageAdapter(response=_LONG, input_tokens=500)
        policy = BudgetPolicy(max_input_tokens=100)
        agent = _make_agent(llm=llm)
        events = _collect_events(agent, budget_policy=policy)
        types = _event_types(events)
        assert BUDGET_EXCEEDED in types

    def test_budget_by_output_tokens(self):
        llm = ExactUsageAdapter(response=_LONG, output_tokens=500)
        policy = BudgetPolicy(max_output_tokens=100)
        agent = _make_agent(llm=llm)
        events = _collect_events(agent, budget_policy=policy)
        types = _event_types(events)
        assert BUDGET_EXCEEDED in types


# ===================================================================
# 5. Budget-exceeded event appears in trace
# ===================================================================


class TestBudgetInTrace:
    def test_trace_budget_exceeded_flag(self):
        policy = BudgetPolicy(max_total_tokens=1)
        agent = _make_agent()
        collector = TraceCollector()
        _collect_events(agent, trace_collector=collector, budget_policy=policy)
        trace = collector.build_trace()
        assert trace.budget_exceeded is True

    def test_trace_status_budget_exceeded(self):
        policy = BudgetPolicy(max_total_tokens=1)
        agent = _make_agent()
        collector = TraceCollector()
        _collect_events(agent, trace_collector=collector, budget_policy=policy)
        trace = collector.build_trace()
        assert trace.status == "budget_exceeded"

    def test_trace_no_budget_exceeded_by_default(self):
        agent = _make_agent()
        collector = TraceCollector()
        _collect_events(agent, trace_collector=collector)
        trace = collector.build_trace()
        assert trace.budget_exceeded is False


# ===================================================================
# 6. Non-budgeted runs behave unchanged
# ===================================================================


class TestNoBudgetPolicy:
    def test_run_unchanged(self):
        agent = _make_agent()
        result = agent.run("Hello")
        assert len(result.response) > 10

    def test_stream_unchanged_without_policy(self):
        agent = _make_agent()
        events = _collect_events(agent)
        types = _event_types(events)
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED
        assert BUDGET_EXCEEDED not in types
        # Usage event still emitted
        assert USAGE_UPDATED in types

    def test_within_budget_completes_normally(self):
        policy = BudgetPolicy(max_total_tokens=999999)
        agent = _make_agent()
        events = _collect_events(agent, budget_policy=policy)
        types = _event_types(events)
        assert types[-1] == RUN_COMPLETED
        assert BUDGET_EXCEEDED not in types


# ===================================================================
# 7. Async path works
# ===================================================================


class TestAsyncBudget:
    def test_async_usage_updated(self):
        agent = _make_agent()

        async def _run():
            events = []
            async for evt in agent.run_stream_async("Hello"):
                events.append(evt)
            return events

        events = asyncio.get_event_loop().run_until_complete(_run())
        types = _event_types(events)
        assert USAGE_UPDATED in types

    def test_async_budget_exceeded(self):
        policy = BudgetPolicy(max_total_tokens=1)
        agent = _make_agent()

        async def _run():
            events = []
            async for evt in agent.run_stream_async(
                "Hello", budget_policy=policy,
            ):
                events.append(evt)
            return events

        events = asyncio.get_event_loop().run_until_complete(_run())
        types = _event_types(events)
        assert BUDGET_EXCEEDED in types
        assert RUN_COMPLETED not in types

    def test_async_exact_accounting(self):
        llm = ExactUsageAdapter(response=_LONG, input_tokens=10, output_tokens=20)
        agent = _make_agent(llm=llm)

        async def _run():
            events = []
            async for evt in agent.run_stream_async("Hello"):
                events.append(evt)
            return events

        events = asyncio.get_event_loop().run_until_complete(_run())
        usage = [e for e in events if e.event_type == USAGE_UPDATED][0]
        assert usage.payload["input_tokens"] == 10
        assert usage.payload["output_tokens"] == 20
        assert usage.payload["accounting_mode"] == "exact"


# ===================================================================
# 8. Serialization stable / JSON-safe
# ===================================================================


class TestSerialization:
    def test_usage_stats_to_dict(self):
        u = UsageStats()
        u.record_generation("hello", "world")
        d = u.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # must not raise
        assert d["total_tokens"] > 0
        assert d["accounting_mode"] == "estimated"

    def test_usage_stats_exact_to_dict(self):
        u = UsageStats()
        u.record_generation("hello", "world", exact_input=10, exact_output=20, cost=0.001, model="m1")
        d = u.to_dict()
        json.dumps(d)
        assert d["input_tokens"] == 10
        assert d["output_tokens"] == 20
        assert d["total_tokens"] == 30
        assert d["model"] == "m1"
        assert d["accounting_mode"] == "exact"

    def test_budget_policy_to_dict(self):
        bp = BudgetPolicy(max_total_tokens=5000, max_cost=0.10)
        d = bp.to_dict()
        json.dumps(d)
        assert d["max_total_tokens"] == 5000
        assert d["max_cost"] == 0.10
        assert d["max_input_tokens"] is None

    def test_trace_with_usage_json_serializable(self):
        agent = _make_agent()
        collector = TraceCollector()
        _collect_events(agent, trace_collector=collector)
        trace = collector.build_trace()
        d = trace.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["total_tokens"] > 0

    def test_budget_policy_frozen(self):
        bp = BudgetPolicy(max_total_tokens=100)
        with pytest.raises(AttributeError):
            bp.max_total_tokens = 200


# ===================================================================
# 9. UsageStats model edge cases
# ===================================================================


class TestUsageStatsModel:
    def test_initial_state(self):
        u = UsageStats()
        assert u.total_tokens == 0
        assert u.accounting_mode == "none"

    def test_multiple_recordings(self):
        u = UsageStats()
        u.record_generation("a", "b", exact_input=10, exact_output=20)
        u.record_generation("c", "d", exact_input=5, exact_output=15)
        assert u.input_tokens == 15
        assert u.output_tokens == 35
        assert u.total_tokens == 50

    def test_mixed_accounting(self):
        u = UsageStats()
        u.record_generation("hello", "world", exact_input=10)
        # input is exact, output is estimated → mixed
        assert u.accounting_mode == "mixed"

    def test_budget_policy_not_exceeded(self):
        bp = BudgetPolicy(max_total_tokens=1000)
        u = UsageStats()
        u.record_generation("a", "b", exact_input=10, exact_output=20)
        assert bp.is_exceeded(u) is None

    def test_budget_policy_exceeded(self):
        bp = BudgetPolicy(max_total_tokens=10)
        u = UsageStats()
        u.record_generation("a", "b", exact_input=10, exact_output=20)
        reason = bp.is_exceeded(u)
        assert reason is not None
        assert "30" in reason  # total_tokens = 30
