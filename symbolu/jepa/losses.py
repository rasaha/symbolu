"""
JEPA Loss Functions for Phase-JEPA Training.

This module implements loss functions for Joint Embedding Predictive Architecture
training, including VICReg regularization and alignment losses.

References:
    - Bardes et al., "VICReg: Variance-Invariance-Covariance Regularization"
    - HYBRID_PHASE_JEPA_DESIGN.md §6, §22
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple


class VICRegLoss(nn.Module):
    """
    Variance-Invariance-Covariance Regularization.

    Prevents representation collapse in JEPA training without negative samples.

    Components:
        - Invariance: MSE between predicted and target representations
        - Variance: Hinge loss ensuring each dimension has variance > threshold
        - Covariance: Decorrelates dimensions to encourage independence

    Args:
        sim_coeff: Weight for invariance (similarity) loss
        std_coeff: Weight for variance (standard deviation) loss
        cov_coeff: Weight for covariance loss
        var_threshold: Minimum variance threshold (default 1.0)
    """

    def __init__(
        self,
        sim_coeff: float = 25.0,
        std_coeff: float = 25.0,
        cov_coeff: float = 1.0,
        var_threshold: float = 1.0,
    ):
        super().__init__()
        self.sim_coeff = sim_coeff
        self.std_coeff = std_coeff
        self.cov_coeff = cov_coeff
        self.var_threshold = var_threshold

    def forward(
        self,
        x: torch.Tensor,
        y: torch.Tensor,
        return_components: bool = False,
    ) -> torch.Tensor:
        """
        Compute VICReg loss.

        Args:
            x: [B, D] predicted representations
            y: [B, D] target representations (should be stop-gradiented)
            return_components: If True, return dict with individual losses

        Returns:
            loss: Scalar VICReg loss (or dict if return_components=True)
        """
        batch_size, num_features = x.shape

        # 1. Invariance Loss (MSE between predicted and target)
        repr_loss = F.mse_loss(x, y)

        # 2. Variance Loss (Hinge) - prevents collapse to a point
        # Ensure each dimension has variance >= threshold
        std_x = torch.sqrt(x.var(dim=0) + 1e-4)
        std_y = torch.sqrt(y.var(dim=0) + 1e-4)
        std_loss = (
            torch.mean(F.relu(self.var_threshold - std_x)) / 2 +
            torch.mean(F.relu(self.var_threshold - std_y)) / 2
        )

        # 3. Covariance Loss - decorrelates dimensions
        x_centered = x - x.mean(dim=0)
        y_centered = y - y.mean(dim=0)

        cov_x = (x_centered.T @ x_centered) / (batch_size - 1)
        cov_y = (y_centered.T @ y_centered) / (batch_size - 1)

        # Sum of squared off-diagonal elements (should be zero for independent dims)
        cov_loss = (
            self._off_diagonal(cov_x).pow(2).sum() / num_features +
            self._off_diagonal(cov_y).pow(2).sum() / num_features
        )

        # Weighted sum
        total_loss = (
            self.sim_coeff * repr_loss +
            self.std_coeff * std_loss +
            self.cov_coeff * cov_loss
        )

        if return_components:
            return {
                'total': total_loss,
                'invariance': repr_loss,
                'variance': std_loss,
                'covariance': cov_loss,
            }
        return total_loss

    def _off_diagonal(self, x: torch.Tensor) -> torch.Tensor:
        """Extract off-diagonal elements from square matrix."""
        n, m = x.shape
        assert n == m, f"Expected square matrix, got {n}x{m}"
        return x.flatten()[:-1].view(n - 1, n + 1)[:, 1:].flatten()


class WeightedAlignmentLoss(nn.Module):
    """
    Per-component weighted MSE for Phase 3 (Union) training.

    Enforces S_visual ≈ S_text with different weights per component:
        - High weight on Bhavas [0:12] - Critical Identity
        - Medium weight on Kosha/Vritti [12:22] - Standard semantic
        - Low weight on Guna/Reserved [22:32] - Loose coupling

    Rationale:
        "Dog" (Vision) and "Dog" (Text) must share Identity (Bhava),
        but images are often Tamasic (static) while words like "Run!"
        are Rajasic (active). Enforcing Guna alignment would confuse the model.

    Args:
        bhava_weight: Weight for Bhava dimensions [0:12]
        semantic_weight: Weight for Kosha/Vritti dimensions [12:22]
        guna_weight: Weight for Guna/Reserved dimensions [22:32]
        state_dim: Sovereign State dimension (default 32)
    """

    def __init__(
        self,
        bhava_weight: float = 10.0,
        semantic_weight: float = 1.0,
        guna_weight: float = 0.1,
        state_dim: int = 32,
    ):
        super().__init__()

        # Build weight vector
        weights = torch.ones(state_dim)
        weights[0:12] = bhava_weight      # Bhavas: Critical Identity
        weights[12:22] = semantic_weight  # Kosha/Vritti: Standard
        weights[22:32] = guna_weight      # Guna/Reserved: Loose coupling

        self.register_buffer('weights', weights)
        self.state_dim = state_dim

    def forward(
        self,
        s_visual: torch.Tensor,
        s_text: torch.Tensor,
        return_components: bool = False,
    ) -> torch.Tensor:
        """
        Compute weighted alignment loss.

        Args:
            s_visual: [B, 32] Visual state from JEPA
            s_text: [B, 32] Text state from SRK
            return_components: If True, return dict with per-component losses

        Returns:
            loss: Weighted alignment loss
        """
        diff_squared = (s_visual - s_text) ** 2  # [B, 32]
        weighted_diff = diff_squared * self.weights  # [B, 32]

        total_loss = weighted_diff.mean()

        if return_components:
            return {
                'total': total_loss,
                'bhava_loss': diff_squared[:, 0:12].mean(),
                'semantic_loss': diff_squared[:, 12:22].mean(),
                'guna_loss': diff_squared[:, 22:32].mean(),
            }
        return total_loss


class JEPAPredictionLoss(nn.Module):
    """
    Main JEPA prediction loss with optional regularization.

    Combines:
        - MSE prediction loss (predicted vs target state)
        - Optional VICReg regularization
        - Optional orthogonality constraint

    Args:
        vicreg_weight: Weight for VICReg loss (0 to disable)
        ortho_weight: Weight for orthogonality loss (0 to disable)
    """

    def __init__(
        self,
        vicreg_weight: float = 1.0,
        ortho_weight: float = 0.1,
    ):
        super().__init__()
        self.vicreg_weight = vicreg_weight
        self.ortho_weight = ortho_weight

        if vicreg_weight > 0:
            self.vicreg = VICRegLoss()
        else:
            self.vicreg = None

    def forward(
        self,
        s_pred: torch.Tensor,
        s_target: torch.Tensor,
        predictor_weight: torch.Tensor = None,
        return_components: bool = False,
    ) -> torch.Tensor:
        """
        Compute JEPA prediction loss.

        Args:
            s_pred: [B, T, D] or [B, D] predicted states
            s_target: [B, T, D] or [B, D] target states (stop-gradiented)
            predictor_weight: Optional weight matrix for orthogonality constraint
            return_components: If True, return dict with individual losses

        Returns:
            loss: Total JEPA loss
        """
        # Flatten if needed for VICReg
        if s_pred.dim() == 3:
            B, T, D = s_pred.shape
            s_pred_flat = s_pred.reshape(-1, D)
            s_target_flat = s_target.reshape(-1, D)
        else:
            s_pred_flat = s_pred
            s_target_flat = s_target

        # 1. MSE Prediction Loss
        pred_loss = F.mse_loss(s_pred, s_target.detach())

        # 2. VICReg Regularization
        if self.vicreg is not None and self.vicreg_weight > 0:
            vicreg_loss = self.vicreg(s_pred_flat, s_target_flat.detach())
        else:
            vicreg_loss = torch.tensor(0.0, device=s_pred.device)

        # 3. Orthogonality Constraint
        if predictor_weight is not None and self.ortho_weight > 0:
            ortho_loss = self._compute_ortho_loss(predictor_weight)
        else:
            ortho_loss = torch.tensor(0.0, device=s_pred.device)

        # Total
        total_loss = (
            pred_loss +
            self.vicreg_weight * vicreg_loss +
            self.ortho_weight * ortho_loss
        )

        if return_components:
            return {
                'total': total_loss,
                'prediction': pred_loss,
                'vicreg': vicreg_loss,
                'ortho': ortho_loss,
            }
        return total_loss

    def _compute_ortho_loss(self, W: torch.Tensor) -> torch.Tensor:
        """
        Orthogonality constraint: W^T W ≈ I.

        Ensures the prediction transformation preserves information volume.
        """
        WtW = W.T @ W
        I = torch.eye(WtW.shape[0], device=W.device)
        return torch.norm(WtW - I)


class CompositeJEPALoss(nn.Module):
    """
    Complete loss function combining JEPA, VICReg, and Patent losses.

    L_total = λ_jepa * L_JEPA + λ_vicreg * L_VICReg + λ_patent * L_Patent

    Supports curriculum-based weight scheduling via training phase.

    Args:
        jepa_weight: Weight for JEPA prediction loss
        vicreg_weight: Weight for VICReg regularization
        alignment_weight: Weight for cross-modal alignment
    """

    def __init__(
        self,
        jepa_weight: float = 1.0,
        vicreg_weight: float = 1.0,
        alignment_weight: float = 0.0,
    ):
        super().__init__()
        self.jepa_weight = jepa_weight
        self.vicreg_weight = vicreg_weight
        self.alignment_weight = alignment_weight

        self.vicreg_loss = VICRegLoss()
        self.alignment_loss = WeightedAlignmentLoss()

    def forward(
        self,
        s_pred: torch.Tensor,
        s_target: torch.Tensor,
        s_visual: torch.Tensor = None,
        s_text: torch.Tensor = None,
        training_phase: int = 1,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute composite loss based on training phase.

        Training Phases:
            1 (Dhyāna): High VICReg, standard JEPA
            2 (Saṃvāda): Balanced VICReg + JEPA
            3 (Kṛti): Add alignment loss for cross-modal

        Args:
            s_pred: Predicted states
            s_target: Target states
            s_visual: Visual states (for Phase 3)
            s_text: Text states (for Phase 3)
            training_phase: Current training phase (1, 2, or 3)

        Returns:
            Dict with 'total' and component losses
        """
        losses = {}

        # JEPA Prediction Loss
        losses['jepa'] = F.mse_loss(s_pred, s_target.detach())

        # VICReg
        if s_pred.dim() == 3:
            s_pred_flat = s_pred.reshape(-1, s_pred.shape[-1])
            s_target_flat = s_target.reshape(-1, s_target.shape[-1])
        else:
            s_pred_flat = s_pred
            s_target_flat = s_target

        vicreg_result = self.vicreg_loss(s_pred_flat, s_target_flat.detach(), return_components=True)
        losses['variance'] = vicreg_result['variance']
        losses['covariance'] = vicreg_result['covariance']

        # Alignment (Phase 3 only)
        if training_phase >= 3 and s_visual is not None and s_text is not None:
            losses['alignment'] = self.alignment_loss(s_visual, s_text)
        else:
            losses['alignment'] = torch.tensor(0.0, device=s_pred.device)

        # Phase-based weighting
        if training_phase == 1:  # Dhyāna
            losses['total'] = (
                losses['jepa'] +
                2.0 * losses['variance'] +
                0.5 * losses['covariance']
            )
        elif training_phase == 2:  # Saṃvāda
            losses['total'] = (
                losses['jepa'] +
                1.0 * losses['variance'] +
                0.5 * losses['covariance']
            )
        else:  # Kṛti
            losses['total'] = (
                0.3 * losses['jepa'] +
                0.1 * losses['variance'] +
                self.alignment_weight * losses['alignment']
            )

        return losses
