"""
Sovereign Metrics Module - The "Nervous System" of Sovereign-1.

Provides real-time health monitoring for the Sovereign training process.
Calculates alignment between model's high-level intent and low-level output.

Patent Formulas Implemented:
- [B1] ConsistencyLagrangian: S-Drift measurement via forward/backward alignment
- [U1/U2] PhaseCoherenceMatrix: Pairwise phase angle coherence across 12 layers
- [S8] StabilityConstraint: Entropy rate tracking with Inertial Brake
- [S3] SovereignLoss: Combined task + consistency + coherence loss
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


# =============================================================================
# SOVEREIGN ENGINE - Trainable Loss Functions
# =============================================================================

@dataclass
class SovereignLossConfig:
    """Configuration for Sovereign-Lagrangian Loss."""
    lambda_b1: float = 0.5      # Consistency Lagrangian weight [B1]
    mu_s3: float = 0.2          # Global Coherence weight [S3]
    lambda_bhava: float = 0.1   # Bhava loss weight (existing)
    gc_floor: float = 0.65      # Minimum GC before PIDv2 intervention
    s_drift_ceiling: float = 0.3  # Maximum S-Drift before warning


class SovereignEngine:
    """
    The Sovereign Logic Engine - Trainable loss functions for Sovereign-1.

    Implements Patent Formulas for training:
    - [B1] ConsistencyLagrangian: Forward/Backward feasibility alignment
    - [U1/U2] Phase-Lock Matrix: Exact pairwise phase coherence
    - [S3] SovereignLoss: Combined objective function
    - [S8] StabilityConstraint: Entropy-based hidden state anchoring

    Usage:
        config = SovereignLossConfig(lambda_b1=0.5, mu_s3=0.2)
        engine = SovereignEngine(config)

        # In training loop:
        loss, metrics = engine.sovereign_loss(
            logits, targets, r_signal, phase_angles
        )
    """

    def __init__(self, config: Optional[SovereignLossConfig] = None):
        self.config = config or SovereignLossConfig()
        self.prev_entropy: Optional[float] = None

    @staticmethod
    def compute_guna_coherence_exact(phase_angles: List[torch.Tensor]) -> torch.Tensor:
        """
        [Patent U1/U2] Exact Pairwise Phase-Lock Matrix.

        Computes mean cosine of phase differences across all layer pairs.
        This version is differentiable for backpropagation.

        Args:
            phase_angles: List of phase angle tensors per layer
                          Each tensor: [B, Heads, Seq, Dim] or [B, Seq, Dim]

        Returns:
            gc: Global coherence tensor (scalar, differentiable)

        Result interpretation:
            gc ≈ 1.0: Perfect Phase Alignment (Sattvic)
            gc ≈ 0.5: Uncorrelated Noise (Rajasic)
            gc ≈ 0.0: Anti-Aligned / Conflict (Viparyaya)
        """
        num_layers = len(phase_angles)
        if num_layers < 2:
            return torch.tensor(1.0, device=phase_angles[0].device)

        total_coherence = torch.tensor(0.0, device=phase_angles[0].device)
        pairs = 0

        for i in range(num_layers):
            for j in range(i + 1, num_layers):
                # Get phase angles, flatten to comparable shapes
                phi_i = phase_angles[i]
                phi_j = phase_angles[j]

                # Handle different tensor shapes
                if phi_i.dim() > 2:
                    phi_i = phi_i.mean(dim=tuple(range(1, phi_i.dim() - 1)))
                if phi_j.dim() > 2:
                    phi_j = phi_j.mean(dim=tuple(range(1, phi_j.dim() - 1)))

                # Ensure same shape
                if phi_i.shape != phi_j.shape:
                    min_size = min(phi_i.shape[-1], phi_j.shape[-1])
                    phi_i = phi_i[..., :min_size]
                    phi_j = phi_j[..., :min_size]

                # cos(phi_i - phi_j) measures alignment stiffness
                cos_diff = torch.cos(phi_i - phi_j)
                layer_pair_coh = cos_diff.mean()
                total_coherence = total_coherence + layer_pair_coh
                pairs += 1

        # Scale from [-1, 1] to [0, 1]
        gc = (total_coherence / pairs + 1.0) / 2.0
        return gc

    def sovereign_loss(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        r_signal: torch.Tensor,
        phase_angles: Optional[List[torch.Tensor]] = None,
        guna_coherence: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        [Patent B1/S3] Sovereign-Lagrangian Loss Function.

        Combines:
        - L_task: Standard cross-entropy for next-token prediction
        - L_consistency [B1]: Forward/Backward feasibility alignment
        - L_align [S3]: Global coherence penalty

        Formula:
            L = L_task + λ_B1 * L_consistency + μ_S3 * L_align

        Args:
            logits: Model output logits [B, Seq, Vocab]
            targets: Target token IDs [B, Seq]
            r_signal: R-Signal from Authority layers [B, Seq, 48] or [B, Seq, D]
            phase_angles: Optional list of phase angles per layer for U1/U2
            guna_coherence: Optional pre-computed GC value

        Returns:
            total_loss: Combined Sovereign loss (differentiable)
            metrics: Dict with component losses and metrics
        """
        device = logits.device
        B, Seq, Vocab = logits.shape

        # 1. L_task: Standard Cross-Entropy
        logits_flat = logits.view(-1, Vocab)
        targets_flat = targets.view(-1)
        l_task = F.cross_entropy(logits_flat, targets_flat)

        # 2. L_consistency [B1]: Forward/Backward Feasibility
        # sf: Token probability for correct class (forward confidence)
        probs = F.softmax(logits, dim=-1)
        targets_expanded = targets.unsqueeze(-1)  # [B, Seq, 1]
        sf = probs.gather(-1, targets_expanded).squeeze(-1)  # [B, Seq]

        # sb: Backward alignment with R-Signal (cosine similarity)
        # Normalize logits and r_signal for proper cosine similarity
        logits_norm = F.normalize(logits, p=2, dim=-1)

        # R-signal may have different dimension, project if needed
        if r_signal.shape[-1] != Vocab:
            # Project R-signal to vocab space or use as-is for similarity
            # Use the first min(Vocab, r_dim) dimensions
            r_dim = r_signal.shape[-1]
            if r_dim < Vocab:
                # Pad r_signal
                r_padded = torch.zeros(B, Seq, Vocab, device=device)
                r_padded[..., :r_dim] = r_signal
                r_signal_use = r_padded
            else:
                r_signal_use = r_signal[..., :Vocab]
        else:
            r_signal_use = r_signal

        r_signal_norm = F.normalize(r_signal_use.detach(), p=2, dim=-1)
        sb = (logits_norm * r_signal_norm).sum(dim=-1)  # [B, Seq]
        sb = (sb + 1.0) / 2.0  # Scale from [-1, 1] to [0, 1]

        # Consistency Lagrangian: (1-sf)² + (1-sb)² + (sf-sb)²
        l_consistency = torch.mean(
            (1 - sf) ** 2 + (1 - sb) ** 2 + (sf - sb) ** 2
        )

        # 3. L_align [S3]: Global Coherence Penalty
        if guna_coherence is not None:
            gc = guna_coherence
        elif phase_angles is not None and len(phase_angles) > 0:
            gc = self.compute_guna_coherence_exact(phase_angles)
        else:
            gc = torch.tensor(0.5, device=device)

        # Ensure gc is a tensor
        if not isinstance(gc, torch.Tensor):
            gc = torch.tensor(gc, device=device)

        l_align = 1.0 - gc

        # 4. Total Sovereign Loss [S3]
        total_loss = (
            l_task
            + self.config.lambda_b1 * l_consistency
            + self.config.mu_s3 * l_align
        )

        # Metrics for logging
        metrics = {
            "l_task": l_task.item(),
            "l_consistency": l_consistency.item(),
            "l_align": l_align.item() if isinstance(l_align, torch.Tensor) else l_align,
            "gc": gc.item() if isinstance(gc, torch.Tensor) else gc,
            "sf_mean": sf.mean().item(),
            "sb_mean": sb.mean().item(),
            "total_loss": total_loss.item(),
        }

        return total_loss, metrics

    def apply_stability_constraint(
        self,
        current_entropy: float,
        r_signal: torch.Tensor,
        hidden_states: torch.Tensor,
        stiffness_scale: float = 5.0,
        max_stiffness: float = 0.9,
    ) -> torch.Tensor:
        """
        [Patent S8] Stability Constraint - Entropy-based Hidden State Anchoring.

        If entropy is rising (confusion/hallucination risk), increase the
        weight of the R-Signal anchor to force hidden states back toward
        the Ontological Authority.

        Args:
            current_entropy: Current semantic entropy value
            r_signal: R-Signal from Authority layers [B, Seq, D]
            hidden_states: Current hidden states [B, Seq, D]
            stiffness_scale: Multiplier for entropy delta
            max_stiffness: Maximum correction strength

        Returns:
            Corrected hidden states (same shape as input)
        """
        if self.prev_entropy is None:
            self.prev_entropy = current_entropy
            return hidden_states

        delta_h = current_entropy - self.prev_entropy
        self.prev_entropy = current_entropy

        if delta_h > 0:
            # Entropy rising - apply Tamasic brake
            stiffness = min(delta_h * stiffness_scale, max_stiffness)
            stiffness = max(0.0, stiffness)

            # Project r_signal to match hidden_states dimension if needed
            if r_signal.shape[-1] != hidden_states.shape[-1]:
                # Simple linear interpolation/padding
                r_dim = r_signal.shape[-1]
                h_dim = hidden_states.shape[-1]
                if r_dim < h_dim:
                    # Repeat r_signal to match
                    repeats = (h_dim + r_dim - 1) // r_dim
                    r_expanded = r_signal.repeat(1, 1, repeats)[..., :h_dim]
                else:
                    r_expanded = r_signal[..., :h_dim]
            else:
                r_expanded = r_signal

            # Force hidden states toward R-Signal anchor
            hidden_states = (1 - stiffness) * hidden_states + stiffness * r_expanded.detach()

        return hidden_states

    def get_loss_status(self, metrics: Dict[str, float]) -> str:
        """
        Get formatted status string for Sovereign loss components.

        Args:
            metrics: Dict from sovereign_loss()

        Returns:
            Formatted status string
        """
        gc = metrics.get("gc", 0.5)
        s_drift = 1.0 - metrics.get("sf_mean", 0.5)  # Approximate drift

        gc_status = "SATTVIC" if gc > 0.85 else "ALIGNED" if gc > self.config.gc_floor else "RAJASIC"
        drift_status = "NULL" if s_drift < 0.1 else "LOW" if s_drift < self.config.s_drift_ceiling else "HIGH"

        return (
            f"L_task={metrics.get('l_task', 0):.4f} | "
            f"L_cons={metrics.get('l_consistency', 0):.4f} | "
            f"GC={gc:.3f} [{gc_status}] | "
            f"S-Drift={s_drift:.3f} [{drift_status}]"
        )


