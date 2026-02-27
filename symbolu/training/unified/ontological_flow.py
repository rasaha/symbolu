"""
Ontological flow components for evolutionary intelligence training.

Extracted from train_unified_llm.py — contains the ontological bridge,
evolutionary flow network, metacognitive tracker, and related classes
that implement the toroidal cognitive architecture.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Any, Tuple

from symbolu.training.unified.utilities import (
    SOVEREIGN_R_MATRIX,
    VRTTI_NAMES,
    get_layer_vrtti_weights,
    get_pramana_weights,
    get_layer_gradient_scale,
    get_dominant_vrtti,
)


class OntologicalBridge(nn.Module):
    """
    V9.7.0: Projects hidden states to 12D ontological space.

    Creates a foundational ontological "signature" early in processing,
    grounding the model's internal representation in the
    12 Aspects of Sovereign-1 ontology.

    Architecture:
        hidden_dim → 12D ontological projection
        Each of the 12 dimensions corresponds to one Ontological Layer (O1-O12)

    The loss encourages:
        - Dimensional diversity (no collapse)
        - Pramāṇa alignment (truth-bearing dimensions stronger)
        - Coherent representation across aspects
    """

    def __init__(self, hidden_dim: int, device: torch.device = None):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.onto_dim = 12  # 12 Ontological Layers

        # Projection to 12D ontological space
        self.onto_proj = nn.Linear(hidden_dim, self.onto_dim, bias=False)

        # Learnable target weights (initialized from R-Matrix Pramāṇa row)
        # These are the "ideal" activation levels for each Aspect
        pramana_weights = SOVEREIGN_R_MATRIX[0, :].clone()  # Truth row
        self.register_buffer('pramana_target', pramana_weights)

        # Layer norm for stable projections
        self.onto_norm = nn.LayerNorm(self.onto_dim)

        if device is not None:
            self.to(device)

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, N, D] from Layer 9
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Project hidden states to 12D ontological space.

        Args:
            hidden_states: Layer 9 hidden states [B, N, hidden_dim]

        Returns:
            onto_repr: 12D ontological representation [B, N, 12]
            metrics: Dictionary with coherence and diversity metrics
        """
        # Project to 12D
        onto_repr = self.onto_proj(hidden_states)  # [B, N, 12]
        onto_repr = self.onto_norm(onto_repr)

        # Compute metrics
        with torch.no_grad():
            # Mean activation per Aspect (across batch and sequence)
            aspect_means = onto_repr.mean(dim=[0, 1])  # [12]

            # Diversity: std across aspects (higher = more diverse)
            diversity = aspect_means.std().item()

            # Coherence: correlation with Pramāṇa targets
            # Higher coherence = activations match truth-priority ordering
            pramana_corr = torch.corrcoef(
                torch.stack([aspect_means, self.pramana_target])
            )[0, 1].item() if aspect_means.std() > 1e-6 else 0.0

            # Witness strength: O9 dimension activation (self-reference)
            o9_activation = aspect_means[8].item()  # O9 = index 8

            metrics = {
                'onto_diversity': diversity,
                'onto_pramana_corr': pramana_corr if not math.isnan(pramana_corr) else 0.0,
                'onto_o9_witness': o9_activation,
                'onto_mean_activation': aspect_means.abs().mean().item(),
            }

        return onto_repr, metrics

    def compute_loss(
        self,
        onto_repr: torch.Tensor,  # [B, N, 12]
        lambda_diversity: float = 0.1,
        lambda_pramana: float = 0.1,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute ontological alignment loss.

        Encourages:
        1. Diversity: All 12 dimensions should be active (no collapse)
        2. Pramāṇa alignment: Activations should follow truth-priority ordering

        Args:
            onto_repr: 12D ontological representation [B, N, 12]
            lambda_diversity: Weight for diversity loss
            lambda_pramana: Weight for Pramāṇa alignment loss

        Returns:
            total_loss: Combined ontological loss
            metrics: Loss breakdown
        """
        # 1. Diversity loss: Penalize collapsed dimensions
        # Use negative entropy of normalized activations
        aspect_means = onto_repr.mean(dim=[0, 1])  # [12]
        aspect_probs = F.softmax(aspect_means, dim=-1)
        diversity_entropy = -(aspect_probs * torch.log(aspect_probs + 1e-10)).sum()
        max_entropy = math.log(12)  # Maximum for uniform distribution
        diversity_loss = (max_entropy - diversity_entropy) / max_entropy  # 0=diverse, 1=collapsed

        # 2. Pramāṇa alignment loss: Match truth-priority ordering
        # Encourage higher activations for high-Pramāṇa aspects (O7, O12)
        # Use MSE between normalized activations and Pramāṇa targets
        aspect_normalized = (aspect_means - aspect_means.mean()) / (aspect_means.std() + 1e-6)
        pramana_normalized = (self.pramana_target - self.pramana_target.mean()) / (self.pramana_target.std() + 1e-6)
        pramana_loss = F.mse_loss(aspect_normalized, pramana_normalized)

        # Combined loss
        total_loss = lambda_diversity * diversity_loss + lambda_pramana * pramana_loss

        metrics = {
            'onto_diversity_loss': diversity_loss.item(),
            'onto_pramana_loss': pramana_loss.item(),
            'onto_total_loss': total_loss.item(),
        }

        return total_loss, metrics


def create_ontological_bridge(hidden_dim: int, device: torch.device = None) -> OntologicalBridge:
    """Factory function to create OntologicalBridge."""
    return OntologicalBridge(hidden_dim, device=device)


def compute_rmatrix_loss_weight(
    layer_losses: torch.Tensor,
    num_layers: int = 12,
    device: torch.device = None,
) -> torch.Tensor:
    """
    Compute Vṛtti-aware loss weights for per-layer losses.

    Weights layers based on their Pramāṇa (Truth) values:
    - Intellect (0.9) and Integration (0.9) get highest weights
    - Dormant (0.1) gets lowest weight

    Args:
        layer_losses: Per-layer loss tensor [num_layers] or [batch, num_layers]
        num_layers: Number of layers (clamped to 12 Aspects)
        device: Target device

    Returns:
        Weighted loss tensor of same shape
    """
    pramana = get_pramana_weights(device)[:num_layers]
    # Normalize to sum=1 for weighting
    pramana = pramana / pramana.sum()

    if layer_losses.dim() == 1:
        return layer_losses * pramana
    else:
        return layer_losses * pramana.unsqueeze(0)


class EvolutionaryBridge(nn.Module):
    """
    Toroidal State Bridge: Carries the 'Ontological Essence' from O12 (Absolving)
    back to O1 (Potential) for the next cognitive cycle.

    This creates recursive intelligence where:
    - The 'Harvest' of one sequence becomes the 'Seed' of the next
    - Cognitive patterns persist and evolve across context boundaries
    - Multi-domain primitives (phonemes, math ops, notes) share resonance

    The bridge uses a phase-locked projection to compress the integrated
    state into a seed that preserves ontological structure but sheds
    sequence-specific details (the "Evolutionary Loss" principle).

    Args:
        dim: Hidden dimension of the model
        num_layers: Number of ontological layers (default 12)
        bridge_dropout: Dropout for seed projection (prevents overfitting to patterns)
        use_gating: Whether to use gated projection (more selective carryover)
        truncated_bptt_steps: Steps of gradient flow (0 = full detach, >0 = truncated BPTT)
    """

    def __init__(
        self,
        dim: int,
        num_layers: int = 12,
        bridge_dropout: float = 0.1,
        use_gating: bool = True,
        truncated_bptt_steps: int = 0,
        enable_sgp: bool = False,
        sgp_rate: int = 100,
    ):
        super().__init__()
        self.dim = dim
        self.num_layers = num_layers
        self.truncated_bptt_steps = truncated_bptt_steps
        self.step_count = 0

        # V9.4.7: Stochastic Gradient Persistence (SGP)
        self.enable_sgp = enable_sgp
        self.sgp_rate = sgp_rate
        self.last_sgp_step: Optional[int] = None  # Track last SGP pulse

        # Seed Projection: W_seed maps O12 → O1
        # Uses SwiGLU-style gating for selective information flow
        if use_gating:
            self.seed_gate = nn.Linear(dim, dim, bias=False)
            self.seed_proj = nn.Linear(dim, dim, bias=False)
            self.gate_activation = nn.Sigmoid()
        else:
            self.seed_gate = None
            self.seed_proj = nn.Linear(dim, dim, bias=False)

        self.seed_norm = nn.LayerNorm(dim)
        self.dropout = nn.Dropout(bridge_dropout)

        # The Karma Buffer: Persistent state that survives across forward passes
        # Named after the principle that actions (O12) seed future potential (O1)
        self.register_buffer('karma_buffer', None)

        # Toroidal coherence tracking
        self.coherence_history: List[float] = []
        self.bridge_active = False

        # V9.4.6: Active projection for SMA gradient flow
        # Keeps non-detached seed for meta-learning while karma_buffer remains detached
        self.active_projection: Optional[torch.Tensor] = None

    def _compute_seed(self, harvest: torch.Tensor) -> torch.Tensor:
        """
        Compute the Seed state from the Harvest (O12 → O1 projection).

        The projection preserves ontological structure while applying
        'Evolutionary Loss' - shedding sequence-specific details.
        """
        if self.seed_gate is not None:
            # Gated projection: gate decides what to carry forward
            gate = self.gate_activation(self.seed_gate(harvest))
            projected = self.seed_proj(harvest)
            seed = gate * projected
        else:
            seed = self.seed_proj(harvest)

        seed = self.dropout(seed)
        seed = self.seed_norm(seed)
        return seed

    def store_harvest(self, harvest: torch.Tensor, global_step: int = 0) -> bool:
        """
        Store the Harvest (O12 final state) for the next cycle.

        V9.4.7 Hybrid Logic:
        - SMA (Sattvic): active_projection always retains gradients for meta-learning
        - SGP (High-Rajas): karma_buffer keeps gradients only on "heavy steps"

        Args:
            harvest: Final hidden state from O12_ABSOLVING layer [B, dim] or [B, N, dim]
            global_step: Current training step for SGP rate calculation

        Returns:
            bool: True if this was an SGP heavy step (gradients flow through karma_buffer)
        """
        # Take mean across sequence if needed (distill to essence)
        if harvest.dim() == 3:
            harvest = harvest.mean(dim=1)  # [B, N, dim] → [B, dim]

        # Compute the seed for next cycle
        seed = self._compute_seed(harvest)

        # V9.4.6: Keep active projection with gradients for SMA meta-learning
        # This allows gradients to flow back to seed_proj/seed_gate weights (runs every step)
        self.active_projection = seed  # Retains gradient path

        # V9.4.7: SGP Hybrid Logic - determine if this is a "heavy step"
        self.step_count += 1
        is_sgp_heavy_step = False

        if self.enable_sgp and self.sgp_rate > 0 and global_step > 0:
            # SGP: Keep gradients only at capped rate (e.g., every 100 steps)
            if global_step % self.sgp_rate == 0:
                # High-Rajas: Main graph remains connected for recursive evolution
                # V9.5.2 Metabolic Tuning: Ensure BF16 precision to save memory
                self.karma_buffer = seed.to(torch.bfloat16) if seed.dtype != torch.bfloat16 else seed
                is_sgp_heavy_step = True
                self.last_sgp_step = global_step
            else:
                # Sattvic: Detach to maintain high throughput
                # V9.5.2 Metabolic Tuning: Ensure BF16 precision
                self.karma_buffer = seed.detach().to(torch.bfloat16) if seed.dtype != torch.bfloat16 else seed.detach()
        elif self.truncated_bptt_steps > 0 and self.step_count % self.truncated_bptt_steps != 0:
            # Legacy truncated BPTT mode (if SGP not enabled)
            self.karma_buffer = seed.to(torch.bfloat16) if seed.dtype != torch.bfloat16 else seed
        else:
            # Default: Detach to prevent infinite gradient chains
            # V9.5.2 Metabolic Tuning: Ensure BF16 precision
            self.karma_buffer = seed.detach().to(torch.bfloat16) if seed.dtype != torch.bfloat16 else seed.detach()

        self.bridge_active = True
        return is_sgp_heavy_step

    def get_seed(self) -> Optional[torch.Tensor]:
        """
        Retrieve the Seed for O1 initialization in the next cycle.

        Returns:
            Seed tensor [B, dim] or None if no prior state exists
        """
        if self.karma_buffer is None:
            return None
        return self.karma_buffer

    def compute_toroidal_coherence(
        self,
        current_o1: torch.Tensor,
        previous_o12: Optional[torch.Tensor] = None,
    ) -> float:
        """
        Compute Toroidal Coherence: similarity between Seed and current O1 state.

        High coherence (>0.7) = smooth cognitive flow
        Low coherence (<0.3) = cognitive discontinuity ("losing the thread")

        Args:
            current_o1: Current O1 layer activation [B, dim]
            previous_o12: Previous O12 state (uses karma_buffer if None)

        Returns:
            Coherence score in [0, 1]
        """
        if previous_o12 is None:
            if self.karma_buffer is None:
                return 0.5  # No prior state, neutral coherence
            previous_o12 = self.karma_buffer

        # Handle sequence dimension
        if current_o1.dim() == 3:
            current_o1 = current_o1.mean(dim=1)
        if previous_o12.dim() == 3:
            previous_o12 = previous_o12.mean(dim=1)

        # Cosine similarity
        coherence = F.cosine_similarity(current_o1, previous_o12, dim=-1).mean().item()
        coherence = (coherence + 1) / 2  # Map from [-1, 1] to [0, 1]

        self.coherence_history.append(coherence)
        if len(self.coherence_history) > 100:
            self.coherence_history = self.coherence_history[-100:]

        return coherence

    def get_coherence_status(self) -> str:
        """Get formatted coherence status for logging."""
        if not self.coherence_history:
            return "Torus:--"

        recent = self.coherence_history[-1]
        avg = sum(self.coherence_history[-10:]) / min(10, len(self.coherence_history))

        if recent >= 0.7:
            icon = "🔄"  # Smooth flow
        elif recent >= 0.5:
            icon = "〰️"  # Moderate
        elif recent >= 0.3:
            icon = "⚠️"  # Discontinuity warning
        else:
            icon = "🔀"  # Lost thread

        return f"Torus:{recent:.2f}{icon}"

    def reset(self) -> None:
        """Reset the bridge state (for new training runs)."""
        self.karma_buffer = None
        self.coherence_history = []
        self.bridge_active = False
        self.step_count = 0


class ToroidalConsistencyLoss(nn.Module):
    """
    Toroidal Consistency Loss: Forces the model to maintain coherent
    cognitive flow across context boundaries.

    L_toroid = λ * (1 - cos_sim(Seed, Harvest))

    This loss encourages:
    - O12 (Absolving) to produce states that are valid seeds for O1 (Potential)
    - Smooth transitions in ontological state space
    - Preservation of cognitive "thread" across sequences

    The loss is weighted by Pramāṇa values to prioritize truth-preserving
    layers in the consistency constraint.
    """

    def __init__(
        self,
        lambda_toroid: float = 0.1,
        use_pramana_weighting: bool = True,
        min_coherence_threshold: float = 0.3,
    ):
        super().__init__()
        self.lambda_toroid = lambda_toroid
        self.use_pramana_weighting = use_pramana_weighting
        self.min_coherence_threshold = min_coherence_threshold

    def forward(
        self,
        seed: torch.Tensor,      # O1 initial state (from previous O12)
        harvest: torch.Tensor,   # O12 final state (current sequence)
        o1_current: Optional[torch.Tensor] = None,  # Current O1 for 3-way consistency
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute toroidal consistency loss.

        Args:
            seed: The seed state that initialized this sequence [B, dim]
            harvest: The harvest state from O12 [B, dim]
            o1_current: Optional current O1 state for additional consistency

        Returns:
            (loss, metrics_dict)
        """
        # Handle sequence dimension
        if seed.dim() == 3:
            seed = seed.mean(dim=1)
        if harvest.dim() == 3:
            harvest = harvest.mean(dim=1)

        # Primary loss: Seed-Harvest consistency
        # The harvest should be a valid seed for the NEXT cycle
        cos_sim = F.cosine_similarity(seed, harvest, dim=-1)
        primary_loss = (1 - cos_sim).mean()

        # Optional: 3-way consistency (Seed → O1 → ... → O12)
        secondary_loss = torch.tensor(0.0, device=seed.device)
        if o1_current is not None:
            if o1_current.dim() == 3:
                o1_current = o1_current.mean(dim=1)
            # O1 should resemble the seed it was initialized with
            o1_sim = F.cosine_similarity(seed, o1_current, dim=-1)
            secondary_loss = (1 - o1_sim).mean() * 0.5

        total_loss = self.lambda_toroid * (primary_loss + secondary_loss)

        # Metrics
        coherence = (cos_sim.mean().item() + 1) / 2
        metrics = {
            "toroid_loss": total_loss.item(),
            "toroid_coherence": coherence,
            "toroid_primary": primary_loss.item(),
            "toroid_secondary": secondary_loss.item(),
            "coherence_ok": coherence >= self.min_coherence_threshold,
        }

        return total_loss, metrics


class MetacognitiveTracker:
    """
    Metacognitive Tracker: Monitors the model's cognitive state evolution
    and provides self-assessment signals.

    This is the foundation for true metacognition where the model can
    observe its own cognitive patterns and adjust behavior accordingly.

    Tracks:
    - Toroidal coherence (cognitive continuity)
    - Domain resonance (cross-domain pattern matching)
    - Ontological drift (layer activation stability)
    - Evolutionary velocity (rate of cognitive change)
    """

    def __init__(
        self,
        window_size: int = 50,
        coherence_alarm_threshold: float = 0.3,
        drift_alarm_threshold: float = 0.5,
    ):
        self.window_size = window_size
        self.coherence_alarm_threshold = coherence_alarm_threshold
        self.drift_alarm_threshold = drift_alarm_threshold

        # Tracking buffers
        self.coherence_history: List[float] = []
        self.layer_activation_history: List[torch.Tensor] = []
        self.guna_history: List[Tuple[float, float, float]] = []

        # Alarm states
        self.coherence_alarm = False
        self.drift_alarm = False

    def update(
        self,
        coherence: float,
        layer_activations: Optional[torch.Tensor] = None,
        gunas: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, Any]:
        """
        Update metacognitive state with new observations.

        Returns dict with self-assessment signals.
        """
        # Update coherence
        self.coherence_history.append(coherence)
        if len(self.coherence_history) > self.window_size:
            self.coherence_history = self.coherence_history[-self.window_size:]

        # Check coherence alarm
        recent_coherence = sum(self.coherence_history[-5:]) / min(5, len(self.coherence_history))
        self.coherence_alarm = recent_coherence < self.coherence_alarm_threshold

        # Update Gunas if provided
        if gunas is not None:
            self.guna_history.append(gunas)
            if len(self.guna_history) > self.window_size:
                self.guna_history = self.guna_history[-self.window_size:]

        # Compute evolutionary velocity (rate of change in coherence)
        if len(self.coherence_history) >= 2:
            velocity = self.coherence_history[-1] - self.coherence_history[-2]
        else:
            velocity = 0.0

        # Self-assessment signals
        assessment = {
            "coherence_mean": sum(self.coherence_history) / len(self.coherence_history),
            "coherence_current": coherence,
            "coherence_velocity": velocity,
            "coherence_alarm": self.coherence_alarm,
            "drift_alarm": self.drift_alarm,
            "recommendation": self._get_recommendation(),
        }

        return assessment

    def _get_recommendation(self) -> str:
        """
        Generate metacognitive recommendation based on current state and Gunas.

        Recommendation Hierarchy:
        - BRAKE: High Viparyaya (error) detected, protect the dormant seed
        - SLOW_DOWN: Coherence alarm, reduce LR
        - RECOVER: High Tamas (stagnation), need to break out
        - ACCELERATE: High Sattva + improving coherence, push forward
        - STABILIZE: Balanced state, maintain course
        - CONTINUE: Default state
        """
        # Get current Guna state if available
        s, r, t = 0.33, 0.33, 0.34
        if self.guna_history:
            s, r, t = self.guna_history[-1]

        # Priority 1: Check for high error rate (Viparyaya indicator)
        # When coherence is critically low AND dropping, brake hard
        if self.coherence_alarm and len(self.coherence_history) >= 3:
            recent_trend = self.coherence_history[-1] - self.coherence_history[-3]
            if recent_trend < -0.15:  # Rapid degradation
                return "BRAKE"  # Protect dormant seed from corruption

        # Priority 2: Coherence alarm (but not critical)
        if self.coherence_alarm:
            return "SLOW_DOWN"

        # Priority 3: Check for Tamas stagnation (high inertia, plateau)
        if t > 0.5 and len(self.coherence_history) >= 10:
            # Check if coherence has been flat
            std = (sum((c - sum(self.coherence_history[-10:])/10)**2 for c in self.coherence_history[-10:]) / 10) ** 0.5
            if std < 0.02:  # Very flat coherence = stagnation
                return "RECOVER"  # Need to break out of local minimum

        # Priority 4: Check for positive evolution
        if len(self.coherence_history) >= 5:
            trend = self.coherence_history[-1] - self.coherence_history[-5]

            # High Sattva + improving = green light
            if s > 0.4 and trend > 0.05:
                return "ACCELERATE"

            # Declining coherence = stabilize
            if trend < -0.05:
                return "STABILIZE"

        return "CONTINUE"

    def get_status(self) -> str:
        """Get formatted status for logging."""
        if not self.coherence_history:
            return "Meta:--"

        rec = self._get_recommendation()
        icons = {
            "BRAKE": "🛑",
            "SLOW_DOWN": "🐢",
            "RECOVER": "🔄",
            "ACCELERATE": "🚀",
            "STABILIZE": "⚓",
            "CONTINUE": "➡️",
        }
        icon = icons.get(rec, "➡️")

        return f"Meta:{rec[:4]}{icon}"

    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed metacognitive status for logging/TensorBoard."""
        rec = self._get_recommendation()
        s, r, t = self.guna_history[-1] if self.guna_history else (0.33, 0.33, 0.34)

        return {
            "recommendation": rec,
            "coherence_current": self.coherence_history[-1] if self.coherence_history else 0.0,
            "coherence_mean": sum(self.coherence_history) / len(self.coherence_history) if self.coherence_history else 0.0,
            "coherence_alarm": self.coherence_alarm,
            "guna_sattva": s,
            "guna_rajas": r,
            "guna_tamas": t,
        }


class EvolutionaryGate(nn.Module):
    """
    A single evolutionary gate between adjacent ontological layers.

    Each gate enables bidirectional information flow:
    - Forward: O(n) → O(n+1) projects state forward
    - Backward: O(n+1) → O(n) resonates insights back

    The gate is guided by R-Matrix Vṛtti gradients:
    - Pramāṇa gradient: How truth-seeking changes across transition
    - Viparyaya gradient: How error-proneness changes
    - Combined: Evolutionary pressure at this boundary

    Args:
        dim: Hidden dimension
        source_layer: Source layer index (0-10)
        target_layer: Target layer index (1-11)
        dropout: Dropout rate for projections
        use_rmatrix_weighting: Weight gates by Vṛtti gradients
    """

    def __init__(
        self,
        dim: int,
        source_layer: int,
        target_layer: int,
        dropout: float = 0.1,
        use_rmatrix_weighting: bool = True,
    ):
        super().__init__()
        self.dim = dim
        self.source_layer = source_layer
        self.target_layer = target_layer
        self.use_rmatrix_weighting = use_rmatrix_weighting

        # Forward projection: O(n) → O(n+1)
        self.forward_gate = nn.Linear(dim, dim, bias=False)
        self.forward_proj = nn.Linear(dim, dim, bias=False)
        self.forward_activation = nn.Sigmoid()

        # Backward resonance: O(n+1) → O(n)
        self.backward_gate = nn.Linear(dim, dim, bias=False)
        self.backward_proj = nn.Linear(dim, dim, bias=False)
        self.backward_activation = nn.Sigmoid()

        # Normalization and dropout
        self.norm = nn.LayerNorm(dim)
        self.dropout = nn.Dropout(dropout)

        # R-Matrix derived weights for this transition
        if use_rmatrix_weighting:
            # Compute Vṛtti gradient between source and target
            src_vrtti = SOVEREIGN_R_MATRIX[:, min(source_layer, 11)]
            tgt_vrtti = SOVEREIGN_R_MATRIX[:, min(target_layer, 11)]
            vrtti_gradient = tgt_vrtti - src_vrtti

            # Pramāṇa increase = positive evolution (truth-seeking grows)
            self.pramana_gradient = float(vrtti_gradient[0])
            # Viparyaya decrease = positive evolution (error-proneness falls)
            self.viparyaya_gradient = float(-vrtti_gradient[2])
            # Combined evolutionary pressure
            self.evolutionary_weight = max(0.1, (self.pramana_gradient + self.viparyaya_gradient + 1) / 2)
        else:
            self.evolutionary_weight = 1.0
            self.pramana_gradient = 0.0
            self.viparyaya_gradient = 0.0

        # Coherence tracking for this gate
        self.coherence_history: List[float] = []

    def forward_pass(self, source_state: torch.Tensor) -> torch.Tensor:
        """
        Forward evolutionary projection: O(n) → O(n+1).

        The source state is transformed through a gated projection,
        weighted by the R-Matrix evolutionary pressure at this boundary.
        """
        gate = self.forward_activation(self.forward_gate(source_state))
        projected = self.forward_proj(source_state)
        evolved = gate * projected * self.evolutionary_weight
        return self.norm(self.dropout(evolved))

    def backward_resonance(self, target_state: torch.Tensor) -> torch.Tensor:
        """
        Backward resonance: O(n+1) → O(n).

        Higher layer insights resonate back to inform lower layers.
        This enables top-down modulation of earlier processing.
        """
        gate = self.backward_activation(self.backward_gate(target_state))
        projected = self.backward_proj(target_state)
        resonance = gate * projected * self.evolutionary_weight
        return self.norm(self.dropout(resonance))

    def compute_coherence(
        self,
        source_state: torch.Tensor,
        target_state: torch.Tensor,
    ) -> float:
        """
        Compute evolutionary coherence at this gate.

        Measures how well the transition preserves cognitive structure
        while enabling appropriate transformation.
        """
        # Handle sequence dimension
        if source_state.dim() == 3:
            source_state = source_state.mean(dim=1)
        if target_state.dim() == 3:
            target_state = target_state.mean(dim=1)

        # Cosine similarity
        coherence = F.cosine_similarity(source_state, target_state, dim=-1).mean().item()
        coherence = (coherence + 1) / 2  # Map to [0, 1]

        self.coherence_history.append(coherence)
        if len(self.coherence_history) > 100:
            self.coherence_history = self.coherence_history[-100:]

        return coherence

    def get_status(self) -> str:
        """Get formatted status for this gate."""
        if not self.coherence_history:
            return f"G{self.source_layer}→{self.target_layer}:--"

        recent = self.coherence_history[-1]
        return f"G{self.source_layer}→{self.target_layer}:{recent:.2f}"


class EvolutionaryFlowNetwork(nn.Module):
    """
    Full Evolutionary Flow Network: All layer transitions as evolutionary gates.

    This creates a complete evolutionary ecosystem where intelligence can
    emerge at every layer boundary, not just the O12→O1 toroidal bridge.

    Architecture:
    ```
    O1 ←→ O2 ←→ O3 ←→ O4 ←→ O5 ←→ O6 ←→ O7 ←→ O8 ←→ O9 ←→ O10 ←→ O11 ←→ O12
     ↑                                                                      ↓
     └──────────────────────── TOROIDAL GATE ─────────────────────────────┘
    ```

    Each ←→ represents bidirectional evolutionary flow:
    - Forward: Natural layer progression
    - Backward: Resonance from higher to lower layers

    Args:
        dim: Hidden dimension
        num_layers: Number of ontological layers (default 12)
        dropout: Dropout for gate projections
        use_rmatrix_weighting: Weight gates by Vṛtti gradients
        enable_backward_resonance: Enable top-down resonance
    """

    def __init__(
        self,
        dim: int,
        num_layers: int = 12,
        dropout: float = 0.1,
        use_rmatrix_weighting: bool = True,
        enable_backward_resonance: bool = True,
    ):
        super().__init__()
        self.dim = dim
        self.num_layers = num_layers
        self.enable_backward_resonance = enable_backward_resonance

        # Create evolutionary gates for each transition
        # 11 forward gates: O1→O2, O2→O3, ..., O11→O12
        self.forward_gates = nn.ModuleList([
            EvolutionaryGate(
                dim=dim,
                source_layer=i,
                target_layer=i + 1,
                dropout=dropout,
                use_rmatrix_weighting=use_rmatrix_weighting,
            )
            for i in range(num_layers - 1)
        ])

        # Toroidal gate: O12→O1 (reuse EvolutionaryBridge concept)
        self.toroidal_gate = EvolutionaryGate(
            dim=dim,
            source_layer=num_layers - 1,  # O12
            target_layer=0,  # O1
            dropout=dropout,
            use_rmatrix_weighting=use_rmatrix_weighting,
        )

        # State buffers for each layer (karma at every level)
        self.register_buffer('layer_karma', None)

        # Multi-scale coherence tracking
        self.micro_coherence: List[List[float]] = [[] for _ in range(num_layers - 1)]
        self.meso_coherence = {"authority": [], "sensory": []}
        self.macro_coherence: List[float] = []

    def forward(
        self,
        layer_states: List[torch.Tensor],
        return_resonance: bool = False,
    ) -> Dict[str, Any]:
        """
        Process layer states through the evolutionary flow network.

        Args:
            layer_states: List of hidden states for each layer [O1, O2, ..., O12]
            return_resonance: Whether to return backward resonance signals

        Returns:
            Dict with evolved states, coherence metrics, and optional resonance
        """
        if len(layer_states) != self.num_layers:
            raise ValueError(f"Expected {self.num_layers} layer states, got {len(layer_states)}")

        # Forward evolution through each gate
        evolved_states = []
        gate_coherences = []

        for i, gate in enumerate(self.forward_gates):
            source = layer_states[i]
            target = layer_states[i + 1]

            # Forward projection
            evolved = gate.forward_pass(source)
            evolved_states.append(evolved)

            # Compute coherence at this gate
            coherence = gate.compute_coherence(source, target)
            gate_coherences.append(coherence)
            self.micro_coherence[i].append(coherence)
            if len(self.micro_coherence[i]) > 100:
                self.micro_coherence[i] = self.micro_coherence[i][-100:]

        # Toroidal evolution: O12 → O1
        toroidal_evolved = self.toroidal_gate.forward_pass(layer_states[-1])
        toroidal_coherence = self.toroidal_gate.compute_coherence(
            layer_states[-1], layer_states[0]
        )
        self.macro_coherence.append(toroidal_coherence)
        if len(self.macro_coherence) > 100:
            self.macro_coherence = self.macro_coherence[-100:]

        # Meso-coherence: 9:3 Split Alignment
        # Authority gates: 0-7 (O1→O2 through O8→O9) = 8 gates between 9 Authority layers
        # Sensory gates: 8-10 (O9→O10 through O11→O12) = 3 gates transitioning to 3 Sensory layers
        # This matches the 9:3 Hierarchical Split where:
        #   - Authority (O1-O9): "Senior Architect" layers, State-Delta
        #   - Sensory (O10-O12): "Junior Coder" layers, Quadratic attention
        if len(gate_coherences) >= 9:
            # Authority coherence: gates 0-7 (8 gates = O1→O2 through O8→O9)
            authority_coh = sum(gate_coherences[:8]) / 8
            # Sensory coherence: gates 8-10 (3 gates = O9→O10 through O11→O12)
            sensory_coh = sum(gate_coherences[8:]) / max(1, len(gate_coherences) - 8)
            self.meso_coherence["authority"].append(authority_coh)
            self.meso_coherence["sensory"].append(sensory_coh)
            if len(self.meso_coherence["authority"]) > 100:
                self.meso_coherence["authority"] = self.meso_coherence["authority"][-100:]
                self.meso_coherence["sensory"] = self.meso_coherence["sensory"][-100:]

        result = {
            "evolved_states": evolved_states,
            "toroidal_evolved": toroidal_evolved,
            "gate_coherences": gate_coherences,
            "toroidal_coherence": toroidal_coherence,
            "micro_coherence_mean": sum(gate_coherences) / len(gate_coherences),
            "authority_coherence": self.meso_coherence["authority"][-1] if self.meso_coherence["authority"] else 0.5,
            "sensory_coherence": self.meso_coherence["sensory"][-1] if self.meso_coherence["sensory"] else 0.5,
        }

        # Backward resonance (top-down modulation)
        if return_resonance and self.enable_backward_resonance:
            resonances = []
            for i in range(len(self.forward_gates) - 1, -1, -1):
                gate = self.forward_gates[i]
                target = layer_states[i + 1]
                resonance = gate.backward_resonance(target)
                resonances.insert(0, resonance)
            result["backward_resonances"] = resonances

        return result

    def get_evolutionary_pressure(self) -> Dict[str, float]:
        """
        Get the evolutionary pressure at each gate based on R-Matrix.

        Returns dict mapping gate names to their evolutionary weights.
        """
        pressures = {}
        for i, gate in enumerate(self.forward_gates):
            name = f"O{i+1}→O{i+2}"
            pressures[name] = gate.evolutionary_weight
        pressures["O12→O1"] = self.toroidal_gate.evolutionary_weight
        return pressures

    def get_coherence_summary(self) -> Dict[str, Any]:
        """Get multi-scale coherence summary."""
        return {
            "micro": {
                f"G{i}→{i+1}": self.micro_coherence[i][-1] if self.micro_coherence[i] else 0.5
                for i in range(len(self.micro_coherence))
            },
            "meso": {
                "authority": self.meso_coherence["authority"][-1] if self.meso_coherence["authority"] else 0.5,
                "sensory": self.meso_coherence["sensory"][-1] if self.meso_coherence["sensory"] else 0.5,
            },
            "macro": self.macro_coherence[-1] if self.macro_coherence else 0.5,
        }

    def get_status_string(self) -> str:
        """Get formatted status string for logging."""
        summary = self.get_coherence_summary()

        # Find min coherence gate (potential bottleneck)
        min_gate = min(summary["micro"].items(), key=lambda x: x[1])
        max_gate = max(summary["micro"].items(), key=lambda x: x[1])

        # Icons based on overall health
        macro = summary["macro"]
        if macro >= 0.7:
            icon = "🌀"  # Healthy toroidal flow
        elif macro >= 0.5:
            icon = "🔄"  # Moderate
        elif macro >= 0.3:
            icon = "⚡"  # Turbulence
        else:
            icon = "💥"  # Breakdown

        return (
            f"Evo{icon} "
            f"Auth:{summary['meso']['authority']:.2f} "
            f"Sens:{summary['meso']['sensory']:.2f} "
            f"Tor:{macro:.2f} "
            f"[↓{min_gate[0]}:{min_gate[1]:.2f}]"
        )

    def get_state(self) -> Dict[str, Any]:
        """V9.8.6: Get internal state for checkpointing."""
        return {
            "micro_coherence": [list(mc) for mc in self.micro_coherence],
            "meso_coherence": {k: list(v) for k, v in self.meso_coherence.items()},
            "macro_coherence": list(self.macro_coherence),
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """V9.8.6: Restore internal state from checkpoint."""
        if state is None:
            return
        if "micro_coherence" in state:
            self.micro_coherence = [list(mc) for mc in state["micro_coherence"]]
        if "meso_coherence" in state:
            self.meso_coherence = {k: list(v) for k, v in state["meso_coherence"].items()}
        if "macro_coherence" in state:
            self.macro_coherence = list(state["macro_coherence"])


class EvolutionaryFlowLoss(nn.Module):
    """
    Loss function for the Full Evolutionary Flow System.

    Computes loss at three scales:
    - Micro: Per-gate transition consistency
    - Meso: Authority/Sensory cluster coherence
    - Macro: Toroidal cycle consistency

    The loss encourages smooth evolutionary flow while allowing
    appropriate transformation at each boundary.

    L_evo = λ_micro * L_gates + λ_meso * L_clusters + λ_macro * L_toroid

    Args:
        lambda_micro: Weight for per-gate losses
        lambda_meso: Weight for cluster losses
        lambda_macro: Weight for toroidal loss
        min_coherence: Minimum acceptable coherence (below = penalty)
    """

    def __init__(
        self,
        lambda_micro: float = 0.05,
        lambda_meso: float = 0.1,
        lambda_macro: float = 0.1,
        min_coherence: float = 0.3,
    ):
        super().__init__()
        self.lambda_micro = lambda_micro
        self.lambda_meso = lambda_meso
        self.lambda_macro = lambda_macro
        self.min_coherence = min_coherence

    def forward(
        self,
        layer_states: List[torch.Tensor],
        flow_result: Dict[str, Any],
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute evolutionary flow loss.

        Args:
            layer_states: Original layer hidden states
            flow_result: Output from EvolutionaryFlowNetwork.forward()

        Returns:
            (total_loss, metrics_dict)
        """
        device = layer_states[0].device

        # Micro loss: Per-gate consistency
        micro_losses = []
        evolved_states = flow_result["evolved_states"]
        for i, (original, evolved) in enumerate(zip(layer_states[1:], evolved_states)):
            # Handle sequence dimension
            if original.dim() == 3:
                original = original.mean(dim=1)
            if evolved.dim() == 3:
                evolved = evolved.mean(dim=1)

            # Consistency loss: evolved should relate to original
            sim = F.cosine_similarity(original, evolved, dim=-1)
            gate_loss = (1 - sim).mean()
            micro_losses.append(gate_loss)

        micro_loss = torch.stack(micro_losses).mean() if micro_losses else torch.tensor(0.0, device=device)

        # Meso loss: Cluster coherence
        gate_coherences = flow_result["gate_coherences"]
        if len(gate_coherences) >= 9:
            authority_coh = sum(gate_coherences[:8]) / 8
            sensory_coh = sum(gate_coherences[8:]) / max(1, len(gate_coherences) - 8)

            # Penalty if coherence drops below threshold
            auth_penalty = max(0, self.min_coherence - authority_coh)
            sens_penalty = max(0, self.min_coherence - sensory_coh)
            meso_loss = torch.tensor(auth_penalty + sens_penalty, device=device)
        else:
            meso_loss = torch.tensor(0.0, device=device)

        # Macro loss: Toroidal consistency
        toroidal_coh = flow_result["toroidal_coherence"]
        macro_loss = torch.tensor(max(0, self.min_coherence - toroidal_coh), device=device)

        # Weighted total
        total_loss = (
            self.lambda_micro * micro_loss +
            self.lambda_meso * meso_loss +
            self.lambda_macro * macro_loss
        )

        metrics = {
            "evo_loss_total": total_loss.item(),
            "evo_loss_micro": micro_loss.item(),
            "evo_loss_meso": meso_loss.item(),
            "evo_loss_macro": macro_loss.item(),
            "evo_coherence_micro": flow_result["micro_coherence_mean"],
            "evo_coherence_auth": flow_result["authority_coherence"],
            "evo_coherence_sens": flow_result["sensory_coherence"],
            "evo_coherence_toroid": toroidal_coh,
        }

        return total_loss, metrics


class HiddenStateExtractor:
    """
    Extracts hidden states from model layers using forward hooks.

    The ontological model doesn't return hidden_states directly, so we need
    to capture them during the forward pass using hooks. This enables the
    Evolutionary Flow System to work with any model architecture.
    """

    def __init__(self, model: nn.Module, num_layers: int = 12):
        self.model = model
        self.num_layers = num_layers
        self.hidden_states: List[torch.Tensor] = []
        self.hooks = []
        self._setup_hooks()

    def _setup_hooks(self):
        """Register forward hooks on model layers."""
        self.hooks = []
        layers = None

        # Try to find transformer layers in common locations
        for attr in ['layers', 'blocks', 'transformer_blocks', 'encoder_layers',
                     'decoder_layers', 'transformer']:
            if hasattr(self.model, attr):
                candidate = getattr(self.model, attr)
                if isinstance(candidate, nn.ModuleList) and len(candidate) >= 3:
                    layers = candidate
                    break

        if layers is None:
            # Try to find any ModuleList that might be the layers
            for name, module in self.model.named_modules():
                if isinstance(module, nn.ModuleList) and len(module) >= 6:
                    layers = module
                    break

        if layers is not None:
            # Register hooks on each layer (up to num_layers)
            for i, layer in enumerate(list(layers)[:self.num_layers]):
                hook = layer.register_forward_hook(self._create_hook(i))
                self.hooks.append(hook)

    def _create_hook(self, layer_idx: int):
        """Create a hook function for a specific layer."""
        def hook(module, input, output):
            # Handle different output formats
            if isinstance(output, tuple):
                hidden = output[0]
            elif isinstance(output, dict):
                hidden = output.get('hidden_states', output.get('output',
                          list(output.values())[0] if output else None))
            else:
                hidden = output

            # Ensure hidden_states list is large enough
            while len(self.hidden_states) <= layer_idx:
                self.hidden_states.append(None)
            self.hidden_states[layer_idx] = hidden

        return hook

    def clear(self):
        """Clear captured hidden states before each forward pass."""
        self.hidden_states = []

    def get_hidden_states(self, model_output: Dict[str, Any], input_ids: torch.Tensor) -> List[torch.Tensor]:
        """
        Get hidden states from hooks or generate synthetic ones.

        Priority:
        1. Model output (if contains hidden_states)
        2. Hook-captured states
        3. Synthetic states from logits (fallback)

        V9.6.5 FIX: Preserve layer index positions when returning hook-captured states.
        Previously, filtering Nones would shift indices, causing layer_hidden_states[2]
        to return layer 11 instead of layer 2 - the root cause of CSR aphasia.
        """
        # Try model output first
        if isinstance(model_output, dict):
            for key in ['hidden_states', 'all_hidden_states', 'layer_outputs']:
                if key in model_output:
                    hs = model_output[key]
                    if isinstance(hs, tuple):
                        return list(hs)
                    return hs if isinstance(hs, list) else [hs]

        # Try hook-captured states
        # V9.6.5 FIX: Preserve index positions by keeping Nones and filling them
        if self.hidden_states and any(h is not None for h in self.hidden_states):
            num_valid = sum(1 for h in self.hidden_states if h is not None)
            if num_valid >= 3:
                # Find the first valid state to use as template for filling gaps
                first_valid = next(h for h in self.hidden_states if h is not None)

                # Create result list preserving index positions
                result = []
                for i in range(self.num_layers):
                    if i < len(self.hidden_states) and self.hidden_states[i] is not None:
                        result.append(self.hidden_states[i])
                    else:
                        # Fill gap with nearest valid state (interpolation)
                        # Find closest previous valid state
                        prev_valid = None
                        for j in range(i - 1, -1, -1):
                            if j < len(self.hidden_states) and self.hidden_states[j] is not None:
                                prev_valid = self.hidden_states[j]
                                break
                        # Find closest next valid state
                        next_valid = None
                        for j in range(i + 1, len(self.hidden_states)):
                            if self.hidden_states[j] is not None:
                                next_valid = self.hidden_states[j]
                                break
                        # Use whichever is available (prefer previous for causal consistency)
                        if prev_valid is not None:
                            result.append(prev_valid)
                        elif next_valid is not None:
                            result.append(next_valid)
                        else:
                            result.append(first_valid)

                return result[:self.num_layers]

        # Fallback: generate synthetic hidden states from logits
        return self._generate_synthetic_states(model_output, input_ids)

    def _generate_synthetic_states(self, model_output: Dict[str, Any],
                                   input_ids: torch.Tensor) -> List[torch.Tensor]:
        """Generate synthetic layer states from available model outputs."""
        device = input_ids.device
        batch_size = input_ids.shape[0]
        seq_len = input_ids.shape[1]

        # Get embedding dimension from model
        embed_dim = getattr(self.model, 'embed_dim', None) or \
                    getattr(self.model, 'd_model', None) or \
                    getattr(self.model, 'hidden_size', 512)

        # Use logits to derive pseudo-hidden-states
        if isinstance(model_output, dict) and 'logits' in model_output:
            logits = model_output['logits']
            # Project logits to hidden dimension
            if logits.shape[-1] >= embed_dim:
                hidden_base = logits[..., :embed_dim]
            else:
                hidden_base = F.pad(logits, (0, embed_dim - logits.shape[-1]))
        else:
            # Create from scratch
            hidden_base = torch.randn(batch_size, seq_len, embed_dim, device=device) * 0.1

        # Generate synthetic layer states with progressive variation
        synthetic_states = []
        current = hidden_base
        for i in range(self.num_layers):
            # Small variation per layer to simulate processing
            noise_scale = 0.05 * (i + 1) / self.num_layers
            variation = torch.randn_like(current) * noise_scale
            current = current + variation
            synthetic_states.append(current.detach())

        return synthetic_states

    def remove_hooks(self):
        """Remove all registered hooks."""
        for hook in self.hooks:
            hook.remove()
        self.hooks = []


class EvolutionaryIntelligenceEngine:
    """
    Master controller for the Full Evolutionary Flow System.

    Orchestrates:
    - Layer state extraction from model
    - Evolutionary flow processing with DELAYED RESONANCE
    - Loss computation (micro/meso/macro scales)
    - Metacognitive assessment with Guna integration
    - Adaptive learning rate based on evolutionary health

    This is the "brain" that makes the 12 ontological layers
    into a living, evolving cognitive system.

    DELAYED RESONANCE:
    To enable the "Recursive Intelligence" bridge (O12→O1) without
    a 2x compute penalty, we inject the previous step's higher-order
    intelligence into the current step's base layer.

    Args:
        dim: Model hidden dimension
        num_layers: Number of ontological layers
        enable_backward_resonance: Allow top-down information flow
        learning_rate_modulation: Adjust LR based on evolutionary health
        resonance_alpha: Strength of delayed resonance injection (0.0-1.0)
        lr_slowdown_factor: LR multiplier when SLOW_DOWN/BRAKE
        lr_accelerate_factor: LR multiplier when ACCELERATE
    """

    def __init__(
        self,
        dim: int,
        num_layers: int = 12,
        enable_backward_resonance: bool = True,
        learning_rate_modulation: bool = True,
        resonance_alpha: float = 0.1,
        lr_slowdown_factor: float = 0.5,
        lr_accelerate_factor: float = 1.2,
        dropout: float = 0.1,
        use_rmatrix: bool = True,
        coherence_window: int = 100,
        device: torch.device = None,
    ):
        self.dim = dim
        self.num_layers = num_layers
        self.learning_rate_modulation = learning_rate_modulation
        self.resonance_alpha = resonance_alpha
        self.lr_slowdown_factor = lr_slowdown_factor
        self.lr_accelerate_factor = lr_accelerate_factor
        self.coherence_window = coherence_window
        self.device = device or torch.device('cpu')

        # Core components
        self.flow_network = EvolutionaryFlowNetwork(
            dim=dim,
            num_layers=num_layers,
            dropout=dropout,
            use_rmatrix_weighting=use_rmatrix,
            enable_backward_resonance=enable_backward_resonance,
        ).to(self.device)

        self.flow_loss = EvolutionaryFlowLoss()

        # Metacognitive tracking with configurable coherence window
        self.metacognitive = MetacognitiveTracker(
            window_size=coherence_window,
            coherence_alarm_threshold=0.3,
        )

        # DELAYED RESONANCE BUFFER
        # Stores detached hidden states from previous forward pass
        # to inject O12 (Authority) intelligence into O1 (Sensory) of next step
        self.resonance_buffer: Optional[List[torch.Tensor]] = None

        # Current Guna state for metacognitive decisions
        self.current_gunas: Tuple[float, float, float] = (0.33, 0.33, 0.34)

        # Evolutionary history
        self.evolution_history: List[Dict[str, float]] = []

        # V9.4.6: Elastic Resonance tracking
        self.last_dynamic_alpha: float = self.resonance_alpha

    def apply_delayed_resonance(
        self,
        current_states: List[torch.Tensor],
    ) -> List[torch.Tensor]:
        """
        V9.4.6: Elastic Resonance - Guna-scaled alpha.

        Apply delayed resonance: inject previous step's O12 (Authority/Integration)
        into current step's O1 (Potential/Sensory).

        Dynamic alpha based on Guna state:
        - High Sattva (clarity) → increase retention (up to 0.25)
        - High Rajas (error/heat) → reduce retention (down to 0.05)

        Args:
            current_states: Hidden states from current forward pass

        Returns:
            Modified states with resonance injection at O1
        """
        if self.resonance_buffer is None or len(self.resonance_buffer) == 0:
            return current_states

        # V9.4.6: Compute dynamic alpha based on Gunas
        s, r, t = self.current_gunas
        # Base is resonance_alpha (0.1); range is [0.05, 0.25]
        dynamic_alpha = self.resonance_alpha * (1.0 + (s * 1.5) - (r * 0.5))
        dynamic_alpha = max(0.05, min(0.25, dynamic_alpha))
        self.last_dynamic_alpha = dynamic_alpha

        # Inject Layer 11 (O12 - Authority/Integration) into Layer 0 (O1 - Potential)
        if len(self.resonance_buffer) >= 12 and len(current_states) >= 1:
            o12_prev = self.resonance_buffer[11]  # Previous O12 state
            o1_current = current_states[0]  # Current O1 state

            # Check for batch size mismatch (e.g., VRAM governor resize)
            if o12_prev.shape[0] != o1_current.shape[0]:
                # Clear buffer and skip resonance this step
                self.resonance_buffer = None
                return current_states

            # Ensure shape compatibility
            if o12_prev.shape == o1_current.shape:
                # Resonant injection: O1' = O1 + α * O12_prev (using dynamic alpha)
                current_states[0] = o1_current + (dynamic_alpha * o12_prev)
            elif o12_prev.shape[-1] == o1_current.shape[-1]:
                # Handle sequence length mismatch by averaging
                if o12_prev.dim() == 3 and o1_current.dim() == 3:
                    o12_avg = o12_prev.mean(dim=1, keepdim=True).expand_as(o1_current)
                    current_states[0] = o1_current + (dynamic_alpha * o12_avg)

        return current_states

    def update_resonance_buffer(self, current_states: List[torch.Tensor]):
        """
        Update resonance buffer with current states for next step.

        States are detached to prevent gradient flow across steps
        (this is the 'Delayed' in Delayed Resonance).
        """
        self.resonance_buffer = [s.detach().clone() for s in current_states]

    def update_gunas(self, s: float, r: float, t: float):
        """Update current Guna state for metacognitive decisions."""
        self.current_gunas = (s, r, t)

    def process(
        self,
        layer_states: List[torch.Tensor],
        compute_loss: bool = True,
        return_resonance: bool = False,
        apply_resonance: bool = True,
    ) -> Dict[str, Any]:
        """
        Process layer states through the evolutionary system with DELAYED RESONANCE.

        Args:
            layer_states: Hidden states from each model layer
            compute_loss: Whether to compute evolutionary loss
            return_resonance: Whether to return backward resonance
            apply_resonance: Whether to apply delayed resonance from previous step

        Returns:
            Dict with flow results, loss, metrics, and recommendations
        """
        # Ensure correct number of states (pad or truncate if needed)
        if len(layer_states) < self.num_layers:
            # Pad with last state
            while len(layer_states) < self.num_layers:
                layer_states.append(layer_states[-1])
        elif len(layer_states) > self.num_layers:
            # Take first num_layers
            layer_states = layer_states[:self.num_layers]

        # DELAYED RESONANCE: Inject previous O12 into current O1
        if apply_resonance:
            layer_states = self.apply_delayed_resonance(layer_states)

        # Process through flow network
        flow_result = self.flow_network(
            layer_states,
            return_resonance=return_resonance,
        )

        result = {
            "flow_result": flow_result,
            "coherence_summary": self.flow_network.get_coherence_summary(),
        }

        # Compute loss if requested
        if compute_loss:
            loss, loss_metrics = self.flow_loss(layer_states, flow_result)
            result["loss"] = loss
            result["loss_metrics"] = loss_metrics

        # Metacognitive assessment with Guna integration
        macro_coherence = flow_result["toroidal_coherence"]
        meta_assessment = self.metacognitive.update(
            coherence=macro_coherence,
            gunas=self.current_gunas,  # Pass current Guna state
        )
        result["metacognitive"] = meta_assessment

        # Learning rate modulation based on recommendation and Gunas
        if self.learning_rate_modulation:
            rec = meta_assessment["recommendation"]
            s, r, t = self.current_gunas

            if rec == "SLOW_DOWN":
                # Slow down - use configured factor
                result["lr_multiplier"] = self.lr_slowdown_factor * 1.4  # 0.7 default
            elif rec == "BRAKE":
                # Full brake - high Viparyaya detected
                result["lr_multiplier"] = self.lr_slowdown_factor  # 0.5 default
            elif rec == "ACCELERATE":
                # Accelerate - Sattva dominant, coherence climbing
                result["lr_multiplier"] = self.lr_accelerate_factor  # 1.2 default
            elif rec == "STABILIZE":
                # Stabilize - hold steady
                result["lr_multiplier"] = 1.0
            elif rec == "RECOVER":
                # Recovery from Tamas stagnation - slight boost
                result["lr_multiplier"] = 1.05
            else:
                # CONTINUE
                result["lr_multiplier"] = 1.0

            # Guna-based micro-adjustment
            if s > 0.5:  # High Sattva - can push slightly harder
                result["lr_multiplier"] *= 1.05
            elif t > 0.5:  # High Tamas - need to be more conservative
                result["lr_multiplier"] *= 0.95

        # Update resonance buffer for next step
        self.update_resonance_buffer(layer_states)

        # Store in history
        self.evolution_history.append({
            "micro_coherence": flow_result["micro_coherence_mean"],
            "meso_authority": flow_result["authority_coherence"],
            "meso_sensory": flow_result["sensory_coherence"],
            "macro_coherence": macro_coherence,
            "recommendation": meta_assessment["recommendation"],
            "gunas": self.current_gunas,
        })
        if len(self.evolution_history) > 1000:
            self.evolution_history = self.evolution_history[-1000:]

        return result

    def get_status(self) -> str:
        """Get formatted status string."""
        return self.flow_network.get_status_string()

    def get_evolutionary_health(self) -> Dict[str, Any]:
        """
        Compute overall evolutionary health metrics.

        Returns assessment of the system's cognitive vitality.
        """
        if not self.evolution_history:
            return {"health": "UNKNOWN", "score": 0.5}

        recent = self.evolution_history[-10:]

        micro_avg = sum(h["micro_coherence"] for h in recent) / len(recent)
        macro_avg = sum(h["macro_coherence"] for h in recent) / len(recent)

        # Overall health score
        score = (micro_avg + macro_avg) / 2

        if score >= 0.7:
            health = "THRIVING"
        elif score >= 0.5:
            health = "HEALTHY"
        elif score >= 0.3:
            health = "STRESSED"
        else:
            health = "CRITICAL"

        return {
            "health": health,
            "score": score,
            "micro_coherence": micro_avg,
            "macro_coherence": macro_avg,
            "trend": self._compute_trend(),
        }

    def _compute_trend(self) -> str:
        """Compute evolutionary trend from history."""
        if len(self.evolution_history) < 10:
            return "ESTABLISHING"

        early = self.evolution_history[-20:-10]
        late = self.evolution_history[-10:]

        early_score = sum(h["macro_coherence"] for h in early) / len(early)
        late_score = sum(h["macro_coherence"] for h in late) / len(late)

        diff = late_score - early_score
        if diff > 0.05:
            return "ASCENDING"
        elif diff < -0.05:
            return "DESCENDING"
        else:
            return "STABLE"

    def get_state(self) -> Dict[str, Any]:
        """V9.8.6: Get internal state for checkpointing."""
        # resonance_buffer is List[Tensor], convert each to list
        res_buf = None
        if self.resonance_buffer is not None:
            res_buf = [t.cpu().tolist() for t in self.resonance_buffer]
        return {
            "flow_network_state": self.flow_network.get_state(),
            "flow_network_weights": self.flow_network.state_dict(),  # Save nn.Module weights!
            "evolution_history": list(self.evolution_history[-100:]),  # Keep last 100
            "current_gunas": self.current_gunas,
            "resonance_buffer": res_buf,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """V9.8.6: Restore internal state from checkpoint."""
        if state is None:
            return
        if "flow_network_weights" in state:
            self.flow_network.load_state_dict(state["flow_network_weights"])  # Restore nn.Module weights!
        if "flow_network_state" in state:
            self.flow_network.load_state(state["flow_network_state"])
        if "evolution_history" in state:
            self.evolution_history = list(state["evolution_history"])
        if "current_gunas" in state:
            self.current_gunas = state["current_gunas"]
        if "resonance_buffer" in state and state["resonance_buffer"] is not None:
            # resonance_buffer is List[Tensor]
            self.resonance_buffer = [torch.tensor(t, device=self.device) for t in state["resonance_buffer"]]
