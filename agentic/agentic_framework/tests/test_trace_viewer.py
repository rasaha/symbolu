"""Tests for the trace_viewer formatting utility."""

import pytest

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
    RUN_CANCELLED,
    REVISION_STARTED,
    REVISION_COMPLETED,
    STRUCTURED_VALIDATION,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    USAGE_UPDATED,
    BUDGET_EXCEEDED,
)
from agentic.agentic_framework.tracing import AgentRunTrace, _build_trace
from agentic.agentic_framework.trace_viewer import (
    format_trace,
    format_trace_summary,
    format_trace_timeline,
)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

SID = "test-session"
TID = 0


def _evt(event_type, payload=None):
    return make_event(event_type, TID, SID, payload)


def _completed_trace():
    """A normal completed run with usage."""
    return _build_trace([
        _evt(RUN_STARTED),
        _evt(GENERATION_STARTED),
        _evt(TEXT_CHUNK, {"chunk": "Hello world"}),
        _evt(GENERATION_COMPLETED, {"response": "Hello world", "quality_score": 0.85}),
        _evt(USAGE_UPDATED, {
            "input_tokens": 10, "output_tokens": 20,
            "total_tokens": 30, "estimated_cost": 0.001,
            "accounting_mode": "estimated",
        }),
        _evt(SAFETY_GATE_RESULT, {"eligible": True}),
        _evt(ACTION_STARTED, {"action_type": "search", "description": "Find papers"}),
        _evt(ACTION_COMPLETED, {"action_type": "search", "status": "completed"}),
        _evt(RUN_COMPLETED),
    ])


# -----------------------------------------------------------------------
# Summary tests
# -----------------------------------------------------------------------