# =============================================================================
# SOVEREIGN ALERT MONITOR - Auto-Pivot Logic
# =============================================================================

@dataclass
class AlertConfig:
    """Configuration for Sovereign Alert thresholds."""
    sa_ratio_danger: float = 0.55       # S/A ratio above this triggers alert
    gc_danger: float = 0.25             # GC below this triggers alert
    consistency_danger: float = 0.45    # L_consistency above this triggers alert
    entropy_spike_threshold: float = 0.15  # Entropy increase % that triggers alert

    # Recovery targets (Sattvic state)
    sa_ratio_healthy_min: float = 0.25
    sa_ratio_healthy_max: float = 0.40
    gc_healthy: float = 0.80
    consistency_healthy: float = 0.10

    # Correction parameters
    brake_factor: float = 0.85          # Inertial brake strength
    alpha_decay: float = 0.90           # Alpha reduction per alert
    alpha_min: float = 0.30             # Minimum alpha floor
    kp_boost: float = 0.05              # PID Kp increase per alert


class SovereignAlertMonitor:
    """
    Sovereign Alert & Auto-Pivot Logic.

    Monitors training stability using Patent Formulas B1, U1, S8.
    Triggers "Ontological Lockdown" when Rajasic drift is detected.

    States:
        - STABLE: Normal training, metrics within healthy range
        - ALERT: Warning threshold crossed, monitoring closely
        - LOCKDOWN_ACTIVE: Emergency corrections applied
        - RECOVERING: After lockdown, metrics improving

    Usage:
        monitor = SovereignAlertMonitor()

        # In training loop:
        state, actions = monitor.check(metrics, step)
        if actions:
            for action in actions:
                print(f"  🛠️  {action}")
    """

    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()
        self.state = "STABLE"
        self.lockdown_step = -1
        self.lockdown_count = 0
        self.prev_entropy = None
        self.recovery_streak = 0
        self.alert_history: List[Dict] = []

    def check(
        self,
        metrics: Dict[str, float],
        step: int,
        controller: Optional[object] = None,  # PIDv2 controller
        gradient_scaler: Optional[object] = None,  # HierarchicalGradientScaler
    ) -> Tuple[str, List[str]]:
        """
        Check metrics and trigger alerts/corrections as needed.

        Args:
            metrics: Dict with keys:
                - sa_ratio: Sensory/Authority gradient ratio
                - guna_coherence or gc: Global coherence score
                - l_consistency: Consistency Lagrangian value
                - entropy: Token entropy
            step: Current training step
            controller: Optional PIDv2 controller for Kp adjustment
            gradient_scaler: Optional HGS for alpha adjustment

        Returns:
            tuple: (state, list of action strings)
        """
        actions = []

        # Extract metrics with defaults
        sa_ratio = metrics.get('sa_ratio', metrics.get('s_a_ratio', 0.35))
        gc = metrics.get('guna_coherence', metrics.get('gc', metrics.get('coherence', 0.5)))
        consistency = metrics.get('l_consistency', 0.0)
        entropy = metrics.get('entropy', 0.0)

        # Check for Rajasic spike conditions
        is_sa_danger = sa_ratio > self.config.sa_ratio_danger
        is_gc_danger = gc < self.config.gc_danger
        is_consistency_danger = consistency > self.config.consistency_danger

        # Check entropy spike
        is_entropy_spike = False
        if self.prev_entropy is not None and self.prev_entropy > 0:
            entropy_change = (entropy - self.prev_entropy) / self.prev_entropy
            is_entropy_spike = entropy_change > self.config.entropy_spike_threshold
        self.prev_entropy = entropy

        # Determine if lockdown is needed
        danger_count = sum([is_sa_danger, is_gc_danger, is_consistency_danger, is_entropy_spike])

        if danger_count >= 2 or (is_sa_danger and is_gc_danger):
            # TRIGGER LOCKDOWN
            if self.state != "LOCKDOWN_ACTIVE":
                self.state = "LOCKDOWN_ACTIVE"
                self.lockdown_step = step
                self.lockdown_count += 1

                # Log the alert
                alert_info = {
                    "step": step,
                    "sa_ratio": sa_ratio,
                    "gc": gc,
                    "consistency": consistency,
                    "entropy": entropy,
                    "triggers": {
                        "sa_danger": is_sa_danger,
                        "gc_danger": is_gc_danger,
                        "consistency_danger": is_consistency_danger,
                        "entropy_spike": is_entropy_spike,
                    }
                }
                self.alert_history.append(alert_info)

                actions.append(
                    f"⚠️  [SOVEREIGN ALERT] Logic Drift Detected! "
                    f"S/A: {sa_ratio:.2f} | GC: {gc:.2f} | L_cons: {consistency:.3f}"
                )

                # Action 1: Apply S8 Inertial Brake via controller
                if controller is not None and hasattr(controller, 'apply_brake'):
                    controller.apply_brake(self.config.brake_factor)
                    actions.append(f"ACTION: Applying S8 Brake (factor={self.config.brake_factor})")

                # Action 2: Reduce alpha_sens_max to restore Authority dominance
                if gradient_scaler is not None and hasattr(gradient_scaler, 'alpha_sens_max'):
                    old_alpha = gradient_scaler.alpha_sens_max
                    new_alpha = max(old_alpha * self.config.alpha_decay, self.config.alpha_min)
                    gradient_scaler.alpha_sens_max = new_alpha
                    actions.append(f"ACTION: Alpha_Max {old_alpha:.2f} -> {new_alpha:.2f}")

                # Action 3: Increase PID Kp to stiffen the "Spine"
                if controller is not None and hasattr(controller, 'Kp'):
                    old_kp = controller.Kp
                    controller.Kp = min(old_kp + self.config.kp_boost, 0.50)
                    actions.append(f"ACTION: Kp {old_kp:.2f} -> {controller.Kp:.2f}")

            self.recovery_streak = 0

        elif self.state == "LOCKDOWN_ACTIVE":
            # Check if we're recovering
            is_recovering = (
                sa_ratio <= self.config.sa_ratio_healthy_max and
                gc >= self.config.gc_danger * 1.5  # At least 50% better than danger
            )

            if is_recovering:
                self.recovery_streak += 1
                if self.recovery_streak >= 5:
                    self.state = "RECOVERING"
                    actions.append(f"📈 [RECOVERING] Metrics improving after lockdown")
            else:
                self.recovery_streak = 0

        elif self.state == "RECOVERING":
            # Check if fully recovered to Sattvic state
            is_sattvic = (
                self.config.sa_ratio_healthy_min <= sa_ratio <= self.config.sa_ratio_healthy_max and
                gc >= self.config.gc_healthy and
                consistency <= self.config.consistency_healthy
            )

            if is_sattvic:
                self.state = "STABLE"
                actions.append(f"✅ [STABLE] Sattvic state restored at step {step}")
            elif danger_count >= 2:
                # Relapse back to lockdown
                self.state = "LOCKDOWN_ACTIVE"
                self.lockdown_step = step
                self.lockdown_count += 1
                actions.append(f"⚠️  [RELAPSE] Returning to lockdown mode")

        elif danger_count == 1:
            # Single danger indicator - just alert
            if self.state == "STABLE":
                self.state = "ALERT"
                trigger = (
                    "S/A" if is_sa_danger else
                    "GC" if is_gc_danger else
                    "Consistency" if is_consistency_danger else
                    "Entropy"
                )
                actions.append(f"⚡ [ALERT] {trigger} approaching danger zone")
        else:
            # All metrics healthy
            if self.state == "ALERT":
                self.state = "STABLE"

        return self.state, actions

    def get_status_indicator(self) -> str:
        """Get emoji/text indicator for current state."""
        indicators = {
            "STABLE": "🟢 STABLE",
            "ALERT": "🟡 ALERT",
            "LOCKDOWN_ACTIVE": "🔴 LOCKDOWN",
            "RECOVERING": "🟠 RECOVERING",
        }
        return indicators.get(self.state, self.state)

    def get_summary(self) -> str:
        """Get summary of alert history."""
        return (
            f"Sovereign Alert Summary:\n"
            f"  Current State: {self.get_status_indicator()}\n"
            f"  Total Lockdowns: {self.lockdown_count}\n"
            f"  Alerts Logged: {len(self.alert_history)}"
        )

    def format_log_line(
        self,
        step: int,
        metrics: Dict[str, float],
    ) -> str:
        """
        Format a log line with Sovereign Alert indicators.

        Returns formatted string like:
            "Step 1530 | ... | S/A:0.67! | Coh: 0.243 [🔴 LOCKDOWN]"
        """
        sa_ratio = metrics.get('sa_ratio', metrics.get('s_a_ratio', 0.35))
        gc = metrics.get('guna_coherence', metrics.get('gc', metrics.get('coherence', 0.5)))

        # Add warning indicators
        sa_indicator = "!" if sa_ratio > self.config.sa_ratio_danger else "~" if sa_ratio > self.config.sa_ratio_healthy_max else ""
        gc_indicator = "!" if gc < self.config.gc_danger else "~" if gc < self.config.gc_healthy else ""

        return f"S/A:{sa_ratio:.2f}{sa_indicator} | Coh:{gc:.3f}{gc_indicator} [{self.get_status_indicator()}]"


