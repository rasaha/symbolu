"""
Tests for Runtime Tracing (R11)

Validates:
1. Traces collect ordered events for sync runs
2. Traces collect ordered events for async runs
3. Cancellation is reflected in trace summary
4. Errors are reflected in trace summary
5. Blocked safety gate is reflected in trace summary
6. Action execution is reflected in trace summary
7. Trace serialization is stable / JSON-safe
8. Existing non-traced runs still work unchanged
"""

import asyncio
import json

import pytest

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.cancellation import CancellationToken
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.streaming_events import (
    RUN_STARTED,
    GENERATION_STARTED,
    TEXT_CHUNK,
    GENERATION_COMPLETED,
    SAFETY_GATE_RESULT,
    ACTION_COMPLETED,
    RUN_COMPLETED,
    RUN_ERROR,
    RUN_CANCELLED,
)
from agentic.agentic_framework.tracing import (
    AgentRunTrace,
    TraceCollector,
    _build_trace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG_RESPONSE = (
    "This is a sufficiently long and detailed mock response "
    "that should pass basic quality checks in the rule-based critic. "
    "It covers the topic comprehensively and provides useful information "
    "about the subject matter requested by the user."
)


def _make_agent(llm=None, **kwargs):
    llm = llm or MockLLMAdapter(default_response=_LONG_RESPONSE)
    defaults = dict(
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
    )
    defaults.update(kwargs)
    agent = AgenticLLMWrapper(llm, **defaults)
    agent.new_session()
    return agent


# ===================================================================
# 1. Traces collect ordered events for sync runs
# ===================================================================

class TestSyncTraceCollection:
    def test_collector_records_events(self):
        agent = _make_agent()
        collector = TraceCollector()
        events = list(agent.run_stream("Hello", trace_collector=collector))
        assert len(collector) == len(events)
        assert len(collector) > 0

    def test_trace_events_match_yielded_events(self):
        agent = _make_agent()
        collector = TraceCollector()
        yielded = list(agent.run_stream("Hello", trace_collector=collector))
        trace = collector.build_trace()
        assert len(trace.events) == len(yielded)
        for a, b in zip(trace.events, yielded):
            assert a.event_type == b.event_type
            assert a.timestamp == b.timestamp

    def test_trace_event_order(self):
        agent = _make_agent()
        collector = TraceCollector()
        list(agent.run_stream("Hello", trace_collector=collector))
        trace = collector.build_trace()
        types = [e.event_type for e in trace.events]
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED

    def test_run_with_trace_convenience(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        assert isinstance(trace, AgentRunTrace)
        assert trace.status == "completed"
        assert trace.event_count > 0

    def test_run_with_trace_has_run_completed(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        assert trace.has_event_type(RUN_COMPLETED)
        completed = trace.get_events(RUN_COMPLETED)
        assert len(completed) == 1
        assert "result" in completed[0].payload


# ===================================================================
# 2. Traces collect ordered events for async runs
# ===================================================================

class TestAsyncTraceCollection:
    def test_async_collector_records_events(self):
        agent = _make_agent()
        collector = TraceCollector()

        async def _run():
            events = []
            async for evt in agent.run_stream_async("Hello", trace_collector=collector):
                events.append(evt)
            return events

        yielded = asyncio.run(_run())
        assert len(collector) == len(yielded)
        assert len(collector) > 0

    def test_async_trace_status_completed(self):
        agent = _make_agent()
        collector = TraceCollector()

        async def _run():
            async for _ in agent.run_stream_async("Hello", trace_collector=collector):
                pass

        asyncio.run(_run())
        trace = collector.build_trace()
        assert trace.status == "completed"


# ===================================================================
# 3. Cancellation reflected in trace summary
# ===================================================================

class TestTraceCancellation:
    def test_cancelled_trace_status(self):
        token = CancellationToken()
        token.cancel(reason="user abort")
        agent = _make_agent()
        trace = agent.run_with_trace("Hello", cancellation_token=token)
        assert trace.status == "cancelled"
        assert trace.cancelled is True

    def test_cancelled_trace_no_run_completed(self):
        token = CancellationToken()
        token.cancel()
        agent = _make_agent()
        trace = agent.run_with_trace("Hello", cancellation_token=token)
        assert not trace.has_event_type(RUN_COMPLETED)
        assert trace.has_event_type(RUN_CANCELLED)


# ===================================================================
# 4. Errors reflected in trace summary
# ===================================================================

class TestTraceErrors:
    def test_error_trace_status(self):
        class Boom:
            def call(self, prompt):
                raise RuntimeError("kaboom")

        agent = _make_agent(llm=Boom())
        trace = agent.run_with_trace("Hello")
        assert trace.status == "error"
        assert trace.error_occurred is True
        assert "kaboom" in trace.error_message

    def test_error_trace_has_run_error(self):
        class Boom:
            def call(self, prompt):
                raise ValueError("bad")

        agent = _make_agent(llm=Boom())
        trace = agent.run_with_trace("Hello")
        assert trace.has_event_type(RUN_ERROR)
        assert not trace.has_event_type(RUN_COMPLETED)


# ===================================================================
# 5. Blocked safety gate reflected in trace summary
# ===================================================================

class TestTraceSafetyBlocked:
    def test_safety_blocked_field(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        # The summary should have safety_blocked field set based on
        # the safety_gate_result event's eligible field
        safety_events = trace.get_events(SAFETY_GATE_RESULT)
        assert len(safety_events) == 1
        eligible = safety_events[0].payload["eligible"]
        assert trace.safety_blocked == (not eligible)


# ===================================================================
# 6. Action execution reflected in trace summary
# ===================================================================

class TestTraceActions:
    def test_actions_executed_count(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Search for quantum computing papers")
        # Count should match action_completed events with status=completed
        completed = [
            e for e in trace.events
            if e.event_type == ACTION_COMPLETED
            and e.payload.get("status") == "completed"
        ]
        assert trace.actions_executed == len(completed)

    def test_text_chunks_count(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        chunks = [e for e in trace.events if e.event_type == TEXT_CHUNK]
        assert trace.text_chunks == len(chunks)
        assert trace.text_chunks >= 1


# ===================================================================
# 7. Trace serialization
# ===================================================================

class TestTraceSerialization:
    def test_to_dict(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        d = trace.to_dict()
        assert isinstance(d, dict)
        assert "events" in d
        assert "status" in d
        assert "session_id" in d
        assert isinstance(d["events"], list)

    def test_json_serializable(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        d = trace.to_dict()
        # Should not raise
        json_str = json.dumps(d)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["status"] == "completed"

    def test_summary_excludes_events(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        summary = trace.summary
        assert "events" not in summary
        assert "status" in summary
        assert "event_count" in summary

    def test_summary_fields(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        s = trace.summary
        assert s["status"] == "completed"
        assert s["event_count"] > 0
        assert s["started_at"] != ""
        assert s["ended_at"] != ""
        assert isinstance(s["cancelled"], bool)
        assert isinstance(s["error_occurred"], bool)
        assert isinstance(s["safety_blocked"], bool)
        assert isinstance(s["actions_executed"], int)
        assert isinstance(s["text_chunks"], int)


# ===================================================================
# 8. Existing non-traced runs unchanged
# ===================================================================

class TestNonTracedUnchanged:
    def test_run_unchanged(self):
        agent = _make_agent()
        result = agent.run("Hello")
        assert result.response == _LONG_RESPONSE

    def test_run_stream_without_collector(self):
        agent = _make_agent()
        events = list(agent.run_stream("Hello"))
        types = [e.event_type for e in events]
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED

    def test_run_stream_with_none_collector(self):
        agent = _make_agent()
        events = list(agent.run_stream("Hello", trace_collector=None))
        assert events[-1].event_type == RUN_COMPLETED


# ===================================================================
# 9. TraceCollector unit tests
# ===================================================================

class TestTraceCollector:
    def test_empty_collector(self):
        c = TraceCollector()
        assert len(c) == 0
        trace = c.build_trace()
        assert trace.event_count == 0
        assert trace.status == "unknown"

    def test_has_event_type(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        assert trace.has_event_type(RUN_STARTED)
        assert trace.has_event_type(TEXT_CHUNK)
        assert not trace.has_event_type("nonexistent_event")

    def test_get_events(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        texts = trace.get_events(TEXT_CHUNK)
        assert len(texts) >= 1
        for e in texts:
            assert e.event_type == TEXT_CHUNK

    def test_identifiers_from_events(self):
        agent = _make_agent()
        trace = agent.run_with_trace("Hello")
        assert trace.session_id != ""
        assert trace.turn_id == 0


# ===================================================================
# 10. Multi-turn tracing
# ===================================================================

class TestMultiTurnTracing:
    def test_separate_traces_per_turn(self):
        agent = _make_agent()
        t1 = agent.run_with_trace("Turn 1")
        t2 = agent.run_with_trace("Turn 2")
        assert t1.turn_id == 0
        assert t2.turn_id == 1
        assert t1.session_id == t2.session_id
