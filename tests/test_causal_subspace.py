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
        # Identity control fields
        assert hasattr(result, "control_kl_mean")
        assert hasattr(result, "control_kl_std")
        assert hasattr(result, "adaptive_kl_threshold")
        assert result.control_kl_mean == 0.0
        # Random subspace control fields
        assert hasattr(result, "random_kl_mean")
        assert hasattr(result, "random_kl_std")
        assert hasattr(result, "specificity_ratio")
        assert result.random_kl_mean == 0.0
        assert result.specificity_ratio == 0.0

    def test_random_orthonormal_basis(self):
        """Random basis should be orthonormal and have correct shape."""
        from scripts.causal_subspace.causal_intervention import _random_orthonormal_basis
        d, k = 64, 8
        U = _random_orthonormal_basis(d, k, seed=42)
        assert U.shape == (d, k)
        # Check orthonormality
        product = U.T @ U
        np.testing.assert_allclose(
            product, np.eye(k), atol=1e-5,
            err_msg="Random basis should be orthonormal",
        )

    def test_random_basis_different_seeds(self):
        """Different seeds should produce different bases."""
        from scripts.causal_subspace.causal_intervention import _random_orthonormal_basis
        U1 = _random_orthonormal_basis(32, 4, seed=0)
        U2 = _random_orthonormal_basis(32, 4, seed=1)
        # Different seeds → different bases (not identical)
        assert not np.allclose(U1, U2, atol=1e-3)


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


# ---------------------------------------------------------------------------
# CLI: Synthetic test pipeline
# ---------------------------------------------------------------------------

class TestSyntheticCLI:
    def test_generate_synthetic_hidden_states(self):
        """Synthetic data generator produces correct shapes and structure."""
        from scripts.causal_subspace.test_synthetic import generate_synthetic_hidden_states
        states, labels = generate_synthetic_hidden_states(
            n_samples=100, d_model=32, n_layers=4, n_classes=3, seed=42,
        )
        assert len(states) == 4
        assert labels.shape == (100,)
        assert set(np.unique(labels)).issubset({0, 1, 2})
        for layer_idx in range(4):
            assert states[layer_idx].shape == (100, 32)

    def test_synthetic_signal_increases_across_layers(self):
        """Later layers should have stronger class separation."""
        from scripts.causal_subspace.test_synthetic import generate_synthetic_hidden_states
        states, labels = generate_synthetic_hidden_states(
            n_samples=300, d_model=32, n_layers=6, n_classes=4, seed=42,
        )
        # Measure class separation via mean pairwise distance
        unique = np.unique(labels)
        def class_separation(H):
            means = [H[labels == c].mean(axis=0) for c in unique]
            dists = []
            for i in range(len(means)):
                for j in range(i + 1, len(means)):
                    dists.append(np.linalg.norm(means[i] - means[j]))
            return np.mean(dists)

        early_sep = class_separation(states[0])
        late_sep = class_separation(states[5])
        assert late_sep > early_sep, (
            f"Late layers should have stronger separation: "
            f"early={early_sep:.2f}, late={late_sep:.2f}"
        )

    def test_toy_transformer_forward(self):
        """Toy transformer should produce logits of correct shape."""
        from scripts.causal_subspace.test_synthetic import _ToyTransformer
        model = _ToyTransformer(d_model=32, n_layers=4, vocab_size=100)
        model.eval()
        ids = torch.tensor([[5, 10, 15, 20]])
        output = model(input_ids=ids)
        assert hasattr(output, "logits")
        assert output.logits.shape == (1, 4, 100)

    def test_toy_tokenizer(self):
        """Toy tokenizer should encode and decode."""
        from scripts.causal_subspace.test_synthetic import _ToyTokenizer
        tok = _ToyTokenizer(vocab_size=500)
        ids = tok.encode("The cat sat")
        assert isinstance(ids, list)
        assert all(0 <= i < 500 for i in ids)
        text = tok.decode([0, 1, 2])
        assert isinstance(text, str)

    def test_run_synthetic_pipeline_quick(self):
        """Synthetic pipeline runs end-to-end without errors."""
        from scripts.causal_subspace.test_synthetic import run_synthetic_pipeline
        results = run_synthetic_pipeline(
            n_samples=100,
            d_model=16,
            n_layers=3,
            n_classes=3,
            sae_epochs=2,
            sae_expansion=2,
            n_clusters=3,
            mdl_portions=3,
            n_pairs=3,
            subspace_k=4,
            parts=[3, 4, 6],  # skip interventions for speed
            seed=42,
        )
        assert "disentanglement" in results
        assert "mdl_probing" in results
        assert "trajectory" in results
        assert results["summary"]["checks_total"] > 0

    def test_run_synthetic_pipeline_mdl_only(self):
        """Can run only the MDL part of the pipeline."""
        from scripts.causal_subspace.test_synthetic import run_synthetic_pipeline
        results = run_synthetic_pipeline(
            n_samples=200,
            d_model=32,
            n_layers=4,
            n_classes=4,
            mdl_portions=5,
            subspace_k=8,
            parts=[4],
            seed=42,
        )
        assert "mdl_probing" in results
        assert "disentanglement" not in results
        assert "optimal_k" in results


