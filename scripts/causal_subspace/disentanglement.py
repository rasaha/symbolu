"""
Part 3 — Feature Disentanglement (SAE + Manifold Clustering)
=============================================================

1. **Global Orthogonal Check**: PCA to establish a baseline explained
   variance curve.
2. **Sparsity Extraction**: Train a Sparse Autoencoder (SAE) on the hidden
   state matrix H ∈ R^{N×d} to extract non-orthogonal, superposed
   structural features.
3. **Contextual Clustering**: Apply K-means to SAE feature activations
   before mapping them to structural labels (because structural roles like
   "subject" may occupy different manifolds depending on context).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DisentanglementConfig:
    """Configuration for the PCA + SAE + clustering pipeline."""

    # PCA
    pca_n_components: int = 64
    """Number of PCA components for the baseline variance curve."""

    # SAE
    sae_expansion_factor: int = 4
    """SAE hidden dimension = d_model * expansion_factor."""

    sae_sparsity_coeff: float = 1e-3
    """L1 penalty on SAE latent activations (controls sparsity)."""

    sae_lr: float = 1e-3
    sae_epochs: int = 50
    sae_batch_size: int = 512

    # Clustering
    n_clusters: int = 32
    """Number of K-means clusters over SAE activations."""

    seed: int = 42
    device: str = "cpu"


# ---------------------------------------------------------------------------
# Results container
# ---------------------------------------------------------------------------

@dataclass
class DisentanglementResult:
    """Output of the disentanglement pipeline for one layer."""

    layer_idx: int = 0

    # PCA
    pca_explained_variance: Optional[np.ndarray] = None
    pca_cumulative_variance: Optional[np.ndarray] = None
    pca_components: Optional[np.ndarray] = None  # [k, d]

    # SAE
    sae_features: Optional[np.ndarray] = None  # [N, sae_dim] activations
    sae_reconstruction_loss: float = 0.0
    sae_sparsity: float = 0.0  # mean L0 of features
    sae_model: Optional[SparseAutoencoder] = None

    # Clustering
    cluster_labels: Optional[np.ndarray] = None  # [N]
    cluster_centers: Optional[np.ndarray] = None  # [K, sae_dim]


# ---------------------------------------------------------------------------
# PCA baseline
# ---------------------------------------------------------------------------

def compute_pca_baseline(
    H: np.ndarray,
    n_components: int = 64,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute PCA explained variance curve.

    Parameters
    ----------
    H : np.ndarray [N, d]
    n_components : int

    Returns
    -------
    explained_var : np.ndarray [k]
    cumulative_var : np.ndarray [k]
    components : np.ndarray [k, d]
    """
    from sklearn.decomposition import PCA

    k = min(n_components, H.shape[1], H.shape[0])
    pca = PCA(n_components=k, random_state=42)
    pca.fit(H)

    explained = pca.explained_variance_ratio_
    cumulative = np.cumsum(explained)
    components = pca.components_

    logger.info(
        "PCA: %d components explain %.1f%% of variance (top-10: %.1f%%)",
        k, cumulative[-1] * 100, cumulative[min(9, k - 1)] * 100,
    )
    return explained, cumulative, components


# ---------------------------------------------------------------------------
# Sparse Autoencoder
# ---------------------------------------------------------------------------

