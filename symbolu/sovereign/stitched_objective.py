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
