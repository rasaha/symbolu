"""
Sovereign Metrics Module - The "Nervous System" of Sovereign-1.

Provides real-time health monitoring for the Sovereign training process.
Calculates alignment between model's high-level intent and low-level output.

Patent Formulas Implemented:
- [B1] ConsistencyLagrangian: S-Drift measurement via forward/backward alignment
- [U1/U2] PhaseCoherenceMatrix: Pairwise phase angle coherence across 12 layers
- [S8] StabilityConstraint: Entropy rate tracking with Inertial Brake
"""

import torch
import torch.nn.functional as F
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
import math


@dataclass
class StabilityState:
    """Tracks entropy history for S8 StabilityConstraint."""
    entropy_history: List[float]
    inertial_brake_active: bool = False
    brake_trigger_step: int = -1

    def __init__(self, window_size: int = 5):
        self.entropy_history = []
        self.window_size = window_size
        self.inertial_brake_active = False
        self.brake_trigger_step = -1


class SovereignMetrics:
    """
    Calculates the 5 Pillars of Sovereign Health:

    1. Ontological Accuracy (R-Signal) - Intent layer prediction
    2. Reality-Lock Accuracy (S-Signal) - Physical vs Abstract classification
    3. Guna Entropy - Sattva (focused) vs Rajas (chaotic) state
    4. Semantic Drift - Distance of model's intent from target
    5. Guna Coherence - Smoothness of attention state transitions
    """

    @staticmethod
    @torch.no_grad()
    def get_health_stats(logits_tok, logits_r, logits_s, targets_tok, targets_r, targets_s):
        """
        Calculate the core Sovereign health metrics.

        Args:
            logits_tok: Token prediction logits [B, Seq, Vocab]
            logits_r: R-Signal (Intent) logits [B, Seq, 12]
            logits_s: S-Signal (Reality) logits [B, Seq, 17]
            targets_tok: Target token IDs [B, Seq]
            targets_r: Target R-Signal categories [B, Seq]
            targets_s: Target S-Signal categories [B, Seq]

        Returns:
            dict with r_acc, s_acc, entropy, drift
        """
        # 1. Ontological Accuracy (R-Signal)
        # How well is the model predicting the Intent category?
        r_preds = logits_r.argmax(dim=-1)
        r_acc = (r_preds == targets_r).float().mean().item() * 100

        # 2. Reality-Lock Accuracy (S-Signal)
        # Is the model correctly identifying Physical vs Abstract objects?
        s_preds = logits_s.argmax(dim=-1)
        s_acc = (s_preds == targets_s).float().mean().item() * 100

        # 3. Guna Entropy (Sattva vs Rajas)
        # High = Rajas (Exploring/Chaotic), Low = Sattva (Determined/Stable)
        p = F.softmax(logits_tok, dim=-1)
        entropy = -torch.sum(p * torch.log(p + 1e-9), dim=-1).mean().item()

        # 4. Semantic Drift (R-space distance)
        # Measures how "far away" the model's intent is from the target
        drift = F.cross_entropy(
            logits_r.reshape(-1, logits_r.size(-1)),
            targets_r.reshape(-1)
        ).item()

        return {
            "r_acc": r_acc,
            "s_acc": s_acc,
            "entropy": entropy,
            "drift": drift,
        }

    @staticmethod
    @torch.no_grad()
    def get_guna_coherence(g_states):
        """
        Measure Guna state coherence across sequence.

        High coherence = consistent Sattva/Rajas/Tamas balance
        Low coherence = erratic attention state shifts

        Args:
            g_states: Guna state tensor [B, Seq, 3]

        Returns:
            coherence value (0-1, higher = more coherent)
        """
        if g_states is None or g_states.numel() == 0:
            return 0.0

        # Normalize to probabilities
        guna_probs = F.softmax(g_states, dim=-1)  # [B, Seq, 3]

        # Compute differences between adjacent positions
        diffs = guna_probs[:, 1:, :] - guna_probs[:, :-1, :]  # [B, Seq-1, 3]

        # Mean squared difference (variance of transitions)
        variance = (diffs ** 2).mean().item()

        # Convert to coherence (lower variance = higher coherence)
        # Max variance is ~0.5 (complete flip between states)
        coherence = max(0.0, 1.0 - (variance / 0.5))

        return coherence

    @staticmethod
    @torch.no_grad()
    def get_guna_state(g_states):
        """
        Get the dominant Guna state across the batch.

        Returns:
            tuple: (dominant_state_name, distribution_dict)
        """
        if g_states is None or g_states.numel() == 0:
            return "UNKNOWN", {"sattva": 0, "rajas": 0, "tamas": 0}

        # Average Guna distribution
        guna_mean = g_states.mean(dim=(0, 1))  # [3]
        guna_probs = F.softmax(guna_mean, dim=0)

        sattva = guna_probs[0].item()
        rajas = guna_probs[1].item()
        tamas = guna_probs[2].item()

        # Determine dominant state
        if sattva >= rajas and sattva >= tamas:
            dominant = "SATTVA"
        elif rajas >= sattva and rajas >= tamas:
            dominant = "RAJAS"
        else:
            dominant = "TAMAS"

        return dominant, {
            "sattva": sattva,
            "rajas": rajas,
            "tamas": tamas,
        }

    @staticmethod
    def format_health_check(step, stats, guna_state, guna_coherence, ppl=None):
        """
        Format a beautiful Sovereign Health Check dashboard.

        Args:
            step: Current training step
            stats: Dict from get_health_stats()
            guna_state: Tuple from get_guna_state()
            guna_coherence: Value from get_guna_coherence()
            ppl: Optional perplexity value

        Returns:
            Formatted string for terminal output
        """
        dominant, guna_dist = guna_state

        # Status indicators
        r_status = "GROUNDED" if stats["r_acc"] > 85 else "LEARNING" if stats["r_acc"] > 50 else "DRIFTING"
        s_status = "LOCKED" if stats["s_acc"] > 90 else "FOCUSING" if stats["s_acc"] > 60 else "EXPLORING"
        coh_status = "SYNCED" if guna_coherence > 0.7 else "ALIGNING" if guna_coherence > 0.4 else "SCATTERED"

        # Guna state emoji/indicator
        guna_indicator = {
            "SATTVA": "SATTVA (Pure/Balanced)",
            "RAJAS": "RAJAS (Active/Dynamic)",
            "TAMAS": "TAMAS (Stable/Inert)",
            "UNKNOWN": "UNKNOWN",
        }.get(dominant, dominant)

        lines = [
            "",
            "=" * 55,
            f"  SOVEREIGN HEALTH CHECK (Step {step})",
            "=" * 55,
            f"  Ontology (R-Acc):  {stats['r_acc']:>6.1f}%  | Goal: >85% | {r_status}",
            f"  Reality  (S-Acc):  {stats['s_acc']:>6.1f}%  | Goal: >90% | {s_status}",
            f"  Coherence (Guna):  {guna_coherence:>6.2f}   | Goal: >0.7 | {coh_status}",
            f"  Drift (R-Space):   {stats['drift']:>6.3f}   | Goal: <1.0 | {'LOW' if stats['drift'] < 1.0 else 'HIGH'}",
            "-" * 55,
            f"  Guna State: {guna_indicator}",
            f"    S:{guna_dist['sattva']:.2f} | R:{guna_dist['rajas']:.2f} | T:{guna_dist['tamas']:.2f}",
            f"  Token Entropy: {stats['entropy']:.3f}",
        ]

        if ppl is not None:
            lines.append(f"  Perplexity: {ppl:.2f}")

        lines.extend([
            "=" * 55,
            "",
        ])

        return "\n".join(lines)

    # =========================================================================
    # PATENT FORMULAS
    # =========================================================================

    @staticmethod
    @torch.no_grad()
    def compute_consistency_lagrangian(
        logits_tok: torch.Tensor,
        logits_r: torch.Tensor,
        targets_r: torch.Tensor,
        layer_hidden_states: Optional[List[torch.Tensor]] = None,
    ) -> Dict[str, float]:
        """
        [Formula B1] ConsistencyLagrangian - S-Drift Measurement.

        Measures alignment between model's forward predictions (sf) and
        backward goal alignment (sb) via R-Signal consistency.

        S-Drift = 1 - (sf · sb) / (||sf|| × ||sb||)

        Where:
            sf = Forward token probability distribution (softmax of logits)
            sb = Backward goal alignment (R-Signal prediction confidence)

        Args:
            logits_tok: Token prediction logits [B, Seq, Vocab]
            logits_r: R-Signal logits [B, Seq, 12]
            targets_r: Target R-Signal categories [B, Seq]
            layer_hidden_states: Optional list of hidden states per layer

        Returns:
            dict with:
                - s_drift: Semantic drift value (0 = aligned, 1 = drifted)
                - forward_confidence: Mean forward prediction confidence
                - backward_alignment: Mean backward goal alignment
                - consistency_score: Overall consistency (1 - s_drift)
        """
        # sf: Forward confidence (max probability per position)
        p_tok = F.softmax(logits_tok, dim=-1)
        sf = p_tok.max(dim=-1).values  # [B, Seq]

        # sb: Backward alignment (R-Signal prediction confidence for correct class)
        p_r = F.softmax(logits_r, dim=-1)  # [B, Seq, 12]
        B, Seq, _ = p_r.shape

        # Gather probability of correct R-Signal class
        targets_r_expanded = targets_r.unsqueeze(-1)  # [B, Seq, 1]
        sb = p_r.gather(dim=-1, index=targets_r_expanded).squeeze(-1)  # [B, Seq]

        # Compute S-Drift via cosine similarity between sf and sb
        # Flatten to vectors for cosine sim
        sf_flat = sf.reshape(-1)
        sb_flat = sb.reshape(-1)

        # Cosine similarity
        dot_product = (sf_flat * sb_flat).sum()
        norm_sf = torch.norm(sf_flat)
        norm_sb = torch.norm(sb_flat)

        if norm_sf > 1e-8 and norm_sb > 1e-8:
            cosine_sim = dot_product / (norm_sf * norm_sb)
            s_drift = (1.0 - cosine_sim.item()) / 2.0  # Scale to [0, 1]
        else:
            s_drift = 0.5  # Neutral when norms are too small

        # Additional metrics
        forward_confidence = sf.mean().item()
        backward_alignment = sb.mean().item()
        consistency_score = 1.0 - s_drift

        return {
            "s_drift": s_drift,
            "forward_confidence": forward_confidence,
            "backward_alignment": backward_alignment,
            "consistency_score": consistency_score,
        }

    @staticmethod
    @torch.no_grad()
    def compute_phase_coherence_matrix(
        phase_angles: torch.Tensor,
    ) -> Dict[str, float]:
        """
        [Formula U1/U2] PhaseCoherenceMatrix - Guna Coherence Calculation.

        Computes pairwise phase angle coherence across all 12 layers using
        cosine similarity of complex phase representations.

        U1: Cij = cos(θi - θj) = Re(e^(i(θi-θj)))
        U2: GC = (2 / (n(n-1))) × Σi<j Cij

        Args:
            phase_angles: Phase angles per layer [B, Seq, 12] or [B, 12]

        Returns:
            dict with:
                - guna_coherence: Global coherence score [0, 1]
                - coherence_matrix: Flattened 12x12 coherence values
                - mean_pairwise: Mean of all pairwise coherences
                - min_coherence: Minimum pairwise coherence
                - max_coherence: Maximum pairwise coherence
        """
        # Handle different input shapes
        if phase_angles.dim() == 3:
            # [B, Seq, 12] -> average over sequence
            angles = phase_angles.mean(dim=1)  # [B, 12]
        else:
            angles = phase_angles  # [B, 12]

        B, n_layers = angles.shape
        assert n_layers == 12, f"Expected 12 layers, got {n_layers}"

        # Compute pairwise phase coherence matrix
        # Cij = cos(θi - θj)
        # Expand for pairwise computation
        angles_i = angles.unsqueeze(2)  # [B, 12, 1]
        angles_j = angles.unsqueeze(1)  # [B, 1, 12]

        # Phase difference coherence
        phase_diff = angles_i - angles_j  # [B, 12, 12]
        coherence_matrix = torch.cos(phase_diff)  # [B, 12, 12]

        # Average over batch
        C = coherence_matrix.mean(dim=0)  # [12, 12]

        # Scale from [-1, 1] to [0, 1]
        C_scaled = (C + 1.0) / 2.0

        # U2: Global coherence from upper triangle (excluding diagonal)
        mask = torch.triu(torch.ones(12, 12, device=angles.device), diagonal=1)
        n_pairs = mask.sum().item()  # 66 pairs for 12 layers

        if n_pairs > 0:
            guna_coherence = (C_scaled * mask).sum().item() / n_pairs
        else:
            guna_coherence = 0.5

        # Additional statistics
        upper_values = C_scaled[mask.bool()]
        mean_pairwise = upper_values.mean().item() if len(upper_values) > 0 else 0.5
        min_coherence = upper_values.min().item() if len(upper_values) > 0 else 0.0
        max_coherence = upper_values.max().item() if len(upper_values) > 0 else 1.0

        return {
            "guna_coherence": guna_coherence,
            "coherence_matrix": C_scaled.flatten().tolist(),
            "mean_pairwise": mean_pairwise,
            "min_coherence": min_coherence,
            "max_coherence": max_coherence,
        }

    @staticmethod
    def check_stability_constraint(
        current_entropy: float,
        stability_state: 'StabilityState',
        current_step: int,
        brake_duration: int = 100,
    ) -> Tuple[bool, 'StabilityState']:
        """
        [Formula S8] StabilityConstraint - Entropy Rate with Inertial Brake.

        Monitors entropy rate (dH/dt) and triggers Inertial Brake if entropy
        increases consistently over the window period.

        Constraint: dH/dt <= 0 (entropy should not increase)

        If violated for `window_size` consecutive steps, activate brake which:
        - Signals PIDv2 to reduce sensory gradient scaling
        - Prevents Rajasic (chaotic) drift

        Args:
            current_entropy: Current semantic entropy value
            stability_state: StabilityState tracking object
            current_step: Current training step
            brake_duration: Steps to keep brake active after trigger

        Returns:
            tuple: (brake_active: bool, updated_state: StabilityState)
        """
        # Add current entropy to history
        stability_state.entropy_history.append(current_entropy)

        # Keep only window_size entries
        if len(stability_state.entropy_history) > stability_state.window_size:
            stability_state.entropy_history.pop(0)

        # Check if brake is already active and should remain so
        if stability_state.inertial_brake_active:
            steps_since_trigger = current_step - stability_state.brake_trigger_step
            if steps_since_trigger < brake_duration:
                # Brake still active
                return True, stability_state
            else:
                # Brake duration expired, deactivate
                stability_state.inertial_brake_active = False
                stability_state.brake_trigger_step = -1

        # Need full window to evaluate
        if len(stability_state.entropy_history) < stability_state.window_size:
            return False, stability_state

        # Compute entropy rate (dH/dt) over window
        # Check if entropy is consistently increasing
        history = stability_state.entropy_history
        increasing_count = 0

        for i in range(1, len(history)):
            if history[i] > history[i - 1]:
                increasing_count += 1

        # If entropy increased in majority of steps, trigger brake
        threshold = (stability_state.window_size - 1) * 0.6  # 60% of transitions

        if increasing_count >= threshold:
            # Trigger Inertial Brake
            stability_state.inertial_brake_active = True
            stability_state.brake_trigger_step = current_step
            return True, stability_state

        return False, stability_state

    @staticmethod
    @torch.no_grad()
    def compute_full_sovereign_metrics(
        logits_tok: torch.Tensor,
        logits_r: torch.Tensor,
        logits_s: torch.Tensor,
        targets_tok: torch.Tensor,
        targets_r: torch.Tensor,
        targets_s: torch.Tensor,
        g_states: Optional[torch.Tensor] = None,
        phase_angles: Optional[torch.Tensor] = None,
        stability_state: Optional['StabilityState'] = None,
        current_step: int = 0,
    ) -> Dict:
        """
        Compute all Sovereign metrics including patent formulas.

        Combines:
            - Basic health stats (R-Acc, S-Acc, Entropy, Drift)
            - Guna state and coherence
            - [B1] ConsistencyLagrangian (S-Drift)
            - [U1/U2] PhaseCoherenceMatrix (if phase_angles provided)
            - [S8] StabilityConstraint (if stability_state provided)

        Returns:
            Complete metrics dictionary for logging/monitoring
        """
        # Basic health stats
        stats = SovereignMetrics.get_health_stats(
            logits_tok, logits_r, logits_s,
            targets_tok, targets_r, targets_s
        )

        # Guna metrics
        guna_coherence = SovereignMetrics.get_guna_coherence(g_states)
        guna_state, guna_dist = SovereignMetrics.get_guna_state(g_states)

        # [B1] ConsistencyLagrangian
        lagrangian = SovereignMetrics.compute_consistency_lagrangian(
            logits_tok, logits_r, targets_r
        )

        result = {
            **stats,
            "guna_coherence": guna_coherence,
            "guna_state": guna_state,
            "guna_dist": guna_dist,
            "s_drift_b1": lagrangian["s_drift"],
            "consistency_score": lagrangian["consistency_score"],
            "forward_confidence": lagrangian["forward_confidence"],
            "backward_alignment": lagrangian["backward_alignment"],
        }

        # [U1/U2] PhaseCoherenceMatrix (if available)
        if phase_angles is not None:
            phase_metrics = SovereignMetrics.compute_phase_coherence_matrix(phase_angles)
            result["guna_coherence_u2"] = phase_metrics["guna_coherence"]
            result["phase_coherence_min"] = phase_metrics["min_coherence"]
            result["phase_coherence_max"] = phase_metrics["max_coherence"]

        # [S8] StabilityConstraint (if tracking)
        if stability_state is not None:
            brake_active, updated_state = SovereignMetrics.check_stability_constraint(
                stats["entropy"], stability_state, current_step
            )
            result["inertial_brake_active"] = brake_active
            result["stability_state"] = updated_state

        return result
