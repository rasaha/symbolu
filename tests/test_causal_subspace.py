"""
Tests for the Causal Subspace Extraction & Validation Pipeline.

These tests validate each module independently using small synthetic data,
without requiring HuggingFace model downloads.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn as nn

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.causal_subspace.structural_labels import (
    GRAMMATICAL_ROLES,
    ROLE_TO_IDX,
    StructuralAnnotations,
    WordAnnotation,
    _dep_to_role,
    _heuristic_parse,
    segment_sentences,
)
from scripts.causal_subspace.disentanglement import (
    DisentanglementConfig,
    SparseAutoencoder,
    cluster_sae_features,
    compute_pca_baseline,
    run_disentanglement,
    train_sae,
)
from scripts.causal_subspace.mdl_probing import (
    MDLProbeConfig,
    MDLProbeResult,
    _geometric_portions,
    run_mdl_probe,
)
from scripts.causal_subspace.causal_intervention import (
    InterventionPair,
    build_subspace_basis,
)
from scripts.causal_subspace.trajectory import (
    LayerTrajectory,
    plot_trajectory_ascii,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rng():
    return np.random.RandomState(42)


@pytest.fixture
def synthetic_hidden_states(rng):
    """Create hidden states with known cluster structure."""
    N, d = 500, 64
    n_classes = 5

    labels = rng.randint(0, n_classes, size=N)

    # Create separable clusters: each class has a distinct mean direction
    class_means = rng.randn(n_classes, d) * 3.0
    H = np.zeros((N, d), dtype=np.float32)
    for i in range(N):
        H[i] = class_means[labels[i]] + rng.randn(d) * 0.5

    return H, labels


@pytest.fixture
def multi_layer_states(rng):
    """Create multi-layer hidden states with increasing structure."""
    N, d = 300, 32
    n_classes = 4
    n_layers = 6

    labels = rng.randint(0, n_classes, size=N)
    class_means = rng.randn(n_classes, d)

    states = {}
    for layer in range(n_layers):
        # Later layers have stronger class signal
        signal_strength = 0.5 + layer * 0.8
        noise_strength = 2.0 - layer * 0.2
        H = np.zeros((N, d), dtype=np.float32)
        for i in range(N):
            H[i] = class_means[labels[i]] * signal_strength + rng.randn(d) * noise_strength
        states[layer] = H

    return states, labels


# ---------------------------------------------------------------------------
# Part 2: Structural Labels
# ---------------------------------------------------------------------------

class TestStructuralLabels:
    def test_sentence_segmentation(self):
        text = "The cat sat. The dog ran. Hello world!"
        sentences = segment_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "The cat sat."
        assert sentences[2] == "Hello world!"

    def test_dep_to_role(self):
        assert _dep_to_role("nsubj") == "subject"
        assert _dep_to_role("dobj") == "object"
        assert _dep_to_role("ROOT") == "root"
        assert _dep_to_role("amod") == "modifier"
        assert _dep_to_role("unknown_dep") == "other"

    def test_heuristic_parse(self):
        sentences = ["The cat sat on the mat"]
        parsed = _heuristic_parse(sentences)
        assert len(parsed) == 1
        words = parsed[0]
        assert len(words) > 0
        # First word should be tagged as subject
        assert words[0][3] == "subject"  # (word, dep, depth, role)

    def test_role_to_idx(self):
        for role in GRAMMATICAL_ROLES:
            assert role in ROLE_TO_IDX
        assert ROLE_TO_IDX["subject"] == 0
        assert ROLE_TO_IDX["object"] == 1


# ---------------------------------------------------------------------------
# Part 3: Disentanglement
# ---------------------------------------------------------------------------

class TestDisentanglement:
    def test_pca_baseline(self, rng):
        H = rng.randn(200, 32).astype(np.float32)
        ev, cv, comps = compute_pca_baseline(H, n_components=10)
        assert len(ev) == 10
        assert len(cv) == 10
        assert comps.shape == (10, 32)
        assert cv[-1] <= 1.0 + 1e-6
        # Cumulative should be monotonically increasing
        for i in range(1, len(cv)):
            assert cv[i] >= cv[i - 1] - 1e-6

    def test_sparse_autoencoder_forward(self):
        d, sae_dim = 32, 128
        sae = SparseAutoencoder(d, sae_dim)
        x = torch.randn(16, d)
        x_hat, latent, pre_act = sae(x)

        assert x_hat.shape == (16, d)
        assert latent.shape == (16, sae_dim)
        assert pre_act.shape == (16, sae_dim)
        # ReLU: latent should be non-negative
        assert (latent >= 0).all()

    def test_sae_decoder_unit_norm_constraint(self):
        """After constrain_decoder_norms(), all decoder columns should be unit norm."""
        d, sae_dim = 32, 128
        sae = SparseAutoencoder(d, sae_dim)

        # Perturb decoder weights
        with torch.no_grad():
            sae.decoder.weight.mul_(5.0)

        sae.constrain_decoder_norms()

        col_norms = sae.decoder.weight.norm(dim=0)
        torch.testing.assert_close(
            col_norms, torch.ones(sae_dim), atol=1e-6, rtol=1e-6,
        )

    def test_sae_training_preserves_decoder_norms(self, rng):
        """After train_sae(), decoder columns should still be ~unit norm."""
        H = rng.randn(200, 16).astype(np.float32)
        cfg = DisentanglementConfig(
            sae_expansion_factor=2, sae_epochs=5,
            sae_batch_size=64, device="cpu",
        )
        sae, _, _, _ = train_sae(H, cfg)

        col_norms = sae.decoder.weight.norm(dim=0)
        # After training with constrain_decoder_norms(), all columns ~1.0
        torch.testing.assert_close(
            col_norms, torch.ones(col_norms.shape[0]), atol=1e-5, rtol=1e-5,
        )

    def test_train_sae(self, rng):
        H = rng.randn(200, 16).astype(np.float32)
        cfg = DisentanglementConfig(
            sae_expansion_factor=2,
            sae_epochs=5,
            sae_batch_size=64,
            device="cpu",
        )
        sae, features, recon_loss, sparsity = train_sae(H, cfg)

        assert features.shape == (200, 32)  # 16 * 2
        assert recon_loss >= 0
        assert sparsity >= 0

    def test_cluster_sae_features(self, rng):
        features = rng.randn(200, 32).astype(np.float32)
        labels, centers = cluster_sae_features(features, n_clusters=5)

        assert labels.shape == (200,)
        assert centers.shape == (5, 32)
        assert set(labels).issubset(set(range(5)))

    def test_full_disentanglement(self, rng):
        H = rng.randn(200, 16).astype(np.float32)
        cfg = DisentanglementConfig(
            pca_n_components=8,
            sae_expansion_factor=2,
            sae_epochs=3,
            sae_batch_size=64,
            n_clusters=4,
            device="cpu",
        )
        result = run_disentanglement(H, layer_idx=0, cfg=cfg)

        assert result.pca_explained_variance is not None
        assert len(result.pca_explained_variance) == 8
        assert result.sae_features is not None
        assert result.sae_features.shape[0] == 200
        assert result.cluster_labels is not None
        assert len(result.cluster_labels) == 200


# ---------------------------------------------------------------------------
# Part 4: MDL Probing
# ---------------------------------------------------------------------------

class TestMDLProbing:
    def test_geometric_portions(self):
        portions = _geometric_portions(1000, 10)
        assert len(portions) == 10
        assert portions[-1] == 1000
        # Monotonically increasing
        for i in range(1, len(portions)):
            assert portions[i] >= portions[i - 1]

    def test_geometric_portions_small(self):
        portions = _geometric_portions(10, 3)
        assert portions[-1] == 10

    def test_mdl_probe_separable_data(self, synthetic_hidden_states):
        """MDL probe on well-separated data should achieve compression."""
        H, labels = synthetic_hidden_states
        cfg = MDLProbeConfig(
            n_portions=5,
            probe_epochs=10,
            device="cpu",
        )
        result = run_mdl_probe(H, labels, layer_idx=0, label_name="test", cfg=cfg)

        assert result.compression_ratio > 1.0, (
            f"Expected compression > 1.0 for separable data, got {result.compression_ratio}"
        )
        assert result.online_code_length < result.uniform_code_length
        assert result.n_classes == 5
        assert result.n_samples == 500

    def test_mdl_probe_random_data(self, rng):
        """MDL probe on random labels should achieve ~no compression."""
        N, d = 500, 64
        H = rng.randn(N, d).astype(np.float32)
        labels = rng.randint(0, 5, size=N).astype(np.int32)

        cfg = MDLProbeConfig(
            n_portions=5,
            probe_epochs=10,
            device="cpu",
        )
        result = run_mdl_probe(H, labels, layer_idx=0, label_name="random", cfg=cfg)

        # Random labels: compression should be close to 1.0 (no useful signal)
        assert result.compression_ratio < 2.0, (
            f"Random data should not compress well, got {result.compression_ratio}"
        )

    def test_mdl_prior_aware_baseline(self, rng):
        """Prior-aware baseline should be <= uniform baseline, and tighter
        for imbalanced data."""
        N, d = 500, 64
        # Highly imbalanced: 80% class 0, 20% class 1
        labels = np.zeros(N, dtype=np.int32)
        labels[int(N * 0.8):] = 1
        H = rng.randn(N, d).astype(np.float32)

        cfg = MDLProbeConfig(n_portions=5, probe_epochs=5, device="cpu")
        result = run_mdl_probe(H, labels, 0, "imbalanced", cfg)

        # Prior code length accounts for class imbalance → shorter than uniform
        assert result.prior_code_length < result.uniform_code_length, (
            f"Prior baseline ({result.prior_code_length:.1f}) should be less "
            f"than uniform ({result.uniform_code_length:.1f}) for imbalanced data"
        )
        # Both compression metrics should exist
        assert result.compression_ratio > 0
        assert result.compression_vs_uniform > 0


# ---------------------------------------------------------------------------
# Part 5: Causal Intervention
# ---------------------------------------------------------------------------

class TestCausalIntervention:
    def test_build_subspace_basis(self, synthetic_hidden_states):
        H, labels = synthetic_hidden_states
        n_classes = len(np.unique(labels))
        k = 8
        U_k = build_subspace_basis(H, labels, k)

        assert U_k.shape == (64, min(k, n_classes))  # min(k, n_classes) from SVD of class means
        # Check orthonormality
        product = U_k.T @ U_k
        np.testing.assert_allclose(
            product, np.eye(product.shape[0]), atol=1e-5,
            err_msg="Subspace basis should be orthonormal",
        )

    def test_subspace_projection(self, synthetic_hidden_states):
        """Verify that projecting onto subspace preserves class signal."""
        H, labels = synthetic_hidden_states
        U_k = build_subspace_basis(H, labels, k=4)

        # Project
        H_proj = H @ U_k @ U_k.T

        # The projected data should still separate classes
        # Check via class-mean distances
        unique = np.unique(labels)
        class_means_original = np.array([H[labels == c].mean(0) for c in unique])
        class_means_projected = np.array([H_proj[labels == c].mean(0) for c in unique])

        # Mean pairwise distance should be preserved in projected space
        orig_dists = []
        proj_dists = []
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                orig_dists.append(np.linalg.norm(class_means_original[i] - class_means_original[j]))
                proj_dists.append(np.linalg.norm(class_means_projected[i] - class_means_projected[j]))

        # Projected distances should correlate with original
        corr = np.corrcoef(orig_dists, proj_dists)[0, 1]
        assert corr > 0.5, f"Class structure not preserved in projection: corr={corr}"

    def test_intervention_pair_dataclass(self):
        pair = InterventionPair(
            seq_a_ids=[1, 2, 3],
            seq_b_ids=[4, 5, 6],
            target_pos_a=1,
            target_pos_b=2,
            role_a="subject",
            role_b="object",
        )
        assert pair.role_a == "subject"
        assert pair.role_b == "object"

    def test_intervention_result_has_control_fields(self):
        """InterventionResult should include control baseline statistics."""
        from scripts.causal_subspace.causal_intervention import InterventionResult
        result = InterventionResult(layer_idx=5)
        assert hasattr(result, "control_kl_mean")
        assert hasattr(result, "control_kl_std")
        assert hasattr(result, "adaptive_kl_threshold")
        assert result.control_kl_mean == 0.0


# ---------------------------------------------------------------------------
# Part 6: Layer Trajectory
# ---------------------------------------------------------------------------

class TestLayerTrajectory:
    def test_trajectory_plot(self):
        traj = LayerTrajectory(
            n_layers=6,
            label_name="test_role",
            layers=[0, 1, 2, 3, 4, 5],
            mdl_compression=[1.0, 1.2, 1.8, 2.5, 2.0, 1.5],
            mdl_bits_per_label=[2.3, 2.1, 1.8, 1.2, 1.5, 1.9],
            causal_success_rate=[0.1, 0.2, 0.3, 0.5, 0.4, 0.2],
            causal_flip_rate=[0.2, 0.3, 0.5, 0.7, 0.6, 0.3],
            causal_fluency_rate=[0.9, 0.9, 0.8, 0.8, 0.8, 0.9],
            pca_cumvar_at_k=[0.3, 0.4, 0.5, 0.6, 0.55, 0.45],
            crystallization_layer=3,
            consumption_layer=5,
            peak_compression=2.5,
            peak_causal_success=0.5,
        )

        output = plot_trajectory_ascii(traj)
        assert "CRYSTALLIZATION" in output
        assert "CONSUMPTION" in output
        assert "test_role" in output
        assert "Layer" in output

    def test_trajectory_empty(self):
        traj = LayerTrajectory(n_layers=0, label_name="empty")
        output = plot_trajectory_ascii(traj)
        assert "(no data)" in output

    def test_mdl_trajectory_increasing_signal(self, multi_layer_states):
        """Verify trajectory detects increasing structure across layers."""
        states, labels = multi_layer_states
        from scripts.causal_subspace.mdl_probing import MDLProbeConfig, run_mdl_probe

        cfg = MDLProbeConfig(n_portions=5, probe_epochs=10, device="cpu")

        compressions = []
        for layer_idx in sorted(states.keys()):
            result = run_mdl_probe(states[layer_idx], labels, layer_idx, "role", cfg)
            compressions.append(result.compression_ratio)

        # Later layers should generally compress better (more signal)
        first_half = np.mean(compressions[: len(compressions) // 2])
        second_half = np.mean(compressions[len(compressions) // 2 :])
        assert second_half > first_half, (
            f"Later layers should have higher compression: "
            f"first_half={first_half:.2f}, second_half={second_half:.2f}"
        )

    def test_trajectory_with_precomputed_mdl(self, multi_layer_states):
        """Trajectory should accept precomputed MDL results and skip recomputation."""
        from scripts.causal_subspace.mdl_probing import MDLProbeConfig, run_mdl_probe
        from scripts.causal_subspace.trajectory import compute_layer_trajectory

        states, labels = multi_layer_states
        cfg = MDLProbeConfig(n_portions=5, probe_epochs=10, device="cpu")

        # Precompute MDL results
        precomputed = {}
        for layer_idx in sorted(states.keys()):
            precomputed[layer_idx] = run_mdl_probe(
                states[layer_idx], labels, layer_idx, "role", cfg,
            )

        # Run trajectory with precomputed results
        traj = compute_layer_trajectory(
            hidden_states=states,
            labels=labels,
            label_name="role",
            subspace_k=8,
            mdl_cfg=cfg,
            run_interventions=False,
            precomputed_mdl=precomputed,
        )

        # Trajectory should use the exact same compression values
        for i, layer_idx in enumerate(traj.layers):
            assert abs(traj.mdl_compression[i] - precomputed[layer_idx].compression_ratio) < 1e-10


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_pca_then_mdl(self, synthetic_hidden_states):
        """PCA projection followed by MDL probing should compress more
        than random-label baseline on the same geometry."""
        H, labels = synthetic_hidden_states

        # PCA project to k dims
        from sklearn.decomposition import PCA
        pca = PCA(n_components=16, random_state=42)
        H_proj = pca.fit_transform(H)

        cfg = MDLProbeConfig(n_portions=8, probe_epochs=20, device="cpu")
        result = run_mdl_probe(H_proj, labels, 0, "pca_proj", cfg)

        # With well-separated data, the online code should be shorter
        # than using the label directly for each class's representation
        rng = np.random.RandomState(99)
        random_labels = rng.randint(0, 5, size=len(labels)).astype(np.int32)
        result_random = run_mdl_probe(H_proj, random_labels, 0, "random_proj", cfg)

        assert result.online_code_length < result_random.online_code_length, (
            f"Separable data should compress better than random: "
            f"real={result.online_code_length:.1f}, random={result_random.online_code_length:.1f}"
        )

    def test_sae_then_clustering_then_mdl(self, rng):
        """Full Part 3 → Part 4 pipeline on synthetic data."""
        N, d = 300, 32
        n_classes = 3
        labels = rng.randint(0, n_classes, size=N)

        # Create data with class structure
        class_means = rng.randn(n_classes, d) * 2.0
        H = np.zeros((N, d), dtype=np.float32)
        for i in range(N):
            H[i] = class_means[labels[i]] + rng.randn(d) * 0.5

        # SAE
        sae_cfg = DisentanglementConfig(
            sae_expansion_factor=2,
            sae_epochs=5,
            sae_batch_size=64,
            n_clusters=6,
            device="cpu",
        )
        _, features, _, _ = train_sae(H, sae_cfg)

        # Cluster
        cluster_labels, _ = cluster_sae_features(features, n_clusters=6)
        assert len(cluster_labels) == N

        # MDL on original space (should compress)
        mdl_cfg = MDLProbeConfig(n_portions=5, probe_epochs=10, device="cpu")
        result = run_mdl_probe(H, labels.astype(np.int32), 0, "integrated", mdl_cfg)
        assert result.compression_ratio > 1.0
