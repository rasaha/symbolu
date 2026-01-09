"""
Phase-JEPA Transformer Wrapper.

Integrates all JEPA components into a unified transformer-like interface
for use with the existing training infrastructure.

Components:
    - Context Encoder (trainable): Processes input sequences
    - Target Encoder (EMA): Provides stable prediction targets
    - State Projector: Maps hidden states to 32D Sovereign State
    - Predictor: Phase-based state delta prediction
    - GoalGenerator: Autonomous goal generation from curiosity (Sankalpa)
    - SovereignJEPA: Self-motivated wrapper with autonomous cycle

Sovereign State Reserved Dimensions (Sankalpa Vector) [28:32]:
    - Dim 28: Goal Valence (positive/negative intent)
    - Dim 29: Goal Urgency (priority level)
    - Dim 30: Goal Complexity (task difficulty estimate)
    - Dim 31: Goal Source (0=external, 1=internal/curiosity-driven)

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


# === Sankalpa (Will/Goal) Vector Constants ===
# Reserved dimensions in 32D Sovereign State for autonomous goal encoding
SANKALPA_START_DIM = 28
SANKALPA_END_DIM = 32
SANKALPA_DIM_VALENCE = 28    # Goal Valence: positive/negative intent [-1, 1]
SANKALPA_DIM_URGENCY = 29    # Goal Urgency: priority level [0, 1]
SANKALPA_DIM_COMPLEXITY = 30  # Goal Complexity: task difficulty [0, 1]
SANKALPA_DIM_SOURCE = 31      # Goal Source: 0=external, 1=internal/curiosity


class GoalGenerator(nn.Module):
    """
    Autonomous Goal Generator Module (Sankalpa Generator).

    Takes current state and curiosity signal, outputs goal delta for
    reserved dimensions [28:32] of Sovereign State.

    The goal generator learns to propose goals that:
    1. Maximize curiosity satisfaction (reduce prediction error over time)
    2. Maintain goal coherence (don't flip goals rapidly)
    3. Balance exploration vs exploitation

    Architecture:
        input: [current_state (32D), curiosity_signal (1D)] -> 33D
        hidden: 64D with LayerNorm
        output: goal_delta (4D) for dims [28:32]
    """

    def __init__(
        self,
        state_dim: int = SOVEREIGN_STATE_DIM,
        hidden_dim: int = 64,
        goal_dim: int = 4,  # Sankalpa vector size
        dropout: float = 0.1,
        goal_momentum: float = 0.9,  # Smoothing for goal stability
    ):
        super().__init__()
        self.state_dim = state_dim
        self.goal_dim = goal_dim
        self.goal_momentum = goal_momentum

        # Input: state (32D) + curiosity (1D) = 33D
        self.goal_net = nn.Sequential(
            nn.Linear(state_dim + 1, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, goal_dim),
        )

        # Output activations for each goal dimension
        # Valence: Tanh -> [-1, 1]
        # Urgency/Complexity/Source: Sigmoid -> [0, 1]

        # Running average of goals for stability
        self.register_buffer('running_goal', torch.zeros(goal_dim))
        self.register_buffer('goal_count', torch.tensor(0, dtype=torch.long))

        # Initialize near zero for gradual goal emergence
        self._init_weights()

    def _init_weights(self):
        """Initialize with small weights for gradual goal emergence."""
        for module in self.goal_net.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, std=0.01)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(
        self,
        current_state: torch.Tensor,
        curiosity_signal: torch.Tensor,
        apply_momentum: bool = True,
    ) -> torch.Tensor:
        """
        Generate goal delta from state and curiosity.

        Args:
            current_state: Current Sovereign State [B, 32] or [B, T, 32]
            curiosity_signal: Curiosity/prediction error [B] or [B, T]
            apply_momentum: Whether to apply goal smoothing

        Returns:
            goal_delta: Goal vector update [B, 4] or [B, T, 4]
        """
        # Handle sequence dimension
        if current_state.dim() == 3:
            B, T, D = current_state.shape
            state_flat = current_state.reshape(B * T, D)
            curiosity_flat = curiosity_signal.reshape(B * T, 1)
        else:
            state_flat = current_state
            curiosity_flat = curiosity_signal.unsqueeze(-1) if curiosity_signal.dim() == 1 else curiosity_signal

        # Concatenate state and curiosity
        goal_input = torch.cat([state_flat, curiosity_flat], dim=-1)

        # Generate raw goal
        raw_goal = self.goal_net(goal_input)

        # Apply per-dimension activations
        goal = torch.zeros_like(raw_goal)
        goal[:, 0] = torch.tanh(raw_goal[:, 0])      # Valence [-1, 1]
        goal[:, 1] = torch.sigmoid(raw_goal[:, 1])   # Urgency [0, 1]
        goal[:, 2] = torch.sigmoid(raw_goal[:, 2])   # Complexity [0, 1]
        goal[:, 3] = torch.sigmoid(raw_goal[:, 3])   # Source [0, 1]

        # Apply momentum smoothing if enabled
        if apply_momentum and self.training:
            self.goal_count += 1
            # Update running average
            self.running_goal = (
                self.goal_momentum * self.running_goal +
                (1 - self.goal_momentum) * goal.mean(dim=0).detach()
            )
            # Blend with running average for stability
            blend_factor = min(1.0, self.goal_count.item() / 100)  # Warm up
            goal = blend_factor * goal + (1 - blend_factor) * self.running_goal.unsqueeze(0)

        # Reshape back if needed
        if current_state.dim() == 3:
            goal = goal.reshape(B, T, self.goal_dim)

        return goal

    def get_curiosity_driven_goal(
        self,
        current_state: torch.Tensor,
        curiosity_signal: torch.Tensor,
    ) -> torch.Tensor:
        """
        Generate a fully internal goal (Source=1.0) driven by curiosity.

        This is used in the autonomous cycle when no external task is given.
        """
        goal = self.forward(current_state, curiosity_signal, apply_momentum=True)
        # Force source dimension to 1.0 (internal)
        if goal.dim() == 3:
            goal[:, :, 3] = 1.0
        else:
            goal[:, 3] = 1.0
        return goal


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

    # Self-Motivation / Sankalpa Settings
    enable_self_motivation: bool = False
    curiosity_temperature: float = 1.0  # Scales curiosity signal
    goal_generator_hidden: int = 64
    goal_momentum: float = 0.9  # Smoothing for goal stability
    curiosity_threshold: float = 0.1  # Minimum curiosity to trigger goal generation
    autonomous_cycle_steps: int = 4  # Steps in autonomous observe→decide→act cycle


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
            ortho_weight=config.orthogonality_weight,
        )

        # === Karma Injection (SRK Integration) ===
        if config.enable_karma_injection and GatedKarmaProjector is not None:
            self.karma_gate = GatedKarmaProjector(state_dim=config.state_dim)
        else:
            self.karma_gate = None

        # === Self-Motivation / Sankalpa (Goal Generator) ===
        if config.enable_self_motivation:
            self.goal_generator = GoalGenerator(
                state_dim=config.state_dim,
                hidden_dim=config.goal_generator_hidden,
                goal_dim=SANKALPA_END_DIM - SANKALPA_START_DIM,  # 4D
                dropout=config.dropout,
                goal_momentum=config.goal_momentum,
            )
            self.curiosity_temperature = config.curiosity_temperature
            self.curiosity_threshold = config.curiosity_threshold
        else:
            self.goal_generator = None
            self.curiosity_temperature = 1.0
            self.curiosity_threshold = 0.1

        # === Phase 3 (Kṛti) Gradient Bridge ===
        # Intent Phase Projector: Maps predicted state to phase rotation for generation
        # CRITICAL: This creates the gradient path L_nll → logits → θ → s_pred → predictor
        self.intent_phase_projector = nn.Sequential(
            nn.Linear(config.state_dim, config.state_dim * 2),
            nn.GELU(),
            nn.Linear(config.state_dim * 2, config.num_encoder_heads),
            nn.Tanh(),  # Output in [-1, 1], scaled to [-π, π]
        )
        # Initialize near-zero for stable training start
        with torch.no_grad():
            self.intent_phase_projector[-2].weight.fill_(0.01)
            self.intent_phase_projector[-2].bias.fill_(0.0)

        # === Training State ===
        self.register_buffer('training_step', torch.tensor(0, dtype=torch.long))
        self.curriculum: Optional[TrainingCurriculumOrchestrator] = None
        self._phase3_mode: bool = False  # Flag for Phase 3 gradient flow

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
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
            labels: Target token IDs for NLL loss [B, T] (Phase 3 only)
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
        # Route to Phase 3 forward if enabled (gradient bridge for NLL→Predictor)
        if self._phase3_mode and (labels is not None or compute_loss):
            return self.forward_phase3(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
                context_len=context_len,
                external_karma=external_karma,
                k_steps=k_steps,
                return_loss_components=return_states,
            )

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
        # Request last_hidden_state for OntologicalHybridTransformer compatibility
        try:
            context_out = self.context_encoder(
                context_ids,
                attention_mask=attention_mask[:, :context_len] if attention_mask is not None else None,
                return_last_hidden=True,
            )
        except TypeError:
            # Encoder doesn't support return_last_hidden kwarg
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
            # Try multiple keys for hidden states (different encoders use different keys)
            h_context = context_out.get('last_hidden_state') or context_out.get('hidden_states')
            if h_context is None:
                # OntologicalHybridTransformer may need forward_hidden for raw hidden states
                raise ValueError(
                    "Encoder returned dict without 'last_hidden_state' or 'hidden_states'. "
                    "Ensure encoder is called with return_last_hidden=True or provides hidden states."
                )
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
                try:
                    target_out = self.target_encoder(
                        target_ids,
                        attention_mask=attention_mask,
                        return_last_hidden=True,
                    )
                except TypeError:
                    target_out = self.target_encoder(
                        target_ids,
                        attention_mask=attention_mask,
                    )

                if isinstance(target_out, tuple):
                    h_target = target_out[0]
                elif isinstance(target_out, dict):
                    h_target = target_out.get('last_hidden_state') or target_out.get('hidden_states')
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
            'variance': vicreg_out['variance'],
            'covariance': vicreg_out['covariance'],
            'alignment': alignment_loss,
            'orthogonality': ortho_loss,
        }

    def compute_curiosity_signal(
        self,
        s_pred: torch.Tensor,
        s_actual: torch.Tensor,
        normalize: bool = True,
    ) -> torch.Tensor:
        """
        Compute curiosity signal as prediction error.

        Curiosity = ||s_pred - s_actual||² (scaled by temperature)

        This is the intrinsic motivation signal that drives autonomous
        goal generation. High curiosity indicates novel/unpredictable
        situations that warrant further exploration.

        Args:
            s_pred: Predicted state [B, 32] or [B, T, 32]
            s_actual: Actual observed state [B, 32] or [B, T, 32]
            normalize: Whether to normalize by state dimension

        Returns:
            curiosity: Scalar curiosity signal [B] or [B, T]
        """
        # Handle shape mismatches between s_pred and s_actual
        # If s_pred is 3D [B, T, D] and s_actual is 2D [B, D], use last state from s_pred
        if s_pred.dim() == 3 and s_actual.dim() == 2:
            s_pred = s_pred[:, -1, :]  # Take last predicted state [B, D]
        elif s_pred.dim() == 2 and s_actual.dim() == 3:
            s_actual = s_actual[:, -1, :]  # Take last actual state [B, D]

        # Compute L2 prediction error
        prediction_error = torch.norm(s_pred - s_actual, p=2, dim=-1)

        # Normalize by sqrt(state_dim) if requested for scale invariance
        if normalize:
            prediction_error = prediction_error / math.sqrt(self.config.state_dim)

        # Scale by temperature (higher temp = more sensitive to errors)
        curiosity = prediction_error * self.curiosity_temperature

        return curiosity

    def inject_sankalpa(
        self,
        state: torch.Tensor,
        goal: torch.Tensor,
    ) -> torch.Tensor:
        """
        Inject Sankalpa (goal) vector into reserved dimensions [28:32].

        This modifies the state to encode the current goal/intent,
        enabling goal-directed behavior.

        Args:
            state: Sovereign State [B, 32] or [B, T, 32]
            goal: Sankalpa vector [B, 4] or [B, T, 4]

        Returns:
            Modified state with goal injected [B, 32] or [B, T, 32]
        """
        modified_state = state.clone()

        if state.dim() == 3:
            # Sequence of states [B, T, 32]
            # If goal is 2D [B, 4], expand to [B, T, 4]
            if goal.dim() == 2:
                goal = goal.unsqueeze(1).expand(-1, state.size(1), -1)
            modified_state[:, :, SANKALPA_START_DIM:SANKALPA_END_DIM] = goal
        else:
            # Single state [B, 32]
            # If goal is 3D, take last timestep
            if goal.dim() == 3:
                goal = goal[:, -1, :]
            modified_state[:, SANKALPA_START_DIM:SANKALPA_END_DIM] = goal

        return modified_state

    def extract_sankalpa(
        self,
        state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Extract Sankalpa (goal) vector from state.

        Args:
            state: Sovereign State [B, 32] or [B, T, 32]

        Returns:
            Sankalpa vector [B, 4] or [B, T, 4]
        """
        if state.dim() == 3:
            return state[:, :, SANKALPA_START_DIM:SANKALPA_END_DIM]
        else:
            return state[:, SANKALPA_START_DIM:SANKALPA_END_DIM]

    def compute_phase_rotation(
        self,
        s_pred: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute phase rotation angles from predicted state.

        CRITICAL: This maintains gradient flow from logits → θ → s_pred → predictor.
        Used during Phase 3 (Kṛti) training to enable L_nll gradients to flow
        back into the PhaseJEPAPredictor.

        Args:
            s_pred: Predicted state [B, 32] or [B, T, 32]

        Returns:
            Phase rotation angles [B, num_heads] or [B, T, num_heads], scaled to [-π, π]
        """
        # s_pred must have gradients attached for Phase 3 training
        # DO NOT detach - this is the critical gradient bridge

        if s_pred.dim() == 3:
            # Handle sequence of states
            B, T, D = s_pred.shape
            s_flat = s_pred.reshape(B * T, D)
            theta_flat = self.intent_phase_projector(s_flat)  # [B*T, num_heads]
            theta = theta_flat.reshape(B, T, -1)
        else:
            theta = self.intent_phase_projector(s_pred)  # [B, num_heads]

        # Scale from [-1, 1] (Tanh output) to [-π, π]
        theta = theta * math.pi

        return theta

    def forward_phase3(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        context_len: Optional[int] = None,
        external_karma: Optional[torch.Tensor] = None,
        k_steps: Optional[int] = None,
        return_loss_components: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Phase 3 (Kṛti) forward pass with gradient flow from NLL to predictor.

        This method ensures that:
        1. Predicted states s_pred are NOT detached
        2. Phase rotation θ = intent_phase_projector(s_pred) maintains gradients
        3. L_nll gradients flow: L_nll → logits → θ → s_pred → predictor

        The predictor learns: "I set θ=45°, got 'Cat'. Should have been θ=90° for 'Dog'."

        Args:
            input_ids: Token IDs [B, T]
            attention_mask: Optional attention mask [B, T]
            labels: Target token IDs for NLL loss [B, T]
            context_len: Split point for context/target
            external_karma: Optional karma state from SRK [B, 32]
            k_steps: Override prediction steps
            return_loss_components: Return individual loss values

        Returns:
            Dictionary containing:
                - 'loss': Combined L_jepa + L_nll with gradient bridge
                - 'nll_loss': Token prediction loss (gradients flow to predictor!)
                - 'jepa_loss': State prediction loss
                - 's_pred': Predicted states
                - 'phase_rotation': Phase angles θ from predictor
                - 'logits': Language model logits
        """
        B, T = input_ids.shape
        k_steps = k_steps or self.config.prediction_steps

        # Determine context/target split
        if context_len is None:
            context_len = T - k_steps
            if context_len < 1:
                context_len = T // 2

        context_ids = input_ids[:, :context_len]
        outputs = {}

        # === Step 1: Context Encoding ===
        try:
            context_out = self.context_encoder(
                context_ids,
                attention_mask=attention_mask[:, :context_len] if attention_mask is not None else None,
                return_last_hidden=True,
            )
        except TypeError:
            context_out = self.context_encoder(
                context_ids,
                attention_mask=attention_mask[:, :context_len] if attention_mask is not None else None,
            )

        if isinstance(context_out, tuple):
            h_context = context_out[0]
        elif isinstance(context_out, dict):
            h_context = context_out.get('last_hidden_state') or context_out.get('hidden_states')
        else:
            h_context = context_out

        # Project to state space
        s_context = self.state_projector(h_context)  # [B, T_ctx, 32]

        # Apply karma injection if enabled
        if external_karma is not None and self.karma_gate is not None:
            internal_karma = s_context[:, -1, :]
            effective_karma = self.karma_gate(external_karma, internal_karma)
            s_context = s_context.clone()
            s_context[:, -1, :] = effective_karma

        # === Step 2: Prediction (CRITICAL: s_pred has gradients) ===
        s_pred, delta_list = self.predictor(s_context, k_steps=k_steps)
        outputs['s_pred'] = s_pred
        outputs['delta_list'] = delta_list

        # === Step 3: Phase Rotation Bridge (CRITICAL: maintains gradients) ===
        # This is the key: θ = f(s_pred), where f is differentiable
        phase_rotation = self.compute_phase_rotation(s_pred)  # [B, num_heads]
        outputs['phase_rotation'] = phase_rotation

        # === Step 4: Full Sequence Forward with Phase Rotation ===
        # Now run full forward through context encoder with phase rotation applied
        # The phase rotation modifies attention patterns based on predicted intent

        # Check if context_encoder supports phase rotation injection
        if hasattr(self.context_encoder, 'forward_with_phase'):
            # Encoder supports direct phase injection
            full_out = self.context_encoder.forward_with_phase(
                input_ids,
                attention_mask=attention_mask,
                phase_rotation=phase_rotation,
                return_last_hidden=True,
            )
        else:
            # Standard forward - phase rotation applied via hidden state modulation
            try:
                full_out = self.context_encoder(
                    input_ids,
                    attention_mask=attention_mask,
                    return_last_hidden=True,
                )
            except TypeError:
                full_out = self.context_encoder(
                    input_ids,
                    attention_mask=attention_mask,
                )

            # Get hidden states and logits
            if isinstance(full_out, tuple):
                h_full = full_out[0]
                logits = full_out[1] if len(full_out) > 1 else None
            elif isinstance(full_out, dict):
                h_full = full_out.get('last_hidden_state') or full_out.get('hidden_states')
                logits = full_out.get('logits')
            else:
                h_full = full_out
                logits = None

            # Apply phase rotation to hidden states before LM head
            # This creates the gradient bridge: hidden_states modulated by θ
            if logits is None and hasattr(self.context_encoder, 'lm_head'):
                # Modulate hidden states with phase rotation
                # Phase rotation shapes attention-like weighting
                h_modulated = self._apply_phase_modulation(h_full, phase_rotation)
                logits = self.context_encoder.lm_head(h_modulated)

        # Get logits from output if not already set
        if logits is None:
            if isinstance(full_out, tuple) and len(full_out) > 1:
                logits = full_out[1]
            elif isinstance(full_out, dict):
                logits = full_out.get('logits')

        # CRITICAL: Always apply phase modulation to logits for gradient bridge
        # This ensures gradients flow: L_nll → logits → phase_rotation → s_pred → predictor
        if logits is not None and phase_rotation is not None:
            logits = self._modulate_logits_with_phase(logits, phase_rotation)

        outputs['logits'] = logits

        # === Step 5: Compute Losses ===
        losses = {}
        total_loss = torch.tensor(0.0, device=input_ids.device, requires_grad=True)

        # 5a. JEPA Loss (state prediction)
        if self.training:
            with torch.no_grad():
                try:
                    target_out = self.target_encoder(input_ids, attention_mask=attention_mask, return_last_hidden=True)
                except TypeError:
                    target_out = self.target_encoder(input_ids, attention_mask=attention_mask)
                if isinstance(target_out, tuple):
                    h_target = target_out[0]
                elif isinstance(target_out, dict):
                    h_target = target_out.get('last_hidden_state') or target_out.get('hidden_states')
                else:
                    h_target = target_out
                s_target = self.target_state_projector(h_target)

                target_positions = list(range(context_len, min(context_len + k_steps, T)))
                if len(target_positions) > 0:
                    s_target_k = s_target[:, target_positions, :]
                else:
                    s_target_k = s_target[:, -1:, :]

            jepa_components = self._compute_losses(
                s_context=s_context,
                s_pred=s_pred,
                s_target=s_target_k,
                delta_list=delta_list,
            )
            losses['jepa'] = jepa_components['total']
            total_loss = total_loss + jepa_components['total']

            if return_loss_components:
                losses.update({f'jepa_{k}': v for k, v in jepa_components.items()})

        # 5b. NLL Loss (CRITICAL: gradients flow back through phase_rotation to predictor)
        if labels is not None and logits is not None:
            # Shift for next token prediction
            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = labels[:, 1:].contiguous()

            # Cross entropy with gradient flow
            nll_loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=-100,
            )
            losses['nll'] = nll_loss

            # Get curriculum NLL weight (Phase 3 has full NLL weight)
            if self.curriculum is not None:
                weights = self.curriculum.get_loss_weights()
                nll_weight = weights.get('nll', 1.0)
            else:
                nll_weight = 1.0

            total_loss = total_loss + nll_weight * nll_loss

        outputs['loss'] = total_loss
        outputs['loss_components'] = losses

        return outputs

    def _apply_phase_modulation(
        self,
        hidden_states: torch.Tensor,
        phase_rotation: torch.Tensor,
    ) -> torch.Tensor:
        """
        Apply phase rotation modulation to hidden states.

        This creates a multiplicative modulation based on phase angles,
        allowing gradient flow from logits through to predicted states.

        Args:
            hidden_states: [B, T, D]
            phase_rotation: [B, num_heads] or [B, T, num_heads]

        Returns:
            Modulated hidden states [B, T, D]
        """
        B, T, D = hidden_states.shape
        num_heads = phase_rotation.shape[-1]
        head_dim = D // num_heads

        # Expand phase rotation if needed
        if phase_rotation.dim() == 2:
            # [B, num_heads] -> [B, T, num_heads]
            phase_rotation = phase_rotation.unsqueeze(1).expand(-1, T, -1)

        # Convert to complex rotation factors
        # cos(θ) + i*sin(θ) applied per head
        cos_theta = torch.cos(phase_rotation)  # [B, T, num_heads]
        sin_theta = torch.sin(phase_rotation)  # [B, T, num_heads]

        # Reshape hidden states for head-wise operation
        h_heads = hidden_states.view(B, T, num_heads, head_dim)

        # Apply rotation: for each head, rotate the feature space
        # Split head_dim in half for (real, imag) pairs
        half_dim = head_dim // 2
        h_real = h_heads[..., :half_dim]
        h_imag = h_heads[..., half_dim:]

        # Complex rotation: (r + i*i) * (cos + i*sin) = (r*cos - i*sin) + i*(r*sin + i*cos)
        cos_expanded = cos_theta.unsqueeze(-1)  # [B, T, num_heads, 1]
        sin_expanded = sin_theta.unsqueeze(-1)  # [B, T, num_heads, 1]

        h_real_rot = h_real * cos_expanded - h_imag * sin_expanded
        h_imag_rot = h_real * sin_expanded + h_imag * cos_expanded

        # Recombine
        h_rotated = torch.cat([h_real_rot, h_imag_rot], dim=-1)
        h_modulated = h_rotated.view(B, T, D)

        return h_modulated

    def _modulate_logits_with_phase(
        self,
        logits: torch.Tensor,
        phase_rotation: torch.Tensor,
    ) -> torch.Tensor:
        """
        Apply soft phase modulation to logits for gradient bridge.

        This creates a differentiable connection from logits back through
        phase_rotation → intent_phase_projector → s_pred → predictor.

        The modulation is intentionally subtle (near-identity) to preserve
        logit distribution while enabling gradient flow.

        Args:
            logits: [B, T, V] vocabulary logits
            phase_rotation: [B, num_heads] or [B, T_ctx, num_heads]

        Returns:
            Modulated logits [B, T, V] with gradient path to phase_rotation
        """
        # Compute a soft scaling factor from phase rotation
        # Use mean across all dimensions for consistent scaling
        # This handles shape mismatch between logits (full seq) and phase_rotation (context)
        if phase_rotation.dim() == 3:
            # [B, T_ctx, num_heads] -> [B, 1] mean over time and heads
            phase_mean = phase_rotation.mean(dim=(1, 2), keepdim=True).squeeze(-1)  # [B, 1]
        else:
            # [B, num_heads] -> [B, 1]
            phase_mean = phase_rotation.mean(dim=-1, keepdim=True)  # [B, 1]

        # Normalize to near-identity scaling (0.98 to 1.02)
        # This preserves logit distribution while creating gradient path
        scale = 1.0 + 0.02 * torch.tanh(phase_mean / math.pi)

        # Expand for broadcasting with logits [B, T, V]
        scale = scale.unsqueeze(-1)  # [B, 1, 1]

        return logits * scale

    def set_phase3_mode(self, enabled: bool = True):
        """
        Enable or disable Phase 3 (Kṛti) gradient flow mode.

        When enabled, forward() will use forward_phase3() for full gradient flow.
        This ensures L_nll gradients flow back to the predictor.

        Args:
            enabled: Whether to enable Phase 3 mode
        """
        self._phase3_mode = enabled

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


@dataclass
class SovereignJEPAConfig:
    """Configuration for SovereignJEPA (self-motivated wrapper)."""

    # Base JEPA config
    jepa_config: Optional[PhaseJEPAConfig] = None

    # Autonomous cycle settings
    autonomous_cycle_steps: int = 4
    curiosity_threshold: float = 0.1
    max_idle_steps: int = 10  # Steps without external input before autonomous goal

    # Goal generation settings
    exploration_rate: float = 0.1  # Probability of random goal exploration
    goal_persistence: int = 8  # Steps to maintain goal before re-evaluation

    # Self-monitoring
    enable_metacognition: bool = True  # Monitor own prediction quality
    metacognition_window: int = 100  # Steps for running statistics


class SovereignJEPA(nn.Module):
    """
    Self-Motivated JEPA Wrapper with Autonomous Goal Selection.

    Implements the Sankalpa (Will/Intention) cycle for autonomous operation:

    1. OBSERVE (Pramāṇa): Encode current context → s_context
    2. PREDICT (Icchā): Generate predictions → s_pred
    3. COMPARE (Viveka): Compute curiosity = ||s_pred - s_actual||²
    4. DECIDE (Sankalpa): Generate/update goal based on curiosity
    5. ACT (Kṛti): Execute goal-directed generation
    6. LEARN (Karma): Update weights based on outcomes

    The system can operate in two modes:
    - External-directed: Goals come from user input (Source=0)
    - Self-directed: Goals emerge from curiosity (Source=1)

    Example:
        >>> config = SovereignJEPAConfig(autonomous_cycle_steps=4)
        >>> model = SovereignJEPA(config)
        >>> # Autonomous step when idle
        >>> outputs = model.autonomous_step(context_ids)
        >>> # The model has generated its own goal and acted on it
    """

    def __init__(
        self,
        config: Optional[SovereignJEPAConfig] = None,
        jepa_model: Optional[PhaseJEPATransformer] = None,
        **kwargs,
    ):
        """
        Initialize SovereignJEPA.

        Args:
            config: SovereignJEPAConfig instance
            jepa_model: Optional pre-built PhaseJEPATransformer
            **kwargs: Override config parameters
        """
        super().__init__()

        # Build config
        if config is None:
            config = SovereignJEPAConfig(**kwargs)
        self.config = config

        # === Core JEPA Model ===
        if jepa_model is not None:
            self.jepa = jepa_model
        else:
            jepa_config = config.jepa_config or PhaseJEPAConfig(
                enable_self_motivation=True,
            )
            # Ensure self-motivation is enabled
            jepa_config.enable_self_motivation = True
            self.jepa = PhaseJEPATransformer(config=jepa_config)

        # === Autonomous Cycle State ===
        self.register_buffer('idle_steps', torch.tensor(0, dtype=torch.long))
        self.register_buffer('current_goal_steps', torch.tensor(0, dtype=torch.long))
        self.register_buffer('total_autonomous_steps', torch.tensor(0, dtype=torch.long))

        # Current goal (persists across steps)
        self.register_buffer('current_goal', torch.zeros(4))  # Sankalpa vector

        # === Metacognition Statistics ===
        if config.enable_metacognition:
            self.register_buffer(
                'curiosity_history',
                torch.zeros(config.metacognition_window),
            )
            self.register_buffer('curiosity_idx', torch.tensor(0, dtype=torch.long))
            self.register_buffer('mean_curiosity', torch.tensor(0.0))
            self.register_buffer('std_curiosity', torch.tensor(1.0))

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        external_goal: Optional[torch.Tensor] = None,
        **kwargs,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with optional external goal injection.

        If external_goal is provided, uses it. Otherwise, uses current
        internally-generated goal.

        Args:
            input_ids: Token IDs [B, T]
            attention_mask: Optional attention mask
            labels: Target labels for NLL loss
            external_goal: External Sankalpa vector [B, 4] (optional)
            **kwargs: Additional arguments for JEPA forward

        Returns:
            JEPA outputs with goal information
        """
        # Reset idle counter on external input
        self.idle_steps.zero_()

        outputs = self.jepa(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
            **kwargs,
        )

        # Inject goal into predicted state if available
        if external_goal is not None:
            # External goal (Source=0)
            goal = external_goal.clone()
            goal[:, 3] = 0.0  # Mark as external source
            outputs['s_pred'] = self.jepa.inject_sankalpa(outputs['s_pred'], goal)
            outputs['goal'] = goal
            outputs['goal_source'] = 'external'
        elif self.current_goal.sum() != 0:
            # Use current internal goal
            B = input_ids.shape[0]
            goal = self.current_goal.unsqueeze(0).expand(B, -1)
            outputs['s_pred'] = self.jepa.inject_sankalpa(outputs['s_pred'], goal)
            outputs['goal'] = goal
            outputs['goal_source'] = 'internal'

        return outputs

    def autonomous_step(
        self,
        context_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        force_new_goal: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Autonomous cycle: Observe → Predict → Compare → Decide → Act.

        This is the core self-motivation loop. When called without external
        direction, the model:
        1. Observes current context
        2. Makes predictions about future states
        3. Computes curiosity from prediction errors
        4. Generates or updates its goal based on curiosity
        5. Acts according to the goal

        Args:
            context_ids: Current context token IDs [B, T]
            attention_mask: Optional attention mask
            force_new_goal: Force generation of new goal regardless of persistence

        Returns:
            Dictionary containing:
                - Standard JEPA outputs
                - 'curiosity': Curiosity signal
                - 'goal': Current/new goal vector
                - 'goal_changed': Whether goal was updated
                - 'autonomous_action': Description of decided action
        """
        B, T = context_ids.shape
        outputs = {}

        # === Step 1: OBSERVE (Pramāṇa) - Encode context ===
        context_out = self.jepa(
            context_ids,
            attention_mask=attention_mask,
            compute_loss=False,
            return_states=True,
        )
        s_context = context_out['s_context']
        s_pred = context_out['s_pred']
        outputs.update(context_out)

        # === Step 2: PREDICT (Icchā) - Already done in context_out ===
        # s_pred contains the predicted future state

        # === Step 3: COMPARE (Viveka) - Compute curiosity ===
        # We need actual future state. In autonomous mode, we compare with
        # our best estimate from the target encoder (self-supervised)
        with torch.no_grad():
            try:
                target_out = self.jepa.target_encoder(
                    context_ids,
                    attention_mask=attention_mask,
                    return_last_hidden=True,
                )
            except TypeError:
                target_out = self.jepa.target_encoder(
                    context_ids,
                    attention_mask=attention_mask,
                )
            if isinstance(target_out, tuple):
                h_target = target_out[0]
            elif isinstance(target_out, dict):
                h_target = target_out.get('last_hidden_state') or target_out.get('hidden_states')
            else:
                h_target = target_out
            s_actual = self.jepa.target_state_projector(h_target)
            # Use last position as "actual" future state estimate
            s_actual = s_actual[:, -1, :]

        curiosity = self.jepa.compute_curiosity_signal(s_pred, s_actual)
        outputs['curiosity'] = curiosity

        # Update metacognition statistics
        if self.config.enable_metacognition:
            self._update_curiosity_stats(curiosity.mean())

        # === Step 4: DECIDE (Sankalpa) - Generate/update goal ===
        goal_changed = False
        mean_curiosity = curiosity.mean().item()

        # Determine if we should generate new goal
        should_generate_goal = (
            force_new_goal or
            self.current_goal.sum() == 0 or  # No current goal
            self.current_goal_steps >= self.config.goal_persistence  # Goal expired
        )

        # Check for surprising event (only if metacognition is enabled)
        if self.config.enable_metacognition:
            surprising_event = mean_curiosity > self.mean_curiosity + 2 * self.std_curiosity
            should_generate_goal = should_generate_goal or surprising_event

        if should_generate_goal and self.jepa.goal_generator is not None:
            # Generate new goal from curiosity
            new_goal = self.jepa.goal_generator.get_curiosity_driven_goal(
                s_context[:, -1, :],  # Last context state
                curiosity,
            )
            self.current_goal = new_goal.mean(dim=0).detach()
            self.current_goal_steps.zero_()
            goal_changed = True
        else:
            self.current_goal_steps += 1

        outputs['goal'] = self.current_goal.unsqueeze(0).expand(B, -1)
        outputs['goal_changed'] = goal_changed

        # === Step 5: ACT (Kṛti) - Goal-directed state ===
        # Inject goal into predicted state for action execution
        s_goal_directed = self.jepa.inject_sankalpa(s_pred, outputs['goal'])
        outputs['s_goal_directed'] = s_goal_directed

        # Determine autonomous action based on goal valence and urgency
        outputs['autonomous_action'] = self._describe_action(
            self.current_goal,
            mean_curiosity,
        )

        # Update counters
        self.total_autonomous_steps += 1
        self.idle_steps += 1

        return outputs

    def _update_curiosity_stats(self, curiosity_value: float):
        """Update running statistics for metacognition."""
        idx = self.curiosity_idx.item() % self.config.metacognition_window
        self.curiosity_history[idx] = curiosity_value
        self.curiosity_idx += 1

        # Update mean and std after warmup
        if self.curiosity_idx >= self.config.metacognition_window:
            self.mean_curiosity = self.curiosity_history.mean()
            self.std_curiosity = self.curiosity_history.std() + 1e-6

    def _describe_action(
        self,
        goal: torch.Tensor,
        curiosity: float,
    ) -> str:
        """
        Describe the autonomous action based on goal state.

        Returns human-readable description of what the system intends to do.
        """
        valence = goal[0].item()
        urgency = goal[1].item()
        complexity = goal[2].item()
        source = goal[3].item()

        source_str = "internal" if source > 0.5 else "external"

        if curiosity > self.config.curiosity_threshold:
            action = "EXPLORE"
            detail = f"high_curiosity={curiosity:.3f}"
        elif valence > 0.3:
            action = "PURSUE_POSITIVE"
            detail = f"valence={valence:.2f}"
        elif valence < -0.3:
            action = "AVOID_NEGATIVE"
            detail = f"valence={valence:.2f}"
        else:
            action = "MAINTAIN"
            detail = "stable_state"

        urgency_str = "URGENT" if urgency > 0.7 else "normal" if urgency > 0.3 else "low_priority"

        return f"{action}({source_str}, {urgency_str}, complexity={complexity:.2f}, {detail})"

    def get_autonomous_state(self) -> Dict[str, any]:
        """Get current autonomous operation state for monitoring."""
        return {
            'idle_steps': self.idle_steps.item(),
            'current_goal': self.current_goal.tolist(),
            'goal_steps': self.current_goal_steps.item(),
            'total_autonomous_steps': self.total_autonomous_steps.item(),
            'mean_curiosity': self.mean_curiosity.item(),
            'std_curiosity': self.std_curiosity.item(),
            'goal_valence': self.current_goal[0].item(),
            'goal_urgency': self.current_goal[1].item(),
            'goal_complexity': self.current_goal[2].item(),
            'goal_source': 'internal' if self.current_goal[3].item() > 0.5 else 'external',
        }

    def should_act_autonomously(self) -> bool:
        """Check if autonomous action should be taken."""
        return (
            self.idle_steps >= self.config.max_idle_steps and
            self.jepa.goal_generator is not None
        )

    def reset_autonomous_state(self):
        """Reset autonomous operation state."""
        self.idle_steps.zero_()
        self.current_goal_steps.zero_()
        self.current_goal.zero_()

    def state_dict(self, *args, **kwargs):
        """Get state dict including autonomous state."""
        state = super().state_dict(*args, **kwargs)
        state['autonomous_state'] = self.get_autonomous_state()
        return state


def create_sovereign_jepa(
    config,
    jepa_model: Optional[PhaseJEPATransformer] = None,
) -> SovereignJEPA:
    """
    Factory function to create SovereignJEPA with self-motivation.

    Args:
        config: Training config with sovereign JEPA settings
        jepa_model: Optional pre-built PhaseJEPATransformer

    Returns:
        Configured SovereignJEPA instance
    """
    # Build JEPA config with self-motivation enabled
    jepa_config = PhaseJEPAConfig(
        vocab_size=getattr(config, 'vocab_size', 50257),
        embed_dim=getattr(config, 'embed_dim', 768),
        num_layers=getattr(config, 'num_layers', 12),
        num_encoder_heads=getattr(config, 'num_heads', 12),
        max_seq_len=getattr(config, 'max_seq_len', 2048),
        dropout=getattr(config, 'dropout', 0.1),
        state_dim=getattr(config, 'state_dim', SOVEREIGN_STATE_DIM),
        # Enable self-motivation
        enable_self_motivation=True,
        curiosity_temperature=getattr(config, 'curiosity_temperature', 1.0),
        goal_generator_hidden=getattr(config, 'goal_generator_hidden', 64),
        goal_momentum=getattr(config, 'goal_momentum', 0.9),
        curiosity_threshold=getattr(config, 'curiosity_threshold', 0.1),
    )

    sovereign_config = SovereignJEPAConfig(
        jepa_config=jepa_config,
        autonomous_cycle_steps=getattr(config, 'autonomous_cycle_steps', 4),
        curiosity_threshold=getattr(config, 'curiosity_threshold', 0.1),
        max_idle_steps=getattr(config, 'max_idle_steps', 10),
        exploration_rate=getattr(config, 'exploration_rate', 0.1),
        goal_persistence=getattr(config, 'goal_persistence', 8),
        enable_metacognition=getattr(config, 'enable_metacognition', True),
        metacognition_window=getattr(config, 'metacognition_window', 100),
    )

    return SovereignJEPA(
        config=sovereign_config,
        jepa_model=jepa_model,
    )