class SparseAutoencoder(nn.Module):
    """A sparse autoencoder for extracting superposed features from hidden
    states.

    Architecture:
        encoder: Linear(d → sae_dim) + ReLU
        decoder: Linear(sae_dim → d)  with unit-norm column constraint

    Loss = MSE_reconstruction + sparsity_coeff * L1(latent)

    The decoder columns are constrained to unit norm after each optimizer
    step via :meth:`constrain_decoder_norms`.  This prevents the SAE from
    shrinking decoder norms to trivially reduce the L1 penalty on latent
    activations (Bricken et al., 2023).
    """

    def __init__(self, d_model: int, sae_dim: int):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(d_model, sae_dim),
            nn.ReLU(),
        )
        self.decoder = nn.Linear(sae_dim, d_model)

        # Initialize decoder as approximate transpose of encoder
        with torch.no_grad():
            self.decoder.weight.copy_(self.encoder[0].weight.T)
            self._normalize_decoder()

    def _normalize_decoder(self) -> None:
        """Project decoder columns to unit norm."""
        with torch.no_grad():
            # decoder.weight shape: [d_model, sae_dim]
            # Each column (feature direction) should be unit norm
            norms = self.decoder.weight.norm(dim=0, keepdim=True).clamp(min=1e-8)
            self.decoder.weight.div_(norms)

    def constrain_decoder_norms(self) -> None:
        """Call after each optimizer.step() to enforce the unit-norm
        constraint on decoder columns."""
        self._normalize_decoder()

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
            x_hat: reconstructed input
            latent: sparse feature activations
            pre_act: pre-activation (before ReLU)
        """
        pre_act = self.encoder[0](x)
        latent = F.relu(pre_act)
        x_hat = self.decoder(latent)
        return x_hat, latent, pre_act

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)


def train_sae(
    H: np.ndarray,
    cfg: DisentanglementConfig,
) -> Tuple[SparseAutoencoder, np.ndarray, float, float]:
    """Train a sparse autoencoder on hidden states H.

    Returns
    -------
    sae : SparseAutoencoder
    features : np.ndarray [N, sae_dim]
    recon_loss : float
    sparsity : float  (mean L0 norm)
    """
    device = torch.device(cfg.device)
    N, d = H.shape
    sae_dim = d * cfg.sae_expansion_factor

    sae = SparseAutoencoder(d, sae_dim).to(device)
    optimizer = torch.optim.Adam(sae.parameters(), lr=cfg.sae_lr)

    # Normalize input
    H_mean = H.mean(axis=0)
    H_std = H.std(axis=0) + 1e-8
    H_norm = (H - H_mean) / H_std
    data = torch.tensor(H_norm, dtype=torch.float32)

    logger.info(
        "Training SAE: d=%d → sae_dim=%d, N=%d, epochs=%d",
        d, sae_dim, N, cfg.sae_epochs,
    )

    sae.train()
    for epoch in range(cfg.sae_epochs):
        perm = torch.randperm(N)
        total_recon = 0.0
        total_l1 = 0.0
        n_batches = 0

        for start in range(0, N, cfg.sae_batch_size):
            idx = perm[start : start + cfg.sae_batch_size]
            x = data[idx].to(device)

            x_hat, latent, _ = sae(x)
            recon_loss = F.mse_loss(x_hat, x)
            l1_loss = latent.abs().mean()
            loss = recon_loss + cfg.sae_sparsity_coeff * l1_loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # Enforce unit-norm decoder columns (prevents L1 shortcut)
            sae.constrain_decoder_norms()

            total_recon += recon_loss.item()
            total_l1 += l1_loss.item()
            n_batches += 1

        if (epoch + 1) % 10 == 0 or epoch == 0:
            logger.info(
                "  SAE epoch %d/%d: recon=%.4f, L1=%.4f",
                epoch + 1, cfg.sae_epochs,
                total_recon / n_batches, total_l1 / n_batches,
            )

    # Extract features
    sae.eval()
    all_features = []
    with torch.no_grad():
        for start in range(0, N, cfg.sae_batch_size):
            x = data[start : start + cfg.sae_batch_size].to(device)
            _, latent, _ = sae(x)
            all_features.append(latent.cpu().numpy())

    features = np.concatenate(all_features, axis=0)

    recon_loss_final = total_recon / max(n_batches, 1)
    sparsity = float((features > 0).sum(axis=1).mean())  # mean L0

    logger.info(
        "SAE training complete: recon=%.4f, mean L0=%.1f / %d (%.1f%% active)",
        recon_loss_final, sparsity, sae_dim, 100.0 * sparsity / sae_dim,
    )

    return sae, features, recon_loss_final, sparsity


# ---------------------------------------------------------------------------
# Contextual K-means clustering
# ---------------------------------------------------------------------------

def cluster_sae_features(
    features: np.ndarray,
    n_clusters: int,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply K-means clustering to SAE feature activations.

    Returns
    -------
    labels : np.ndarray [N]
    centers : np.ndarray [K, sae_dim]
    """
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=n_clusters, random_state=seed, n_init=10, max_iter=300)
    labels = km.fit_predict(features)
    centers = km.cluster_centers_

    # Report cluster distribution
    unique, counts = np.unique(labels, return_counts=True)
    logger.info(
        "K-means: %d clusters, min_size=%d, max_size=%d, median=%d",
        len(unique), counts.min(), counts.max(), int(np.median(counts)),
    )
    return labels, centers


# ---------------------------------------------------------------------------
# Full pipeline per layer
# ---------------------------------------------------------------------------

def run_disentanglement(
    H: np.ndarray,
    layer_idx: int,
    cfg: DisentanglementConfig,
) -> DisentanglementResult:
    """Run the complete disentanglement pipeline on hidden states for one layer.

    Steps:
        1. PCA baseline
        2. SAE training
        3. K-means clustering on SAE features

    Parameters
    ----------
    H : np.ndarray [N, d]
    layer_idx : int
    cfg : DisentanglementConfig

    Returns
    -------
    DisentanglementResult
    """
    result = DisentanglementResult(layer_idx=layer_idx)

    # 1. PCA baseline
    logger.info("=== Layer %d: PCA baseline ===", layer_idx)
    ev, cv, comps = compute_pca_baseline(H, cfg.pca_n_components)
    result.pca_explained_variance = ev
    result.pca_cumulative_variance = cv
    result.pca_components = comps

    # 2. SAE
    logger.info("=== Layer %d: SAE training ===", layer_idx)
    sae, features, recon_loss, sparsity = train_sae(H, cfg)
    result.sae_features = features
    result.sae_reconstruction_loss = recon_loss
    result.sae_sparsity = sparsity
    result.sae_model = sae

    # 3. K-means clustering
    logger.info("=== Layer %d: Contextual clustering ===", layer_idx)
    labels, centers = cluster_sae_features(features, cfg.n_clusters, cfg.seed)
    result.cluster_labels = labels
    result.cluster_centers = centers

    return result
