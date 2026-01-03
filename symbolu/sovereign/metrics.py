"""
Sovereign Metrics Module - The "Nervous System" of Sovereign-1.

Provides real-time health monitoring for the Sovereign training process.
Calculates alignment between model's high-level intent and low-level output.
"""

import torch
import torch.nn.functional as F


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