# =============================================================================
# SEMANTIC ENTROPY - Patent S5
# =============================================================================

@torch.no_grad()
def compute_semantic_entropy(logits: torch.Tensor) -> float:
    """
    [Patent S5] Calculate Shannon Entropy of the token distribution.

    Measures the "mental clarity" of the model:
    - Low entropy (0.1-0.4): Crystal clarity, high confidence (ideal for code)
    - Medium entropy (0.4-0.7): Balanced exploration (good for prose)
    - High entropy (>0.7): Dissolution/Nidra - model is confused

    Args:
        logits: Model output logits [B, Seq, Vocab]

    Returns:
        Mean semantic entropy value (normalized to [0, 1])
    """
    # Compute softmax probabilities
    probs = F.softmax(logits, dim=-1)

    # Shannon entropy: H = -sum(p * log(p))
    # Add epsilon to prevent log(0)
    entropy = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)

    # Normalize by max possible entropy (log(vocab_size))
    vocab_size = logits.shape[-1]
    max_entropy = math.log(vocab_size)
    normalized_entropy = entropy / max_entropy

    return normalized_entropy.mean().item()


def get_entropy_status(entropy: float) -> Tuple[str, str]:
    """
    Get status indicator and description for entropy value.

    Args:
        entropy: Normalized entropy value (0-1)

    Returns:
        tuple: (emoji_indicator, status_name)
    """
    if entropy < 0.30:
        return "🔵", "SATTVIC"  # Crystal clarity
    elif entropy < 0.50:
        return "🟢", "FOCUSED"  # High precision
    elif entropy < 0.70:
        return "🟡", "BALANCED"  # Creative exploration
    elif entropy < 0.85:
        return "🟠", "RAJASIC"  # Getting confused
    else:
        return "🔴", "NIDRA"  # Collapse/dissolution


