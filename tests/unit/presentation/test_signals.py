"""Tests for presentation signal structures.

Part 6: Signal Bundle Structure
"""

import pytest
from symbolu.presentation import (
    VrittiDistribution,
    SessionContext,
    SignalBundle,
)


class TestVrittiDistribution:
    """Tests for VrittiDistribution dataclass."""

    def test_default_zeros(self):
        """Default distribution should be all zeros."""
        dist = VrittiDistribution()
        assert dist.pramana == 0.0
        assert dist.viparyaya == 0.0
        assert dist.vikalpa == 0.0
        assert dist.smrti == 0.0
        assert dist.nidra == 0.0

    def test_custom_values(self):
        """Custom values should be set correctly."""
        dist = VrittiDistribution(
            pramana=0.8,
            viparyaya=0.05,
            vikalpa=0.05,
            smrti=0.05,
            nidra=0.05,
        )
        assert dist.pramana == 0.8
        assert dist.viparyaya == 0.05

    def test_validation_rejects_out_of_range(self):
        """Values outside [0, 1] should raise error."""
        with pytest.raises(ValueError):
            VrittiDistribution(pramana=1.5)
        with pytest.raises(ValueError):
            VrittiDistribution(viparyaya=-0.1)

    def test_from_dict(self):
        """from_dict should construct from CV result dict."""
        vritti_dict = {
            "pramana": 0.6,
            "viparyaya": 0.1,
            "vikalpa": 0.1,
            "smrti": 0.1,
            "nidra": 0.1,
        }
        dist = VrittiDistribution.from_dict(vritti_dict)
        assert dist.pramana == 0.6
        assert dist.viparyaya == 0.1

    def test_from_dict_missing_keys(self):
        """Missing keys should default to 0.0."""
        dist = VrittiDistribution.from_dict({"pramana": 0.5})
        assert dist.pramana == 0.5
        assert dist.viparyaya == 0.0


class TestSessionContext:
    """Tests for SessionContext dataclass."""

    def test_default_values(self):
        """Default context should have zero/None values."""
        ctx = SessionContext()
        assert ctx.turn_count == 0
        assert ctx.consecutive_low_scores == 0
        assert ctx.consecutive_high_scores == 0
        assert ctx.consecutive_low_motion == 0
        assert ctx.previous_dominant_vritti is None
        assert ctx.accumulated_smrti == 0.0

    def test_custom_context(self):
        """Custom context values should be set."""
        ctx = SessionContext(
            turn_count=5,
            consecutive_low_scores=2,
            previous_dominant_vritti="vikalpa",
            accumulated_smrti=0.3,
        )
        assert ctx.turn_count == 5
        assert ctx.consecutive_low_scores == 2
        assert ctx.previous_dominant_vritti == "vikalpa"


class TestSignalBundle:
    """Tests for SignalBundle dataclass."""

    def test_create_minimal(self):
        """create_minimal should provide sensible defaults."""
        bundle = SignalBundle.create_minimal()
        assert bundle.score == 0.5
        assert bundle.coherence == 0.5
        assert bundle.layers_present_count == 4
        assert isinstance(bundle.vritti, VrittiDistribution)
        assert isinstance(bundle.session, SessionContext)

    def test_create_minimal_custom(self):
        """create_minimal should accept custom values."""
        bundle = SignalBundle.create_minimal(
            score=0.9,
            coherence=0.95,
            dominant_vritti="pramana",
        )
        assert bundle.score == 0.9
        assert bundle.coherence == 0.95
        assert bundle.dominant_vritti == "pramana"

    def test_frozen_bundle(self):
        """Bundle should be immutable."""
        bundle = SignalBundle.create_minimal()
        with pytest.raises(Exception):
            bundle.score = 0.8

    def test_bundle_with_missing_layers(self):
        """Bundle should track missing layers."""
        bundle = SignalBundle.create_minimal(
            layers_present_count=2,
            missing_layers=("semantic", "temporal"),
        )
        assert bundle.layers_present_count == 2
        assert "semantic" in bundle.missing_layers
        assert "temporal" in bundle.missing_layers

    def test_bundle_with_fractures(self):
        """Bundle should include fracture information."""
        bundle = SignalBundle.create_minimal(
            fractures={("semantic", "structural"): 0.4},
            primary_fracture=("semantic", "structural"),
        )
        assert bundle.primary_fracture == ("semantic", "structural")
        assert ("semantic", "structural") in bundle.fractures

    def test_bundle_with_session(self):
        """Bundle should include session context."""
        session = SessionContext(
            turn_count=3,
            consecutive_low_motion=4,
        )
        bundle = SignalBundle.create_minimal(session=session)
        assert bundle.session.turn_count == 3
        assert bundle.session.consecutive_low_motion == 4
