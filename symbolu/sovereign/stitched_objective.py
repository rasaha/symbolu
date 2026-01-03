"""
Stitched Objective Optimization - Patent Formulas [001]-[008] Implementation.

This module transforms the Sovereign model from a simple "Next Token Predictor"
into a Penalized Optimization System. Token selection maximizes Relevance while
minimizing Redundancy and Domain-Drift, governed by the 5 Vritti states.

Key Patent Formulas Implemented:
- [001] Aspect Weighting: C-Signal drives Ontological layer activation
- [002] Context-Vritti Coupling: Alignment between Vritti and semantic context
- [003] Redundancy Penalty: Phase coherence to detect repetition loops
- [005] Domain-Jump Penalty: Cross-domain distance using transition matrix
- [007] Stitched Objective: Penalized scoring replacing argmax
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class StitchedConfig:
    """Configuration for Stitched Objective optimization."""

    # Penalty weights
    lambda_relevance: float = 1.0
    lambda_redundancy: float = 0.3
    lambda_domain_jump: float = 0.5

    # Context-Vritti Coupling thresholds
    coupling_alert: float = 0.3
    coupling_reset: float = 0.15

    # Redundancy detection
    redundancy_window: int = 5
    redundancy_threshold: float = 0.85

    @classmethod
    def from_json(cls, path: str) -> "StitchedConfig":
        """Load config from vritti_config.json."""
        with open(path) as f:
            data = json.load(f)

        obj = data.get("stitched_objective", {})
        weights = obj.get("weights", {})
        thresholds = obj.get("thresholds", {})

        return cls(
            lambda_relevance=weights.get("lambda_relevance", 1.0),
            lambda_redundancy=weights.get("lambda_redundancy", 0.3),
            lambda_domain_jump=weights.get("lambda_domain_jump", 0.5),
            coupling_alert=thresholds.get("coupling_alert", 0.3),
            coupling_reset=thresholds.get("coupling_reset", 0.15),
            redundancy_window=thresholds.get("redundancy_window", 5),
            redundancy_threshold=thresholds.get("redundancy_threshold", 0.85),
        )


class AspectWeighting(nn.Module):
    """
    Formula [001]: C-Signal to Ontological Layer Activation.

    The hash of a syllable/phoneme activates a subset of the 12 Ontological
    layers (Bhavas). This ensures the "Sound" of the word constrains the
    "Aspect" of the meaning.
    """

    def __init__(self, c_dim: int = 32, n_aspects: int = 12):
        super().__init__()
        self.c_dim = c_dim
        self.n_aspects = n_aspects

        # Project C-Signal to aspect weights
        self.aspect_proj = nn.Linear(c_dim, n_aspects)

        # Phoneme category to aspect mapping (trainable bias)
        self.category_bias = nn.Parameter(torch.zeros(5, n_aspects))

    def forward(
        self,
        c_signals: torch.Tensor,
        phoneme_categories: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute aspect weights from C-Signals.

        Args:
            c_signals: [B, Seq, 32] - Phoneme/syllable hash
            phoneme_categories: [B, Seq] - Optional phoneme category (0-4)

        Returns:
            aspect_weights: [B, Seq, 12] - Normalized weights per aspect
        """
        # Base aspect activation from C-Signal
        aspects = self.aspect_proj(c_signals)  # [B, Seq, 12]

        # Add category bias if provided
        if phoneme_categories is not None:
            cat_bias = self.category_bias[phoneme_categories]  # [B, Seq, 12]
            aspects = aspects + cat_bias

        # Normalize to probability distribution
        aspect_weights = F.softmax(aspects, dim=-1)

        return aspect_weights