@dataclass
class S8BrakeState:
    """Tracks the S8 Stability Constraint brake state."""
    brake_intensity: float = 1.0  # 1.0 = no brake, <1.0 = braking
    entropy_history: List[float] = None
    brake_active_steps: int = 0
    last_delta_h: float = 0.0

    def __post_init__(self):
        if self.entropy_history is None:
            self.entropy_history = []


class S8StabilityHook:
    """
    [Patent S8] Stability Constraint Hook - The "Inertial Brake".

    Monitors entropy rate (dH/dt) and applies corrective braking when
    entropy rises, preventing Rajasic drift and Nidra collapse.

    Usage:
        hook = S8StabilityHook()

        # In training loop:
        brake_intensity = hook.update(current_entropy)
        if brake_intensity < 1.0:
            print(f"S8 Brake Active: {brake_intensity:.2f}")
    """

    def __init__(
        self,
        window_size: int = 5,
        brake_sensitivity: float = 5.0,
        max_brake: float = 0.5,  # Maximum braking (50% reduction)
        recovery_rate: float = 0.1,  # How fast brake releases
    ):
        self.window_size = window_size
        self.brake_sensitivity = brake_sensitivity
        self.max_brake = max_brake
        self.recovery_rate = recovery_rate
        self.state = S8BrakeState()

    def update(self, current_entropy: float) -> float:
        """
        Update brake state based on current entropy.

        Args:
            current_entropy: Current semantic entropy value

        Returns:
            brake_intensity: 1.0 = no brake, <1.0 = braking active
        """
        self.state.entropy_history.append(current_entropy)

        # Keep only window_size entries
        if len(self.state.entropy_history) > self.window_size:
            self.state.entropy_history.pop(0)

        # Need at least 2 values to compute delta
        if len(self.state.entropy_history) < 2:
            return self.state.brake_intensity

        # Compute entropy rate (dH/dt)
        prev_entropy = self.state.entropy_history[-2]
        delta_h = current_entropy - prev_entropy
        self.state.last_delta_h = delta_h

        if delta_h > 0:
            # Entropy rising - apply brake
            brake_amount = min(delta_h * self.brake_sensitivity, self.max_brake)
            self.state.brake_intensity = max(1.0 - self.max_brake, self.state.brake_intensity - brake_amount)
            self.state.brake_active_steps += 1
        else:
            # Entropy stable/falling - release brake
            self.state.brake_intensity = min(1.0, self.state.brake_intensity + self.recovery_rate)
            if self.state.brake_intensity >= 0.99:
                self.state.brake_active_steps = 0

        return self.state.brake_intensity

    def get_status(self) -> str:
        """Get formatted status string for S8 brake."""
        if self.state.brake_intensity >= 0.99:
            return "STABLE"
        elif self.state.brake_intensity >= 0.85:
            return "LIGHT"
        elif self.state.brake_intensity >= 0.70:
            return "MODERATE"
        else:
            return "HEAVY"

    def format_log(self) -> str:
        """Format brake status for log line."""
        ent_icon, ent_status = get_entropy_status(
            self.state.entropy_history[-1] if self.state.entropy_history else 0.5
        )
        return (
            f"Brake:{self.state.brake_intensity:.2f} [{self.get_status()}] | "
            f"dH/dt:{self.state.last_delta_h:+.3f}"
        )


