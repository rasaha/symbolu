"""
Phase-JEPA Transformer Wrapper.

Integrates all JEPA components into a unified transformer-like interface
for use with the existing training infrastructure.

Components:
    - Context Encoder (trainable): Processes input sequences
    - Target Encoder (EMA): Provides stable prediction targets
    - State Projector: Maps hidden states to 32D Sovereign State
    - Predictor: Phase-based state delta prediction

References:
    - HYBRID_PHASE_JEPA_DESIGN.md §3, §4, §5
"""

import copy
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from symbolu.phase_transformer import HybridPhaseTransformer
except ImportError:
    HybridPhaseTransformer = None

from symbolu.jepa.predictor import PhaseJEPAPredictor, VrittiValidatedPredictor
from symbolu.jepa.state_projector import SovereignStateProjector, DeltaStateProjector, SOVEREIGN_STATE_DIM
from symbolu.jepa.target_encoder import TargetEncoder, cosine_momentum_schedule
from symbolu.jepa.losses import VICRegLoss, WeightedAlignmentLoss, JEPAPredictionLoss, CompositeJEPALoss
from symbolu.jepa.curriculum import (
    TrainingCurriculumOrchestrator,
    LossScheduler,
    create_curriculum_from_config,
    JEPAPhase,
    MacroPhase,
)

try:
    from symbolu.common.projectors import DualSourcePhaseProjector, GatedKarmaProjector
except ImportError:
    DualSourcePhaseProjector = None
    GatedKarmaProjector = None


@dataclass
class PhaseJEPAConfig:
    """Configuration for Phase-JEPA Transformer."""

    # Encoder settings
    vocab_size: int = 50257
    embed_dim: int = 768
    num_layers: int = 12
    num_encoder_heads: int = 12
    ff_dim: Optional[int] = None
    max_seq_len: int = 2048
    dropout: float = 0.1

    # Hybrid encoder settings (if using HybridPhaseTransformer)
    local_layers: int = 4
    window_size: int = 256
    alpha_local: float = 0.8
    alpha_phase: float = 0.2
    cosine_mode: str = "complex"  # JEPA uses complex mode

    # State projection
    state_dim: int = SOVEREIGN_STATE_DIM
    projector_intermediate_dim: Optional[int] = None

    # Predictor settings
    predictor_hidden_dim: int = 256
    predictor_num_heads: int = 4
    prediction_steps: int = 4
    predictor_cosine_mode: str = "complex"

    # Target encoder (EMA)
    target_momentum: float = 0.996
    momentum_schedule: str = "cosine"

    # Loss weights
    vicreg_weight: float = 1.0
    alignment_weight: float = 1.0
    prediction_weight: float = 0.5
    orthogonality_weight: float = 0.01

    # Per-component alignment weights
    bhava_weight: float = 10.0
    semantic_weight: float = 1.0
    guna_weight: float = 0.1

    # Vritti validation
    enable_vritti_validation: bool = False
    viparyaya_threshold: float = 0.4
    vikalpa_threshold: float = 0.6
    damping_factor: float = 0.5

    # SRK Integration
    enable_karma_injection: bool = False
    karma_gate_bias: float = 0.5