class ContextVrittiCoupling(nn.Module):
    """
    Formula [002]: Context-Vritti Coupling Measurement.

    Computes alignment between predicted Vritti state and semantic context.
    Low coupling indicates the model is in the wrong "Mental Mode" and should
    trigger Viparyaya (Error) for a hard reset.
    """

    def __init__(self, d_model: int = 1024, coupling_dim: int = 64):
        super().__init__()
        self.d_model = d_model
        self.coupling_dim = coupling_dim

        # Project hidden state to coupling space
        self.context_proj = nn.Linear(d_model, coupling_dim)

        # Project Vritti embedding to coupling space
        self.vritti_embed = nn.Embedding(5, coupling_dim)

        # Coupling score head
        self.coupling_head = nn.Sequential(
            nn.Linear(coupling_dim * 2, coupling_dim),
            nn.ReLU(),
            nn.Linear(coupling_dim, 1),
            nn.Sigmoid(),
        )

    def forward(
        self,
        hidden_states: torch.Tensor,
        vritti_ids: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute context-Vritti coupling score.

        Args:
            hidden_states: [B, Seq, d_model] - Transformer hidden states
            vritti_ids: [B, Seq] - Predicted Vritti states (0-4)

        Returns:
            coupling: [B, Seq] - Coupling score (0-1)
            should_reset: [B, Seq] - Boolean mask for reset triggers
        """
        # Project context
        context = self.context_proj(hidden_states)  # [B, Seq, coupling_dim]

        # Get Vritti embeddings
        vritti = self.vritti_embed(vritti_ids)  # [B, Seq, coupling_dim]

        # Concatenate and compute coupling
        combined = torch.cat([context, vritti], dim=-1)  # [B, Seq, 2*coupling_dim]
        coupling = self.coupling_head(combined).squeeze(-1)  # [B, Seq]

        # Determine reset triggers (low coupling)
        should_reset = coupling < 0.15

        return coupling, should_reset

    def compute_coupling_loss(
        self,
        hidden_states: torch.Tensor,
        vritti_ids: torch.Tensor,
        target_vritti: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute coupling loss for training.

        High coupling when predicted Vritti matches target.
        Low coupling when mismatched (trains the detector).
        """
        coupling, _ = self.forward(hidden_states, vritti_ids)

        # Target: high coupling when match, low when mismatch
        match_mask = (vritti_ids == target_vritti).float()
        target_coupling = match_mask * 0.9 + (1 - match_mask) * 0.1

        loss = F.mse_loss(coupling, target_coupling)
        return loss


class RedundancyPenalty(nn.Module):
    """
    Formula [003]: Redundancy Penalty using Phase Coherence.

    Detects repetitive loops by measuring similarity between current state
    and recent history. High similarity = repetition = penalty.
    """

    def __init__(self, d_model: int = 1024, window_size: int = 5):
        super().__init__()
        self.d_model = d_model
        self.window_size = window_size

        # State buffer for history tracking
        self.register_buffer("state_history", None)

    def reset_history(self, batch_size: int, device: torch.device):
        """Reset history buffer for new sequence."""
        self.state_history = torch.zeros(
            batch_size, self.window_size, self.d_model, device=device
        )

    def forward(
        self,
        hidden_state: torch.Tensor,
        update_history: bool = True,
    ) -> torch.Tensor:
        """
        Compute redundancy penalty for current state.

        Args:
            hidden_state: [B, d_model] - Current hidden state (single position)
            update_history: Whether to add current state to history

        Returns:
            penalty: [B] - Redundancy penalty (0-1, higher = more redundant)
        """
        if self.state_history is None:
            self.reset_history(hidden_state.size(0), hidden_state.device)

        # Compute cosine similarity with history
        # hidden_state: [B, d_model]
        # state_history: [B, window, d_model]
        current_norm = F.normalize(hidden_state, dim=-1).unsqueeze(1)  # [B, 1, d_model]
        history_norm = F.normalize(self.state_history, dim=-1)  # [B, window, d_model]

        similarities = torch.bmm(current_norm, history_norm.transpose(1, 2))  # [B, 1, window]
        similarities = similarities.squeeze(1)  # [B, window]

        # Max similarity is the redundancy score
        max_sim = similarities.max(dim=-1).values  # [B]

        # Clamp to [0, 1]
        penalty = max_sim.clamp(0, 1)

        # Update history (FIFO)
        if update_history:
            self.state_history = torch.cat(
                [self.state_history[:, 1:, :], hidden_state.unsqueeze(1)],
                dim=1,
            )

        return penalty


class DomainJumpPenalty(nn.Module):
    """
    Formula [005]: Domain-Jump Penalty using Transition Matrix.

    Calculates the cross-domain distance between consecutive Vritti states.
    Penalizes abrupt jumps without proper transitions (e.g., Nidrā → Pramāṇa).
    """

    def __init__(self):
        super().__init__()

        # Transition Penalty Matrix: [From, To]
        # Higher value = more illegal/high-energy jump
        self.register_buffer(
            "transition_matrix",
            torch.tensor([
                #  Pra   Vip   Vik   Smr   Nid
                [0.1, 0.8, 0.9, 0.2, 0.5],  # From Pramāṇa
                [0.5, 0.1, 0.5, 0.5, 0.5],  # From Viparyaya
                [0.7, 0.5, 0.1, 0.3, 0.2],  # From Vikalpa
                [0.2, 0.4, 0.4, 0.1, 0.3],  # From Smṛti
                [0.9, 0.8, 0.5, 0.2, 0.1],  # From Nidrā
            ]),
        )

    def forward(
        self,
        prev_vritti: torch.Tensor,
        curr_vritti: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute domain-jump penalty.

        Args:
            prev_vritti: [B] or [B, Seq] - Previous Vritti state(s)
            curr_vritti: [B] or [B, Seq] - Current Vritti state(s)

        Returns:
            penalty: Same shape as input - Transition penalty (0-1)
        """
        prev_clamped = prev_vritti.clamp(0, 4)
        curr_clamped = curr_vritti.clamp(0, 4)

        penalty = self.transition_matrix[prev_clamped, curr_clamped]
        return penalty

    def get_legal_transitions(self, current_vritti: int) -> List[Tuple[int, float]]:
        """Get legal transitions from current state, sorted by penalty."""
        penalties = self.transition_matrix[current_vritti].tolist()
        transitions = [(i, p) for i, p in enumerate(penalties)]
        return sorted(transitions, key=lambda x: x[1])


class StitchedObjective(nn.Module):
    """
    Formula [007]: Stitched Objective - Penalized Scoring Function.

    Replaces simple argmax with cost-aware optimization:
    Score(w) = Relevance(w) - λ_red * Redundancy(w) - λ_dom * DomainJump(w)

    This transforms the model from a "Probability Machine" to a "State-Control System".
    """

    def __init__(
        self,
        d_model: int = 1024,
        config: Optional[StitchedConfig] = None,
    ):
        super().__init__()

        if config is None:
            config = StitchedConfig()
        self.config = config

        # Penalty components
        self.redundancy = RedundancyPenalty(d_model, config.redundancy_window)
        self.domain_jump = DomainJumpPenalty()
        self.coupling = ContextVrittiCoupling(d_model)

    def forward(
        self,
        logits: torch.Tensor,
        hidden_states: torch.Tensor,
        prev_vritti: torch.Tensor,
        curr_vritti: torch.Tensor,
        current_hidden: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Apply stitched objective scoring to logits.

        Args:
            logits: [B, Vocab] - Raw token logits (single position)
            hidden_states: [B, Seq, d_model] - Full hidden state sequence
            prev_vritti: [B] - Previous Vritti state
            curr_vritti: [B] - Current/predicted Vritti state
            current_hidden: [B, d_model] - Current position hidden state

        Returns:
            adjusted_logits: [B, Vocab] - Penalty-adjusted logits
            penalties: Dict with individual penalty values
        """
        B, V = logits.shape

        # 1. Relevance (base logits as log-probabilities)
        relevance = F.log_softmax(logits, dim=-1)  # [B, V]

        # 2. Redundancy Penalty
        if current_hidden is not None:
            redundancy_penalty = self.redundancy(current_hidden)  # [B]
        else:
            redundancy_penalty = torch.zeros(B, device=logits.device)

        # 3. Domain-Jump Penalty
        domain_penalty = self.domain_jump(prev_vritti, curr_vritti)  # [B]

        # 4. Coupling check (for logging/triggering reset)
        coupling_score, should_reset = self.coupling(
            hidden_states[:, -1:, :], curr_vritti.unsqueeze(-1)
        )
        coupling_score = coupling_score.squeeze(-1)  # [B]

        # 5. Combine penalties (broadcast to vocab size)
        total_penalty = (
            self.config.lambda_redundancy * redundancy_penalty
            + self.config.lambda_domain_jump * domain_penalty
        )  # [B]

        # 6. Adjust logits
        # Penalty reduces all logits uniformly (affects sampling temperature effectively)
        adjusted_logits = relevance - total_penalty.unsqueeze(-1)

        penalties = {
            "redundancy": redundancy_penalty,
            "domain_jump": domain_penalty,
            "coupling": coupling_score,
            "should_reset": should_reset.squeeze(-1),
            "total_penalty": total_penalty,
        }

        return adjusted_logits, penalties

    def reset_state(self, batch_size: int, device: torch.device):
        """Reset internal state for new generation."""
        self.redundancy.reset_history(batch_size, device)


class VrittiGovernor(nn.Module):
    """
    The PID Mode-Switch Governor.

    Orchestrates all penalty components and manages Vritti state transitions.
    Acts as the "Central Control System" for the Sovereign model.
    """

    def __init__(
        self,
        d_model: int = 1024,
        config_path: Optional[str] = None,
    ):
        super().__init__()

        # Load config
        if config_path and Path(config_path).exists():
            self.config = StitchedConfig.from_json(config_path)
        else:
            self.config = StitchedConfig()

        # Core components
        self.stitched = StitchedObjective(d_model, self.config)
        self.aspect_weighting = AspectWeighting()

        # PID gains (from vritti.py)
        self.register_buffer("kp_table", torch.tensor([0.9, 0.7, 0.3, 0.5, 0.2]))
        self.register_buffer("ki_table", torch.tensor([0.01, 0.2, 0.05, 0.4, 0.7]))
        self.register_buffer("kd_table", torch.tensor([0.01, 0.2, 0.6, 0.1, 0.01]))

        # State tracking
        self.prev_vritti: Optional[torch.Tensor] = None
        self.error_integral = 0.0
        self.prev_error = 0.0

    def get_pid_gains(self, vritti_id: torch.Tensor) -> torch.Tensor:
        """Get [Kp, Ki, Kd] for current Vritti state."""
        vritti_id = vritti_id.clamp(0, 4)
        kp = self.kp_table[vritti_id]
        ki = self.ki_table[vritti_id]
        kd = self.kd_table[vritti_id]
        return torch.stack([kp, ki, kd], dim=-1)

    def apply_emergency_brake(
        self,
        should_reset: torch.Tensor,
        learning_rate: float,
    ) -> float:
        """Apply emergency brake if reset triggered."""
        if should_reset.any():
            # Dampen learning rate by 0.1x during Viparyaya
            return learning_rate * 0.1
        return learning_rate

    def forward(
        self,
        logits: torch.Tensor,
        hidden_states: torch.Tensor,
        vritti_pred: torch.Tensor,
        c_signals: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Apply full Governor pipeline to token selection.

        Args:
            logits: [B, Vocab] - Raw token logits
            hidden_states: [B, Seq, d_model] - Hidden states
            vritti_pred: [B] - Predicted Vritti state
            c_signals: [B, 32] - Optional C-Signal for aspect weighting

        Returns:
            adjusted_logits: [B, Vocab] - Governor-adjusted logits
            info: Dict with all penalty and state information
        """
        B = logits.size(0)
        device = logits.device

        # Initialize prev_vritti if needed
        if self.prev_vritti is None:
            self.prev_vritti = torch.full((B,), 4, device=device)  # Start in Nidrā

        # Apply stitched objective
        adjusted_logits, penalties = self.stitched(
            logits,
            hidden_states,
            self.prev_vritti,
            vritti_pred,
            hidden_states[:, -1, :] if hidden_states.dim() == 3 else None,
        )

        # Get PID gains for current state
        pid_gains = self.get_pid_gains(vritti_pred)

        # Compute aspect weights if C-Signal provided
        if c_signals is not None:
            aspect_weights = self.aspect_weighting(c_signals.unsqueeze(1))
            aspect_weights = aspect_weights.squeeze(1)
        else:
            aspect_weights = None

        # Update state
        self.prev_vritti = vritti_pred.clone()

        info = {
            **penalties,
            "pid_gains": pid_gains,
            "aspect_weights": aspect_weights,
            "vritti_state": vritti_pred,
        }

        return adjusted_logits, info

    def reset(self, batch_size: int, device: torch.device):
        """Reset Governor state for new generation."""
        self.prev_vritti = torch.full((batch_size,), 4, device=device)  # Nidrā
        self.stitched.reset_state(batch_size, device)
        self.error_integral = 0.0
        self.prev_error = 0.0


def format_governor_log(
    step: int,
    token: str,
    vritti: int,
    penalties: Dict[str, torch.Tensor],
    pid_gains: torch.Tensor,
) -> str:
    """Format a detailed Governor action log."""
    vritti_names = ["PRAMANA", "VIPARYAYA", "VIKALPA", "SMRTI", "NIDRA"]
    vritti_name = vritti_names[vritti]

    kp, ki, kd = pid_gains[0].item(), pid_gains[1].item(), pid_gains[2].item()
    red = penalties["redundancy"].item() if penalties["redundancy"].dim() == 0 else penalties["redundancy"][0].item()
    dom = penalties["domain_jump"].item() if penalties["domain_jump"].dim() == 0 else penalties["domain_jump"][0].item()
    coup = penalties["coupling"].item() if penalties["coupling"].dim() == 0 else penalties["coupling"][0].item()
    reset = penalties["should_reset"].item() if penalties["should_reset"].dim() == 0 else penalties["should_reset"][0].item()

    action = "RESET" if reset else "PASS"

    return (
        f"[{step:4d}] {token:<15} | {vritti_name:<10} | "
        f"Kp={kp:.2f} Ki={ki:.2f} Kd={kd:.2f} | "
        f"Red={red:.3f} Dom={dom:.3f} Coup={coup:.3f} | {action}"
    )


# =============================================================================
# STITCHED SCORER - Formula [214], [220], [223], [226] Implementation
# =============================================================================

@dataclass
class ScorerConfig:
    """Configuration for StitchedScorer matching patent formulas."""

    # Multi-factor relevance weights (Formula [214])
    theta1: float = 0.3  # Aspect weight exponent
    theta2: float = 0.25  # Vritti-Aspect coupling exponent
    theta3: float = 0.2  # Domain fit exponent
    theta4: float = 0.15  # Template fit exponent
    theta5: float = 0.1  # Confidence coefficient exponent

    # Penalty weights (Formula [226])
    lambda1: float = 0.3  # Redundancy weight
    lambda2: float = 0.5  # Domain-jump weight

    # Redundancy sub-weights (Formula [220])
    alpha_sem: float = 0.5  # Semantic similarity weight
    alpha_asp: float = 0.3  # Aspect overlap weight
    alpha_tmp: float = 0.2  # Template overlap weight


class VrittiAspectCoupling(nn.Module):
    """
    Vritti-Aspect Coupling Matrix (R) from Formula [214].

    Defines how each Vritti state resonates with each Ontological Aspect.
    This is the bridge between mental state and reasoning layer.
    """

    def __init__(self, n_vritti: int = 5, n_aspects: int = 12):
        super().__init__()
        self.n_vritti = n_vritti
        self.n_aspects = n_aspects

        # Coupling matrix R[vritti, aspect] - trainable
        # Initialized based on semantic alignment:
        # - Pramāṇa (Truth) → Action, Structure, Quantity (factual)
        # - Vikalpa (Imagination) → Quality, Modification (creative)
        # - Smṛti (Memory) → Reference, Connection (contextual)
        # - Nidrā (Dormancy) → Punctuation, Neutral (filler)
        initial_coupling = torch.tensor([
            # Asp: 0    1    2    3    4    5    6    7    8    9   10   11
            [0.9, 0.3, 0.7, 0.9, 0.5, 0.4, 0.3, 0.8, 0.9, 0.3, 0.2, 0.5],  # Pramāṇa
            [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],  # Viparyaya
            [0.4, 0.5, 0.6, 0.4, 0.8, 0.9, 0.9, 0.6, 0.3, 0.5, 0.3, 0.6],  # Vikalpa
            [0.6, 0.8, 0.5, 0.6, 0.4, 0.4, 0.5, 0.7, 0.5, 0.9, 0.4, 0.5],  # Smṛti
            [0.2, 0.7, 0.3, 0.2, 0.3, 0.2, 0.4, 0.2, 0.2, 0.4, 0.9, 0.8],  # Nidrā
        ])
        self.register_buffer("coupling_matrix", initial_coupling)

    def forward(
        self,
        vritti_dist: torch.Tensor,
        aspect_dist: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute Vritti-Aspect coupling score.

        Args:
            vritti_dist: [B, 5] - Vritti probability distribution
            aspect_dist: [B, 12] - Aspect probability distribution

        Returns:
            coupling: [B] - Coupling score
        """
        # Compute weighted coupling: sum(pv * R * pa)
        # vritti_dist: [B, 5], coupling_matrix: [5, 12], aspect_dist: [B, 12]
        weighted_R = torch.matmul(vritti_dist, self.coupling_matrix)  # [B, 12]
        coupling = (weighted_R * aspect_dist).sum(dim=-1)  # [B]
        return coupling


class EntropyConfidence(nn.Module):
    """
    Confidence Coefficient (c) from Formula [214].

    Derived from the "Trinity of Entropy": Sattva, Rajas, Tamas.
    High confidence = focused (Sattva), Low = scattered (Tamas).
    """

    def __init__(self):
        super().__init__()

    def forward(self, guna_states: torch.Tensor) -> torch.Tensor:
        """
        Compute confidence from Guna entropy.

        Args:
            guna_states: [B, 3] - [Sattva, Rajas, Tamas] values

        Returns:
            confidence: [B] - Confidence coefficient (0-1)
        """
        # Normalize to probabilities
        guna_probs = F.softmax(guna_states, dim=-1)

        # Entropy: high entropy = low confidence
        entropy = -(guna_probs * torch.log(guna_probs + 1e-8)).sum(dim=-1)
        max_entropy = math.log(3)  # Max entropy for 3 states

        # Confidence = 1 - normalized entropy
        confidence = 1.0 - (entropy / max_entropy)
        return confidence


class StitchedScorer(nn.Module):
    """
    Stitched Scoring Module - Full Patent Implementation.

    Implements Formula [226]: S* = argmax(rel_i - λ1*red - λ2*dj)

    Where:
    - rel_i: Multi-factor relevance (Formula [214])
    - red: Redundancy penalty (Formula [220])
    - dj: Domain-jump penalty (Formula [223])

    This replaces standard greedy/beam search with State-Aware Optimization.
    """

    def __init__(
        self,
        d_model: int = 1024,
        n_aspects: int = 12,
        config: Optional[ScorerConfig] = None,
    ):
        super().__init__()

        if config is None:
            config = ScorerConfig()
        self.config = config

        # Multi-factor components (Formula [214])
        self.vritti_aspect_coupling = VrittiAspectCoupling(n_vritti=5, n_aspects=n_aspects)
        self.entropy_confidence = EntropyConfidence()

        # Aspect projection from hidden state
        self.aspect_proj = nn.Linear(d_model, n_aspects)

        # Template embedding for overlap detection
        self.template_proj = nn.Linear(d_model, 64)

        # History tracking for redundancy
        self.register_buffer("history_embeds", None)
        self.register_buffer("history_aspects", None)
        self.register_buffer("history_templates", None)
        self.register_buffer("prev_domain", None)

        # Transition matrix (Formula [223])
        self.register_buffer(
            "transition_costs",
            torch.tensor([
                [0.1, 0.8, 0.9, 0.2, 0.5],
                [0.5, 0.1, 0.5, 0.5, 0.5],
                [0.7, 0.5, 0.1, 0.3, 0.2],
                [0.2, 0.4, 0.4, 0.1, 0.3],
                [0.9, 0.8, 0.5, 0.2, 0.1],
            ])
        )

    def reset_history(self, batch_size: int, device: torch.device):
        """Reset history for new generation."""
        self.history_embeds = torch.zeros(batch_size, 5, 1024, device=device)
        self.history_aspects = torch.zeros(batch_size, 5, 12, device=device)
        self.history_templates = torch.zeros(batch_size, 5, 64, device=device)
        self.prev_domain = torch.full((batch_size,), 4, device=device, dtype=torch.long)

    def compute_relevance(
        self,
        token_probs: torch.Tensor,
        aspect_dist: torch.Tensor,
        vritti_dist: torch.Tensor,
        entropy_conf: torch.Tensor,
        domain_fit: Optional[torch.Tensor] = None,
        template_fit: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute multi-factor relevance score (Formula [214]).

        rel_i = (pα^θ1) * (Σ(pv·R)^θ2) * (pd^θ3) * (pt^θ4) * (c^θ5)

        Args:
            token_probs: [B, V] - Token probability distribution
            aspect_dist: [B, 12] - Aspect distribution
            vritti_dist: [B, 5] - Vritti distribution
            entropy_conf: [B] - Confidence from Guna entropy
            domain_fit: [B] - Optional domain alignment score
            template_fit: [B] - Optional template alignment score

        Returns:
            relevance: [B, V] - Multi-factor relevance scores
        """
        cfg = self.config

        # 1. Aspect weight (max aspect probability)
        aspect_weight = aspect_dist.max(dim=-1).values  # [B]

        # 2. Vritti-Aspect coupling
        coupling = self.vritti_aspect_coupling(vritti_dist, aspect_dist)  # [B]

        # 3. Domain fit (default to 1 if not provided)
        if domain_fit is None:
            domain_fit = torch.ones_like(aspect_weight)

        # 4. Template fit (default to 1 if not provided)
        if template_fit is None:
            template_fit = torch.ones_like(aspect_weight)

        # 5. Multi-factor combination
        # [B] values, broadcast to [B, 1] for multiplication with token_probs
        multi_factor = (
            (aspect_weight ** cfg.theta1)
            * (coupling ** cfg.theta2)
            * (domain_fit ** cfg.theta3)
            * (template_fit ** cfg.theta4)
            * (entropy_conf ** cfg.theta5)
        ).unsqueeze(-1)  # [B, 1]

        relevance = token_probs * multi_factor  # [B, V]
        return relevance

    def compute_redundancy(
        self,
        current_embed: torch.Tensor,
        current_aspect: torch.Tensor,
        current_template: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute redundancy penalty (Formula [220]).

        red(S) = α_sem·sim_semantic + α_asp·overlap_aspect + α_tmp·overlap_template

        Args:
            current_embed: [B, d_model] - Current hidden state
            current_aspect: [B, 12] - Current aspect distribution
            current_template: [B, 64] - Current template embedding

        Returns:
            redundancy: [B] - Redundancy penalty
        """
        if self.history_embeds is None:
            return torch.zeros(current_embed.size(0), device=current_embed.device)

        cfg = self.config

        # 1. Semantic similarity (cosine with history)
        current_norm = F.normalize(current_embed, dim=-1).unsqueeze(1)  # [B, 1, d]
        history_norm = F.normalize(self.history_embeds, dim=-1)  # [B, H, d]
        sem_sim = torch.bmm(current_norm, history_norm.transpose(1, 2)).squeeze(1)  # [B, H]
        sem_sim = sem_sim.max(dim=-1).values  # [B]

        # 2. Aspect overlap (how similar is current aspect to history)
        current_asp = current_aspect.unsqueeze(1)  # [B, 1, 12]
        asp_overlap = (current_asp * self.history_aspects).sum(dim=-1).max(dim=-1).values  # [B]

        # 3. Template overlap (phrasing similarity)
        current_tmp = F.normalize(current_template, dim=-1).unsqueeze(1)  # [B, 1, 64]
        history_tmp = F.normalize(self.history_templates, dim=-1)  # [B, H, 64]
        tmp_overlap = torch.bmm(current_tmp, history_tmp.transpose(1, 2)).squeeze(1)  # [B, H]
        tmp_overlap = tmp_overlap.max(dim=-1).values  # [B]

        # Combined redundancy
        redundancy = (
            cfg.alpha_sem * sem_sim
            + cfg.alpha_asp * asp_overlap
            + cfg.alpha_tmp * tmp_overlap
        )

        return redundancy.clamp(0, 1)

    def compute_domain_jump(
        self,
        current_vritti: torch.Tensor,
        resonance: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute domain-jump penalty (Formula [223]).

        dj(S) = transition_cost(prev_domain, current_domain) * resonance_adjustment

        Args:
            current_vritti: [B] - Current Vritti state (0-4)
            resonance: [B] - Optional resonance for dynamic adjustment

        Returns:
            domain_jump: [B] - Domain-jump penalty
        """
        if self.prev_domain is None:
            return torch.zeros(current_vritti.size(0), device=current_vritti.device)

        # Base transition cost from matrix
        prev = self.prev_domain.clamp(0, 4)
        curr = current_vritti.clamp(0, 4)
        base_cost = self.transition_costs[prev, curr]  # [B]

        # Resonance adjustment (if provided)
        if resonance is not None:
            # High resonance = stable, reduce penalty
            # Low resonance = unstable, increase penalty
            adjustment = 1.0 + (0.5 - resonance)  # Range: [0.5, 1.5]
            base_cost = base_cost * adjustment

        return base_cost

    def update_history(
        self,
        embed: torch.Tensor,
        aspect: torch.Tensor,
        template: torch.Tensor,
        vritti: torch.Tensor,
    ):
        """Update history buffers with current step (FIFO)."""
        if self.history_embeds is None:
            return

        # Shift history and add new
        self.history_embeds = torch.cat(
            [self.history_embeds[:, 1:, :], embed.unsqueeze(1)], dim=1
        )
        self.history_aspects = torch.cat(
            [self.history_aspects[:, 1:, :], aspect.unsqueeze(1)], dim=1
        )
        self.history_templates = torch.cat(
            [self.history_templates[:, 1:, :], template.unsqueeze(1)], dim=1
        )
        self.prev_domain = vritti.clone()

    def select_next_token(
        self,
        logits: torch.Tensor,
        hidden_state: torch.Tensor,
        vritti_logits: torch.Tensor,
        guna_states: torch.Tensor,
        aspect_logits: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Executive Stitching Objective (Formula [226]).

        S* = argmax(rel_i - λ1*red - λ2*dj)

        Args:
            logits: [B, V] - Token logits
            hidden_state: [B, d_model] - Current hidden state
            vritti_logits: [B, 5] - Vritti prediction logits
            guna_states: [B, 3] - Guna state values
            aspect_logits: [B, 12] - Optional aspect logits

        Returns:
            selected_token: [B] - Selected token indices
            info: Dict with scoring details
        """
        B, V = logits.shape
        device = logits.device

        # Initialize history if needed
        if self.history_embeds is None:
            self.reset_history(B, device)

        # Compute distributions
        token_probs = F.softmax(logits, dim=-1)  # [B, V]
        vritti_dist = F.softmax(vritti_logits, dim=-1)  # [B, 5]
        current_vritti = vritti_logits.argmax(dim=-1)  # [B]

        # Compute aspect distribution
        if aspect_logits is None:
            aspect_logits = self.aspect_proj(hidden_state)  # [B, 12]
        aspect_dist = F.softmax(aspect_logits, dim=-1)  # [B, 12]

        # Compute template embedding
        template_embed = self.template_proj(hidden_state)  # [B, 64]

        # Compute confidence from Guna entropy
        entropy_conf = self.entropy_confidence(guna_states)  # [B]

        # 1. Multi-factor Relevance (Formula [214])
        relevance = self.compute_relevance(
            token_probs, aspect_dist, vritti_dist, entropy_conf
        )  # [B, V]

        # 2. Redundancy Penalty (Formula [220])
        redundancy = self.compute_redundancy(
            hidden_state, aspect_dist, template_embed
        )  # [B]

        # 3. Domain-Jump Penalty (Formula [223])
        domain_jump = self.compute_domain_jump(current_vritti)  # [B]

        # 4. Stitched Objective (Formula [226])
        # S* = argmax(rel_i - λ1*red - λ2*dj)
        penalty = (
            self.config.lambda1 * redundancy
            + self.config.lambda2 * domain_jump
        ).unsqueeze(-1)  # [B, 1]

        final_scores = relevance - penalty  # [B, V]
        selected_token = torch.argmax(final_scores, dim=-1)  # [B]

        # Update history
        self.update_history(hidden_state, aspect_dist, template_embed, current_vritti)

        info = {
            "relevance": relevance.max(dim=-1).values,
            "redundancy": redundancy,
            "domain_jump": domain_jump,
            "entropy_conf": entropy_conf,
            "vritti_coupling": self.vritti_aspect_coupling(vritti_dist, aspect_dist),
            "selected_score": final_scores.gather(1, selected_token.unsqueeze(-1)).squeeze(-1),
        }

        return selected_token, info
