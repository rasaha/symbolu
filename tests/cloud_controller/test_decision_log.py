"""Tests for Decision Log Formatter — production observability."""

import json
import time

from symbolu.cloud_controller.controller import Controller
from symbolu.cloud_controller.observability.decision_log import (
    DecisionLogEntry,
    DecisionLogFormatter,
    DecisionPhase,
)
from symbolu.cloud_controller.recommend.confidence import (
    ConfidenceLevel,
    ConfidenceResult,
)
from symbolu.cloud_controller.recommend.safety import SafetyResult


# ============================================================
# Helpers
# ============================================================

def _make_action(delta=2, score=0.65, pressure=0.7, coherence=0.8,
                 recommendation="scale_out_2"):
    ctrl = Controller()
    result = ctrl.step(
        metrics={"cpu": 0.7, "memory": 0.5, "latency_p99": 0.6, "error_rate": 0.1},
        current_replicas=5,
    )
    result.replica_delta = delta
    result.action_score = score
    result.pressure = pressure
    result.recommendation = recommendation
    if result.coherence is not None:
        result.coherence.coherence = coherence
    return result


def _make_confidence(level=ConfidenceLevel.HIGH, score=0.65, coherence=0.8):
    return ConfidenceResult(
        level=level,
        action_score=score,
        coherence=coherence,
        should_recommend=level != ConfidenceLevel.NONE,
        reason="test",
    )


def _make_safety(original=3, clamped=2, target=7):
    return SafetyResult(
        original_delta=original,
        clamped_delta=clamped,
        target_replicas=target,
        was_clamped=original != clamped,
        clamp_reason="scale-out limit" if original != clamped else "",
        in_cooldown=False,
        cooldown_remaining=0.0,
    )


# ============================================================
# DecisionLogEntry serialization
# ============================================================

class TestDecisionLogEntry:
    def test_to_dict_includes_required_fields(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.RECOMMEND,
            timestamp=time.time(),
            service="api-gw",
            namespace="prod",
        )
        d = entry.to_dict()
        assert d["phase"] == "recommend"
        assert d["service"] == "api-gw"
        assert d["namespace"] == "prod"
        assert "ts" in d

    def test_to_dict_omits_defaults(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.RECOMMEND,
            timestamp=time.time(),
            service="api-gw",
            namespace="prod",
        )
        d = entry.to_dict()
        assert "action_score" not in d
        assert "verdict" not in d
        assert "approved_by" not in d

    def test_to_dict_includes_non_default_values(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.EXECUTE,
            timestamp=time.time(),
            service="api-gw",
            namespace="prod",
            decision_id="rec-123",
            execution_success=True,
            execution_mode="scale_patch",
        )
        d = entry.to_dict()
        assert d["decision_id"] == "rec-123"
        assert d["execution_success"] is True
        assert d["execution_mode"] == "scale_patch"

    def test_to_json_is_valid_json(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.OUTCOME,
            timestamp=time.time(),
            service="api-gw",
            namespace="prod",
            verdict="positive",
        )
        parsed = json.loads(entry.to_json())
        assert parsed["phase"] == "outcome"
        assert parsed["verdict"] == "positive"

    def test_to_json_compact(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.RECOMMEND,
            timestamp=time.time(),
            service="svc",
            namespace="ns",
        )
        raw = entry.to_json()
        assert " " not in raw  # compact separators

    def test_to_text_format(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.RECOMMEND,
            timestamp=time.time(),
            service="api-gw",
            namespace="prod",
            recommendation="scale_out_2",
            replica_delta=2,
            confidence_level="high",
        )
        text = entry.to_text()
        assert "RECOMMEND" in text
        assert "api-gw/prod" in text
        assert "scale_out_2" in text
        assert "delta=+2" in text
        assert "conf=high" in text

    def test_to_text_suppressed(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.RECOMMEND,
            timestamp=time.time(),
            service="api-gw",
            namespace="prod",
            suppressed=True,
            suppress_reason="In cooldown",
        )
        text = entry.to_text()
        assert "SUPPRESSED(In cooldown)" in text

    def test_to_text_execution_failure(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.EXECUTE,
            timestamp=time.time(),
            service="api-gw",
            namespace="prod",
            execution_success=False,
            execution_error="403 Forbidden",
        )
        text = entry.to_text()
        assert "FAIL(403 Forbidden)" in text

    def test_to_text_execution_success(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.EXECUTE,
            timestamp=time.time(),
            service="api-gw",
            namespace="prod",
            execution_success=True,
        )
        assert "OK" in entry.to_text()

    def test_floats_rounded_in_dict(self):
        entry = DecisionLogEntry(
            phase=DecisionPhase.RECOMMEND,
            timestamp=time.time(),
            service="svc",
            namespace="ns",
            action_score=0.123456789,
        )
        d = entry.to_dict()
        assert d["action_score"] == 0.1235  # 4 decimal places


# ============================================================
# DecisionLogFormatter — from_cycle
# ============================================================

