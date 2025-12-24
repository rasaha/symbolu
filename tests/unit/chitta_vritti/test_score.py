"""Tests for threshold-driven score composition."""

import pytest

from symbolu.chitta_vritti.types import OptimizedConfig
from symbolu.chitta_vritti.score import (
    compute_score,
    get_active_penalties,
    compute_penalty_breakdown,
    interpret_score,
)


class TestScoreComputation:
    """Test score computation with threshold-driven penalties."""

    def test_full_coherence_no_penalties_max_score(self):
        """Full coherence + no penalties → score = 1.0."""
        config = OptimizedConfig()

        vritti = {
            "pramana": 0.9,
            "viparyaya": 0.02,
            "vikalpa": 0.03,
            "smrti": 0.03,
            "nidra": 0.02,
        }

        score = compute_score(coherence=1.0, vritti=vritti, config=config)
        assert score == pytest.approx(1.0)

    def test_viparyaya_above_threshold_applies_penalty(self):
        """Viparyaya above threshold → penalty applied."""
        config = OptimizedConfig(
            viparyaya_activation_threshold=0.1,
            penalty_viparyaya=0.25,
        )

        vritti = {
            "pramana": 0.5,
            "viparyaya": 0.2,  # Above 0.1 threshold
            "vikalpa": 0.1,
            "smrti": 0.1,
            "nidra": 0.1,
        }

        score = compute_score(coherence=1.0, vritti=vritti, config=config)

        # 1.0 - 0.25 = 0.75
        assert score == pytest.approx(0.75)

    def test_multiple_penalties_stack(self):
        """Multiple penalties should stack."""
        config = OptimizedConfig(
            viparyaya_activation_threshold=0.1,
            penalty_viparyaya=0.2,
            vikalpa_activation_threshold=0.1,
            penalty_vikalpa=0.15,
        )

        vritti = {
            "pramana": 0.3,
            "viparyaya": 0.2,  # Above threshold
            "vikalpa": 0.2,   # Above threshold
            "smrti": 0.15,
            "nidra": 0.15,
        }

        score = compute_score(coherence=1.0, vritti=vritti, config=config)

        # 1.0 - 0.2 - 0.15 = 0.65
        assert score == pytest.approx(0.65)

    def test_below_threshold_no_penalty(self):
        """Values below threshold → no penalty."""
        config = OptimizedConfig(
            viparyaya_activation_threshold=0.3,  # High threshold
            penalty_viparyaya=0.5,
        )

        vritti = {
            "pramana": 0.6,
            "viparyaya": 0.2,  # Below 0.3 threshold
            "vikalpa": 0.1,
            "smrti": 0.05,
            "nidra": 0.05,
        }

        score = compute_score(coherence=1.0, vritti=vritti, config=config)

        # No penalty applied
        assert score == pytest.approx(1.0)

    def test_score_clamped_to_zero(self):
        """Score should not go below 0."""
        config = OptimizedConfig(
            penalty_viparyaya=0.4,
            penalty_vikalpa=0.4,
            penalty_smrti=0.4,
            penalty_nidra=0.4,
            viparyaya_activation_threshold=0.1,
            vikalpa_activation_threshold=0.1,
            smrti_activation_threshold=0.1,
            nidra_activation_threshold=0.1,
        )

        vritti = {
            "pramana": 0.1,
            "viparyaya": 0.2,
            "vikalpa": 0.2,
            "smrti": 0.25,
            "nidra": 0.25,
        }

        # All penalties would sum to 1.6
        score = compute_score(coherence=0.5, vritti=vritti, config=config)

        # Should be clamped to 0
        assert score == 0.0


class TestActivePenalties:
    """Test active penalty detection."""

    def test_no_active_penalties(self):
        """Low vritti values → no active penalties."""
        config = OptimizedConfig()

        vritti = {
            "pramana": 0.9,
            "viparyaya": 0.02,
            "vikalpa": 0.03,
            "smrti": 0.03,
            "nidra": 0.02,
        }

        active = get_active_penalties(vritti, config)
        assert active == []

    def test_viparyaya_active(self):
        """Viparyaya above threshold → listed."""
        config = OptimizedConfig(viparyaya_activation_threshold=0.1)

        vritti = {
            "pramana": 0.6,
            "viparyaya": 0.2,
            "vikalpa": 0.1,
            "smrti": 0.05,
            "nidra": 0.05,
        }

        active = get_active_penalties(vritti, config)
        assert "viparyaya" in active


class TestPenaltyBreakdown:
    """Test penalty breakdown computation."""

    def test_breakdown_shows_applied_penalties(self):
        """Breakdown should show applied penalty values."""
        config = OptimizedConfig(
            viparyaya_activation_threshold=0.1,
            penalty_viparyaya=0.25,
        )

        vritti = {
            "pramana": 0.6,
            "viparyaya": 0.2,
            "vikalpa": 0.1,
            "smrti": 0.05,
            "nidra": 0.05,
        }

        breakdown = compute_penalty_breakdown(vritti, config)

        assert breakdown["viparyaya"] == 0.25
        assert breakdown["vikalpa"] == 0.0
        assert breakdown["smrti"] == 0.0
        assert breakdown["nidra"] == 0.0


class TestScoreInterpretation:
    """Test score interpretation."""

    def test_excellent_score(self):
        """Score >= 0.9 → Excellent."""
        interp = interpret_score(0.95)
        assert "Excellent" in interp

    def test_good_score(self):
        """Score in [0.7, 0.9) → Good."""
        interp = interpret_score(0.75)
        assert "Good" in interp

    def test_moderate_score(self):
        """Score in [0.5, 0.7) → Moderate."""
        interp = interpret_score(0.55)
        assert "Moderate" in interp

    def test_poor_score(self):
        """Score in [0.3, 0.5) → Poor."""
        interp = interpret_score(0.35)
        assert "Poor" in interp

    def test_critical_score(self):
        """Score < 0.3 → Critical."""
        interp = interpret_score(0.2)
        assert "Critical" in interp