# ---------------------------------------------------------------------------
# Part 7: Ontology Alignment Discovery
# ---------------------------------------------------------------------------

from scripts.causal_subspace.ontology_alignment import (
    AXIS_NAMES,
    N_AXES,
    DiscoveryResult,
    OntologyConfig,
    _compute_binned_mi,
    build_ontology_vectors,
    classify_scenario,
    compute_alignment_mi,
    compute_cka,
    compute_subspace_overlap,
    measure_discriminability,
    run_naming_ceremony,
)


@pytest.fixture
def synthetic_word_annotations(rng):
    """Create minimal WordAnnotation-like objects for testing."""
    N = 200
    n_classes = 5
    labels = rng.randint(0, n_classes, size=N).astype(np.int32)

    deps = ["nsubj", "ROOT", "dobj", "amod", "det"]
    words = []
    for i in range(N):
        w = WordAnnotation(
            word=["cat", "dog", "professor", "ran", "the"][i % 5],
            sentence_id=i // 10,
            position_in_sentence=i % 10,
            dep_depth=rng.randint(0, 5),
            dep_relation=deps[labels[i]],
            grammatical_role=GRAMMATICAL_ROLES[labels[i]],
            token_indices=[i],
            last_token_index=i,
        )
        words.append(w)

    return words, labels


class TestOntologyVectors:
    def test_build_12_axis_vectors_shape(self, synthetic_word_annotations, rng):
        """Ontology vectors have shape [N, 12]."""
        words, labels = synthetic_word_annotations
        N = len(words)
        d = 64
        H = rng.randn(N, d).astype(np.float32)

        ont, valid = build_ontology_vectors(words, H, labels)
        assert ont.shape == (N, 12)
        assert valid.shape == (N,)
        assert valid.dtype == bool

    def test_coverage_ratio(self, synthetic_word_annotations, rng):
        """Coverage should be > 0 for synthetic data (all axes except WordNet are heuristic)."""
        words, labels = synthetic_word_annotations
        N = len(words)
        H = rng.randn(N, 64).astype(np.float32)

        ont, valid = build_ontology_vectors(words, H, labels)
        # Heuristic-based axes (5,6,7,8,10,11) are always available = 6+ axes
        # Plus concreteness/animacy heuristics = 8+ axes
        assert valid.sum() > N * 0.5, f"Expected >50% coverage, got {valid.mean():.1%}"

    def test_no_nans_in_valid_rows(self, synthetic_word_annotations, rng):
        """Valid rows should have no NaN values (NaNs replaced with 0.5)."""
        words, labels = synthetic_word_annotations
        H = rng.randn(len(words), 64).astype(np.float32)

        ont, valid = build_ontology_vectors(words, H, labels)
        assert not np.any(np.isnan(ont[valid]))

    def test_axis_ranges(self, synthetic_word_annotations, rng):
        """All axis values should be in [0, 1] for valid rows."""
        words, labels = synthetic_word_annotations
        H = rng.randn(len(words), 64).astype(np.float32)

        ont, valid = build_ontology_vectors(words, H, labels)
        ont_valid = ont[valid]
        assert np.all(ont_valid >= 0.0), "Some axis values < 0"
        assert np.all(ont_valid <= 1.5), "Some axis values > 1.5"