class TestFromCycle:
    def test_basic_cycle(self):
        fmt = DecisionLogFormatter(service="api-gw", namespace="prod")
        action = _make_action()
        confidence = _make_confidence()
        safety = _make_safety()

        entry = fmt.from_cycle(
            action=action,
            confidence=confidence,
            safety=safety,
            recommendation_id="rec-abc",
            current_replicas=5,
        )

        assert entry.phase == DecisionPhase.RECOMMEND
        assert entry.service == "api-gw"
        assert entry.decision_id == "rec-abc"
        assert entry.recommendation == "scale_out_2"
        assert entry.replica_delta == 2  # clamped
        assert entry.target_replicas == 7
        assert entry.confidence_level == "high"
        assert entry.was_clamped is True
        assert entry.pressure == 0.7

    def test_suppressed_cycle(self):
        fmt = DecisionLogFormatter(service="api-gw", namespace="prod")
        action = _make_action(delta=0, recommendation="no_action")
        confidence = _make_confidence(level=ConfidenceLevel.NONE)

        entry = fmt.from_cycle(
            action=action,
            confidence=confidence,
            suppressed=True,
            suppress_reason="Below threshold",
        )

        assert entry.suppressed is True
        assert entry.suppress_reason == "Below threshold"

    def test_cycle_without_safety(self):
        fmt = DecisionLogFormatter(service="svc")
        action = _make_action()
        confidence = _make_confidence()

        entry = fmt.from_cycle(action=action, confidence=confidence)
        assert entry.replica_delta == 2  # falls back to action.replica_delta
        assert entry.target_replicas == 0

    def test_cycle_includes_metrics_snapshot(self):
        fmt = DecisionLogFormatter(service="svc")
        action = _make_action()
        confidence = _make_confidence()

        entry = fmt.from_cycle(action=action, confidence=confidence)
        assert "cpu" in entry.metrics

    def test_cycle_includes_controller_components(self):
        fmt = DecisionLogFormatter(service="svc")
        action = _make_action()
        confidence = _make_confidence()

        entry = fmt.from_cycle(action=action, confidence=confidence)
        assert entry.gain > 0
        assert entry.damping > 0
        assert entry.step == action.step


# ============================================================
# DecisionLogFormatter — from_approval
# ============================================================

class TestFromApproval:
    def test_approval_entry(self):
        fmt = DecisionLogFormatter(service="api-gw", namespace="prod")
        entry = fmt.from_approval(
            recommendation_id="rec-xyz",
            approved_by="ops-team",
            current_replicas=5,
            target_replicas=7,
            execution_mode="scale_patch",
            execution_success=True,
        )

        assert entry.phase == DecisionPhase.EXECUTE
        assert entry.decision_id == "rec-xyz"
        assert entry.approved_by == "ops-team"
        assert entry.replica_delta == 2
        assert entry.execution_success is True

    def test_approval_failure(self):
        fmt = DecisionLogFormatter(service="api-gw")
        entry = fmt.from_approval(
            recommendation_id="rec-fail",
            approved_by="ops",
            current_replicas=5,
            target_replicas=7,
            execution_success=False,
            execution_error="Timeout",
        )
        assert entry.execution_success is False
        assert entry.execution_error == "Timeout"


# ============================================================
# DecisionLogFormatter — from_outcome
# ============================================================

class TestFromOutcome:
    def test_outcome_entry(self):
        fmt = DecisionLogFormatter(service="api-gw", namespace="prod")
        entry = fmt.from_outcome(
            recommendation_id="rec-abc",
            verdict="positive",
            verdict_reason="Latency improved 20%",
            metrics={"latency_p99": 0.2},
        )

        assert entry.phase == DecisionPhase.OUTCOME
        assert entry.verdict == "positive"
        assert entry.verdict_reason == "Latency improved 20%"
        assert entry.metrics["latency_p99"] == 0.2

    def test_outcome_deployment_override(self):
        fmt = DecisionLogFormatter(service="api-gw")
        entry = fmt.from_outcome(
            recommendation_id="rec-1",
            verdict="negative",
            deployment="worker-svc",
        )
        assert entry.service == "worker-svc"


# ============================================================
# DecisionLogFormatter — from_feedback
# ============================================================

class TestFromFeedback:
    def test_feedback_entry(self):
        fmt = DecisionLogFormatter(service="api-gw", namespace="prod")
        entry = fmt.from_feedback(
            signal="boost",
            applied=True,
            adjustments=3,
            total_verdicts=12,
        )

        assert entry.phase == DecisionPhase.FEEDBACK
        assert entry.feedback_signal == "boost"
        assert entry.feedback_applied is True
        assert entry.feedback_adjustments == 3
        assert "12 verdicts" in entry.explanation

    def test_feedback_skipped(self):
        fmt = DecisionLogFormatter(service="api-gw")
        entry = fmt.from_feedback(
            signal="neutral",
            applied=False,
            adjustments=0,
            skip_reason="Insufficient verdicts",
        )
        assert entry.feedback_applied is False
        assert entry.suppress_reason == "Insufficient verdicts"


# ============================================================
# End-to-end: full lifecycle JSON
# ============================================================

class TestEndToEnd:
    def test_full_lifecycle_produces_valid_json(self):
        fmt = DecisionLogFormatter(service="api-gw", namespace="prod")

        entries = [
            fmt.from_cycle(
                action=_make_action(),
                confidence=_make_confidence(),
                safety=_make_safety(),
                recommendation_id="rec-001",
                current_replicas=5,
            ),
            fmt.from_approval(
                recommendation_id="rec-001",
                approved_by="ops",
                current_replicas=5,
                target_replicas=7,
                execution_mode="scale_patch",
                execution_success=True,
            ),
            fmt.from_outcome(
                recommendation_id="rec-001",
                verdict="positive",
            ),
            fmt.from_feedback(
                signal="boost",
                applied=True,
                adjustments=2,
                total_verdicts=5,
            ),
        ]

        for entry in entries:
            raw = entry.to_json()
            parsed = json.loads(raw)
            assert "ts" in parsed
            assert "phase" in parsed
            assert "service" in parsed