class TestSummaryFormat:
    def test_completed_run_summary(self):
        trace = _completed_trace()
        out = format_trace_summary(trace)

        assert "[COMPLETED]" in out
        assert "Actions executed:   1" in out
        assert "Text chunks:        1" in out
        assert "Safety blocked:     no" in out
        assert "Total tokens:       30" in out
        assert "Input tokens:     10" in out
        assert "Output tokens:    20" in out
        assert "Accounting mode:    estimated" in out
        assert "Budget exceeded:    no" in out

    def test_error_run_summary(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(RUN_ERROR, {"error": "Something broke"}),
        ])
        out = format_trace_summary(trace)

        assert "[ERROR]" in out
        assert "Something broke" in out

    def test_cancelled_run_summary(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(RUN_CANCELLED, {"reason": "user requested"}),
        ])
        out = format_trace_summary(trace)

        assert "[CANCELLED]" in out

    def test_budget_exceeded_summary(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(USAGE_UPDATED, {
                "total_tokens": 5000, "accounting_mode": "exact",
            }),
            _evt(BUDGET_EXCEEDED, {"reason": "max_total_tokens exceeded"}),
        ])
        out = format_trace_summary(trace)

        assert "[BUDGET EXCEEDED]" in out
        assert "Budget exceeded:    yes" in out
        assert "Total tokens:       5000" in out

    def test_approval_section_shown_when_present(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(APPROVAL_REQUESTED, {"action_type": "delete"}),
            _evt(APPROVAL_RESOLVED, {"approved": False, "reason": "too risky"}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_summary(trace)

        assert "Approvals requested: 1" in out
        assert "Approvals denied:    1" in out

    def test_approval_section_hidden_when_none(self):
        trace = _completed_trace()
        out = format_trace_summary(trace)

        assert "Approvals requested" not in out
        assert "Approvals denied" not in out

    def test_session_and_turn_shown(self):
        trace = _completed_trace()
        out = format_trace_summary(trace)

        assert SID in out
        assert "Turn:               0" in out

    def test_safety_blocked_shown(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(SAFETY_GATE_RESULT, {"eligible": False, "blocking_reasons": ["low coherence"]}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_summary(trace)

        assert "Safety blocked:     yes" in out


# -----------------------------------------------------------------------
# Timeline tests
# -----------------------------------------------------------------------


class TestTimelineFormat:
    def test_completed_run_timeline(self):
        trace = _completed_trace()
        out = format_trace_timeline(trace)

        assert "Event Timeline" in out
        assert "RUN START" in out
        assert "GEN START" in out
        assert "TEXT" in out
        assert "GEN DONE" in out
        assert "SAFETY" in out
        assert "ACTION >>" in out
        assert "ACTION <<" in out
        assert "RUN DONE" in out
        assert "9 events total" in out

    def test_event_ordering_preserved(self):
        trace = _completed_trace()
        out = format_trace_timeline(trace)
        lines = out.split("\n")
        event_lines = [l.strip() for l in lines if l.strip().startswith(("1.", "2.", "3."))]

        assert event_lines[0].startswith("1.")
        assert "RUN START" in event_lines[0]
        assert event_lines[1].startswith("2.")
        assert "GEN START" in event_lines[1]

    def test_generation_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(GENERATION_COMPLETED, {
                "response": "A" * 100,
                "quality_score": 0.92,
            }),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "quality=0.92" in out
        assert "..." in out  # response truncated

    def test_action_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(ACTION_STARTED, {"action_type": "search", "description": "Find papers"}),
            _evt(ACTION_COMPLETED, {"action_type": "search", "status": "completed"}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "search: Find papers" in out
        assert "search: completed" in out

    def test_action_error_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(ACTION_COMPLETED, {"action_type": "compute", "status": "error", "error": "timeout"}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "compute: error" in out
        assert "timeout" in out

    def test_approval_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(APPROVAL_REQUESTED, {"action_type": "delete", "description": "Remove file"}),
            _evt(APPROVAL_RESOLVED, {"approved": True, "reason": "user confirmed"}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "APPROVE?" in out
        assert "delete: Remove file" in out
        assert "APPROVED" in out
        assert "approved (user confirmed)" in out

    def test_denial_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(APPROVAL_RESOLVED, {"approved": False, "reason": "too risky"}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "DENIED" in out
        assert "too risky" in out

    def test_budget_exceeded_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(BUDGET_EXCEEDED, {"reason": "max_total_tokens exceeded"}),
        ])
        out = format_trace_timeline(trace)

        assert "BUDGET!" in out
        assert "max_total_tokens exceeded" in out

    def test_structured_validation_pass(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(STRUCTURED_VALIDATION, {"success": True}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "VALIDATE" in out
        assert "passed" in out

    def test_structured_validation_fail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(STRUCTURED_VALIDATION, {"success": False, "validation_error": "missing field 'name'"}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "FAILED" in out
        assert "missing field" in out

    def test_usage_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(USAGE_UPDATED, {"total_tokens": 42, "accounting_mode": "exact"}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "42 tokens (exact)" in out

    def test_safety_blocked_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(SAFETY_GATE_RESULT, {"eligible": False, "blocking_reasons": ["low coherence"]}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "BLOCKED" in out
        assert "low coherence" in out

    def test_safety_eligible_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(SAFETY_GATE_RESULT, {"eligible": True}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "eligible" in out

    def test_revision_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(REVISION_STARTED, {"revision_number": 2}),
            _evt(REVISION_COMPLETED, {"quality_score": 0.88}),
            _evt(RUN_COMPLETED),
        ])
        out = format_trace_timeline(trace)

        assert "revision #2" in out
        assert "quality=0.88" in out

    def test_run_error_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(RUN_ERROR, {"error": "Connection refused"}),
        ])
        out = format_trace_timeline(trace)

        assert "RUN ERR" in out
        assert "Connection refused" in out

    def test_cancellation_detail(self):
        trace = _build_trace([
            _evt(RUN_STARTED),
            _evt(RUN_CANCELLED, {"reason": "user cancelled"}),
        ])
        out = format_trace_timeline(trace)

        assert "CANCELLED" in out
        assert "user cancelled" in out


# -----------------------------------------------------------------------
# Empty / edge-case tests
# -----------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_trace(self):
        trace = _build_trace([])
        out = format_trace_summary(trace)
        assert "[UNKNOWN]" in out
        assert "Events:             0" in out

    def test_empty_timeline(self):
        trace = _build_trace([])
        out = format_trace_timeline(trace)
        assert "no events" in out

    def test_missing_payload_fields(self):
        """Events with empty payloads should not crash."""
        trace = _build_trace([
            _evt(RUN_STARTED, {}),
            _evt(GENERATION_COMPLETED, {}),
            _evt(SAFETY_GATE_RESULT, {}),
            _evt(ACTION_STARTED, {}),
            _evt(ACTION_COMPLETED, {}),
            _evt(APPROVAL_REQUESTED, {}),
            _evt(APPROVAL_RESOLVED, {}),
            _evt(USAGE_UPDATED, {}),
            _evt(STRUCTURED_VALIDATION, {}),
            _evt(REVISION_STARTED, {}),
            _evt(REVISION_COMPLETED, {}),
            _evt(RUN_COMPLETED, {}),
        ])
        # Should not raise
        out = format_trace_timeline(trace)
        assert "12 events total" in out

    def test_format_trace_combines_both(self):
        trace = _completed_trace()
        out = format_trace(trace)

        assert "Trace Summary" in out
        assert "Event Timeline" in out
        assert "[COMPLETED]" in out
        assert "RUN START" in out


# -----------------------------------------------------------------------
# Combined format_trace test
# -----------------------------------------------------------------------


class TestFormatTrace:
    def test_format_trace_returns_string(self):
        trace = _completed_trace()
        out = format_trace(trace)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_format_trace_summary_then_timeline(self):
        trace = _completed_trace()
        out = format_trace(trace)
        summary_pos = out.index("Trace Summary")
        timeline_pos = out.index("Event Timeline")
        assert summary_pos < timeline_pos