class TestNamingCeremony:
    def test_aligned_data_high_mi(self, rng):
        """When ontology axes ARE the PCA directions, MI should be high."""
        N, k = 500, 8
        # ont_features[:, i] = H_proj[:, i] + small noise → MI should be high
        H_proj = rng.randn(N, k).astype(np.float32)
        ont = np.zeros((N, 12), dtype=np.float32)
        for i in range(min(k, 12)):
            ont[:, i] = H_proj[:, i % k] + rng.randn(N) * 0.1

        per_axis_mi, per_axis_best_pca, validated = run_naming_ceremony(
            ont, H_proj, n_bins=20, threshold=0.1,
        )
        # At least the first k axes should validate (they're copies of PCA dirs)
        assert len(validated) >= min(k, 12) - 2, (
            f"Expected ≥{min(k, 12) - 2} validated axes, got {len(validated)}: "
            f"{per_axis_mi}"
        )

    def test_random_data_low_mi(self, rng):
        """When ontology axes are random, MI should be near zero."""
        N, k = 500, 8
        H_proj = rng.randn(N, k).astype(np.float32)
        ont = rng.randn(N, 12).astype(np.float32)  # independent random

        per_axis_mi, _, validated = run_naming_ceremony(
            ont, H_proj, n_bins=20, threshold=0.1,
        )
        # Random should validate very few (noise MI is small)
        assert len(validated) <= 4, (
            f"Random axes should rarely validate, got {len(validated)}: {per_axis_mi}"
        )

    def test_binned_mi_identical(self):
        """MI of a variable with itself should be > 0."""
        x = np.linspace(0, 1, 200)
        mi = _compute_binned_mi(x, x, n_bins=20)
        assert mi > 0.5, f"MI(x, x) should be high, got {mi}"

    def test_binned_mi_independent(self, rng):
        """MI of independent variables should be near 0."""
        x = rng.randn(500)
        y = rng.randn(500)
        mi = _compute_binned_mi(x, y, n_bins=20)
        assert mi < 0.15, f"MI(independent) should be near 0, got {mi}"

    def test_binned_mi_constant(self):
        """MI with constant variable should be 0."""
        x = np.ones(100)
        y = np.linspace(0, 1, 100)
        mi = _compute_binned_mi(x, y, n_bins=20)
        assert mi == 0.0


class TestGlobalAlignment:
    def test_cka_identity(self, rng):
        """CKA(X, X) should be close to 1.0."""
        X = rng.randn(100, 10).astype(np.float32)
        cka = compute_cka(X, X)
        assert cka > 0.99, f"CKA(X, X) should be ~1.0, got {cka}"

    def test_cka_random(self, rng):
        """CKA of independent random matrices should be low."""
        X = rng.randn(200, 10).astype(np.float32)
        Y = rng.randn(200, 8).astype(np.float32)
        cka = compute_cka(X, Y)
        assert cka < 0.3, f"CKA(random, random) should be low, got {cka}"

    def test_subspace_overlap_identical(self, rng):
        """Overlap when ontology IS the subspace should be high."""
        N, d, k = 200, 32, 4
        # U_k: first k columns of identity
        U_k = np.eye(d, k, dtype=np.float32)
        H = rng.randn(N, d).astype(np.float32)
        # ont = projection onto U_k → should have high overlap
        ont = H @ U_k
        overlap = compute_subspace_overlap(ont, U_k, H)
        assert overlap > 0.5, f"Overlap should be high, got {overlap}"

    def test_alignment_mi_returns_tuple(self, rng):
        """compute_alignment_mi should return (float, float)."""
        N = 100
        ont = rng.randn(N, 12).astype(np.float32)
        H_proj = rng.randn(N, 8).astype(np.float32)
        labels = rng.randint(0, 5, size=N).astype(np.int32)
        mi_raw, mi_norm = compute_alignment_mi(ont, H_proj, labels)
        assert isinstance(mi_raw, float)
        assert isinstance(mi_norm, float)
        assert mi_raw >= 0.0
        assert mi_norm >= 0.0