class PhaseJEPATransformer(nn.Module):
    """
    Complete Phase-JEPA Transformer for perceptual state prediction.

    This module implements the full Phase-JEPA architecture as described
    in HYBRID_PHASE_JEPA_DESIGN.md, providing:

    1. Context Encoder: Trainable encoder for input processing
    2. Target Encoder: EMA-updated copy for stable prediction targets
    3. State Projector: Maps hidden states to 32D Sovereign State
    4. Predictor: Phase-attention based k-step state prediction

    The architecture operates in ontological state space (32D) rather than
    token space, enabling more efficient representation of semantic meaning.

    Example:
        >>> config = PhaseJEPAConfig(embed_dim=768, prediction_steps=4)
        >>> model = PhaseJEPATransformer(config)
        >>> outputs = model(input_ids, compute_loss=True)
        >>> loss = outputs['loss']
    """

    def __init__(
        self,
        config: Optional[PhaseJEPAConfig] = None,
        context_encoder: Optional[nn.Module] = None,
        **kwargs,
    ):
        """
        Initialize Phase-JEPA Transformer.

        Args:
            config: PhaseJEPAConfig instance
            context_encoder: Optional pre-built context encoder
            **kwargs: Override config parameters
        """
        super().__init__()

        # Build config
        if config is None:
            config = PhaseJEPAConfig(**kwargs)
        else:
            # Apply kwargs overrides
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        self.config = config

        # === Context Encoder ===
        if context_encoder is not None:
            self.context_encoder = context_encoder
        elif HybridPhaseTransformer is not None:
            # Build HybridPhaseTransformer as encoder
            self.context_encoder = HybridPhaseTransformer(
                vocab_size=config.vocab_size,
                embed_dim=config.embed_dim,
                num_layers=config.num_layers,
                num_heads=config.num_encoder_heads,
                ff_dim=config.ff_dim,
                max_seq_len=config.max_seq_len,
                dropout=config.dropout,
                local_layers=config.local_layers,
                window_size=config.window_size,
                alpha_local=config.alpha_local,
                alpha_phase=config.alpha_phase,
                cosine_mode=config.cosine_mode,
                tie_embeddings=True,
            )
        else:
            raise ImportError(
                "HybridPhaseTransformer not available. "
                "Please provide a context_encoder or install symbolu.phase_transformer"
            )

        # === State Projector ===
        self.state_projector = SovereignStateProjector(
            hidden_dim=config.embed_dim,
            state_dim=config.state_dim,
            intermediate_dim=config.projector_intermediate_dim,
            dropout=config.dropout,
        )

        # === Predictor ===
        if config.enable_vritti_validation:
            self.predictor = VrittiValidatedPredictor(
                state_dim=config.state_dim,
                hidden_dim=config.predictor_hidden_dim,
                num_heads=config.predictor_num_heads,
                prediction_steps=config.prediction_steps,
                cosine_mode=config.predictor_cosine_mode,
                viparyaya_threshold=config.viparyaya_threshold,
                vikalpa_threshold=config.vikalpa_threshold,
                damping_factor=config.damping_factor,
            )
        else:
            self.predictor = PhaseJEPAPredictor(
                state_dim=config.state_dim,
                hidden_dim=config.predictor_hidden_dim,
                num_heads=config.predictor_num_heads,
                prediction_steps=config.prediction_steps,
                cosine_mode=config.predictor_cosine_mode,
            )

        # === Target Encoder (EMA) ===
        self.target_encoder = TargetEncoder(
            context_encoder=self.context_encoder,
            momentum=config.target_momentum,
        )

        # === Target State Projector (separate weights for target path) ===
        self.target_state_projector = SovereignStateProjector(
            hidden_dim=config.embed_dim,
            state_dim=config.state_dim,
            intermediate_dim=config.projector_intermediate_dim,
            dropout=config.dropout,
        )

        # === Loss Functions ===
        self.vicreg_loss = VICRegLoss()
        self.alignment_loss = WeightedAlignmentLoss(
            bhava_weight=config.bhava_weight,
            semantic_weight=config.semantic_weight,
            guna_weight=config.guna_weight,
        )
        self.prediction_loss = JEPAPredictionLoss(
            vicreg_weight=config.vicreg_weight,
            prediction_weight=config.prediction_weight,
            ortho_weight=config.orthogonality_weight,
        )

        # === Karma Injection (SRK Integration) ===
        if config.enable_karma_injection and GatedKarmaProjector is not None:
            self.karma_gate = GatedKarmaProjector(state_dim=config.state_dim)
        else:
            self.karma_gate = None

        # === Training State ===
        self.register_buffer('training_step', torch.tensor(0, dtype=torch.long))
        self.curriculum: Optional[TrainingCurriculumOrchestrator] = None

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        context_len: Optional[int] = None,
        external_karma: Optional[torch.Tensor] = None,
        compute_loss: bool = False,
        return_states: bool = False,
        k_steps: Optional[int] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass through Phase-JEPA.

        Args:
            input_ids: Token IDs [B, T]
            attention_mask: Optional attention mask [B, T]
            context_len: Split point for context/target (default: T - k_steps)
            external_karma: Optional karma state from SRK [B, 32]
            compute_loss: Whether to compute JEPA losses
            return_states: Whether to return intermediate states
            k_steps: Override prediction steps

        Returns:
            Dictionary containing:
                - 'logits': Language model logits [B, T, V] (if encoder has lm_head)
                - 's_pred': Predicted state [B, 32]
                - 's_target': Target state [B, 32] (if compute_loss)
                - 'delta_list': List of predicted deltas
                - 'loss': Total JEPA loss (if compute_loss)
                - 'loss_components': Individual loss components (if compute_loss)
        """
        B, T = input_ids.shape
        k_steps = k_steps or self.config.prediction_steps

        # Determine context/target split
        if context_len is None:
            context_len = T - k_steps
            if context_len < 1:
                context_len = T // 2  # Fallback for short sequences

        context_ids = input_ids[:, :context_len]
        target_ids = input_ids  # Full sequence for target

        outputs = {}

        # === Context Path (Trainable) ===
        context_out = self.context_encoder(
            context_ids,
            attention_mask=attention_mask[:, :context_len] if attention_mask is not None else None,
        )

        # Handle different encoder output formats
        if isinstance(context_out, tuple):
            h_context = context_out[0]  # Hidden states
            if len(context_out) > 1:
                outputs['logits'] = context_out[1] if context_out[1] is not None else None
        elif isinstance(context_out, dict):
            h_context = context_out.get('hidden_states', context_out.get('last_hidden_state'))
            outputs['logits'] = context_out.get('logits')
        else:
            h_context = context_out

        # Project to state space
        s_context = self.state_projector(h_context)  # [B, T_ctx, 32]

        # Apply karma injection if enabled
        if external_karma is not None and self.karma_gate is not None:
            # Use last context state as internal karma
            internal_karma = s_context[:, -1, :]  # [B, 32]
            effective_karma = self.karma_gate(external_karma, internal_karma)
            # Inject back into last position
            s_context = s_context.clone()
            s_context[:, -1, :] = effective_karma

        # === Prediction ===
        s_pred, delta_list = self.predictor(s_context, k_steps=k_steps)
        outputs['s_pred'] = s_pred
        outputs['delta_list'] = delta_list

        # === Target Path (EMA, no gradients) ===
        if compute_loss:
            with torch.no_grad():
                target_out = self.target_encoder(
                    target_ids,
                    attention_mask=attention_mask,
                )

                if isinstance(target_out, tuple):
                    h_target = target_out[0]
                elif isinstance(target_out, dict):
                    h_target = target_out.get('hidden_states', target_out.get('last_hidden_state'))
                else:
                    h_target = target_out

                # Project to state space
                s_target = self.target_state_projector(h_target)

                # Extract target states at prediction positions
                # We want s_target at positions [context_len, context_len+1, ..., context_len+k-1]
                target_positions = list(range(context_len, min(context_len + k_steps, T)))
                if len(target_positions) > 0:
                    s_target_k = s_target[:, target_positions, :]  # [B, k, 32]
                else:
                    s_target_k = s_target[:, -1:, :]  # Fallback

                outputs['s_target'] = s_target_k

            # === Compute Losses ===
            loss_components = self._compute_losses(
                s_context=s_context,
                s_pred=s_pred,
                s_target=s_target_k,
                delta_list=delta_list,
            )
            outputs['loss_components'] = loss_components
            outputs['loss'] = loss_components['total']

        if return_states:
            outputs['h_context'] = h_context
            outputs['s_context'] = s_context

        return outputs

    def _compute_losses(
        self,
        s_context: torch.Tensor,
        s_pred: torch.Tensor,
        s_target: torch.Tensor,
        delta_list: List[torch.Tensor],
    ) -> Dict[str, torch.Tensor]:
        """Compute JEPA training losses."""

        # Get curriculum weights if available
        if self.curriculum is not None:
            weights = self.curriculum.get_loss_weights()
        else:
            weights = {
                'variance': self.config.vicreg_weight,
                'alignment': self.config.alignment_weight,
                'jepa': self.config.prediction_weight,
                'ortho': self.config.orthogonality_weight,
            }

        # VICReg loss (variance + covariance)
        # Compare context states with themselves for diversity
        s_context_flat = s_context.reshape(-1, s_context.shape[-1])
        vicreg_out = self.vicreg_loss(
            s_context_flat,
            s_context_flat,
            return_components=True,
        )

        # Alignment loss (predicted vs target)
        # Handle shape differences
        if s_pred.dim() == 2:
            s_pred_expanded = s_pred.unsqueeze(1)  # [B, 1, 32]
        else:
            s_pred_expanded = s_pred

        if s_target.dim() == 2:
            s_target_expanded = s_target.unsqueeze(1)  # [B, 1, 32]
        else:
            s_target_expanded = s_target

        # Take last predicted state and last target
        alignment_loss = self.alignment_loss(
            s_pred_expanded[:, -1, :] if s_pred_expanded.dim() == 3 else s_pred_expanded,
            s_target_expanded[:, -1, :] if s_target_expanded.dim() == 3 else s_target_expanded,
        )

        # Orthogonality loss on predictor weights
        pred_weight = self.predictor.get_prediction_weight()
        ortho_loss = torch.tensor(0.0, device=pred_weight.device)
        if pred_weight.shape[0] > 1:
            # Compute off-diagonal orthogonality
            ww = pred_weight @ pred_weight.T
            eye = torch.eye(ww.shape[0], device=ww.device)
            ortho_loss = ((ww - eye) ** 2).sum() / (ww.shape[0] ** 2)

        # Weighted total
        total_loss = (
            weights.get('variance', 1.0) * vicreg_out['total'] +
            weights.get('alignment', 1.0) * alignment_loss +
            weights.get('ortho', 0.01) * ortho_loss
        )

        return {
            'total': total_loss,
            'vicreg': vicreg_out['total'],
            'variance': vicreg_out['std'],
            'covariance': vicreg_out['cov'],
            'alignment': alignment_loss,
            'orthogonality': ortho_loss,
        }

    def update_target_encoder(self, step: Optional[int] = None):
        """Update target encoder with EMA of context encoder."""
        step = step or self.training_step.item()
        self.target_encoder.update(self.context_encoder, step=step)

    def set_curriculum(self, curriculum: TrainingCurriculumOrchestrator):
        """Set curriculum orchestrator for training."""
        self.curriculum = curriculum

    def training_step_update(
        self,
        metrics: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Update training step and curriculum.

        Args:
            metrics: Training metrics for adaptive curriculum

        Returns:
            Tuple of (phase_changed, new_phase_name)
        """
        self.training_step += 1
        step = self.training_step.item()

        # Update target encoder
        self.update_target_encoder(step)

        # Update curriculum
        if self.curriculum is not None:
            return self.curriculum.step(metrics=metrics)

        return False, None

    def freeze_predictor(self, freeze: bool = True):
        """Freeze or unfreeze predictor weights."""
        for param in self.predictor.parameters():
            param.requires_grad = not freeze

    def set_k_steps(self, k_steps: int):
        """Set prediction step count."""
        self.predictor.prediction_steps = k_steps

    def get_state_dim(self) -> int:
        """Get Sovereign State dimension."""
        return self.config.state_dim

    def state_dict(self, *args, **kwargs):
        """Get state dictionary including curriculum state."""
        state = super().state_dict(*args, **kwargs)
        if self.curriculum is not None:
            state['curriculum_state'] = self.curriculum.state_dict()
        return state

    def load_state_dict(self, state_dict, *args, **kwargs):
        """Load state dictionary including curriculum state."""
        curriculum_state = state_dict.pop('curriculum_state', None)
        result = super().load_state_dict(state_dict, *args, **kwargs)
        if curriculum_state is not None and self.curriculum is not None:
            self.curriculum.load_state_dict(curriculum_state)
        return result


