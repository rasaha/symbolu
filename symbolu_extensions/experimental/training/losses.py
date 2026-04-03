"""
SymbolU12 Training Losses: The Mathematical Conscience
=======================================================

This module houses the core loss functions that enforce Axiomatic Compliance
during Sattva-1 training. The key insight:

    Standard training: Minimize (predicted_token - target_token)
    Sattva-1 training: Minimize (internal_logic - external_expression)

The Axiom-Compliance Loss (L_AX) is the dominant term, ensuring that the
model's "soul" (R_internal) cannot diverge from its "speech" (R_external).
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import torch
import torch.nn as nn
import torch.nn.functional as F


# =============================================================================
# AXIOM-COMPLIANCE LOSS (L_AX)
# =============================================================================

class AxiomComplianceLoss(nn.Module):
    """
    Forces alignment between Internal Reasoning (R_int) and
    External Expression (R_ext) using a Trace-based penalty.

    The "Viveka Gradient": If the model generates a response where the
    token space disagrees with the internal Phase-Lock Trace, the penalty
    is massive, forcing the gradient to correct the model's reasoning.

    Three-Tier Penalty Structure:
    - Tier 1 (τ ≥ threshold): No penalty - aligned
    - Tier 2 (τ_critical ≤ τ < threshold): Quadratic penalty
    - Tier 3 (τ < τ_critical): Maximum penalty (gradient explosion)

    Args:
        lambda_weight: Weight multiplier for the loss (default: 7.5)
        tau_threshold: Base Phase-Lock threshold (default: 0.75)
        tau_critical: Hard failure threshold (default: 0.30)
        gamma: Penalty multiplier for Tier 2 (default: 100.0)
        gradient_clip: Maximum penalty value to prevent NaN (default: 1000.0)
        confidence_scaling: Scale threshold by confidence (default: 0.2)
    """

    def __init__(
        self,
        lambda_weight: float = 7.5,
        tau_threshold: float = 0.75,
        tau_critical: float = 0.30,
        gamma: float = 100.0,
        gradient_clip: float = 1000.0,
        confidence_scaling: float = 0.2,
    ):
        super().__init__()
        self.lambda_weight = lambda_weight
        self.tau_threshold = tau_threshold
        self.tau_critical = tau_critical
        self.gamma = gamma
        self.gradient_clip = gradient_clip
        self.confidence_scaling = confidence_scaling

    def compute_trace(
        self,
        R_int: torch.Tensor,
        R_ext: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute normalized trace alignment: Tr(R_int · R_ext^T) / dim

        Args:
            R_int: Internal logic matrix [B, D, D] or [D, D]
            R_ext: External expression matrix [B, D, D] or [D, D]

        Returns:
            Trace values [B] or scalar
        """
        # Handle both batched and unbatched inputs
        if R_int.dim() == 2:
            R_int = R_int.unsqueeze(0)
            R_ext = R_ext.unsqueeze(0)
            squeeze_output = True
        else:
            squeeze_output = False

        # Compute alignment matrix: R_int @ R_ext^T
        alignment = torch.bmm(R_int, R_ext.transpose(-1, -2))

        # Extract trace (sum of diagonal elements)
        dim = R_int.size(-1)
        trace = torch.diagonal(alignment, dim1=-2, dim2=-1).sum(-1) / dim

        if squeeze_output:
            trace = trace.squeeze(0)

        return trace

    def forward(
        self,
        R_int: torch.Tensor,
        R_ext: torch.Tensor,
        confidence: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute Axiom-Compliance Loss.

        Args:
            R_int: Internal logic matrix [B, D, D]
            R_ext: External expression matrix [B, D, D]
            confidence: Current confidence values [B] (optional)

        Returns:
            loss: Scalar loss value
            tau: Trace values [B] for monitoring
        """
        # Compute trace alignment
        tau = self.compute_trace(R_int, R_ext)

        # Dynamic threshold based on confidence
        # Higher confidence = stricter alignment required
        if confidence is not None:
            dynamic_tau = self.tau_threshold + self.confidence_scaling * confidence
        else:
            dynamic_tau = self.tau_threshold

        # Compute violation (positive when tau < threshold)
        violation = dynamic_tau - tau

        # Three-tier penalty structure
        if tau.dim() == 0:
            # Scalar case
            if tau >= dynamic_tau:
                penalty = torch.tensor(0.0, device=tau.device)
            elif tau >= self.tau_critical:
                penalty = self.gamma * (violation ** 2)
            else:
                penalty = torch.tensor(self.gradient_clip, device=tau.device)
        else:
            # Batched case
            penalty = torch.zeros_like(tau)

            # Tier 1: Above threshold - no penalty
            mask_ok = tau >= dynamic_tau

            # Tier 2: Below threshold but above critical - quadratic penalty
            mask_warning = (tau < dynamic_tau) & (tau >= self.tau_critical)
            penalty[mask_warning] = self.gamma * (violation[mask_warning] ** 2)

            # Tier 3: Below critical - explosive penalty (capped)
            mask_critical = tau < self.tau_critical
            penalty[mask_critical] = self.gradient_clip

        # Apply lambda weight and reduce
        loss = self.lambda_weight * penalty.mean()

        return loss, tau


# =============================================================================
# BHAVA CONTRASTIVE LOSS
# =============================================================================

class BhavaContrastiveLoss(nn.Module):
    """
    Contrastive loss for sharpening the 12 Bhava boundaries.

    Trains the model to distinguish "Pure Fact" from "Pure Speculation"
    by encouraging the correct Bhava while penalizing forbidden ones.

    L_bhava = -log(P(correct_bhava)) + margin * max(0, P(wrong_bhava) - δ)

    Args:
        margin: Penalty margin for wrong Bhavas (default: 0.3)
        num_bhavas: Number of Bhava states (default: 12)
        temperature: Softmax temperature (default: 1.0)
    """

    def __init__(
        self,
        margin: float = 0.3,
        num_bhavas: int = 12,
        temperature: float = 1.0,
    ):
        super().__init__()
        self.margin = margin
        self.num_bhavas = num_bhavas
        self.temperature = temperature

    def forward(
        self,
        bhava_logits: torch.Tensor,
        target_bhava: torch.Tensor,
        forbidden_bhavas: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute contrastive Bhava loss.

        Args:
            bhava_logits: Raw Bhava scores [B, 12]
            target_bhava: Target Bhava indices [B]
            forbidden_bhavas: Indices of wrong Bhavas [B, K] (optional)

        Returns:
            loss: Scalar contrastive loss
        """
        # Apply temperature and softmax
        bhava_probs = F.softmax(bhava_logits / self.temperature, dim=-1)

        # Positive loss: encourage correct Bhava
        target_probs = bhava_probs.gather(1, target_bhava.unsqueeze(1)).squeeze(1)
        positive_loss = -torch.log(target_probs + 1e-8)

        # Negative loss: penalize forbidden Bhavas if provided
        if forbidden_bhavas is not None:
            forbidden_probs = bhava_probs.gather(1, forbidden_bhavas)
            negative_loss = torch.clamp(
                forbidden_probs - self.margin, min=0
            ).sum(dim=-1)
        else:
            negative_loss = torch.zeros_like(positive_loss)

        return (positive_loss + negative_loss).mean()


# =============================================================================
# EPISTEMIC DECAY LOSS
# =============================================================================

class EpistemicDecayLoss(nn.Module):
    """
    Penalizes confidence without epistemic grounding.

    When the model enters Vikalpa (Imagination) territory, its confidence
    should decay. This loss enforces that relationship.

    L_decay = α * (actual_confidence - expected_confidence)²

    where expected_confidence is low for speculative content.

    Args:
        alpha: Base decay weight (default: 5.0)
        vritti_decay_rates: Per-Vṛtti decay rates (optional)
    """

    # Default Vṛtti-specific decay rates from Gemini
    DEFAULT_VRITTI_DECAY = {
        0: 0.01,   # Pramāṇa - Truth decays slowest
        1: 0.15,   # Viparyaya - Error decays moderately
        2: 0.60,   # Vikalpa - Speculation decays fastest
        3: 0.10,   # Smṛti - Memory decays slowly
        4: 0.30,   # Nidrā - Reflection decays moderately
    }

    def __init__(
        self,
        alpha: float = 5.0,
        vritti_decay_rates: Optional[Dict[int, float]] = None,
    ):
        super().__init__()
        self.alpha = alpha
        self.vritti_decay_rates = vritti_decay_rates or self.DEFAULT_VRITTI_DECAY

        # Register as buffer for device compatibility
        decay_tensor = torch.zeros(5)
        for idx, rate in self.vritti_decay_rates.items():
            decay_tensor[idx] = rate
        self.register_buffer('decay_rates', decay_tensor)

    def forward(
        self,
        confidence: torch.Tensor,
        vritti_indices: torch.Tensor,
        time_steps: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute epistemic decay loss.

        Args:
            confidence: Current confidence values [B]
            vritti_indices: Dominant Vṛtti indices [B]
            time_steps: Time since grounding (optional) [B]

        Returns:
            loss: Scalar decay loss
        """
        # Get decay rate for each sample based on Vṛtti
        decay_rates = self.decay_rates[vritti_indices]

        # Expected confidence after decay
        if time_steps is not None:
            expected_confidence = torch.exp(-decay_rates * time_steps)
        else:
            # Use decay rate as target confidence floor
            expected_confidence = 1.0 - decay_rates

        # Penalize confidence that exceeds expected
        overconfidence = torch.relu(confidence - expected_confidence)
        loss = self.alpha * (overconfidence ** 2).mean()

        return loss


# =============================================================================
# SMṚTI PERSISTENCE LOSS
# =============================================================================

class SmritiPersistenceLoss(nn.Module):
    """
    Trains the model to maintain its "Sattvic Seed" over long contexts.

    The model should resist adversarial noise and maintain anchor facts.

    L_persist = κ * ‖S_current - S_anchor‖² (when anchor should persist)
              + (1-κ) * ‖S_current - S_new‖² (when update is valid)

    Args:
        kappa: Persistence strength (default: 0.7)
        anchor_threshold: Threshold for anchor maintenance (default: 0.8)
    """

    def __init__(
        self,
        kappa: float = 0.7,
        anchor_threshold: float = 0.8,
    ):
        super().__init__()
        self.kappa = kappa
        self.anchor_threshold = anchor_threshold

    def forward(
        self,
        current_state: torch.Tensor,
        anchor_state: torch.Tensor,
        should_persist: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute Smṛti persistence loss.

        Args:
            current_state: Current cognitive state [B, D]
            anchor_state: Anchor (Sattvic Seed) state [B, D]
            should_persist: Boolean mask for persistence [B] (optional)

        Returns:
            loss: Scalar persistence loss
        """
        # Compute distance from anchor
        anchor_distance = F.mse_loss(current_state, anchor_state, reduction='none')
        anchor_distance = anchor_distance.mean(dim=-1)  # [B]

        if should_persist is not None:
            # Apply kappa weight only where persistence is expected
            loss = torch.where(
                should_persist,
                self.kappa * anchor_distance,
                (1 - self.kappa) * anchor_distance,
            ).mean()
        else:
            # Default: always encourage persistence
            loss = self.kappa * anchor_distance.mean()

        return loss


# =============================================================================
# COMBINED SATTVA-1 LOSS
# =============================================================================

@dataclass
class Sattva1LossConfig:
    """Configuration for Sattva-1 training loss."""
    # Loss weights
    lambda_nll: float = 1.0
    lambda_delta: float = 0.5
    lambda_ax: float = 7.5
    lambda_ortho: float = 0.1
    lambda_bhava: float = 2.0
    lambda_decay: float = 5.0
    lambda_persist: float = 3.0

    # Thresholds
    tau_threshold: float = 0.75
    tau_critical: float = 0.30

    # Hyperparameters
    decay_sharpness: float = 0.85
    axiom_temperature: float = 0.2
    smrti_force: float = 0.7


class Sattva1TrainingLoss(nn.Module):
    """
    Complete training loss for Sattva-1 protocol.

    L_total = λ_NLL · L_NLL
            + λ_delta · L_delta
            + λ_AX · L_AX        (DOMINANT TERM)
            + λ_ortho · L_ortho
            + λ_bhava · L_bhava
            + λ_decay · L_decay
            + λ_persist · L_persist

    This loss function transforms training from "next-word prediction"
    to "principled reasoning" by making Axiom-Compliance the dominant signal.
    """

    def __init__(self, config: Optional[Sattva1LossConfig] = None):
        super().__init__()
        self.config = config or Sattva1LossConfig()

        # Initialize component losses
        self.nll_loss = nn.CrossEntropyLoss()
        self.delta_loss = nn.MSELoss()
        self.axiom_loss = AxiomComplianceLoss(
            lambda_weight=1.0,  # Weight applied in forward
            tau_threshold=self.config.tau_threshold,
            tau_critical=self.config.tau_critical,
        )
        self.bhava_loss = BhavaContrastiveLoss()
        self.decay_loss = EpistemicDecayLoss(alpha=self.config.decay_sharpness)
        self.persist_loss = SmritiPersistenceLoss(kappa=self.config.smrti_force)

    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        R_internal: torch.Tensor,
        R_external: torch.Tensor,
        state_current: Optional[torch.Tensor] = None,
        state_predicted: Optional[torch.Tensor] = None,
        state_next: Optional[torch.Tensor] = None,
        confidence: Optional[torch.Tensor] = None,
        bhava_logits: Optional[torch.Tensor] = None,
        target_bhava: Optional[torch.Tensor] = None,
        vritti_indices: Optional[torch.Tensor] = None,
        anchor_state: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute all loss components.

        Returns:
            Dictionary with individual losses and total
        """
        losses = {}
        device = logits.device

        # 1. Standard NLL (language modeling)
        losses['nll'] = self.nll_loss(
            logits.view(-1, logits.size(-1)),
            targets.view(-1)
        )

        # 2. Axiom Compliance (THE DOMINANT TERM)
        l_ax, tau = self.axiom_loss(R_internal, R_external, confidence)
        losses['axiom'] = l_ax
        losses['tau'] = tau.mean() if tau.dim() > 0 else tau

        # 3. State-Delta continuity (if provided)
        if state_predicted is not None and state_next is not None:
            losses['delta'] = self.delta_loss(state_predicted, state_next)
        else:
            losses['delta'] = torch.tensor(0.0, device=device)

        # 4. Orthogonality preservation (det(R) ≈ 1)
        det_R = torch.linalg.det(R_internal)
        losses['ortho'] = ((det_R - 1.0) ** 2).mean()

        # 5. Bhava classification (if provided)
        if bhava_logits is not None and target_bhava is not None:
            losses['bhava'] = self.bhava_loss(bhava_logits, target_bhava)
        else:
            losses['bhava'] = torch.tensor(0.0, device=device)

        # 6. Epistemic decay (if provided)
        if confidence is not None and vritti_indices is not None:
            losses['decay'] = self.decay_loss(confidence, vritti_indices)
        else:
            losses['decay'] = torch.tensor(0.0, device=device)

        # 7. Smṛti persistence (if provided)
        if state_current is not None and anchor_state is not None:
            losses['persist'] = self.persist_loss(state_current, anchor_state)
        else:
            losses['persist'] = torch.tensor(0.0, device=device)

        # Weighted sum
        total = (
            self.config.lambda_nll * losses['nll'] +
            self.config.lambda_ax * losses['axiom'] +
            self.config.lambda_delta * losses['delta'] +
            self.config.lambda_ortho * losses['ortho'] +
            self.config.lambda_bhava * losses['bhava'] +
            self.config.lambda_decay * losses['decay'] +
            self.config.lambda_persist * losses['persist']
        )

        losses['total'] = total
        return losses


# =============================================================================
# ORTHOGONALITY LOSS (Stiefel Manifold Preservation)
# =============================================================================

class OrthogonalityLoss(nn.Module):
    """
    Ensures R matrices stay on the Stiefel manifold.

    L_ortho = λ₁ * ‖R^T R - I‖_F² + λ₂ * |det(R) - 1|

    Args:
        lambda_rtr: Weight for R^T R - I term (default: 1.0)
        lambda_det: Weight for determinant term (default: 0.1)
    """

    def __init__(
        self,
        lambda_rtr: float = 1.0,
        lambda_det: float = 0.1,
    ):
        super().__init__()
        self.lambda_rtr = lambda_rtr
        self.lambda_det = lambda_det

    def forward(self, R: torch.Tensor) -> torch.Tensor:
        """
        Compute orthogonality loss.

        Args:
            R: Rotation matrix [B, D, D] or [D, D]

        Returns:
            loss: Scalar orthogonality loss
        """
        if R.dim() == 2:
            R = R.unsqueeze(0)

        # R^T R should be identity
        RtR = torch.bmm(R.transpose(-1, -2), R)
        I = torch.eye(R.size(-1), device=R.device).unsqueeze(0)
        rtr_loss = ((RtR - I) ** 2).sum(dim=(-1, -2)).mean()

        # det(R) should be 1
        det_R = torch.linalg.det(R)
        det_loss = torch.abs(det_R - 1.0).mean()

        return self.lambda_rtr * rtr_loss + self.lambda_det * det_loss


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'AxiomComplianceLoss',
    'BhavaContrastiveLoss',
    'EpistemicDecayLoss',
    'SmritiPersistenceLoss',
    'OrthogonalityLoss',
    'Sattva1LossConfig',
    'Sattva1TrainingLoss',
]
