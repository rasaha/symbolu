"""
Ontological State Predictor — Phase-Space Delta Prediction.

Predicts state transitions (deltas) in the 32D Sovereign State space
using phase-space dynamics. This is NOT Meta's VL-JEPA — it is a custom
latent-space predictor inspired by the JEPA principle of predicting in
representation space without reconstruction.

The predictor operates across the five planes of the 32D Sovereign State:
    - Ontological Plane [0:12]:  12 Bhavas (identity, phase rotation)
    - Depth Plane [12:17]:       5 Koshas (processing depth)
    - Intellectual Plane [17:22]: 5 Vrittis (cognitive reliability)
    - Dynamics Plane [22:28]:    6 Gunas (energy/system dynamics)
    - Learning Plane [28:32]:    4 Reserved (goal encoding/feedback)

The VrittiValidatedPredictor uses the Intellectual Plane (Vrittis) as an
epistemological gate — rejecting predictions where Viparyaya (error) or
Vikalpa (imagination) spike beyond threshold for factual tasks.

Key Innovation:
    - Intent-guided phase rotation
    - O(n) complexity via cumulative sums
    - Multi-step autoregressive prediction
    - Vritti-based intellectual validation

References:
    - HYBRID_PHASE_JEPA_DESIGN.md §4
    - PHASE_ATTENTION_ALGORITHM.md
"""

import math
import torch
import torch.nn as nn
from typing import List, Tuple, Optional, Dict

try:
    from symbolu.sovereign.reasoning_kernel import SOVEREIGN_STATE_DIM
except ImportError:
    SOVEREIGN_STATE_DIM = 32