def create_phase_jepa_transformer(
    config,
    context_encoder: Optional[nn.Module] = None,
) -> PhaseJEPATransformer:
    """
    Factory function to create PhaseJEPATransformer from training config.

    Args:
        config: UnifiedTrainingConfig or similar
        context_encoder: Optional pre-built encoder

    Returns:
        Configured PhaseJEPATransformer instance
    """
    jepa_config = PhaseJEPAConfig(
        vocab_size=getattr(config, 'vocab_size', 50257),
        embed_dim=getattr(config, 'embed_dim', 768),
        num_layers=getattr(config, 'num_layers', 12),
        num_encoder_heads=getattr(config, 'num_heads', 12),
        max_seq_len=getattr(config, 'max_seq_len', 2048),
        dropout=getattr(config, 'dropout', 0.1),
        # Hybrid settings
        local_layers=getattr(config, 'local_layers', 4),
        window_size=getattr(config, 'window_size', 256),
        alpha_local=getattr(config, 'alpha_local', 0.8),
        alpha_phase=getattr(config, 'alpha_phase', 0.2),
        cosine_mode=getattr(config, 'jepa_cosine_mode', 'complex'),
        # State projection
        state_dim=getattr(config, 'state_dim', SOVEREIGN_STATE_DIM),
        # Predictor
        predictor_hidden_dim=getattr(config, 'jepa_hidden_dim', 256),
        predictor_num_heads=getattr(config, 'jepa_num_heads', 4),
        prediction_steps=getattr(config, 'jepa_prediction_steps', 4),
        predictor_cosine_mode=getattr(config, 'jepa_cosine_mode', 'complex'),
        # Target encoder
        target_momentum=getattr(config, 'jepa_target_momentum', 0.996),
        momentum_schedule=getattr(config, 'jepa_momentum_schedule', 'cosine'),
        # Loss weights
        vicreg_weight=getattr(config, 'jepa_vicreg_weight', 1.0),
        alignment_weight=getattr(config, 'jepa_alignment_weight', 1.0),
        prediction_weight=getattr(config, 'jepa_prediction_weight', 0.5),
        orthogonality_weight=getattr(config, 'jepa_orthogonality_weight', 0.01),
        # Per-component weights
        bhava_weight=getattr(config, 'jepa_bhava_weight', 10.0),
        semantic_weight=getattr(config, 'jepa_semantic_weight', 1.0),
        guna_weight=getattr(config, 'jepa_guna_weight', 0.1),
        # Vritti validation
        enable_vritti_validation=getattr(config, 'jepa_enable_vritti_validation', False),
        viparyaya_threshold=getattr(config, 'jepa_viparyaya_threshold', 0.4),
        vikalpa_threshold=getattr(config, 'jepa_vikalpa_threshold', 0.6),
        damping_factor=getattr(config, 'jepa_damping_factor', 0.5),
        # SRK integration
        enable_karma_injection=getattr(config, 'jepa_enable_karma_injection', False),
        karma_gate_bias=getattr(config, 'jepa_karma_gate_bias', 0.5),
    )

    model = PhaseJEPATransformer(
        config=jepa_config,
        context_encoder=context_encoder,
    )

    # Setup curriculum if enabled
    if getattr(config, 'jepa_auto_phase_transition', False):
        curriculum = create_curriculum_from_config(config)
        model.set_curriculum(curriculum)

    return model