def format_sovereign_dashboard(
    step: int,
    loss: float,
    ppl: float,
    entropy: float,
    coherence: float,
    sa_ratio: float,
    brake_intensity: float = 1.0,
    kp: float = None,
    alert_state: str = "STABLE",
) -> str:
    """
    Format the complete Sovereign Dashboard log line.

    Combines all patent metrics into a single high-density status line.

    Args:
        step: Training step
        loss: Current loss value
        ppl: Perplexity
        entropy: Semantic entropy (S5)
        coherence: Guna coherence (U1)
        sa_ratio: Sensory/Authority ratio (1331)
        brake_intensity: S8 brake value (1.0 = no brake)
        kp: Optional PIDv2 Kp value
        alert_state: Current alert state

    Returns:
        Formatted log string
    """
    # Get entropy status
    ent_icon, ent_status = get_entropy_status(entropy)

    # Get coherence status
    if coherence > 0.85:
        coh_status = "SATTVIC"
    elif coherence > 0.65:
        coh_status = "ALIGNED"
    else:
        coh_status = "RAJASIC"

    # Get S/A status
    if sa_ratio < 0.25:
        sa_indicator = ""
    elif sa_ratio < 0.40:
        sa_indicator = "~"
    elif sa_ratio < 0.55:
        sa_indicator = "!"
    else:
        sa_indicator = "!!"

    # Get brake status
    if brake_intensity >= 0.99:
        brake_status = ""
    elif brake_intensity >= 0.85:
        brake_status = " [LIGHT]"
    elif brake_intensity >= 0.70:
        brake_status = " [MODERATE]"
    else:
        brake_status = " [HEAVY]"

    # Build the dashboard line
    parts = [
        f"Step {step:>5}",
        f"Loss:{loss:.3f}",
        f"PPL:{ppl:>6.1f}",
        f"Ent:{entropy:.2f}{ent_icon}",
        f"Coh:{coherence:.2f}[{coh_status}]",
        f"S/A:{sa_ratio:.2f}{sa_indicator}",
        f"Brake:{brake_intensity:.2f}{brake_status}",
    ]

    if kp is not None:
        parts.append(f"Kp:{kp:.2f}")

    # Add alert state indicator
    alert_icons = {
        "STABLE": "🟢",
        "ALERT": "🟡",
        "LOCKDOWN_ACTIVE": "🔴",
        "RECOVERING": "🟠",
    }
    parts.append(f"[{alert_icons.get(alert_state, '')} {alert_state}]")

    return " | ".join(parts)
