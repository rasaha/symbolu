"""Tests for Speech Pipeline, Prosodic Renderer, and GOVERNED Gate.

Comprehensive tests covering:
1. ProsodicRenderer - SSML generation from acoustic frames
2. GovernedGate - GOVERNED/OPEN mode enforcement
3. SpeechPipeline - End-to-end speech generation
4. Integration - Complete pipeline flow
"""

import pytest
from symbolu.presentation import (
    # Types
    DeliveryMode,
    ConfidenceIndicator,
    PresentationDirective,
    SuggestedBehaviors,
    # Acoustic Chain
    AcousticGovernanceChain,
    run_acoustic_chain,
    # Prosodic Renderer
    ProsodicRenderer,
    SSMLOutput,
    ProsodyLevel,
    render_ssml,
    render_minimal_ssml,
    # GOVERNED Gate
    GovernedGate,
    GateDecision,
    GateMode,
    GateAction,
    evaluate_governed,
    evaluate_open,
    should_block_output,
    # Speech Pipeline
    SpeechPipeline,
    SpeechOutput,
    PipelineMode,
    generate_speech,
    generate_ssml,
    is_speech_allowed,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticRegime,
    AcousticParameterFrame,
    EmphasisPolicy,
    PausePolicy,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def confident_directive():
    """CONFIDENT delivery mode directive."""
    return PresentationDirective(
        delivery_mode=DeliveryMode.CONFIDENT,
        confidence=ConfidenceIndicator.HIGH,
        triggered_rule="high_pramana",
    )


@pytest.fixture
def silent_directive():
    """SILENT delivery mode directive."""
    return PresentationDirective(
        delivery_mode=DeliveryMode.SILENT,
        confidence=ConfidenceIndicator.LOW,
        triggered_rule="critical_viparyaya",
    )


@pytest.fixture
def hedged_directive():
    """HEDGED delivery mode directive."""
    return PresentationDirective(
        delivery_mode=DeliveryMode.HEDGED,
        confidence=ConfidenceIndicator.MEDIUM,
        triggered_rule="moderate_uncertainty",
    )


@pytest.fixture
def neutral_acoustic_frame():
    """Create a NEUTRAL regime acoustic frame."""
    return AcousticParameterFrame(
        regime=AcousticRegime.NEUTRAL,
        speech_rate=4.5,
        energy_level=0.45,
        pitch_range=(100, 130),
        pause_policy=PausePolicy.NORMAL,
        pause_duration_ms=(150, 250),
        emphasis_policy=EmphasisPolicy.LIMITED,
        max_stressed_tokens=1,
        suppress_emotion=True,
        suppress_emphasis=False,
        suppress_certainty=False,
        source_regime="INFORM",
        source_discourse_act="EXPLANATION",
        architectural_phase="P10",
    )


@pytest.fixture
def flat_acoustic_frame():
    """Create a FLAT regime acoustic frame."""
    return AcousticParameterFrame(
        regime=AcousticRegime.FLAT,
        speech_rate=3.5,
        energy_level=0.25,
        pitch_range=(95, 105),
        pause_policy=PausePolicy.MINIMAL,
        pause_duration_ms=(100, 150),
        emphasis_policy=EmphasisPolicy.NONE,
        max_stressed_tokens=0,
        suppress_emotion=True,
        suppress_emphasis=True,
        suppress_certainty=True,
        source_regime="HOLD",
        source_discourse_act="DEFERRAL",
        architectural_phase="P10",
    )


# =============================================================================
# Test Class 1: ProsodicRenderer
# =============================================================================


class TestProsodicRenderer:
    """Test SSML generation from acoustic frames."""

    def test_renderer_creation(self):
        """Renderer should be created successfully."""
        renderer = ProsodicRenderer()
        assert renderer is not None

    def test_render_neutral_frame(self, neutral_acoustic_frame):
        """Neutral frame should produce standard SSML."""
        renderer = ProsodicRenderer()
        output = renderer.render(neutral_acoustic_frame, "Hello world")

        assert isinstance(output, SSMLOutput)
        assert "<speak>" in output.ssml
        assert "</speak>" in output.ssml
        assert "Hello world" in output.ssml

    def test_render_flat_frame(self, flat_acoustic_frame):
        """Flat frame should produce minimal prosody SSML."""
        renderer = ProsodicRenderer()
        output = renderer.render(flat_acoustic_frame, "I need to pause.")

        assert "<speak>" in output.ssml
        assert output.acoustic_regime == AcousticRegime.FLAT

    def test_render_with_prosody_element(self, neutral_acoustic_frame):
        """Prosody element should be present."""
        renderer = ProsodicRenderer()
        output = renderer.render(neutral_acoustic_frame, "Test text")

        assert output.has_prosody is True
        assert "<prosody" in output.ssml

    def test_render_with_emphasis(self, neutral_acoustic_frame):
        """Emphasis should be applied to specified tokens."""
        renderer = ProsodicRenderer()
        output = renderer.render(
            neutral_acoustic_frame,
            "This is important text",
            emphasis_tokens=["important"],
        )

        assert output.has_emphasis is True
        assert "<emphasis" in output.ssml

    def test_flat_regime_no_emphasis(self, flat_acoustic_frame):
        """Flat regime should not allow emphasis."""
        renderer = ProsodicRenderer()
        output = renderer.render(
            flat_acoustic_frame,
            "This is important",
            emphasis_tokens=["important"],
        )

        # Emphasis should NOT be applied for flat regime
        assert output.has_emphasis is False

    def test_render_raises_on_none_frame(self):
        """Renderer should raise on None frame."""
        renderer = ProsodicRenderer()
        with pytest.raises(ValueError, match="frame cannot be None"):
            renderer.render(None, "text")

    def test_render_raises_on_empty_text(self, neutral_acoustic_frame):
        """Renderer should raise on empty text."""
        renderer = ProsodicRenderer()
        with pytest.raises(ValueError, match="text cannot be empty"):
            renderer.render(neutral_acoustic_frame, "")

    def test_prosody_directive_values(self, neutral_acoustic_frame):
        """Prosody directive should have correct values."""
        renderer = ProsodicRenderer()
        output = renderer.render(neutral_acoustic_frame, "Test")

        directive = output.prosody_directive
        assert directive.rate_percent > 0
        assert directive.pitch_hz > 0
        assert directive.prosody_level == ProsodyLevel.NEUTRAL


class TestRenderConvenience:
    """Test convenience functions."""

    def test_render_ssml_function(self, neutral_acoustic_frame):
        """render_ssml should work correctly."""
        output = render_ssml(neutral_acoustic_frame, "Hello")

        assert isinstance(output, SSMLOutput)
        assert "<speak>" in output.ssml

    def test_render_minimal_ssml(self):
        """render_minimal_ssml should produce basic SSML."""
        ssml = render_minimal_ssml("Simple text")

        assert ssml == "<speak>Simple text</speak>"

    def test_render_minimal_ssml_empty(self):
        """render_minimal_ssml should handle empty text."""
        ssml = render_minimal_ssml("")

        assert ssml == "<speak></speak>"


# =============================================================================
# Test Class 2: GovernedGate
# =============================================================================


class TestGovernedGate:
    """Test GOVERNED mode gate enforcement."""

    def test_gate_creation_governed(self):
        """Gate should be created in GOVERNED mode."""
        gate = GovernedGate(mode=GateMode.GOVERNED)
        assert gate.mode == GateMode.GOVERNED

    def test_gate_creation_open(self):
        """Gate should be created in OPEN mode."""
        gate = GovernedGate(mode=GateMode.OPEN)
        assert gate.mode == GateMode.OPEN

    def test_clean_result_allows(self, confident_directive):
        """Clean result (no violations) should be allowed."""
        chain_result = run_acoustic_chain(confident_directive)
        gate = GovernedGate(mode=GateMode.GOVERNED)
        decision = gate.evaluate(chain_result)

        assert decision.action == GateAction.ALLOW
        assert decision.should_block is False
        assert decision.is_clean is True

    def test_decision_has_timestamp(self, confident_directive):
        """Decision should have timestamp."""
        chain_result = run_acoustic_chain(confident_directive)
        gate = GovernedGate(mode=GateMode.GOVERNED)
        decision = gate.evaluate(chain_result)

        assert decision.timestamp is not None
        assert len(decision.timestamp) > 0

    def test_decision_has_debug_info(self, confident_directive):
        """Decision should have debug info."""
        chain_result = run_acoustic_chain(confident_directive)
        gate = GovernedGate(mode=GateMode.GOVERNED)
        decision = gate.evaluate(chain_result)

        assert decision.debug is not None
        assert "mode" in decision.debug
        assert "source_regime" in decision.debug

    def test_evaluate_raises_on_none(self):
        """Evaluate should raise on None result."""
        gate = GovernedGate()
        with pytest.raises(ValueError, match="result cannot be None"):
            gate.evaluate(None)


class TestGateConvenience:
    """Test gate convenience functions."""

    def test_evaluate_governed(self, confident_directive):
        """evaluate_governed should work correctly."""
        chain_result = run_acoustic_chain(confident_directive)
        decision = evaluate_governed(chain_result)

        assert decision.mode == GateMode.GOVERNED

    def test_evaluate_open(self, confident_directive):
        """evaluate_open should work correctly."""
        chain_result = run_acoustic_chain(confident_directive)
        decision = evaluate_open(chain_result)

        assert decision.mode == GateMode.OPEN

    def test_should_block_output(self, confident_directive):
        """should_block_output should return False for clean result."""
        chain_result = run_acoustic_chain(confident_directive)
        blocked = should_block_output(chain_result)

        assert blocked is False


# =============================================================================
# Test Class 3: SpeechPipeline
# =============================================================================


class TestSpeechPipeline:
    """Test end-to-end speech pipeline."""

    def test_pipeline_creation_governed(self):
        """Pipeline should be created in GOVERNED mode."""
        pipeline = SpeechPipeline(mode=PipelineMode.GOVERNED)
        assert pipeline.mode == PipelineMode.GOVERNED

    def test_pipeline_creation_open(self):
        """Pipeline should be created in OPEN mode."""
        pipeline = SpeechPipeline(mode=PipelineMode.OPEN)
        assert pipeline.mode == PipelineMode.OPEN

    def test_execute_confident_directive(self, confident_directive):
        """Execute should produce valid speech output."""
        pipeline = SpeechPipeline(mode=PipelineMode.GOVERNED)
        output = pipeline.execute(confident_directive, "Hello world")

        assert isinstance(output, SpeechOutput)
        assert output.is_blocked is False
        assert "<speak>" in output.ssml
        assert "Hello world" in output.ssml

    def test_execute_returns_ssml(self, confident_directive):
        """Execute should return SSML string."""
        pipeline = SpeechPipeline()
        output = pipeline.execute(confident_directive, "Test message")

        assert output.ssml.startswith("<speak>")
        assert output.ssml.endswith("</speak>")

    def test_output_has_chain_result(self, confident_directive):
        """Output should have chain result."""
        pipeline = SpeechPipeline()
        output = pipeline.execute(confident_directive, "Test")

        assert output.chain_result is not None
        assert output.chain_result.acoustic_frame is not None

    def test_output_has_gate_decision(self, confident_directive):
        """Output should have gate decision."""
        pipeline = SpeechPipeline()
        output = pipeline.execute(confident_directive, "Test")

        assert output.gate_decision is not None
        assert output.gate_decision.action == GateAction.ALLOW

    def test_execute_raises_on_none_directive(self):
        """Execute should raise on None directive."""
        pipeline = SpeechPipeline()
        with pytest.raises(ValueError, match="directive cannot be None"):
            pipeline.execute(None, "text")

    def test_execute_raises_on_empty_text(self, confident_directive):
        """Execute should raise on empty text."""
        pipeline = SpeechPipeline()
        with pytest.raises(ValueError, match="text cannot be empty"):
            pipeline.execute(confident_directive, "")

    def test_output_properties(self, confident_directive):
        """Output should have correct properties."""
        pipeline = SpeechPipeline()
        output = pipeline.execute(confident_directive, "Test")

        assert output.is_consistent is True
        assert output.delivery_mode == "confident"
        assert output.violation_count == 0


class TestPipelineConvenience:
    """Test pipeline convenience functions."""

    def test_generate_speech(self, confident_directive):
        """generate_speech should work correctly."""
        output = generate_speech(confident_directive, "Hello")

        assert isinstance(output, SpeechOutput)
        assert output.is_blocked is False

    def test_generate_ssml(self, confident_directive):
        """generate_ssml should return SSML string."""
        ssml = generate_ssml(confident_directive, "Hello")

        assert isinstance(ssml, str)
        assert "<speak>" in ssml

    def test_is_speech_allowed(self, confident_directive):
        """is_speech_allowed should return True for clean directive."""
        allowed = is_speech_allowed(confident_directive)

        assert allowed is True


# =============================================================================
# Test Class 4: All Delivery Modes
# =============================================================================


class TestAllDeliveryModes:
    """Test pipeline with all delivery modes."""

    @pytest.mark.parametrize("mode", list(DeliveryMode))
    def test_all_modes_produce_ssml(self, mode):
        """All delivery modes should produce valid SSML."""
        directive = PresentationDirective(
            delivery_mode=mode,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule=f"test_{mode.value}",
        )

        pipeline = SpeechPipeline(mode=PipelineMode.GOVERNED)
        output = pipeline.execute(directive, "Test message")

        assert isinstance(output, SpeechOutput)
        assert "<speak>" in output.ssml
        assert "</speak>" in output.ssml

    @pytest.mark.parametrize("mode", list(DeliveryMode))
    def test_all_modes_not_blocked(self, mode):
        """All well-formed modes should not be blocked."""
        directive = PresentationDirective(
            delivery_mode=mode,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule=f"test_{mode.value}",
        )

        pipeline = SpeechPipeline(mode=PipelineMode.GOVERNED)
        output = pipeline.execute(directive, "Test message")

        # Well-formed directives should not be blocked
        assert output.is_blocked is False


# =============================================================================
# Test Class 5: Pipeline Modes
# =============================================================================


class TestPipelineModes:
    """Test different pipeline modes."""

    def test_governed_mode_strict(self, confident_directive):
        """GOVERNED mode should be strict."""
        pipeline = SpeechPipeline(mode=PipelineMode.GOVERNED)
        output = pipeline.execute(confident_directive, "Test")

        assert output.gate_decision.mode == GateMode.GOVERNED

    def test_open_mode_permissive(self, confident_directive):
        """OPEN mode should be permissive."""
        pipeline = SpeechPipeline(mode=PipelineMode.OPEN)
        output = pipeline.execute(confident_directive, "Test")

        assert output.gate_decision.mode == GateMode.OPEN

    def test_bypass_mode_audit(self, confident_directive):
        """BYPASS mode should use audit-only gate."""
        pipeline = SpeechPipeline(mode=PipelineMode.BYPASS)
        output = pipeline.execute(confident_directive, "Test")

        assert output.gate_decision.mode == GateMode.AUDIT_ONLY
        assert output.is_blocked is False


# =============================================================================
# Test Class 6: Determinism
# =============================================================================


class TestDeterminism:
    """Test pipeline determinism."""

    def test_same_input_same_ssml(self, confident_directive):
        """Same input should produce identical SSML."""
        pipeline = SpeechPipeline()

        output1 = pipeline.execute(confident_directive, "Hello world")
        output2 = pipeline.execute(confident_directive, "Hello world")

        assert output1.ssml == output2.ssml

    def test_different_pipelines_same_result(self, confident_directive):
        """Different pipeline instances should produce same result."""
        pipeline1 = SpeechPipeline(mode=PipelineMode.GOVERNED)
        pipeline2 = SpeechPipeline(mode=PipelineMode.GOVERNED)

        output1 = pipeline1.execute(confident_directive, "Test")
        output2 = pipeline2.execute(confident_directive, "Test")

        assert output1.ssml == output2.ssml
        assert output1.is_blocked == output2.is_blocked


# =============================================================================
# Test Class 7: Acoustic Regime Effects
# =============================================================================


class TestAcousticRegimeEffects:
    """Test that acoustic regimes affect SSML output."""

    def test_confident_produces_neutral(self, confident_directive):
        """CONFIDENT should produce NEUTRAL acoustic regime."""
        output = generate_speech(confident_directive, "I am certain.")

        assert output.acoustic_regime == "neutral"

    def test_silent_produces_flat(self, silent_directive):
        """SILENT should produce FLAT acoustic regime."""
        output = generate_speech(silent_directive, "...")

        assert output.acoustic_regime == "flat"

    def test_hedged_produces_soft(self, hedged_directive):
        """HEDGED should produce SOFT acoustic regime."""
        output = generate_speech(hedged_directive, "I'm not sure.")

        assert output.acoustic_regime == "soft"


# =============================================================================
# Test Class 8: Debug Information
# =============================================================================


class TestDebugInformation:
    """Test debug information in outputs."""

    def test_speech_output_has_debug(self, confident_directive):
        """Speech output should have debug info."""
        output = generate_speech(confident_directive, "Test")

        assert output.debug is not None
        assert "pipeline_mode" in output.debug
        assert "gate_action" in output.debug
        assert "delivery_mode" in output.debug

    def test_ssml_output_has_debug(self, neutral_acoustic_frame):
        """SSML output should have debug info."""
        output = render_ssml(neutral_acoustic_frame, "Test")

        assert output.debug is not None
        assert "source_regime" in output.debug
        assert "rate_percent" in output.debug
