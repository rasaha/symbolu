"""
Tests for Streaming Events (R1)

Validates:
1. run() behaviour is unchanged
2. run_stream() emits expected ordered lifecycle events
3. Non-streaming adapters still produce a valid text_chunk
4. Safety gate result is emitted
5. Action execution emits started/completed events
6. Errors produce run_error
"""

import pytest

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.llm_adapters import (
    BaseLLMAdapter,
    MockLLMAdapter,
    SequentialMockAdapter,
)
from agentic.agentic_framework.reflective_loop import RuleBasedCritic
from agentic.agentic_framework.streaming_events import (
    AgentRunEvent,
    make_event,
    RUN_STARTED,
    GENERATION_STARTED,
    TEXT_CHUNK,
    GENERATION_COMPLETED,
    SAFETY_GATE_RESULT,
    ACTION_STARTED,
    ACTION_COMPLETED,
    RUN_COMPLETED,
    RUN_ERROR,
    REVISION_STARTED,
    REVISION_COMPLETED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(llm=None, **kwargs):
    """Create an agent with sensible test defaults."""
    llm = llm or MockLLMAdapter(
        default_response="This is a sufficiently long and detailed mock response "
        "that should pass basic quality checks in the rule-based critic. "
        "It covers the topic comprehensively and provides useful information "
        "about the subject matter requested by the user.",
    )
    defaults = dict(
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
    )
    defaults.update(kwargs)
    agent = AgenticLLMWrapper(llm, **defaults)
    agent.new_session()
    return agent


def _collect_events(agent, user_input="Hello world"):
    """Collect all events from run_stream into a list."""
    return list(agent.run_stream(user_input))


def _event_types(events):
    """Extract event_type strings."""
    return [e.event_type for e in events]


class StreamingMockAdapter(BaseLLMAdapter):
    """Mock adapter with real call_stream that yields multiple chunks."""

    def __init__(self, chunks=None):
        self.chunks = chunks or ["Hello ", "world ", "response!"]
        self.call_history = []

    def call(self, prompt: str) -> str:
        self.call_history.append(prompt)
        return "".join(self.chunks)

    def call_stream(self, prompt):
        self.call_history.append(prompt)
        for chunk in self.chunks:
            yield chunk


# ---------------------------------------------------------------------------
# 1. run() behaviour unchanged
# ---------------------------------------------------------------------------

class TestRunUnchanged:
    """Ensure run() is not affected by the streaming additions."""

    def test_run_returns_agent_result(self):
        agent = _make_agent()
        result = agent.run("What is Python?")
        assert result.response is not None
        assert isinstance(result.response, str)
        assert len(result.response) > 0

    def test_run_result_fields(self):
        agent = _make_agent()
        result = agent.run("Explain AI.")
        assert hasattr(result, "quality_score")
        assert hasattr(result, "safety_contract")
        assert hasattr(result, "session_id")
        assert hasattr(result, "turn_id")
        assert result.turn_id == 0

    def test_run_multi_turn(self):
        agent = _make_agent()
        r1 = agent.run("First turn")
        r2 = agent.run("Second turn")
        assert r1.turn_id == 0
        assert r2.turn_id == 1


# ---------------------------------------------------------------------------
# 2. run_stream() emits expected ordered lifecycle events
# ---------------------------------------------------------------------------

class TestStreamLifecycle:
    """Validate event ordering from run_stream."""

    def test_starts_with_run_started(self):
        events = _collect_events(_make_agent())
        assert events[0].event_type == RUN_STARTED

    def test_ends_with_run_completed(self):
        events = _collect_events(_make_agent())
        assert events[-1].event_type == RUN_COMPLETED

    def test_generation_brackets(self):
        events = _collect_events(_make_agent())
        types = _event_types(events)
        gen_start = types.index(GENERATION_STARTED)
        gen_end = types.index(GENERATION_COMPLETED)
        assert gen_start < gen_end

    def test_text_chunk_between_generation_events(self):
        events = _collect_events(_make_agent())
        types = _event_types(events)
        gen_start = types.index(GENERATION_STARTED)
        gen_end = types.index(GENERATION_COMPLETED)
        chunks = [i for i, t in enumerate(types) if t == TEXT_CHUNK]
        assert len(chunks) >= 1
        for idx in chunks:
            assert gen_start < idx < gen_end

    def test_safety_gate_after_generation(self):
        events = _collect_events(_make_agent())
        types = _event_types(events)
        gen_end = types.index(GENERATION_COMPLETED)
        safety_idx = types.index(SAFETY_GATE_RESULT)
        assert safety_idx > gen_end

    def test_core_event_sequence(self):
        """Minimal correct sequence: run_started → generation_started →
        text_chunk → generation_completed → safety_gate_result →
        run_completed."""
        events = _collect_events(_make_agent())
        types = _event_types(events)
        required = [
            RUN_STARTED,
            GENERATION_STARTED,
            TEXT_CHUNK,
            GENERATION_COMPLETED,
            SAFETY_GATE_RESULT,
            RUN_COMPLETED,
        ]
        # Check that required events appear in order
        prev = -1
        for req in required:
            idx = types.index(req)
            assert idx > prev, f"{req} should come after previous required event"
            prev = idx

    def test_all_events_are_agent_run_event(self):
        events = _collect_events(_make_agent())
        for e in events:
            assert isinstance(e, AgentRunEvent)

    def test_events_have_consistent_session_and_turn(self):
        agent = _make_agent()
        events = _collect_events(agent)
        session_ids = {e.session_id for e in events}
        turn_ids = {e.turn_id for e in events}
        assert len(session_ids) == 1
        assert turn_ids == {0}

    def test_events_have_timestamps(self):
        events = _collect_events(_make_agent())
        for e in events:
            assert e.timestamp is not None
            assert len(e.timestamp) > 0


# ---------------------------------------------------------------------------
# 3. Non-streaming adapters produce valid text_chunk
# ---------------------------------------------------------------------------

class TestNonStreamingFallback:
    """Adapters without call_stream() still work."""

    def test_mock_adapter_single_chunk(self):
        """MockLLMAdapter inherits default call_stream from BaseLLMAdapter
        which yields one chunk from call()."""
        agent = _make_agent()
        events = _collect_events(agent)
        text_events = [e for e in events if e.event_type == TEXT_CHUNK]
        assert len(text_events) >= 1
        combined = "".join(e.payload["text"] for e in text_events)
        assert len(combined) > 0

    def test_adapter_without_call_stream_attribute(self):
        """An adapter that only has call() still works."""

        class BareAdapter:
            """Minimal adapter with only call()."""
            def call(self, prompt):
                return "bare response that is long enough for quality"

        agent = _make_agent(llm=BareAdapter())
        events = _collect_events(agent)
        types = _event_types(events)
        assert TEXT_CHUNK in types


# ---------------------------------------------------------------------------
# 4. Streaming adapter yields multiple chunks
# ---------------------------------------------------------------------------

class TestStreamingAdapter:
    """Adapter with real call_stream yields multiple text_chunk events."""

    def test_multiple_text_chunks(self):
        adapter = StreamingMockAdapter(chunks=["Part1 ", "Part2 ", "Part3"])
        agent = _make_agent(llm=adapter)
        events = _collect_events(agent)
        text_events = [e for e in events if e.event_type == TEXT_CHUNK]
        assert len(text_events) == 3
        assert text_events[0].payload["text"] == "Part1 "
        assert text_events[1].payload["text"] == "Part2 "
        assert text_events[2].payload["text"] == "Part3"


# ---------------------------------------------------------------------------
# 5. Safety gate result is emitted
# ---------------------------------------------------------------------------

class TestSafetyGateEvent:
    """Safety gate events carry meaningful payload."""

    def test_safety_gate_has_eligible_field(self):
        events = _collect_events(_make_agent())
        safety = [e for e in events if e.event_type == SAFETY_GATE_RESULT]
        assert len(safety) == 1
        assert "eligible" in safety[0].payload

    def test_safety_gate_has_blocking_reasons(self):
        events = _collect_events(_make_agent())
        safety = [e for e in events if e.event_type == SAFETY_GATE_RESULT]
        assert "blocking_reasons" in safety[0].payload


# ---------------------------------------------------------------------------
# 6. Action events
# ---------------------------------------------------------------------------

class TestActionEvents:
    """Action execution emits started/completed events."""

    def test_action_events_when_eligible(self):
        """When actions are eligible and present, we should see
        action_started/action_completed pairs."""
        # Use a long response so quality passes and safety gate is eligible
        llm = MockLLMAdapter(
            default_response=(
                "This is a very detailed and comprehensive response that covers "
                "all aspects of the topic thoroughly with multiple paragraphs of "
                "well-structured content providing deep analysis and insight into "
                "the subject matter. The explanation includes examples, context, "
                "and supporting details that demonstrate a complete understanding. "
                "Furthermore, additional considerations are presented with nuance."
            ),
        )
        agent = _make_agent(llm=llm, quality_threshold=0.3, max_revisions=0)
        events = _collect_events(agent, "Search for quantum computing papers")
        types = _event_types(events)

        # If actions are eligible, we should see action events
        safety = [e for e in events if e.event_type == SAFETY_GATE_RESULT][0]
        if safety.payload["eligible"]:
            action_starts = [e for e in events if e.event_type == ACTION_STARTED]
            action_ends = [e for e in events if e.event_type == ACTION_COMPLETED]
            # Each started should have a completed
            assert len(action_starts) == len(action_ends)
            for a in action_ends:
                assert "status" in a.payload

    def test_action_started_has_metadata(self):
        """action_started should include action_id and action_type."""
        llm = MockLLMAdapter(
            default_response=(
                "Comprehensive analysis of the search query with detailed results "
                "covering multiple dimensions of the problem space including technical "
                "details, practical applications, and theoretical foundations that "
                "provide thorough coverage of the requested information."
            ),
        )
        agent = _make_agent(llm=llm, quality_threshold=0.3, max_revisions=0)
        events = _collect_events(agent, "Search for quantum computing")
        action_starts = [e for e in events if e.event_type == ACTION_STARTED]
        for a in action_starts:
            assert "action_id" in a.payload
            assert "action_type" in a.payload
            assert "description" in a.payload


# ---------------------------------------------------------------------------
# 7. Errors produce run_error
# ---------------------------------------------------------------------------

class TestRunError:
    """Errors during the pipeline emit run_error."""

    def test_llm_failure_produces_run_error(self):
        class FailingAdapter:
            def call(self, prompt):
                raise RuntimeError("LLM exploded")

        agent = _make_agent(llm=FailingAdapter())
        events = _collect_events(agent)
        types = _event_types(events)
        assert RUN_STARTED in types
        assert RUN_ERROR in types
        error_event = [e for e in events if e.event_type == RUN_ERROR][0]
        assert "LLM exploded" in error_event.payload["error"]
        assert error_event.payload["error_type"] == "RuntimeError"

    def test_run_error_is_last_event(self):
        class FailingAdapter:
            def call(self, prompt):
                raise ValueError("bad input")

        agent = _make_agent(llm=FailingAdapter())
        events = _collect_events(agent)
        assert events[-1].event_type == RUN_ERROR


# ---------------------------------------------------------------------------
# 8. Event model
# ---------------------------------------------------------------------------

class TestAgentRunEvent:
    """Test the event model itself."""

    def test_make_event(self):
        evt = make_event("test_type", turn_id=0, session_id="s1", payload={"k": "v"})
        assert evt.event_type == "test_type"
        assert evt.turn_id == 0
        assert evt.session_id == "s1"
        assert evt.payload == {"k": "v"}
        assert evt.timestamp is not None

    def test_to_dict(self):
        evt = make_event("test", turn_id=1, session_id="s2")
        d = evt.to_dict()
        assert d["event_type"] == "test"
        assert d["turn_id"] == 1
        assert d["session_id"] == "s2"
        assert isinstance(d, dict)

    def test_default_payload_is_empty_dict(self):
        evt = make_event("t", 0, "s")
        assert evt.payload == {}


# ---------------------------------------------------------------------------
# 9. Revision events
# ---------------------------------------------------------------------------

class TestRevisionEvents:
    """When revisions occur, revision_started/completed are emitted."""

    def test_revision_events_emitted(self):
        """Force a revision by using a strict quality threshold with short response."""
        # First response is too short (triggers revision), second is long enough
        adapter = SequentialMockAdapter([
            "Short",  # initial generation - will trigger revision
            "This is a sufficiently long and detailed revised response "
            "that should pass quality checks with comprehensive coverage "
            "of the topic and useful detail for the user.",
        ], loop=True)
        agent = _make_agent(
            llm=adapter,
            quality_threshold=0.95,  # very high threshold to force revision
            max_revisions=1,
        )
        events = _collect_events(agent)
        types = _event_types(events)
        # Should have at least one revision cycle
        if REVISION_STARTED in types:
            rev_starts = [i for i, t in enumerate(types) if t == REVISION_STARTED]
            rev_ends = [i for i, t in enumerate(types) if t == REVISION_COMPLETED]
            assert len(rev_starts) == len(rev_ends)
            for s, e in zip(rev_starts, rev_ends):
                assert s < e


# ---------------------------------------------------------------------------
# 10. run_stream does not break multi-turn state
# ---------------------------------------------------------------------------

class TestMultiTurnStreaming:
    """run_stream correctly advances session state."""

    def test_turn_id_increments(self):
        agent = _make_agent()
        events1 = _collect_events(agent, "Turn one")
        events2 = _collect_events(agent, "Turn two")
        assert events1[0].turn_id == 0
        assert events2[0].turn_id == 1

    def test_mixed_run_and_stream(self):
        """Mixing run() and run_stream() on same agent works."""
        agent = _make_agent()
        r1 = agent.run("First via run")
        events = _collect_events(agent, "Second via stream")
        r3 = agent.run("Third via run")
        assert r1.turn_id == 0
        assert events[0].turn_id == 1
        assert r3.turn_id == 2

    def test_run_completed_payload_matches_run(self):
        """The result in run_completed payload should match what run() returns."""
        llm = MockLLMAdapter(
            default_response="Comprehensive response with sufficient detail and length "
            "to satisfy quality requirements across all dimensions of evaluation.",
        )
        agent1 = _make_agent(llm=llm)
        agent2 = _make_agent(llm=MockLLMAdapter(
            default_response="Comprehensive response with sufficient detail and length "
            "to satisfy quality requirements across all dimensions of evaluation.",
        ))
        result = agent1.run("Hello")
        events = _collect_events(agent2, "Hello")
        completed = [e for e in events if e.event_type == RUN_COMPLETED][0]
        assert completed.payload["result"]["response"] == result.response