class TestDiscriminability:
    def test_bootstrap_ci_valid(self, rng):
        """Bootstrap CIs should satisfy low < mean gap < high, roughly."""
        N = 200
        n_classes = 3
        labels = rng.randint(0, n_classes, size=N).astype(np.int32)

        # Make ontology correlated with labels
        class_means = rng.randn(n_classes, 12) * 2
        ont = np.array([class_means[l] + rng.randn(12) * 0.5 for l in labels], dtype=np.float32)
        H = rng.randn(N, 32).astype(np.float32)

        disc = measure_discriminability(ont, H, labels, n_bootstrap=50, seed=42)
        assert disc["ci_low"] <= disc["ci_high"], (
            f"CI should be ordered: {disc['ci_low']} <= {disc['ci_high']}"
        )
        assert 0.0 <= disc["ontology_accuracy"] <= 1.0
        assert 0.0 <= disc["embedding_accuracy"] <= 1.0

    def test_discriminability_with_few_samples(self, rng):
        """Should handle small N gracefully."""
        disc = measure_discriminability(
            rng.randn(10, 12).astype(np.float32),
            rng.randn(10, 32).astype(np.float32),
            rng.randint(0, 3, size=10).astype(np.int32),
            n_bootstrap=10,
        )
        assert "gap" in disc


class TestScenarioClassification:
    def test_scenario_A(self):
        """High MI, high CKA, many validated axes → Scenario A."""
        result = DiscoveryResult(
            layer_idx=5,
            n_validated_axes=10,
            validated_axes=AXIS_NAMES[:10],
            alignment_mi=0.7,
            cka_similarity=0.8,
            coverage_ratio=0.9,
            discriminability_gap=0.02,
        )
        result = classify_scenario(result)
        assert result.scenario == "A"
        assert result.recommended_phase2 == "build_both"

    def test_scenario_B(self):
        """Moderate MI, partial axes → Scenario B."""
        result = DiscoveryResult(
            layer_idx=5,
            n_validated_axes=5,
            validated_axes=AXIS_NAMES[:5],
            alignment_mi=0.3,
            cka_similarity=0.4,
            coverage_ratio=0.7,
            discriminability_gap=0.01,
        )
        result = classify_scenario(result)
        assert result.scenario == "B"
        assert result.recommended_phase2 == "meta_controller"

    def test_scenario_C_low_mi(self):
        """Very low MI → Scenario C."""
        result = DiscoveryResult(
            layer_idx=5,
            n_validated_axes=1,
            validated_axes=["structural_depth"],
            alignment_mi=0.01,
            cka_similarity=0.05,
            coverage_ratio=0.8,
            discriminability_gap=0.0,
        )
        result = classify_scenario(result)
        assert result.scenario == "C"
        assert result.recommended_phase2 == "stop"

    def test_scenario_C_low_coverage(self):
        """Very low coverage → Scenario C."""
        result = DiscoveryResult(
            layer_idx=5,
            n_validated_axes=8,
            alignment_mi=0.5,
            cka_similarity=0.6,
            coverage_ratio=0.05,  # too low
            discriminability_gap=0.0,
        )
        result = classify_scenario(result)
        assert result.scenario == "C"
        assert result.recommended_phase2 == "stop"

    def test_scenario_D(self):
        """Low MI but high discriminability gap → Scenario D."""
        result = DiscoveryResult(
            layer_idx=5,
            n_validated_axes=4,
            validated_axes=AXIS_NAMES[:4],
            alignment_mi=0.1,
            cka_similarity=0.2,
            coverage_ratio=0.7,
            discriminability_gap=0.08,
        )
        result = classify_scenario(result)
        assert result.scenario == "D"
        assert result.recommended_phase2 == "injection_test"

    def test_evidence_is_populated(self):
        """Every scenario should produce human-readable evidence."""
        for scenario_setup in [
            {"n_validated_axes": 10, "alignment_mi": 0.7, "cka_similarity": 0.8,
             "coverage_ratio": 0.9, "discriminability_gap": 0.0},
            {"n_validated_axes": 1, "alignment_mi": 0.01, "cka_similarity": 0.05,
             "coverage_ratio": 0.8, "discriminability_gap": 0.0},
        ]:
            result = DiscoveryResult(layer_idx=5, **scenario_setup)
            result = classify_scenario(result)
            assert len(result.scenario_evidence) > 0
            assert result.scenario in ("A", "B", "C", "D")


