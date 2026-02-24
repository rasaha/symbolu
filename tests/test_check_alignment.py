"""
Tests for check_alignment CLI — JEPA-Ontology alignment diagnosis.

Tests the four-outcome classification logic, synthetic data generation,
rendering, and end-to-end pipeline.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

# Ensure project root is importable
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.causal_subspace.check_alignment import (
    OUTCOME_DESCRIPTIONS,
    SOVEREIGN_DIM_NAMES,
    AlignmentOutcome,
    classify_outcome,
    generate_synthetic_hidden_states,
    render_outcome,
    run_alignment_check,
)
from scripts.causal_subspace.ontology_alignment import (
    N_ROBUST,
    ROBUST_AXES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def small_synthetic_data():
    """Generate a small synthetic dataset for fast tests."""
    H, ont, mask = generate_synthetic_hidden_states(
        n_samples=200, d_model=128, seed=42,
    )
    return H, ont, mask


# ── Test synthetic data generation ────────────────────────────────────────

class TestSyntheticGeneration:
    def test_shapes(self):
        H, ont, mask = generate_synthetic_hidden_states(n_samples=100, d_model=64)
        assert H.shape == (100, 64)
        assert ont.shape == (100, 12)
        assert mask.shape == (100,)
        assert mask.all()

    def test_ontology_range(self):
        _, ont, _ = generate_synthetic_hidden_states(n_samples=500, d_model=64)
        assert ont.min() >= 0.0
        assert ont.max() <= 1.0

    def test_reproducible(self):
        H1, _, _ = generate_synthetic_hidden_states(n_samples=50, d_model=32, seed=99)
        H2, _, _ = generate_synthetic_hidden_states(n_samples=50, d_model=32, seed=99)
        np.testing.assert_array_equal(H1, H2)

    def test_different_seeds_differ(self):
        H1, _, _ = generate_synthetic_hidden_states(n_samples=50, d_model=32, seed=1)
        H2, _, _ = generate_synthetic_hidden_states(n_samples=50, d_model=32, seed=2)
        assert not np.allclose(H1, H2)


# ── Test outcome classification ───────────────────────────────────────────

class TestClassifyOutcome:
    def test_strong_overlap(self):
        """All axes with |corr| > 0.5 → Outcome 1."""
        corr = np.zeros((4, 32))
        corr[0, 1] = 0.7
        corr[1, 5] = -0.6
        corr[2, 10] = 0.8
        corr[3, 20] = -0.55
        r2 = {ax: 0.5 for ax in ROBUST_AXES}
        mi = {ax: 0.3 for ax in ROBUST_AXES}

        result = classify_outcome(corr, r2, mi)
        assert result.outcome_number == 1
        assert result.outcome_name == "STRONG OVERLAP"
        assert result.n_strong_axes == 4

    def test_partial_overlap(self):
        """2 strong, 2 weak → Outcome 2."""
        corr = np.zeros((4, 32))
        corr[0, 1] = 0.6   # strong
        corr[1, 5] = -0.55  # strong
        corr[2, 10] = 0.2   # weak
        corr[3, 20] = 0.15  # weak
        r2 = {ax: 0.1 for ax in ROBUST_AXES}
        mi = {ax: 0.1 for ax in ROBUST_AXES}

        result = classify_outcome(corr, r2, mi)
        assert result.outcome_number == 2
        assert result.n_strong_axes == 2

    def test_distributed_encoding(self):
        """No single dim maps, but linear probe works → Outcome 3."""
        corr = np.zeros((4, 32))
        # All correlations weak
        corr[0, 1] = 0.15
        corr[1, 5] = 0.10
        corr[2, 10] = 0.20
        corr[3, 20] = 0.12
        # But bridge R² is high
        r2 = {ax: 0.4 for ax in ROBUST_AXES}
        mi = {ax: 0.2 for ax in ROBUST_AXES}

        result = classify_outcome(corr, r2, mi)
        assert result.outcome_number == 3
        assert "linear probe" in result.evidence[0].lower() or "distributed" in result.outcome_name.lower()

    def test_orthogonal(self):
        """No correlation, no probe signal → Outcome 4."""
        corr = np.zeros((4, 32))
        corr[0, 1] = 0.05
        corr[1, 5] = -0.03
        corr[2, 10] = 0.02
        corr[3, 20] = 0.01
        r2 = {ax: -0.01 for ax in ROBUST_AXES}
        mi = {ax: 0.01 for ax in ROBUST_AXES}

        result = classify_outcome(corr, r2, mi)
        assert result.outcome_number == 4
        assert result.outcome_name == "COMPLETELY ORTHOGONAL"

    def test_all_outcomes_have_descriptions(self):
        for num in [1, 2, 3, 4]:
            assert num in OUTCOME_DESCRIPTIONS
            name, desc = OUTCOME_DESCRIPTIONS[num]
            assert len(name) > 0
            assert len(desc) > 0

    def test_evidence_populated(self):
        """All outcomes produce at least one evidence string."""
        for num in [1, 2, 3, 4]:
            corr = np.zeros((4, 32))
            r2 = {ax: 0.0 for ax in ROBUST_AXES}
            mi = {ax: 0.0 for ax in ROBUST_AXES}

            if num == 1:
                for j in range(4):
                    corr[j, j * 3] = 0.7
                r2 = {ax: 0.5 for ax in ROBUST_AXES}
            elif num == 2:
                corr[0, 0] = 0.6
                corr[1, 1] = 0.55
            elif num == 3:
                r2 = {ax: 0.4 for ax in ROBUST_AXES}

            result = classify_outcome(corr, r2, mi)
            assert len(result.evidence) > 0


# ── Test rendering ────────────────────────────────────────────────────────

class TestRendering:
    def test_render_all_outcomes(self):
        """Each outcome renders without error."""
        for num in [1, 2, 3, 4]:
            outcome = AlignmentOutcome(
                outcome_number=num,
                outcome_name=OUTCOME_DESCRIPTIONS[num][0],
                outcome_description=OUTCOME_DESCRIPTIONS[num][1],
                per_axis_best_corr={ax: 0.5 for ax in ROBUST_AXES},
                per_axis_best_dim={ax: i for i, ax in enumerate(ROBUST_AXES)},
                per_axis_best_dim_name={ax: f"Bhava.{i}" for i, ax in enumerate(ROBUST_AXES)},
                per_axis_mi={ax: 0.1 for ax in ROBUST_AXES},
                bridge_r2_per_axis={ax: 0.3 for ax in ROBUST_AXES},
                bridge_r2_mean=0.3,
                evidence=[f"Test evidence for outcome {num}"],
            )
            text = render_outcome(outcome)
            assert f"OUTCOME {num}" in text
            assert OUTCOME_DESCRIPTIONS[num][0] in text

    def test_render_contains_axes(self):
        """Report includes all 4 axis names."""
        outcome = AlignmentOutcome(
            outcome_number=1,
            outcome_name="TEST",
            outcome_description="Test",
            per_axis_best_corr={ax: 0.5 for ax in ROBUST_AXES},
            per_axis_best_dim={ax: 0 for ax in ROBUST_AXES},
            per_axis_best_dim_name={ax: "dim_0" for ax in ROBUST_AXES},
            per_axis_mi={ax: 0.1 for ax in ROBUST_AXES},
            bridge_r2_per_axis={ax: 0.3 for ax in ROBUST_AXES},
            evidence=["test"],
        )
        text = render_outcome(outcome)
        for ax in ROBUST_AXES:
            # Axis name appears in some form
            short = ax.replace("O", "").replace("_", " ")
            assert short in text

    def test_render_has_box_chars(self):
        """Report uses box-drawing characters."""
        outcome = AlignmentOutcome(
            outcome_number=1,
            outcome_name="TEST",
            outcome_description="Test",
            per_axis_best_corr={ax: 0.5 for ax in ROBUST_AXES},
            per_axis_best_dim={ax: 0 for ax in ROBUST_AXES},
            per_axis_best_dim_name={ax: "dim_0" for ax in ROBUST_AXES},
            per_axis_mi={ax: 0.1 for ax in ROBUST_AXES},
            bridge_r2_per_axis={ax: 0.3 for ax in ROBUST_AXES},
            evidence=["test"],
        )
        text = render_outcome(outcome)
        assert "\u250c" in text  # top-left corner
        assert "\u2514" in text  # bottom-left corner


# ── Test sovereign dim names ──────────────────────────────────────────────

class TestSovereignDimNames:
    def test_length(self):
        assert len(SOVEREIGN_DIM_NAMES) == 32

    def test_components(self):
        assert SOVEREIGN_DIM_NAMES[0].startswith("Bhava.")
        assert SOVEREIGN_DIM_NAMES[12].startswith("Kosha.")
        assert SOVEREIGN_DIM_NAMES[17].startswith("Vritti.")
        assert SOVEREIGN_DIM_NAMES[22].startswith("Guna.")
        assert SOVEREIGN_DIM_NAMES[28].startswith("Reserved.")


# ── Test end-to-end pipeline ──────────────────────────────────────────────

class TestEndToEnd:
    def test_run_alignment_check(self, small_synthetic_data):
        """Full pipeline completes and returns valid outcome."""
        H, ont, mask = small_synthetic_data
        outcome = run_alignment_check(
            H=H, ont_features=ont, valid_mask=mask,
            d_model=128, state_dim=32,
            n_epochs_bridge=10, n_epochs_monitor=10,
            seed=42,
        )
        assert outcome.outcome_number in [1, 2, 3, 4]
        assert outcome.outcome_name != ""
        assert len(outcome.evidence) > 0
        assert outcome.n_strong_axes + outcome.n_moderate_axes + outcome.n_weak_axes == N_ROBUST
        # AUC should be finite
        assert 0.0 <= outcome.jepa_auc <= 1.0
        assert 0.0 <= outcome.ontology_auc <= 1.0
        assert 0.0 <= outcome.combined_auc <= 1.0


# ── Test CLI execution ────────────────────────────────────────────────────

class TestCLI:
    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "scripts/causal_subspace/check_alignment.py", "--help"],
            capture_output=True, text=True, cwd=_PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "STRONG OVERLAP" in result.stdout
        assert "ORTHOGONAL" in result.stdout

    def test_small_run(self):
        """CLI runs end-to-end with small parameters."""
        result = subprocess.run(
            [
                sys.executable, "scripts/causal_subspace/check_alignment.py",
                "--n-samples", "100",
                "--d-model", "64",
                "--bridge-epochs", "5",
                "--monitor-epochs", "5",
            ],
            capture_output=True, text=True, cwd=_PROJECT_ROOT,
            timeout=120,
        )
        assert result.returncode == 0
        assert "OUTCOME" in result.stdout
        assert "ALIGNMENT CHECK" in result.stdout

    def test_json_output(self):
        """CLI saves valid JSON when --output is specified."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            outpath = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable, "scripts/causal_subspace/check_alignment.py",
                    "--n-samples", "100",
                    "--d-model", "64",
                    "--bridge-epochs", "5",
                    "--monitor-epochs", "5",
                    "--output", outpath,
                ],
                capture_output=True, text=True, cwd=_PROJECT_ROOT,
                timeout=120,
            )
            assert result.returncode == 0

            with open(outpath) as f:
                data = json.load(f)

            assert "outcome_number" in data
            assert data["outcome_number"] in [1, 2, 3, 4]
            assert "outcome_name" in data
            assert "evidence" in data
            assert "per_axis_best_corr" in data
            assert "bridge_r2_per_axis" in data
            assert "config" in data
        finally:
            Path(outpath).unlink(missing_ok=True)
