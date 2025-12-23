"""
DHA Integration Tests
=====================

Tests for DHA pipeline integration.
"""

import pytest
from symbolu.dha import (
    DHAStage,
    DHAConfig,
    EntropySource,
)
from symbolu.dha.integration import (
    extract_signals_from_context,
    extract_base_output,
    maybe_run_dha,
    get_dha_delivery_profile,
)


class MockRequest:
    """Mock request for testing."""
    def __init__(self, text="test", metadata=None):
        self.text = text
        self.user_id = "test_user"
        self.metadata = metadata or {}
        self.render_mode = "standard"


class MockMLCR:
    """Mock MLCR result for testing."""
    def __init__(self, explain_log=None):
        self._explain_log = explain_log or {}

    @property
    def explain_log(self):
        return self._explain_log


class MockFusion:
    """Mock Fusion result for testing."""
    def __init__(self, text="fused text"):
        self._text = text
        self.trace = {"candidate_count": 1}
        self.fused_candidates = self

    @property
    def selected_text(self):
        return self._text

    @property
    def selected_candidate(self):
        return type('obj', (object,), {'text': self._text})()


class MockCoherenceState:
    """Mock coherence state for testing."""
    def __init__(self, score=0.8):
        self.coherence_score = score
        self.coherence_score_v2 = score


class MockP18:
    """Mock P18 temporal entropy for testing."""
    def __init__(self, delta=0.1, now=0.5):
        self.delta_entropy = delta
        self.entropy_now = now


class MockPipelineContext:
    """Mock pipeline context for testing."""
    def __init__(
        self,
        request=None,
        mlcr=None,
        fusion=None,
        coherence_state=None,
        p18=None,
        p17=None,
    ):
        self.request = request or MockRequest()
        self.mlcr = mlcr
        self.fusion = fusion
        self.coherence_state = coherence_state
        self.p18 = p18
        self.p17 = p17
        self.dha = None