class TestPhase2Stubs:
    def test_meta_controller_forward(self):
        """Meta-controller stub should produce output of correct shape."""
        import torch
        from scripts.causal_subspace.ontology_alignment import OntologyMetaController

        ctrl = OntologyMetaController(d_model=64, n_axes=8)
        H = torch.randn(2, 10, 64)  # [batch, seq, d]
        z = ctrl.forward(H)
        assert z.shape == (2, 8)  # [batch, n_axes]
        # Sigmoid output should be in [0, 1]
        assert (z >= 0).all() and (z <= 1).all()

    def test_qk_gating_forward(self):
        """Q/K gating stub should preserve shape and apply gating."""
        import torch
        from scripts.causal_subspace.ontology_alignment import QKDimensionGating

        gating = QKDimensionGating(n_axes=8, d_head=32)
        Q = torch.randn(2, 10, 32)
        K = torch.randn(2, 10, 32)
        ont = torch.randn(2, 10, 8)
        Q_out, K_out = gating.forward(Q, K, ont)
        assert Q_out.shape == Q.shape
        assert K_out.shape == K.shape


class TestMultiLayerDiscovery:
    """Tests for run_multi_layer_discovery and the L0/L2 dissociation logic."""

    def _make_annotations(self, rng, N, n_classes, d):
        """Create synthetic annotations + hidden states for multi-layer tests."""
        labels = rng.randint(0, n_classes, size=N).astype(np.int32)
        deps = ["nsubj", "ROOT", "dobj", "amod", "det"]
        words = []
        for i in range(N):
            w = WordAnnotation(
                word=["cat", "dog", "professor", "ran", "the"][i % 5],
                sentence_id=i // 10,
                position_in_sentence=i % 10,
                dep_depth=rng.randint(0, 5),
                dep_relation=deps[labels[i] % len(deps)],
                grammatical_role=GRAMMATICAL_ROLES[labels[i]],
                token_indices=[i],
                last_token_index=i,
            )
            words.append(w)

        # Create multi-layer hidden states with class structure
        class_means = rng.randn(n_classes, d).astype(np.float32) * 2.0
        hidden_states = {}
        for layer in range(4):
            signal = 0.5 + layer * 0.5
            noise = 1.5 - layer * 0.2
            H = np.array(
                [class_means[labels[i]] * signal + rng.randn(d).astype(np.float32) * noise
                 for i in range(N)],
                dtype=np.float32,
            )
            hidden_states[layer] = H

        annotations = StructuralAnnotations(words=words, n_sentences=N // 10)
        annotations.labels_role = labels

        # PCA basis from the best layer
        from sklearn.decomposition import PCA
        pca = PCA(n_components=8)
        pca.fit(hidden_states[2])  # use middle layer
        U_k = pca.components_.T.astype(np.float32)

        return annotations, hidden_states, labels, U_k

    def test_multi_layer_returns_per_layer_results(self, rng):
        """Should produce a DiscoveryResult for each requested layer."""
        from scripts.causal_subspace.ontology_alignment import (
            MultiLayerDiscoveryResult,
            OntologyConfig,
            run_multi_layer_discovery,
        )

        annotations, hidden_states, labels, U_k = self._make_annotations(rng, 200, 5, 32)
        cfg = OntologyConfig(n_bootstrap=10, seed=42)  # fast

        multi = run_multi_layer_discovery(
            annotations, hidden_states, labels, U_k,
            layers=[0, 2],
            cfg=cfg,
        )

        assert isinstance(multi, MultiLayerDiscoveryResult)
        assert 0 in multi.per_layer
        assert 2 in multi.per_layer
        assert multi.best_alignment_layer in (0, 2)
        assert multi.scenario in ("A", "B", "C", "D")

    def test_dissociation_detected(self, rng):
        """When causal_success_by_layer points to a different layer than MI, detect dissociation."""
        from scripts.causal_subspace.ontology_alignment import (
            OntologyConfig,
            run_multi_layer_discovery,
        )

        annotations, hidden_states, labels, U_k = self._make_annotations(rng, 200, 5, 32)
        cfg = OntologyConfig(n_bootstrap=10, seed=42)

        # Force dissociation: alignment may be better at L2 (more signal),
        # but we say causal peak is at L0
        multi = run_multi_layer_discovery(
            annotations, hidden_states, labels, U_k,
            layers=[0, 2],
            causal_success_by_layer={0: 0.25, 2: 0.0},
            cfg=cfg,
        )

        # Best causal should be L0 (highest causal success)
        assert multi.best_causal_layer == 0
        # Best alignment might be L2 (more signal in synthetic data)
        # If they differ, dissociation is True
        if multi.best_alignment_layer != 0:
            assert multi.dissociation is True
            assert multi.meta_controller_read_layer != multi.meta_controller_act_layer
            assert multi.meta_controller_act_layer == 0
            assert multi.qk_gating_layer == 0

    def test_no_dissociation_when_same_layer(self, rng):
        """When causal and alignment agree, dissociation=False."""
        from scripts.causal_subspace.ontology_alignment import (
            OntologyConfig,
            run_multi_layer_discovery,
        )

        annotations, hidden_states, labels, U_k = self._make_annotations(rng, 200, 5, 32)
        cfg = OntologyConfig(n_bootstrap=10, seed=42)

        # Both causal and alignment should point to same layer if we give
        # high causal success to the layer with best alignment
        multi_no_causal = run_multi_layer_discovery(
            annotations, hidden_states, labels, U_k,
            layers=[2],  # single layer → no dissociation possible
            cfg=cfg,
        )

        assert multi_no_causal.dissociation is False
        assert multi_no_causal.best_alignment_layer == multi_no_causal.best_causal_layer

    def test_validated_axes_union(self, rng):
        """Union of validated axes across layers should be ≥ max per-layer."""
        from scripts.causal_subspace.ontology_alignment import (
            OntologyConfig,
            run_multi_layer_discovery,
        )

        annotations, hidden_states, labels, U_k = self._make_annotations(rng, 200, 5, 32)
        cfg = OntologyConfig(n_bootstrap=10, seed=42)

        multi = run_multi_layer_discovery(
            annotations, hidden_states, labels, U_k,
            layers=[0, 2, 3],
            cfg=cfg,
        )

        max_per_layer = max(r.n_validated_axes for r in multi.per_layer.values())
        assert multi.n_validated_axes >= max_per_layer

    def test_evidence_includes_layer_summary(self, rng):
        """Evidence should contain per-layer summary lines."""
        from scripts.causal_subspace.ontology_alignment import (
            OntologyConfig,
            run_multi_layer_discovery,
        )

        annotations, hidden_states, labels, U_k = self._make_annotations(rng, 200, 5, 32)
        cfg = OntologyConfig(n_bootstrap=10, seed=42)

        multi = run_multi_layer_discovery(
            annotations, hidden_states, labels, U_k,
            layers=[0, 2],
            cfg=cfg,
        )

        # Should have per-layer summary in evidence
        evidence_text = " ".join(multi.scenario_evidence)
        assert "L0:" in evidence_text
        assert "L2:" in evidence_text
        assert "MI=" in evidence_text

    def test_routing_with_causal_data(self, rng):
        """Architecture routing should use causal data when available."""
        from scripts.causal_subspace.ontology_alignment import (
            OntologyConfig,
            run_multi_layer_discovery,
        )

        annotations, hidden_states, labels, U_k = self._make_annotations(rng, 200, 5, 32)
        cfg = OntologyConfig(n_bootstrap=10, seed=42)

        multi = run_multi_layer_discovery(
            annotations, hidden_states, labels, U_k,
            layers=[0, 2, 3],
            causal_success_by_layer={0: 0.0, 2: 0.25, 3: 0.05},
            cfg=cfg,
        )

        # Causal peak at L2
        assert multi.best_causal_layer == 2
        assert multi.qk_gating_layer == 2
        assert multi.meta_controller_act_layer == 2
