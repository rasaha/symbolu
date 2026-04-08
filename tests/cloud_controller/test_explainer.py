"""Tests for the Explainer module — unified decision explanations."""

import pytest
from symbolu.cloud_controller.controller import Controller, ActionResult
from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.explain.explainer import (
    Audience,
    DecisionCategory,
    Explainer,
    Explanation,
    Factor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def controller():
    return Controller(InfraControllerConfig())


@pytest.fixture
def explainer():
    return Explainer()


def _make_action(controller, cpu=0.5, latency=0.5, error=0.0, memory=0.5) -> ActionResult:
    """Helper to produce an ActionResult with known metrics."""
    return controller.step(
        metrics={"cpu": cpu, "memory": memory, "latency_p99": latency, "error_rate": error},
        current_replicas=5,
    )


# ---------------------------------------------------------------------------
# Basic explain
# ---------------------------------------------------------------------------

class TestExplainerBasic:
    def test_explain_returns_explanation(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        assert isinstance(result, Explanation)
        assert result.timestamp > 0
        assert result.recommendation == action.recommendation

    def test_explain_hold_category(self, controller, explainer):
        action = _make_action(controller, cpu=0.5, latency=0.5)
        result = explainer.explain(action)
        # Low pressure → no scaling → HOLD or OBSERVE
        assert result.category in (DecisionCategory.HOLD, DecisionCategory.OBSERVE)

    def test_explain_suppressed_category(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action, suppress_reason="In cooldown")
        assert result.category == DecisionCategory.SUPPRESSED
        assert result.suppress_reason == "In cooldown"

    def test_explain_with_safety_context(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(
            action,
            confidence_level="high",
            safety_clamped=True,
            safety_reason="Scale-out clamped from +3 to +2",
        )
        assert result.confidence_level == "high"
        assert result.safety_clamped is True
        assert "clamped" in result.safety_reason

    def test_explain_has_factors(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        assert len(result.factors) == 6  # pressure, coherence, plasticity, gain, damping, identity
        names = {f.name for f in result.factors}
        assert "Pressure (S_t)" in names
        assert "Coherence (C_t)" in names
        assert "Plasticity (P_t)" in names
        assert "Gain (G_t)" in names
        assert "Damping (d_t)" in names
        assert "Identity Drift" in names

    def test_explain_has_dominant_factor(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        assert result.dominant_factor != ""
        # Should reference one of the multiplicative components
        assert any(
            name in result.dominant_factor
            for name in ["Pressure", "Plasticity", "Gain", "Damping"]
        )

    def test_explain_has_counterfactual(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        assert result.counterfactual != ""
        assert "threshold" in result.counterfactual.lower() or "maximum" in result.counterfactual.lower()

    def test_explain_component_values(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        assert "pressure" in result.component_values
        assert "coherence" in result.component_values
        assert "plasticity" in result.component_values
        assert "gain" in result.component_values
        assert "damping" in result.component_values
        assert "action_score" in result.component_values


# ---------------------------------------------------------------------------
# Factor influence labeling
# ---------------------------------------------------------------------------

class TestFactorInfluence:
    def test_high_pressure_is_supporting(self, controller, explainer):
        action = _make_action(controller, cpu=0.95, latency=0.9, memory=0.9)
        result = explainer.explain(action)
        pressure_factor = next(f for f in result.factors if "Pressure" in f.name)
        assert pressure_factor.influence == "supporting"

    def test_balanced_pressure_is_neutral(self, controller, explainer):
        action = _make_action(controller, cpu=0.5, latency=0.5, memory=0.5)
        result = explainer.explain(action)
        pressure_factor = next(f for f in result.factors if "Pressure" in f.name)
        assert pressure_factor.influence == "neutral"

    def test_each_factor_has_required_fields(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        for f in result.factors:
            assert isinstance(f.name, str) and f.name
            assert isinstance(f.value, float)
            assert isinstance(f.label, str) and f.label
            assert f.influence in ("supporting", "opposing", "neutral")


# ---------------------------------------------------------------------------
# Audience filtering
# ---------------------------------------------------------------------------

class TestAudienceFiltering:
    def test_operator_audience_is_minimal(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        data = result.for_audience(Audience.OPERATOR)
        assert "summary" in data
        assert "category" in data
        assert "action_score" in data
        # Operator level should NOT include factors or metrics
        assert "factors" not in data
        assert "metrics_snapshot" not in data

    def test_sre_audience_includes_factors(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        data = result.for_audience(Audience.SRE)
        assert "factors" in data
        assert len(data["factors"]) == 6
        assert "dominant_factor" in data
        assert "counterfactual" in data
        assert "component_values" in data
        # SRE level should NOT include full metrics snapshot
        assert "metrics_snapshot" not in data

    def test_audit_audience_includes_everything(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(
            action,
            confidence_level="medium",
            safety_clamped=True,
            safety_reason="clamped",
        )
        data = result.for_audience(Audience.AUDIT)
        assert "factors" in data
        assert "metrics_snapshot" in data
        assert "confidence_level" in data
        assert data["confidence_level"] == "medium"
        assert data["safety_clamped"] is True
        assert "timestamp" in data

    def test_audience_values_are_rounded(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        data = result.for_audience(Audience.SRE)
        for f in data["factors"]:
            # Value should be rounded to 4 decimals
            val_str = str(f["value"])
            if "." in val_str:
                decimals = len(val_str.split(".")[1])
                assert decimals <= 4


# ---------------------------------------------------------------------------
# Text formatting
# ---------------------------------------------------------------------------

class TestTextFormatting:
    def test_operator_text_is_one_line(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        text = result.format_text(Audience.OPERATOR)
        assert "\n" not in text
        assert text == result.summary

    def test_sre_text_includes_factors(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        text = result.format_text(Audience.SRE)
        assert "Pressure" in text
        assert "Coherence" in text
        assert "Dominant:" in text

    def test_audit_text_includes_metrics(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action, confidence_level="high")
        text = result.format_text(Audience.AUDIT)
        assert "Confidence: high" in text
        assert "Metrics:" in text


# ---------------------------------------------------------------------------
# Decision categories with scaling
# ---------------------------------------------------------------------------

class TestDecisionCategories:
    def test_scale_out_category(self, controller, explainer):
        """Generate high enough pressure to trigger scale_out."""
        # Run many cycles with extreme metrics to build up enough state
        config = InfraControllerConfig(
            G_base=3.0,
            action_thresholds={"no_action": 0.01, "recommend": 0.02, "scale_1": 0.05, "scale_2": 0.5},
        )
        ctrl = Controller(config)
        # Warmup
        for _ in range(110):
            ctrl.step(
                metrics={"cpu": 0.95, "memory": 0.9, "latency_p99": 0.95, "error_rate": 0.0},
                current_replicas=5,
            )
        action = ctrl.step(
            metrics={"cpu": 0.95, "memory": 0.9, "latency_p99": 0.95, "error_rate": 0.0},
            current_replicas=5,
        )
        result = explainer.explain(action)
        if action.replica_delta > 0:
            assert result.category == DecisionCategory.SCALE_OUT
            assert "SCALE OUT" in result.summary

    def test_observe_category(self, controller, explainer):
        """Observe is when score is between no_action and recommend thresholds."""
        action = _make_action(controller, cpu=0.55, latency=0.55)
        result = explainer.explain(action)
        if action.recommendation.startswith("observe"):
            assert result.category == DecisionCategory.OBSERVE


# ---------------------------------------------------------------------------
# Custom thresholds
# ---------------------------------------------------------------------------

class TestCustomThresholds:
    def test_custom_thresholds_affect_counterfactual(self, controller):
        explainer = Explainer(thresholds={
            "no_action": 0.1,
            "recommend": 0.3,
            "scale_1": 0.6,
            "scale_2": 1.5,
        })
        action = _make_action(controller)
        result = explainer.explain(action)
        # Counterfactual should reference the custom thresholds
        assert result.counterfactual != ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_explain_after_reset(self, controller, explainer):
        """Explain works on fresh controller output after reset."""
        controller.reset()
        action = controller.step(
            metrics={"cpu": 0.5},
            current_replicas=1,
        )
        result = explainer.explain(action)
        assert result.category in (
            DecisionCategory.HOLD,
            DecisionCategory.OBSERVE,
            DecisionCategory.SCALE_OUT,
            DecisionCategory.SCALE_IN,
        )

    def test_explain_with_empty_optional_context(self, controller, explainer):
        action = _make_action(controller)
        result = explainer.explain(action)
        assert result.confidence_level == ""
        assert result.safety_clamped is False
        assert result.safety_reason == ""
        assert result.suppress_reason == ""

    def test_metrics_snapshot_preserved(self, controller, explainer):
        action = _make_action(controller, cpu=0.7, memory=0.8)
        result = explainer.explain(action)
        assert "cpu" in result.metrics_snapshot
        assert "memory" in result.metrics_snapshot