class TestSignalExtraction:
    """Test signal extraction from pipeline context."""

    def test_extract_coherence_from_state(self):
        """Extract C_s from coherence_state."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(score=0.9)
        )
        config = DHAConfig(enabled=True)

        signals = extract_signals_from_context(ctx, config)

        assert signals.C_s == 0.9
        assert "C_s" not in signals.missing_signals

    def test_extract_coherence_default(self):
        """Use default C_s when not available.

        Note: Default is 1.0 (assume coherent) per signal_extraction.py
        line 362-365: "Default: assume coherent"
        """
        ctx = MockPipelineContext()
        config = DHAConfig(enabled=True)

        signals = extract_signals_from_context(ctx, config)

        # Default is 1.0 (assume coherent) when no coherence data available
        assert signals.C_s == 1.0
        assert "C_s" in signals.missing_signals

    def test_extract_motion_from_p18(self):
        """Extract M from p18 temporal entropy."""
        ctx = MockPipelineContext(
            p18=MockP18(delta=0.2)
        )
        config = DHAConfig(enabled=True)

        signals = extract_signals_from_context(ctx, config)

        assert signals.M == 0.2
        assert "M" not in signals.missing_signals

    def test_extract_entropy_from_mlcr(self):
        """Extract entropy from MLCR explain_log.

        Note: Only H_G is currently extracted per signal_extraction.py
        lines 670-671: H_D and H_K are "Not extracted in this version"
        """
        ctx = MockPipelineContext(
            mlcr=MockMLCR(explain_log={
                "entropy": {"H_G": 0.5, "H_D": 0.6, "H_K": 0.4}
            })
        )
        config = DHAConfig(enabled=True)

        signals = extract_signals_from_context(ctx, config)

        # Only H_G is extracted in current implementation
        assert signals.H_G == 0.5
        # H_D and H_K are not extracted in this version
        assert signals.H_D is None
        assert signals.H_K is None

    def test_extract_guna_from_mlcr(self):
        """Extract Guna distribution from MLCR."""
        ctx = MockPipelineContext(
            mlcr=MockMLCR(explain_log={
                "guna": {"sattva": 0.5, "rajas": 0.3, "tamas": 0.2}
            })
        )
        config = DHAConfig(enabled=True)

        signals = extract_signals_from_context(ctx, config)

        assert signals.s == 0.5
        assert signals.r == 0.3
        assert signals.t == 0.2


class TestBaseOutputExtraction:
    """Test base output extraction."""

    def test_extract_from_fusion(self):
        """Extract text from fusion result."""
        ctx = MockPipelineContext(
            fusion=MockFusion(text="This is the fused output.")
        )

        text = extract_base_output(ctx)

        assert text == "This is the fused output."

    def test_extract_fallback_to_request(self):
        """Fall back to request text when fusion not available."""
        ctx = MockPipelineContext(
            request=MockRequest(text="Original request text")
        )

        text = extract_base_output(ctx)

        assert text == "Original request text"


class TestDHAStage:
    """Test DHAStage pipeline integration."""

    def test_stage_disabled(self):
        """Disabled stage is a no-op."""
        config = DHAConfig(enabled=False)
        stage = DHAStage(config)

        ctx = MockPipelineContext()
        result_ctx = stage.run(ctx)

        assert "dha" in result_ctx.request.metadata
        assert result_ctx.request.metadata["dha"]["enabled"] is False

    def test_stage_enabled_computes(self):
        """Enabled stage computes DHA."""
        config = DHAConfig(enabled=True)
        stage = DHAStage(config)

        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(score=0.8),
            mlcr=MockMLCR(explain_log={
                "entropy": {"H_G": 0.5}
            }),
        )
        result_ctx = stage.run(ctx)

        assert "dha" in result_ctx.request.metadata
        dha_result = result_ctx.request.metadata["dha"]
        assert "D" in dha_result
        assert "I" in dha_result
        assert "R" in dha_result

    def test_stage_for_tier(self):
        """DHAStage.for_tier creates tier-specific stage."""
        stage = DHAStage.for_tier("enterprise_tier_1")

        assert stage.config.enabled is True

    def test_stage_attaches_delivery_profile(self):
        """Stage attaches delivery profile."""
        config = DHAConfig(enabled=True)
        stage = DHAStage(config)

        ctx = MockPipelineContext()
        result_ctx = stage.run(ctx)

        assert "dha_delivery_profile" in result_ctx.request.metadata


class TestMaybeRunDHA:
    """Test maybe_run_dha helper."""

    def test_maybe_run_disabled(self):
        """Returns None when disabled."""
        config = DHAConfig(enabled=False)
        ctx = MockPipelineContext()

        result = maybe_run_dha(ctx, config)

        assert result is None

    def test_maybe_run_enabled(self):
        """Returns result when enabled."""
        config = DHAConfig(enabled=True)
        ctx = MockPipelineContext()

        result = maybe_run_dha(ctx, config)

        assert result is not None
        assert "D" in result or "enabled" in result


class TestGetDeliveryProfile:
    """Test get_dha_delivery_profile helper."""

    def test_get_profile_after_stage(self):
        """Get delivery profile after stage run."""
        config = DHAConfig(enabled=True)
        stage = DHAStage(config)

        ctx = MockPipelineContext()
        stage.run(ctx)

        profile = get_dha_delivery_profile(ctx)

        assert profile is not None
        assert "dominant_tone" in profile
        assert "intensity" in profile
        assert "restraint" in profile


class TestEntropySourceSelection:
    """Test entropy source selection in integration."""

    def test_guna_source_uses_H_G(self):
        """Guna entropy source uses H_G."""
        config = DHAConfig(enabled=True, entropy_source=EntropySource.GUNA)
        stage = DHAStage(config)

        ctx = MockPipelineContext(
            mlcr=MockMLCR(explain_log={
                "entropy": {"H_G": 0.5, "H_D": 0.7, "H_K": 0.3}
            })
        )
        stage.run(ctx)

        dha = ctx.request.metadata["dha"]
        assert dha["audit"]["entropy_source_used"] == "guna"

    def test_dimensional_source_falls_back_to_guna(self):
        """Dimensional entropy source falls back to guna when H_D not extracted.

        Note: H_D is not extracted in current implementation (signal_extraction.py
        line 670: "H_D=None  # Not extracted in this version"). The math.py
        get_normalized_entropy function falls back to guna when H_D is None.
        """
        config = DHAConfig(enabled=True, entropy_source=EntropySource.DIMENSIONAL)
        stage = DHAStage(config)

        ctx = MockPipelineContext(
            mlcr=MockMLCR(explain_log={
                "entropy": {"H_G": 0.5, "H_D": 0.7, "H_K": 0.3}
            })
        )
        stage.run(ctx)

        dha = ctx.request.metadata["dha"]
        # Falls back to guna since H_D is not extracted
        assert dha["audit"]["entropy_source_used"] == "guna"

    def test_kosha_source_falls_back_to_guna(self):
        """Kosha entropy source falls back to guna when H_K not extracted.

        Note: H_K is not extracted in current implementation (signal_extraction.py
        line 671: "H_K=None  # Not extracted in this version"). The math.py
        get_normalized_entropy function falls back to guna when H_K is None.
        """
        config = DHAConfig(enabled=True, entropy_source=EntropySource.KOSHA)
        stage = DHAStage(config)

        ctx = MockPipelineContext(
            mlcr=MockMLCR(explain_log={
                "entropy": {"H_G": 0.5, "H_D": 0.7, "H_K": 0.3}
            })
        )
        stage.run(ctx)

        dha = ctx.request.metadata["dha"]
        # Falls back to guna since H_K is not extracted
        assert dha["audit"]["entropy_source_used"] == "guna"