class PhaseJEPAPredictor(nn.Module):
    """
    Ontological State Predictor using phase-space dynamics.

    Predicts state deltas across all five planes of the 32D Sovereign State
    using complex phasor attention. Operates in latent state space, not
    token or pixel space.

    Architecture:
        1. Phase-Amplitude Decomposition of input state
        2. Intent-guided Phase Rotation
        3. Phasor Prediction via complex cumsum (O(n))
        4. Multi-step autoregressive rollout

    Args:
        state_dim: Sovereign State dimension (default 32)
        hidden_dim: Predictor hidden dimension
        num_heads: Number of attention heads for phase attention
        head_dim: Dimension per head (default state_dim // num_heads)
        prediction_steps: Maximum prediction steps (k-step lookahead)
        cosine_mode: Phase attention cosine mode ('standard', 'shifted', 'complex')
        dropout: Dropout probability
    """

    def __init__(
        self,
        state_dim: int = SOVEREIGN_STATE_DIM,
        hidden_dim: int = 256,
        num_heads: int = 4,
        head_dim: Optional[int] = None,
        prediction_steps: int = 4,
        cosine_mode: str = 'complex',  # 'complex' preserves full phasor info
        dropout: float = 0.1,
    ):
        super().__init__()

        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.head_dim = head_dim or (state_dim // num_heads)
        self.prediction_steps = prediction_steps
        self.cosine_mode = cosine_mode

        # Phase/Amplitude Projections (separate Q/K for asymmetric attention)
        self.W_q_phase = nn.Linear(state_dim, state_dim, bias=False)
        self.W_q_amp = nn.Linear(state_dim, state_dim, bias=False)
        self.W_k_phase = nn.Linear(state_dim, state_dim, bias=False)
        self.W_k_amp = nn.Linear(state_dim, state_dim, bias=False)
        self.W_v = nn.Linear(state_dim, state_dim, bias=False)

        # Intent Phase Projector (derives rotation from current state)
        self.intent_projector = nn.Sequential(
            nn.Linear(state_dim, state_dim),
            nn.GELU(),
            nn.Linear(state_dim, state_dim),
            nn.Tanh(),  # Output in [-1, 1], scaled to [-π, π]
        )

        # Delta Prediction MLP
        self.delta_mlp = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, state_dim),
        )

        # Multi-step prediction: learned step embeddings
        self.step_embeddings = nn.Embedding(prediction_steps, state_dim)

        # Complex mode: projection from [real, imag] -> real
        if cosine_mode == 'complex':
            self.complex_to_real = nn.Linear(2 * state_dim, state_dim, bias=False)
            # Initialize to favor real (cos) component
            with torch.no_grad():
                self.complex_to_real.weight[:, :state_dim] = torch.eye(state_dim) * 0.8
                self.complex_to_real.weight[:, state_dim:] = torch.eye(state_dim) * 0.2
        else:
            self.complex_to_real = None

        # Output layer norm
        self.output_norm = nn.LayerNorm(state_dim)

        # Initialize phase projections uniformly in [-π, π]
        nn.init.uniform_(self.W_q_phase.weight, -math.pi, math.pi)
        nn.init.uniform_(self.W_k_phase.weight, -math.pi, math.pi)

    def forward(
        self,
        s_context: torch.Tensor,
        k_steps: Optional[int] = None,
        return_intermediates: bool = False,
    ) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        """
        Predict k-step state deltas.

        Args:
            s_context: Context state [B, T, 32] or [B, 32]
            k_steps: Number of prediction steps (default: self.prediction_steps)
            return_intermediates: If True, return intermediate states

        Returns:
            s_pred: Final predicted state [B, T, 32] or [B, 32]
            delta_list: List of predicted deltas [ΔS₁, ΔS₂, ..., ΔSₖ]
        """
        k_steps = k_steps or self.prediction_steps

        # Handle both sequence and single-state inputs
        squeeze_output = False
        if s_context.dim() == 2:
            s_context = s_context.unsqueeze(1)  # [B, 1, D]
            squeeze_output = True

        B, T, D = s_context.shape

        # Extract intent phase from current state (how to rotate predictions)
        # θ_intent determines the "cognitive mode" for prediction
        theta_intent = self.intent_projector(s_context) * math.pi  # [B, T, D]

        delta_list = []
        intermediate_states = []
        s_current = s_context

        for step in range(k_steps):
            # Get step embedding (conditions prediction on which step we're predicting)
            step_emb = self.step_embeddings(
                torch.tensor([step], device=s_context.device)
            ).expand(B, T, -1)  # [B, T, D]

            # Condition current state on step
            s_step = s_current + step_emb

            # Phase-Amplitude Projections
            phi_q = self.W_q_phase(s_step)  # [B, T, D]
            a_q = torch.sigmoid(self.W_q_amp(s_step))  # [B, T, D]
            phi_k = self.W_k_phase(s_step)  # [B, T, D]
            a_k = torch.sigmoid(self.W_k_amp(s_step))  # [B, T, D]
            v = self.W_v(s_step)  # [B, T, D]

            # Apply intent rotation to query phase
            phi_q_rotated = phi_q + theta_intent

            # Compute phase attention output
            phase_output = self._phase_attention(
                phi_q_rotated, a_q, phi_k, a_k, v
            )  # [B, T, D]

            # Predict delta through MLP
            delta_s = self.delta_mlp(phase_output)  # [B, T, D]
            delta_s = self.output_norm(delta_s)

            delta_list.append(delta_s)

            # Update state for next step (autoregressive)
            s_current = s_current + delta_s

            if return_intermediates:
                intermediate_states.append(s_current.clone())

        # Final predicted state
        s_pred = s_current

        if squeeze_output:
            s_pred = s_pred.squeeze(1)
            delta_list = [d.squeeze(1) for d in delta_list]

        if return_intermediates:
            return s_pred, delta_list, intermediate_states
        return s_pred, delta_list

    def _phase_attention(
        self,
        phi_q: torch.Tensor,
        a_q: torch.Tensor,
        phi_k: torch.Tensor,
        a_k: torch.Tensor,
        v: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute phase attention using complex phasors.

        Q = a_q × e^{iφ_q}   (Query phasor)
        K = a_k × e^{-iφ_k}  (Key phasor, conjugate)
        State = cumsum(K × V)
        Output = Re(Q × State) / normalizer

        Args:
            phi_q: Query phases [B, T, D]
            a_q: Query amplitudes [B, T, D]
            phi_k: Key phases [B, T, D]
            a_k: Key amplitudes [B, T, D]
            v: Values [B, T, D]

        Returns:
            output: Phase attention output [B, T, D]
        """
        # Form complex phasors
        # Note: torch.polar doesn't support bfloat16, cast if needed
        orig_dtype = phi_q.dtype
        if orig_dtype == torch.bfloat16:
            phi_q = phi_q.float()
            phi_k = phi_k.float()
            a_q = a_q.float()
            a_k = a_k.float()
            v = v.float()

        q_phasor = torch.polar(a_q, phi_q)       # a_q × e^{iφ_q}
        k_phasor = torch.polar(a_k, -phi_k)      # a_k × e^{-iφ_k} (conjugate)
        v_complex = torch.complex(v, torch.zeros_like(v))

        # O(n) state accumulation via cumsum
        kv = k_phasor * v_complex  # [B, T, D]
        state = torch.cumsum(kv, dim=1)  # [B, T, D]

        # Readout: Q × State
        qk_product = q_phasor * state  # [B, T, D]

        # Normalizer: amplitude-based
        normalizer = a_q * torch.cumsum(a_k, dim=1) + 1e-6  # [B, T, D]

        if self.cosine_mode == 'standard':
            # cos(φ_q - φ_k), range [-1, +1]
            output = qk_product.real / normalizer

        elif self.cosine_mode == 'shifted':
            # 1 + cos(φ_q - φ_k), range [0, 2]
            av_state = torch.cumsum(a_k * v, dim=1)
            shift_term = a_q * av_state
            cos_term = qk_product.real
            output = (shift_term + cos_term) / (normalizer * 2)

        elif self.cosine_mode == 'complex':
            # Full complex: uses both cos (real) and sin (imag)
            real_part = qk_product.real / normalizer  # [B, T, D]
            imag_part = qk_product.imag / normalizer  # [B, T, D]

            # Concatenate and project
            complex_concat = torch.cat([real_part, imag_part], dim=-1)  # [B, T, 2D]
            output = self.complex_to_real(complex_concat)  # [B, T, D]

        else:
            raise ValueError(f"Unknown cosine_mode: {self.cosine_mode}")

        # Cast back if needed
        if orig_dtype == torch.bfloat16:
            output = output.to(orig_dtype)

        return output

    def get_prediction_weight(self) -> torch.Tensor:
        """
        Get the main prediction weight matrix (for orthogonality loss).

        Returns:
            Weight matrix from first layer of delta_mlp
        """
        return self.delta_mlp[0].weight


class VrittiValidatedPredictor(PhaseJEPAPredictor):
    """
    Ontological State Predictor with Intellectual Plane (Vritti) validation.

    Uses the Intellectual Plane [17:22] as an epistemological gate to
    reject predictions where cognitive reliability is compromised:
    - Viparyaya (error/misconception) exceeds threshold
    - Vikalpa (imagination/fantasy) exceeds threshold for factual tasks

    Args:
        viparyaya_threshold: Max error before damping (default 0.4)
        vikalpa_threshold: Max imagination for factual (default 0.6)
        damping_factor: How much to dampen rejected predictions
        **kwargs: Passed to PhaseJEPAPredictor
    """

    # Vritti dimension indices within the 32D state
    VRITTI_START = 17
    PRAMANA_IDX = 17   # Valid cognition
    VIPARYAYA_IDX = 18  # Error/misconception
    VIKALPA_IDX = 19    # Imagination/fantasy
    NIDRA_IDX = 20      # Sleep/dormancy
    SMRITI_IDX = 21     # Memory

    def __init__(
        self,
        viparyaya_threshold: float = 0.4,
        vikalpa_threshold: float = 0.6,
        damping_factor: float = 0.5,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.viparyaya_threshold = viparyaya_threshold
        self.vikalpa_threshold = vikalpa_threshold
        self.damping_factor = damping_factor

    def forward(
        self,
        s_context: torch.Tensor,
        k_steps: Optional[int] = None,
        validate: bool = True,
        task_type: str = 'factual',
    ) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        """
        Predict with optional Vritti validation.

        Args:
            s_context: Context state
            k_steps: Prediction steps
            validate: Whether to apply Vritti validation
            task_type: 'factual' or 'creative' (affects Vikalpa threshold)

        Returns:
            s_pred: Predicted state
            delta_list: List of deltas
        """
        s_pred, delta_list = super().forward(s_context, k_steps)

        if validate:
            s_pred, delta_list = self._validate_vritti(
                s_context, s_pred, delta_list, task_type
            )

        return s_pred, delta_list

    def _validate_vritti(
        self,
        s_context: torch.Tensor,
        s_pred: torch.Tensor,
        delta_list: List[torch.Tensor],
        task_type: str,
    ) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        """
        Validate prediction against Vritti bounds.

        If Viparyaya (error) is too high, dampen the prediction.
        If Vikalpa (imagination) is too high for factual tasks, dampen.
        """
        # Extract Vritti dimensions from predicted state
        if s_pred.dim() == 2:
            vritti = s_pred[:, self.VRITTI_START:self.VRITTI_START + 5]
        else:
            vritti = s_pred[:, -1, self.VRITTI_START:self.VRITTI_START + 5]

        viparyaya = vritti[:, 1]  # Error dimension
        vikalpa = vritti[:, 2]    # Imagination dimension

        # Check thresholds
        error_violation = viparyaya > self.viparyaya_threshold
        vikalpa_threshold = (
            self.vikalpa_threshold if task_type == 'factual' else 1.0
        )
        imagination_violation = vikalpa > vikalpa_threshold

        # Apply damping if violations detected
        violation_mask = error_violation | imagination_violation

        if violation_mask.any():
            # Dampen deltas for violating samples
            dampened_deltas = []
            for delta in delta_list:
                if delta.dim() == 2:
                    mask = violation_mask.unsqueeze(-1)
                else:
                    mask = violation_mask.unsqueeze(1).unsqueeze(-1)
                dampened = torch.where(
                    mask,
                    delta * self.damping_factor,
                    delta
                )
                dampened_deltas.append(dampened)

            # Recompute prediction with dampened deltas
            s_pred = s_context + sum(dampened_deltas)
            delta_list = dampened_deltas

        return s_pred, delta_list

    def get_vritti_diagnostics(self, s_pred: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Get Vritti diagnostics for predicted state.

        Returns dict with Vritti component values and violation flags.
        """
        if s_pred.dim() == 2:
            vritti = s_pred[:, self.VRITTI_START:self.VRITTI_START + 5]
        else:
            vritti = s_pred[:, -1, self.VRITTI_START:self.VRITTI_START + 5]

        return {
            'pramana': vritti[:, 0],
            'viparyaya': vritti[:, 1],
            'vikalpa': vritti[:, 2],
            'nidra': vritti[:, 3],
            'smriti': vritti[:, 4],
            'error_violation': vritti[:, 1] > self.viparyaya_threshold,
            'imagination_violation': vritti[:, 2] > self.vikalpa_threshold,
        }
