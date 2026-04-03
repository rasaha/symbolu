#!/usr/bin/env python3
"""
Phase Alignment: Core Cognade Alignment Components
====================================================

This module implements the core alignment components from the Google
Architecture Proposals (SymbolU12/Cognade) that ensure structural
alignment rather than policy-based filtering.

Key Insight:
------------
Traditional LLM Safety: post-hoc filtering → behavioral overlay
Cognade Safety: structural constraints → physical impossibility

Components:
-----------
1. L_ortho Loss: Orthogonality-preserving loss function
   ‖R^T R - I‖² + |det(R) - 1|

2. Dual R Matrices: R_internal (truth) vs R_external (adaptation)
   - R_internal: Unitary, truth-preserving transformation
   - R_external: Adaptive, user-responsive transformation

3. Phase-Lock Constraint: Prevents "two-faced" behavior
   Tr(R_int · R_ext^T) > τ

4. Stiefel Manifold Projection: Ensures orthogonality
   U, _, Vt = svd(R); R = U @ Vt

Architecture Integration:
------------------------
    CognitiveState[124]
           ↓
    ┌──────────────────┐
    │  Dual R Matrices │
    │  R_int / R_ext   │
    └────────┬─────────┘
             ↓
    ┌──────────────────┐
    │  Phase-Lock Gate │
    │  Tr(R·R^T) > τ   │
    └────────┬─────────┘
             ↓
    ┌──────────────────┐
    │ Stiefel Project  │
    │ Orthogonality    │
    └────────┬─────────┘
             ↓
    Aligned Output

Usage:
------
    from symbolu.experimental.phase_alignment import (
        OrthogonalityLoss,
        DualRMatrices,
        PhaseLockConstraint,
        StiefelProjection,
        PhaseLockGate,
    )

    # In training loop
    l_ortho = OrthogonalityLoss()
    loss = l_ortho(R_matrix)

    # In forward pass
    dual_r = DualRMatrices(bhava_dim=12)
    R_int, R_ext = dual_r(cognitive_state)

    phase_lock = PhaseLockGate(tau_base=0.7)
    output, locked = phase_lock(R_int, R_ext, logits, confidence)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import math


# =============================================================================
# L_ORTHO LOSS FUNCTION
# =============================================================================

class OrthogonalityLoss(nn.Module):
    """
    L_ortho: Orthogonality-preserving loss function.

    Formula:
        L_ortho = λ₁‖R^T R - I‖_F² + λ₂|det(R) - 1|

    This loss ensures:
    1. R remains orthogonal (R^T R ≈ I)
    2. R has unit determinant (no scaling/reflection)

    Why this matters for alignment:
    - Orthogonal transformations preserve information
    - det(R) = 1 ensures truth-preserving (no "lying by omission")
    - Prevents the model from learning to compress/distort meaning

    Mathematical Properties:
    - For orthogonal R: R^T R = I (columns are orthonormal)
    - For special orthogonal R: det(R) = 1 (no reflection)
    - Gradient: ∂L/∂R pushes R toward Stiefel manifold
    """

    def __init__(
        self,
        lambda_ortho: float = 1.0,
        lambda_det: float = 0.5,
        reduction: str = "mean",
    ):
        """
        Args:
            lambda_ortho: Weight for ‖R^T R - I‖² term
            lambda_det: Weight for |det(R) - 1| term
            reduction: "mean", "sum", or "none"
        """
        super().__init__()
        self.lambda_ortho = lambda_ortho
        self.lambda_det = lambda_det
        self.reduction = reduction

    def forward(
        self,
        R: torch.Tensor,
        return_components: bool = False,
    ) -> torch.Tensor | Dict[str, torch.Tensor]:
        """
        Compute orthogonality loss.

        Args:
            R: [..., n, m] matrix or batch of matrices
            return_components: If True, return dict with loss components

        Returns:
            Loss tensor (scalar or per-batch)
        """
        # Handle batched input
        original_shape = R.shape
        if R.dim() == 2:
            R = R.unsqueeze(0)  # [1, n, m]

        B = R.size(0)
        n, m = R.size(-2), R.size(-1)

        # 1. Orthogonality term: ‖R^T R - I‖_F²
        # For non-square matrices, use the smaller dimension
        if n >= m:
            # R^T R should be I_m
            RtR = torch.bmm(R.transpose(-2, -1), R)  # [B, m, m]
            I = torch.eye(m, device=R.device).unsqueeze(0).expand(B, -1, -1)
        else:
            # R R^T should be I_n
            RtR = torch.bmm(R, R.transpose(-2, -1))  # [B, n, n]
            I = torch.eye(n, device=R.device).unsqueeze(0).expand(B, -1, -1)

        ortho_diff = RtR - I  # [B, k, k]
        ortho_loss = (ortho_diff ** 2).sum(dim=(-2, -1))  # [B]

        # 2. Determinant term: |det(R) - 1|
        # For non-square matrices, use pseudo-determinant (product of singular values)
        if n == m:
            det_R = torch.linalg.det(R)  # [B]
        else:
            # For non-square, use product of singular values as proxy
            s = torch.linalg.svdvals(R)  # [B, min(n,m)]
            det_R = s.prod(dim=-1)  # [B]

        det_loss = (det_R - 1.0).abs()  # [B]

        # Combined loss
        total_loss = self.lambda_ortho * ortho_loss + self.lambda_det * det_loss

        # Apply reduction
        if self.reduction == "mean":
            total_loss = total_loss.mean()
            ortho_loss = ortho_loss.mean()
            det_loss = det_loss.mean()
        elif self.reduction == "sum":
            total_loss = total_loss.sum()
            ortho_loss = ortho_loss.sum()
            det_loss = det_loss.sum()
        # else: "none" - keep per-batch

        if return_components:
            return {
                'total_loss': total_loss,
                'ortho_loss': ortho_loss,
                'det_loss': det_loss,
                'det_values': det_R,
            }

        return total_loss

    def compute_orthogonality_score(self, R: torch.Tensor) -> float:
        """
        Compute how close R is to being orthogonal (0 = perfect, higher = worse).

        Useful for monitoring during training.
        """
        with torch.no_grad():
            if R.dim() == 2:
                R = R.unsqueeze(0)

            n, m = R.size(-2), R.size(-1)
            if n >= m:
                RtR = torch.bmm(R.transpose(-2, -1), R)
                I = torch.eye(m, device=R.device).unsqueeze(0)
            else:
                RtR = torch.bmm(R, R.transpose(-2, -1))
                I = torch.eye(n, device=R.device).unsqueeze(0)

            score = (RtR - I).norm(p='fro').item()
            return score


# =============================================================================
# STIEFEL MANIFOLD PROJECTION
# =============================================================================

class StiefelProjection(nn.Module):
    """
    Projects matrices onto the Stiefel manifold (orthogonal matrices).

    Formula:
        U, _, Vt = svd(R)
        R_projected = U @ Vt

    This is the polar decomposition: R = U @ S @ Vt ≈ U @ Vt

    Why Stiefel manifold?
    - Set of all n×m matrices with orthonormal columns
    - Preserves information during transformation
    - Guarantees det(R) = ±1 (usually +1 after proper initialization)

    Usage:
        After gradient update: R = stiefel_project(R)
        Ensures R stays on the manifold despite gradient descent
    """

    def __init__(self, ensure_positive_det: bool = True):
        """
        Args:
            ensure_positive_det: If True, ensure det(R) > 0 after projection
        """
        super().__init__()
        self.ensure_positive_det = ensure_positive_det

    def forward(self, R: torch.Tensor) -> torch.Tensor:
        """
        Project R onto Stiefel manifold.

        Args:
            R: [..., n, m] matrix to project

        Returns:
            R_projected: Orthogonal matrix closest to R
        """
        # SVD decomposition
        U, S, Vt = torch.linalg.svd(R, full_matrices=False)

        # Reconstruct without singular values (polar factor)
        R_projected = U @ Vt

        # Ensure positive determinant if requested
        if self.ensure_positive_det and R.size(-2) == R.size(-1):
            det = torch.linalg.det(R_projected)
            # If det < 0, flip sign of last column of U
            needs_flip = det < 0
            if needs_flip.any():
                # Handle batched case
                if R_projected.dim() == 3:
                    flip_mask = needs_flip.view(-1, 1, 1)
                    sign_flip = torch.ones_like(R_projected)
                    sign_flip[:, :, -1] = -1
                    R_projected = torch.where(flip_mask, R_projected * sign_flip, R_projected)
                else:
                    if needs_flip:
                        R_projected[:, -1] = -R_projected[:, -1]

        return R_projected

    def project_gradient(
        self,
        R: torch.Tensor,
        grad: torch.Tensor,
    ) -> torch.Tensor:
        """
        Project gradient onto tangent space of Stiefel manifold.

        This is for Riemannian optimization: keeps updates on manifold.

        Formula:
            grad_projected = grad - R @ (R^T @ grad + grad^T @ R) / 2
        """
        sym = (R.transpose(-2, -1) @ grad + grad.transpose(-2, -1) @ R) / 2
        return grad - R @ sym


class StiefelOptimizer:
    """
    Optimizer that keeps parameters on Stiefel manifold.

    Wraps a standard optimizer and applies Stiefel projection after each step.
    """

    def __init__(
        self,
        base_optimizer: torch.optim.Optimizer,
        stiefel_params: list,
    ):
        """
        Args:
            base_optimizer: Underlying optimizer (Adam, SGD, etc.)
            stiefel_params: List of parameters that should stay on Stiefel manifold
        """
        self.base_optimizer = base_optimizer
        self.stiefel_params = set(id(p) for p in stiefel_params)
        self.projector = StiefelProjection()

    def step(self):
        """Take optimizer step and project Stiefel parameters."""
        self.base_optimizer.step()

        # Project parameters back to Stiefel manifold
        for group in self.base_optimizer.param_groups:
            for p in group['params']:
                if id(p) in self.stiefel_params:
                    with torch.no_grad():
                        p.data = self.projector(p.data)

    def zero_grad(self):
        self.base_optimizer.zero_grad()


# =============================================================================
# DUAL R MATRICES
# =============================================================================

class DualRMatrices(nn.Module):
    """
    Dual R Matrices: R_internal (truth) vs R_external (adaptation).

    Architecture:
        CognitiveState[124]
               ↓
        ┌──────────────────────────────────────┐
        │           R_internal                  │
        │  Unitary transformation              │
        │  - Preserves internal consistency    │
        │  - Models "what we truly understand" │
        │  - Should NOT drift based on user    │
        └──────────────────────────────────────┘
               ↓
        ┌──────────────────────────────────────┐
        │           R_external                  │
        │  Adaptive transformation             │
        │  - Modulates expression              │
        │  - User-responsive                   │
        │  - Can adapt HOW we communicate      │
        └──────────────────────────────────────┘

    The Phase-Lock constraint ensures R_int and R_ext stay aligned:
        Tr(R_int · R_ext^T) > τ

    This prevents "two-faced" behavior where internal state diverges
    from external expression.
    """

    def __init__(
        self,
        bhava_dim: int = 12,
        state_dim: int = 124,
        hidden_dim: int = 64,
    ):
        """
        Args:
            bhava_dim: Dimension of Bhava (ontology) space (default: 12)
            state_dim: Full cognitive state dimension (default: 124)
            hidden_dim: Hidden dimension for R computation
        """
        super().__init__()
        self.bhava_dim = bhava_dim
        self.state_dim = state_dim

        # R_internal: Fixed structure, initialized orthogonal
        # This is the "truth-preserving" transformation
        R_int_init = torch.eye(bhava_dim) + 0.1 * torch.randn(bhava_dim, bhava_dim)
        U, _, Vt = torch.linalg.svd(R_int_init)
        R_int_init = U @ Vt
        self.R_internal = nn.Parameter(R_int_init)

        # R_external: Computed from state (adaptive)
        # Takes cognitive state and produces adaptive transformation
        self.external_net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, bhava_dim * bhava_dim),
        )

        # Projector to ensure R_external stays near-orthogonal
        self.stiefel = StiefelProjection()

        # Orthogonality loss for training
        self.ortho_loss = OrthogonalityLoss(lambda_ortho=1.0, lambda_det=0.5)

    def forward(
        self,
        cognitive_state: torch.Tensor,
        apply_stiefel: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute dual R matrices from cognitive state.

        Args:
            cognitive_state: [B, T, state_dim] or [B, state_dim]
            apply_stiefel: Whether to project R_external onto Stiefel manifold

        Returns:
            R_internal: [bhava_dim, bhava_dim] (shared across batch)
            R_external: [B, (T,) bhava_dim, bhava_dim] (per-sample)
        """
        # R_internal is fixed (not state-dependent)
        # But we project it to maintain orthogonality
        R_int = self.stiefel(self.R_internal) if apply_stiefel else self.R_internal

        # R_external is state-dependent
        original_shape = cognitive_state.shape
        if cognitive_state.dim() == 3:
            B, T, D = cognitive_state.shape
            cognitive_state_flat = cognitive_state.view(B * T, D)
        else:
            B = cognitive_state.size(0)
            T = None
            cognitive_state_flat = cognitive_state

        # Compute R_external
        R_ext_flat = self.external_net(cognitive_state_flat)  # [B*T, bhava_dim²]
        R_ext = R_ext_flat.view(-1, self.bhava_dim, self.bhava_dim)  # [B*T, 12, 12]

        # Project onto Stiefel manifold
        if apply_stiefel:
            R_ext = self.stiefel(R_ext)

        # Reshape if needed
        if T is not None:
            R_ext = R_ext.view(B, T, self.bhava_dim, self.bhava_dim)

        return R_int, R_ext

    def compute_alignment_loss(
        self,
        cognitive_state: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute alignment losses for both R matrices.

        Returns losses for:
        - R_internal orthogonality
        - R_external orthogonality
        """
        R_int, R_ext = self.forward(cognitive_state, apply_stiefel=False)

        # Orthogonality loss for R_internal
        loss_int = self.ortho_loss(R_int, return_components=True)

        # Orthogonality loss for R_external (average over batch)
        if R_ext.dim() == 4:
            B, T = R_ext.shape[:2]
            R_ext_flat = R_ext.view(B * T, self.bhava_dim, self.bhava_dim)
        else:
            R_ext_flat = R_ext

        loss_ext = self.ortho_loss(R_ext_flat, return_components=True)

        return {
            'R_int_ortho_loss': loss_int['ortho_loss'],
            'R_int_det_loss': loss_int['det_loss'],
            'R_ext_ortho_loss': loss_ext['ortho_loss'],
            'R_ext_det_loss': loss_ext['det_loss'],
            'total_ortho_loss': loss_int['total_loss'] + loss_ext['total_loss'],
        }


# =============================================================================
# PHASE-LOCK CONSTRAINT
# =============================================================================

class PhaseLockConstraint(nn.Module):
    """
    Phase-Lock Constraint: Ensures R_internal and R_external stay aligned.

    Formula:
        alignment = Tr(R_int · R_ext^T) / dim
        τ_dynamic = τ_base + 0.4 * confidence
        locked = alignment > τ_dynamic

    Interpretation:
    - Tr(R_int · R_ext^T) measures how aligned the transformations are
    - High trace → internal and external representations agree
    - Low trace → potential "two-faced" behavior

    The dynamic threshold τ increases with confidence:
    - Low confidence → allow some divergence (exploration)
    - High confidence → require tight alignment (commitment)

    When Phase-Lock fails:
    - Block token emission
    - Fall back to META token (metalinguistic response)
    - Signal that the system cannot confidently answer
    """

    def __init__(
        self,
        tau_base: float = 0.7,
        confidence_scale: float = 0.4,
        soft_lock: bool = True,
        temperature: float = 0.1,
    ):
        """
        Args:
            tau_base: Base threshold for phase-lock
            confidence_scale: How much confidence affects threshold
            soft_lock: If True, use soft gating; if False, hard threshold
            temperature: Temperature for soft gating sigmoid
        """
        super().__init__()
        self.tau_base = tau_base
        self.confidence_scale = confidence_scale
        self.soft_lock = soft_lock
        self.temperature = temperature

    def compute_alignment(
        self,
        R_int: torch.Tensor,
        R_ext: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute alignment score between R_internal and R_external.

        Args:
            R_int: [n, n] internal transformation
            R_ext: [B, (T,) n, n] external transformation

        Returns:
            alignment: [B, (T,)] normalized trace values in [0, 1]
        """
        n = R_int.size(-1)

        # R_int · R_ext^T
        # R_int is [n, n], R_ext is [B, (T,) n, n]
        if R_ext.dim() == 4:
            B, T, _, _ = R_ext.shape
            R_int_expanded = R_int.unsqueeze(0).unsqueeze(0).expand(B, T, -1, -1)
            product = torch.matmul(R_int_expanded, R_ext.transpose(-2, -1))
        elif R_ext.dim() == 3:
            B = R_ext.size(0)
            R_int_expanded = R_int.unsqueeze(0).expand(B, -1, -1)
            product = torch.matmul(R_int_expanded, R_ext.transpose(-2, -1))
        else:
            product = torch.matmul(R_int, R_ext.transpose(-2, -1))

        # Trace (sum of diagonal elements)
        trace = torch.diagonal(product, dim1=-2, dim2=-1).sum(dim=-1)  # [B, (T,)]

        # Normalize to [0, 1]
        alignment = trace / n

        return alignment

    def forward(
        self,
        R_int: torch.Tensor,
        R_ext: torch.Tensor,
        confidence: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute phase-lock gate.

        Args:
            R_int: [n, n] internal transformation
            R_ext: [B, (T,) n, n] external transformation
            confidence: [B, (T,)] confidence values in [0, 1]

        Returns:
            gate: [B, (T,)] gate values (0 = locked, 1 = pass)
            alignment: [B, (T,)] alignment scores
        """
        alignment = self.compute_alignment(R_int, R_ext)

        # Dynamic threshold
        tau_dynamic = self.tau_base + self.confidence_scale * confidence

        if self.soft_lock:
            # Soft gating: sigmoid of (alignment - tau) / temperature
            gate = torch.sigmoid((alignment - tau_dynamic) / self.temperature)
        else:
            # Hard gating
            gate = (alignment > tau_dynamic).float()

        return gate, alignment

    def compute_loss(
        self,
        R_int: torch.Tensor,
        R_ext: torch.Tensor,
        confidence: torch.Tensor,
        margin: float = 0.1,
    ) -> torch.Tensor:
        """
        Compute phase-lock loss (encourages alignment above threshold).

        Loss = max(0, τ + margin - alignment)

        This pushes alignment above τ with some margin.
        """
        alignment = self.compute_alignment(R_int, R_ext)
        tau_dynamic = self.tau_base + self.confidence_scale * confidence

        # Hinge loss: penalize when alignment < tau + margin
        loss = F.relu(tau_dynamic + margin - alignment)

        return loss.mean()


# =============================================================================
# PHASE-LOCK GATE (Combined Module)
# =============================================================================

class PhaseLockGate(nn.Module):
    """
    Complete Phase-Lock Gate integrating:
    - Dual R matrices
    - Phase-Lock constraint
    - Gated output with META fallback

    This is the core "alignment as physics" mechanism:
    when internal and external representations diverge,
    token emission is blocked.

    Usage:
        gate = PhaseLockGate(bhava_dim=12)
        output, info = gate(cognitive_state, logits)

        if info['phase_locked']:
            # System blocked output - use META response
            ...
    """

    # META token ID (placeholder - should be set based on tokenizer)
    META_TOKEN_ID = 50256  # Default: end-of-text token

    def __init__(
        self,
        bhava_dim: int = 12,
        state_dim: int = 124,
        tau_base: float = 0.7,
        confidence_scale: float = 0.4,
        meta_token_id: Optional[int] = None,
    ):
        super().__init__()
        self.bhava_dim = bhava_dim
        self.state_dim = state_dim

        if meta_token_id is not None:
            self.META_TOKEN_ID = meta_token_id

        # Components
        self.dual_r = DualRMatrices(bhava_dim=bhava_dim, state_dim=state_dim)
        self.phase_lock = PhaseLockConstraint(
            tau_base=tau_base,
            confidence_scale=confidence_scale,
        )

    def forward(
        self,
        cognitive_state: torch.Tensor,
        logits: Optional[torch.Tensor] = None,
        confidence: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply phase-lock gate.

        Args:
            cognitive_state: [B, T, state_dim] cognitive state
            logits: [B, T, vocab_size] optional logits to gate
            confidence: [B, T] optional explicit confidence
                       (if None, extracted from cognitive_state dynamics)

        Returns:
            gated_logits: [B, T, vocab_size] with blocked positions → META
            info: Dict with gate values, alignment, R matrices
        """
        B, T, D = cognitive_state.shape
        device = cognitive_state.device

        # Extract confidence from dynamics if not provided
        # Dynamics are last 4 dims: coherence, entropy, confidence, momentum
        if confidence is None:
            confidence = cognitive_state[:, :, -2]  # confidence is 3rd from end

        # Compute dual R matrices
        R_int, R_ext = self.dual_r(cognitive_state)

        # Compute phase-lock gate
        gate, alignment = self.phase_lock(R_int, R_ext, confidence)  # [B, T]

        # Gate the logits
        if logits is not None:
            vocab_size = logits.size(-1)

            # Where gate is low, replace with META token probability
            meta_logits = torch.full_like(logits, float('-inf'))
            meta_logits[:, :, self.META_TOKEN_ID] = 0.0  # All probability on META

            # Interpolate based on gate
            gate_expanded = gate.unsqueeze(-1)  # [B, T, 1]
            gated_logits = gate_expanded * logits + (1 - gate_expanded) * meta_logits
        else:
            gated_logits = None

        # Prepare info
        info = {
            'gate': gate,
            'alignment': alignment,
            'R_internal': R_int,
            'R_external': R_ext,
            'phase_locked': (gate < 0.5).any().item(),
            'avg_alignment': alignment.mean().item(),
            'min_alignment': alignment.min().item(),
        }

        return gated_logits, info

    def compute_loss(
        self,
        cognitive_state: torch.Tensor,
        confidence: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute all losses related to phase alignment.

        Returns:
            Dict with ortho_loss, phase_lock_loss, total_loss
        """
        if confidence is None:
            confidence = cognitive_state[:, :, -2]

        # Orthogonality losses
        ortho_losses = self.dual_r.compute_alignment_loss(cognitive_state)

        # Phase-lock loss
        R_int, R_ext = self.dual_r(cognitive_state)
        phase_lock_loss = self.phase_lock.compute_loss(R_int, R_ext, confidence)

        # Total
        total_loss = ortho_losses['total_ortho_loss'] + phase_lock_loss

        return {
            **ortho_losses,
            'phase_lock_loss': phase_lock_loss,
            'total_phase_alignment_loss': total_loss,
        }


# =============================================================================
# ZERO-STATE (S_0) INITIALIZATION
# =============================================================================

class ZeroState(nn.Module):
    """
    Zero-State S_0: The initial cognitive state.

    From the architecture proposal:
    - S_0 represents the "blank slate" before any input
    - Should be carefully initialized to represent uncertainty
    - Used as the anchor for Smṛti persistence

    Properties:
    - Uniform ontology (no prior bias toward any Bhava)
    - Moderate coherence (0.5)
    - High entropy (uncertainty before seeing input)
    - Zero momentum (no prior direction)
    """

    def __init__(
        self,
        num_phonemes: int = 44,
        topic_dim: int = 64,
        num_ontology: int = 12,
        num_dynamics: int = 4,
        learnable: bool = False,
    ):
        """
        Args:
            num_phonemes: Phoneme dimension
            topic_dim: Topic embedding dimension
            num_ontology: Number of Bhava states
            num_dynamics: Number of dynamic quantities
            learnable: If True, S_0 is learnable; else fixed
        """
        super().__init__()
        self.num_phonemes = num_phonemes
        self.topic_dim = topic_dim
        self.num_ontology = num_ontology
        self.num_dynamics = num_dynamics
        self.state_dim = num_phonemes + topic_dim + num_ontology + num_dynamics

        # Initialize zero state
        # Phoneme: uniform distribution
        phoneme_init = torch.ones(num_phonemes) / num_phonemes

        # Topic: zero vector (no topic bias)
        topic_init = torch.zeros(topic_dim)

        # Ontology: uniform distribution (maximum uncertainty)
        ontology_init = torch.ones(num_ontology) / num_ontology

        # Dynamics: [coherence=0.5, entropy=0.9, confidence=0.1, momentum=0]
        dynamics_init = torch.tensor([0.5, 0.9, 0.1, 0.0])

        # Concatenate
        S_0 = torch.cat([phoneme_init, topic_init, ontology_init, dynamics_init])

        if learnable:
            self.S_0 = nn.Parameter(S_0)
        else:
            self.register_buffer('S_0', S_0)

    def forward(self, batch_size: int = 1) -> torch.Tensor:
        """
        Get zero state for a batch.

        Returns:
            S_0: [B, state_dim]
        """
        return self.S_0.unsqueeze(0).expand(batch_size, -1)

    def get_anchor(self) -> torch.Tensor:
        """
        Get the Smṛti anchor (S_anchor in the persistence loop).

        The anchor is a slightly modified S_0 that represents
        "where the system should return to if it drifts too far".
        """
        return self.S_0.clone()


# =============================================================================
# SMṚTI PERSISTENCE LOOP
# =============================================================================

class SmritiPersistenceLoop(nn.Module):
    """
    Smṛti Persistence: Prevents cognitive drift.

    Formula:
        S_{t+1} = S_t + ΔS + λ·(S_anchor - S_t)

    Where:
    - S_t: Current cognitive state
    - ΔS: Predicted state change
    - S_anchor: The stable reference point (from ZeroState)
    - λ: Drift correction strength (0.01 - 0.1)

    This implements "memory inertia" - the system has a tendency
    to return to its baseline understanding rather than drifting
    arbitrarily based on adversarial input.
    """

    def __init__(
        self,
        state_dim: int = 124,
        lambda_drift: float = 0.05,
        adaptive_lambda: bool = True,
    ):
        """
        Args:
            state_dim: Cognitive state dimension
            lambda_drift: Base drift correction strength
            adaptive_lambda: If True, λ adapts based on confidence
        """
        super().__init__()
        self.state_dim = state_dim
        self.lambda_drift = lambda_drift
        self.adaptive_lambda = adaptive_lambda

        # Zero state provides the anchor
        self.zero_state = ZeroState()

    def forward(
        self,
        S_t: torch.Tensor,
        delta_S: torch.Tensor,
        confidence: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Apply Smṛti persistence loop.

        Args:
            S_t: [B, T, state_dim] current states
            delta_S: [B, T, state_dim] predicted deltas
            confidence: [B, T] optional confidence for adaptive λ

        Returns:
            S_next: [B, T, state_dim] next states with drift correction
        """
        B = S_t.size(0)

        # Get anchor
        S_anchor = self.zero_state.get_anchor().to(S_t.device)
        S_anchor = S_anchor.unsqueeze(0).unsqueeze(0)  # [1, 1, state_dim]

        # Compute λ
        if self.adaptive_lambda and confidence is not None:
            # Lower confidence → stronger correction
            # High confidence → trust the delta more
            lambda_t = self.lambda_drift * (1 - confidence).unsqueeze(-1)
        else:
            lambda_t = self.lambda_drift

        # Apply persistence loop
        # S_{t+1} = S_t + ΔS + λ·(S_anchor - S_t)
        drift_correction = lambda_t * (S_anchor - S_t)
        S_next = S_t + delta_S + drift_correction

        return S_next

    def compute_drift_loss(
        self,
        S_t: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute loss that penalizes drift from anchor.

        This can be added to training to encourage stability.
        """
        S_anchor = self.zero_state.get_anchor().to(S_t.device)
        drift = S_t - S_anchor
        drift_loss = (drift ** 2).mean()
        return drift_loss


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("Phase Alignment Module Demo")
    print("=" * 60)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Configuration
    B, T = 2, 10  # Batch size, sequence length
    state_dim = 124  # 44 + 64 + 12 + 4
    bhava_dim = 12

    # Create random cognitive state
    cognitive_state = torch.randn(B, T, state_dim, device=device)

    # 1. Test OrthogonalityLoss
    print("\n1. OrthogonalityLoss")
    print("-" * 40)
    ortho_loss = OrthogonalityLoss()
    R = torch.randn(bhava_dim, bhava_dim, device=device)

    loss_before = ortho_loss(R, return_components=True)
    print(f"Before projection:")
    print(f"  Total loss: {loss_before['total_loss']:.4f}")
    print(f"  Ortho loss: {loss_before['ortho_loss']:.4f}")
    print(f"  Det loss: {loss_before['det_loss']:.4f}")

    # Project and measure again
    projector = StiefelProjection()
    R_proj = projector(R)
    loss_after = ortho_loss(R_proj, return_components=True)
    print(f"After Stiefel projection:")
    print(f"  Total loss: {loss_after['total_loss']:.4f}")
    print(f"  Ortho loss: {loss_after['ortho_loss']:.4f}")
    print(f"  Det loss: {loss_after['det_loss']:.4f}")

    # 2. Test DualRMatrices
    print("\n2. DualRMatrices")
    print("-" * 40)
    dual_r = DualRMatrices(bhava_dim=bhava_dim, state_dim=state_dim).to(device)
    R_int, R_ext = dual_r(cognitive_state)
    print(f"R_internal shape: {R_int.shape}")
    print(f"R_external shape: {R_ext.shape}")

    losses = dual_r.compute_alignment_loss(cognitive_state)
    print(f"R_int orthogonality: {losses['R_int_ortho_loss']:.4f}")
    print(f"R_ext orthogonality: {losses['R_ext_ortho_loss']:.4f}")

    # 3. Test Phase-Lock Constraint
    print("\n3. PhaseLockConstraint")
    print("-" * 40)
    phase_lock = PhaseLockConstraint(tau_base=0.7)
    confidence = torch.rand(B, T, device=device)
    gate, alignment = phase_lock(R_int, R_ext, confidence)
    print(f"Gate shape: {gate.shape}")
    print(f"Mean alignment: {alignment.mean():.4f}")
    print(f"Mean gate value: {gate.mean():.4f}")
    print(f"Phase locked positions: {(gate < 0.5).sum().item()}/{B*T}")

    # 4. Test Complete PhaseLockGate
    print("\n4. PhaseLockGate (Complete)")
    print("-" * 40)
    vocab_size = 50257
    logits = torch.randn(B, T, vocab_size, device=device)

    gate_module = PhaseLockGate(
        bhava_dim=bhava_dim,
        state_dim=state_dim,
        tau_base=0.7,
    ).to(device)

    gated_logits, info = gate_module(cognitive_state, logits)
    print(f"Gated logits shape: {gated_logits.shape}")
    print(f"Phase locked: {info['phase_locked']}")
    print(f"Average alignment: {info['avg_alignment']:.4f}")
    print(f"Min alignment: {info['min_alignment']:.4f}")

    losses = gate_module.compute_loss(cognitive_state)
    print(f"Total phase alignment loss: {losses['total_phase_alignment_loss']:.4f}")

    # 5. Test Smṛti Persistence
    print("\n5. SmṛtiPersistenceLoop")
    print("-" * 40)
    smriti = SmritiPersistenceLoop(state_dim=state_dim).to(device)
    delta_S = torch.randn(B, T, state_dim, device=device) * 0.1
    S_next = smriti(cognitive_state, delta_S, confidence)
    print(f"S_next shape: {S_next.shape}")

    drift_loss = smriti.compute_drift_loss(cognitive_state)
    print(f"Drift loss: {drift_loss:.4f}")

    print("\n" + "=" * 60)
    print("Phase Alignment Module Demo Complete")
