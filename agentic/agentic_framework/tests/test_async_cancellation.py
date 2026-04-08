"""
Tests for Async Streaming + Cancellation (R2)

Validates:
1. Existing sync APIs still work unchanged
2. run_stream_async() emits expected events
3. Cancellation before generation yields terminal RUN_CANCELLED
4. Cancellation during generation stops further chunks
5. Cancellation before action execution prevents actions
6. Already-started action runs to completion (non-preemptive)
7. Event ordering stays sane under cancellation
"""

import asyncio

import pytest

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.cancellation import CancellationToken
from agentic.agentic_framework.llm_adapters import (
    BaseLLMAdapter,
    MockLLMAdapter,
    SequentialMockAdapter,
)
from agentic.agentic_framework.streaming_events import (
    AgentRunEvent,
    RUN_STARTED,
    GENERATION_STARTED,
    TEXT_CHUNK,
    GENERATION_COMPLETED,
    SAFETY_GATE_RESULT,
    ACTION_STARTED,
    ACTION_COMPLETED,
    RUN_COMPLETED,
    RUN_ERROR,
    RUN_CANCELLED,
    REVISION_STARTED,
    REVISION_COMPLETED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_RESPONSE = (
    "This is a sufficiently long and detailed mock response "
    "that should pass basic quality checks in the rule-based critic. "
    "It covers the topic comprehensively and provides useful information "
    "about the subject matter requested by the user."
)


def _make_agent(llm=None, **kwargs):
    llm = llm or MockLLMAdapter(default_response=_DEFAULT_RESPONSE)
    defaults = dict(
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
    )
    defaults.update(kwargs)
    agent = AgenticLLMWrapper(llm, **defaults)
    agent.new_session()
    return agent


def _event_types(events):
    return [e.event_type for e in events]


async def _collect_async(agent, user_input="Hello world", token=None):
    events = []
    async for evt in agent.run_stream_async(user_input, cancellation_token=token):
        events.append(evt)
    return events


class MultiChunkAdapter(BaseLLMAdapter):
    """Yields multiple chunks via call_stream / call_stream_async."""

    def __init__(self, chunks=None):
        self.chunks = chunks or ["A ", "B ", "C"]
        self.call_count = 0

    def call(self, prompt):
        self.call_count += 1
        return "".join(self.chunks)

    def call_stream(self, prompt):
        self.call_count += 1
        for c in self.chunks:
            yield c

    async def call_stream_async(self, prompt):
        self.call_count += 1
        for c in self.chunks:
            yield c


# ===================================================================
# 1. Existing sync APIs still work
# ===================================================================

class TestSyncUnchanged:
    def test_run_still_works(self):
        agent = _make_agent()
        result = agent.run("Hello")
        assert result.response == _DEFAULT_RESPONSE

    def test_run_stream_still_works_without_token(self):
        agent = _make_agent()
        events = list(agent.run_stream("Hello"))
        types = _event_types(events)
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED

    def test_run_stream_with_none_token(self):
        agent = _make_agent()
        events = list(agent.run_stream("Hello", cancellation_token=None))
        assert _event_types(events)[-1] == RUN_COMPLETED


# ===================================================================
# 2. run_stream_async emits expected events
# ===================================================================

class TestAsyncStreamLifecycle:
    def test_basic_lifecycle(self):
        agent = _make_agent()
        events = asyncio.run(_collect_async(agent))
        types = _event_types(events)
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED
        assert GENERATION_STARTED in types
        assert TEXT_CHUNK in types
        assert GENERATION_COMPLETED in types
        assert SAFETY_GATE_RESULT in types

    def test_event_ordering(self):
        agent = _make_agent()
        events = asyncio.run(_collect_async(agent))
        types = _event_types(events)
        required = [
            RUN_STARTED,
            GENERATION_STARTED,
            TEXT_CHUNK,
            GENERATION_COMPLETED,
            SAFETY_GATE_RESULT,
            RUN_COMPLETED,
        ]
        prev = -1
        for req in required:
            idx = types.index(req)
            assert idx > prev, f"{req} out of order"
            prev = idx

    def test_multi_chunk_adapter(self):
        adapter = MultiChunkAdapter(chunks=["X ", "Y ", "Z"])
        agent = _make_agent(llm=adapter)
        events = asyncio.run(_collect_async(agent))
        text_events = [e for e in events if e.event_type == TEXT_CHUNK]
        assert len(text_events) == 3
        assert text_events[0].payload["text"] == "X "

    def test_timestamps_present(self):
        events = asyncio.run(_collect_async(_make_agent()))
        for e in events:
            assert isinstance(e, AgentRunEvent)
            assert e.timestamp

    def test_session_and_turn_consistent(self):
        agent = _make_agent()
        events = asyncio.run(_collect_async(agent))
        sessions = {e.session_id for e in events}
        turns = {e.turn_id for e in events}
        assert len(sessions) == 1
        assert turns == {0}

    def test_error_produces_run_error(self):
        class Boom:
            def call(self, prompt):
                raise RuntimeError("async boom")

        agent = _make_agent(llm=Boom())
        events = asyncio.run(_collect_async(agent))
        types = _event_types(events)
        assert RUN_ERROR in types
        assert types[-1] == RUN_ERROR
        err = [e for e in events if e.event_type == RUN_ERROR][0]
        assert "async boom" in err.payload["error"]


# ===================================================================
# 3. Cancellation BEFORE generation
# ===================================================================

class TestCancelBeforeGeneration:
    def test_sync_cancel_before_generation(self):
        token = CancellationToken()
        token.cancel(reason="too early")
        agent = _make_agent()
        events = list(agent.run_stream("Hello", cancellation_token=token))
        types = _event_types(events)
        assert RUN_STARTED in types
        assert RUN_CANCELLED in types
        assert types[-1] == RUN_CANCELLED
        # No generation should have started
        assert GENERATION_STARTED not in types
        assert TEXT_CHUNK not in types

    def test_async_cancel_before_generation(self):
        token = CancellationToken()
        token.cancel(reason="pre-cancelled")
        agent = _make_agent()
        events = asyncio.run(_collect_async(agent, token=token))
        types = _event_types(events)
        assert types[-1] == RUN_CANCELLED
        assert GENERATION_STARTED not in types

    def test_cancelled_payload_has_reason(self):
        token = CancellationToken()
        token.cancel(reason="user abort")
        agent = _make_agent()
        events = list(agent.run_stream("Hello", cancellation_token=token))
        cancelled = [e for e in events if e.event_type == RUN_CANCELLED][0]
        assert cancelled.payload["reason"] == "user abort"


# ===================================================================
# 4. Cancellation DURING generation (between chunks)
# ===================================================================

class TestCancelDuringGeneration:
    def test_sync_cancel_after_first_chunk(self):
        """Cancel after the first chunk — should stop further emission."""
        token = CancellationToken()
        adapter = MultiChunkAdapter(chunks=["First ", "Second ", "Third"])
        agent = _make_agent(llm=adapter)
        events = []
        for evt in agent.run_stream("Hello", cancellation_token=token):
            events.append(evt)
            if evt.event_type == TEXT_CHUNK:
                token.cancel(reason="mid-stream")
        types = _event_types(events)
        assert RUN_CANCELLED in types
        assert types[-1] == RUN_CANCELLED
        text_chunks = [e for e in events if e.event_type == TEXT_CHUNK]
        # Should have gotten exactly 1 chunk before cancellation was detected
        assert len(text_chunks) == 1

    def test_async_cancel_after_first_chunk(self):
        token = CancellationToken()
        adapter = MultiChunkAdapter(chunks=["A ", "B ", "C"])
        agent = _make_agent(llm=adapter)

        async def _run():
            events = []
            async for evt in agent.run_stream_async("Hello", cancellation_token=token):
                events.append(evt)
                if evt.event_type == TEXT_CHUNK:
                    token.cancel(reason="async mid-stream")
            return events

        events = asyncio.run(_run())
        types = _event_types(events)
        assert types[-1] == RUN_CANCELLED
        text_chunks = [e for e in events if e.event_type == TEXT_CHUNK]
        assert len(text_chunks) == 1

    def test_no_generation_completed_after_cancel(self):
        token = CancellationToken()
        adapter = MultiChunkAdapter(chunks=["One ", "Two"])
        agent = _make_agent(llm=adapter)
        events = []
        for evt in agent.run_stream("Hello", cancellation_token=token):
            events.append(evt)
            if evt.event_type == TEXT_CHUNK:
                token.cancel()
        types = _event_types(events)
        assert GENERATION_COMPLETED not in types


# ===================================================================
# 5. Cancellation BEFORE action execution
# ===================================================================

class TestCancelBeforeActions:
    def test_cancel_after_safety_gate_prevents_actions(self):
        """Cancel right after safety_gate_result — no actions should start."""
        token = CancellationToken()
        agent = _make_agent()
        events = []
        for evt in agent.run_stream("Search for data", cancellation_token=token):
            events.append(evt)
            if evt.event_type == SAFETY_GATE_RESULT:
                token.cancel(reason="stop before actions")
        types = _event_types(events)
        assert ACTION_STARTED not in types
        assert RUN_CANCELLED in types
        assert types[-1] == RUN_CANCELLED


# ===================================================================
# 6. Already-started action is non-preemptive
# ===================================================================

class TestActionNonPreemptive:
    def test_started_action_completes(self):
        """Once action_started is emitted the action runs to completion.
        Cancellation between actions prevents the NEXT action, but
        does not kill an in-flight one."""
        token = CancellationToken()
        agent = _make_agent()
        events = []
        for evt in agent.run_stream("Search for data", cancellation_token=token):
            events.append(evt)
            # Cancel after first action_completed — this means the action
            # that was already started ran to completion.
            if evt.event_type == ACTION_COMPLETED:
                token.cancel(reason="after first action")
        types = _event_types(events)
        # The first action should have both STARTED and COMPLETED
        starts = [e for e in events if e.event_type == ACTION_STARTED]
        completions = [e for e in events if e.event_type == ACTION_COMPLETED]
        if starts:
            # At least as many completions as starts that preceded cancellation
            assert len(completions) >= 1
            assert completions[0].payload["status"] in ("completed", "skipped", "blocked", "failed")


# ===================================================================
# 7. Event ordering under cancellation
# ===================================================================

class TestCancellationEventOrder:
    def test_run_started_always_first(self):
        """Even with pre-cancellation, run_started comes first."""
        token = CancellationToken()
        token.cancel()
        events = list(_make_agent().run_stream("X", cancellation_token=token))
        assert events[0].event_type == RUN_STARTED

    def test_run_cancelled_always_last(self):
        token = CancellationToken()
        token.cancel()
        events = list(_make_agent().run_stream("X", cancellation_token=token))
        assert events[-1].event_type == RUN_CANCELLED

    def test_no_events_after_cancellation(self):
        """No further pipeline events appear after RUN_CANCELLED."""
        token = CancellationToken()
        adapter = MultiChunkAdapter(chunks=["a ", "b "])
        agent = _make_agent(llm=adapter)
        events = []
        for evt in agent.run_stream("Hello", cancellation_token=token):
            events.append(evt)
            if evt.event_type == TEXT_CHUNK:
                token.cancel()
        types = _event_types(events)
        cancel_idx = types.index(RUN_CANCELLED)
        assert cancel_idx == len(types) - 1

    def test_cancel_reason_propagates(self):
        token = CancellationToken()
        token.cancel(reason="test-reason-123")
        events = list(_make_agent().run_stream("X", cancellation_token=token))
        cancelled = events[-1]
        assert cancelled.payload["reason"] == "test-reason-123"


# ===================================================================
# 8. CancellationToken unit tests
# ===================================================================

class TestCancellationToken:
    def test_initial_state(self):
        t = CancellationToken()
        assert not t.is_cancelled
        assert t.reason is None

    def test_cancel(self):
        t = CancellationToken()
        t.cancel(reason="user requested")
        assert t.is_cancelled
        assert t.reason == "user requested"

    def test_cancel_idempotent(self):
        t = CancellationToken()
        t.cancel(reason="first")
        t.cancel(reason="second")
        assert t.reason == "first"

    def test_cancel_no_reason(self):
        t = CancellationToken()
        t.cancel()
        assert t.is_cancelled
        assert t.reason is None

    def test_repr(self):
        t = CancellationToken()
        assert "active" in repr(t)
        t.cancel()
        assert "cancelled" in repr(t)

    def test_thread_safety(self):
        """Concurrent cancel calls don't crash."""
        import threading

        token = CancellationToken()
        errors = []

        def _cancel(n):
            try:
                token.cancel(reason=f"thread-{n}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_cancel, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert token.is_cancelled


# ===================================================================
# 9. Async adapter fallback
# ===================================================================

class TestAsyncAdapterFallback:
    def test_adapter_without_call_stream_async(self):
        """MockLLMAdapter has no call_stream_async — async path falls
        back to asyncio.to_thread(call)."""
        agent = _make_agent()
        events = asyncio.run(_collect_async(agent))
        types = _event_types(events)
        assert TEXT_CHUNK in types
        assert types[-1] == RUN_COMPLETED

    def test_bare_adapter_async(self):
        """Adapter with only call() works in async path."""

        class BareAdapter:
            def call(self, prompt):
                return "bare async response long enough for critic"

        agent = _make_agent(llm=BareAdapter())
        events = asyncio.run(_collect_async(agent))
        types = _event_types(events)
        assert TEXT_CHUNK in types
        assert types[-1] == RUN_COMPLETED


# ===================================================================
# 10. Mixed sync/async multi-turn
# ===================================================================

class TestMixedMultiTurn:
    def test_sync_then_async(self):
        agent = _make_agent()
        sync_events = list(agent.run_stream("Turn 1"))
        async_events = asyncio.run(_collect_async(agent, "Turn 2"))
        assert sync_events[0].turn_id == 0
        assert async_events[0].turn_id == 1

    def test_async_then_run(self):
        agent = _make_agent()
        async_events = asyncio.run(_collect_async(agent, "Turn 1"))
        result = agent.run("Turn 2")
        assert async_events[0].turn_id == 0
        assert result.turn_id == 1
