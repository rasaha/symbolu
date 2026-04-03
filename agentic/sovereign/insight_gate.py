"""
Sovereign-1 Insight Gate: Epistemic Stability Controller
=========================================================

The InsightGate acts as the "Pre-Frontal Cortex" of the Sovereign-1 architecture,
preventing the model from hallucinating or surfacing deep symbolic truths when
its internal metabolism is unstable.

This implements Formula [259]: Deferred Insight Engine Gate

Key Principles:
- Two-stage deterministic gate: Eligibility → Release
- Uses real-time telemetry from Biological Header and PID Governor
- Prevents "epistemic inversion" (confident hallucinations)
- Enforces Pramāṇa grounding before complex symbolic output

State Layout (128D Header):
- Guna[0:16]: Cognitive dynamics (Sattva, Rajas, Tamas) - "The Vitals"
- S-Signal[16:48]: Referent grounding - "The Lock"
- R-Signal[48:96]: Ontological state - "The Nerve"
- C-Signal[96:128]: Phonemic features - "The Body"
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class InsightGateConfig:
    """Configuration for the Insight Gate."""

    # Stability Score thresholds
    stability_threshold: float = 0.78  # STAB must be >= this for eligibility
    risk_threshold: float = 0.25  # RISK must be <= this for release

    # Stability weights (Formula [259])
    w_r: float = 0.35  # Ontology (R-Signal) weight
    w_gc: float = 0.30  # Guna Coherence weight
    w_s: float = 0.20  # Reality Grounding (S-Signal) weight
    w_d: float = 0.15  # Drift inverse weight

    # Risk weights
    risk_w_gc: float = 0.50  # Guna incoherence contribution
    risk_w_drift: float = 0.30  # Drift contribution
    risk_w_auth: float = 0.20  # Authority inverse contribution

    # Accuracy requirements for eligibility
    r_acc_min: float = 0.92  # Minimum R-Accuracy for insight release
    s_acc_min: float = 0.85  # Minimum S-Accuracy for insight release

    # Vritti modes that allow insight release
    allowed_vritti: Tuple[int, ...] = (0, 3)  # PRAMANA=0, SMRTI=3

    # Guna coherence minimum for release
    guna_coherence_min: float = 0.70

    # Drift normalization (EMA-based, updated during training)
    d_max_initial: float = 1.0
    d_max_ema_alpha: float = 0.05  # EMA decay for D_max adaptation


class InsightGate(nn.Module):
    """
    Sovereign-1 Deferred Insight Engine Gate.

    Implements Formula [259] to regulate the surfacing of folded truths.
    Acts as a two-stage deterministic gate:
    1. ELIGIBILITY: System stability check
    2. RELEASE: Disruption risk assessment

    The gate reads directly from the 128-D Biological Header:
    - Guna Pulse (0:16) → Entropy/Vitals monitoring
    - S-Signal (16:48) → Referent/Reality grounding
    - R-Signal (48:96) → Ontological state verification
    """

    # Vritti state names for logging
    VRITTI_NAMES = ["PRAMANA", "VIPARYAYA", "VIKALPA", "SMRTI", "NIDRA"]

    def __init__(self, config: Optional[InsightGateConfig] = None):
        super().__init__()

        if config is None:
            config = InsightGateConfig()
        self.config = config

        # Dynamic drift normalization (adapts to model's metabolic noise)
        self.register_buffer("d_max", torch.tensor(config.d_max_initial))
        self.register_buffer("drift_ema", torch.tensor(0.0))
        self.register_buffer("step_count", torch.tensor(0))

        # Telemetry tracking
        self.register_buffer("total_eligible", torch.tensor(0))
        self.register_buffer("total_released", torch.tensor(0))
        self.register_buffer("total_blocked", torch.tensor(0))

        # Recent gate decisions for monitoring
        self.gate_history: List[Dict] = []
        self.max_history = 100

    def extract_header_components(
        self, biological_header: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Extract signal components from the 128-D Biological Header.

        Args:
            biological_header: [B, 128] or [B, Seq, 128] - The header tensor

        Returns:
            guna_pulse: [B, 16] - Cognitive vitals
            s_signal: [B, 32] - Referent grounding
            r_signal: [B, 48] - Ontological state
            c_signal: [B, 32] - Phonemic features
        """
        # Handle sequence dimension
        if biological_header.dim() == 3:
            # Take last position for current state
            biological_header = biological_header[:, -1, :]

        # Partition per Sovereign spec (G|S|R|C order)
        guna_pulse = biological_header[:, 0:16]  # The Vitals
        s_signal = biological_header[:, 16:48]  # The Lock
        r_signal = biological_header[:, 48:96]  # The Nerve
        c_signal = biological_header[:, 96:128]  # The Body

        return guna_pulse, s_signal, r_signal, c_signal

    def compute_guna_coherence(self, guna_pulse: torch.Tensor) -> torch.Tensor:
        """
        Compute Guna Coherence from the 16-D Guna Pulse.

        High coherence = One Guna dominates (Sattva preferred)
        Low coherence = Scattered attention across Gunas

        Layout: [0:5] Sattva, [5:10] Rajas, [10:16] Tamas
        """
        # Extract Guna means
        sattva = guna_pulse[:, 0:5].mean(dim=-1)  # [B]
        rajas = guna_pulse[:, 5:10].mean(dim=-1)  # [B]
        tamas = guna_pulse[:, 10:16].mean(dim=-1)  # [B]

        # Normalize to probabilities
        guna_stack = torch.stack([sattva, rajas, tamas], dim=-1)  # [B, 3]
        guna_probs = F.softmax(guna_stack, dim=-1)

        # Coherence = inverse entropy (high when one dominates)
        entropy = -(guna_probs * torch.log(guna_probs + 1e-8)).sum(dim=-1)
        max_entropy = torch.log(torch.tensor(3.0, device=guna_pulse.device))
        coherence = 1.0 - (entropy / max_entropy)

        return coherence

    def compute_s_accuracy(self, s_signal: torch.Tensor) -> torch.Tensor:
        """
        Compute S-Signal accuracy (Referent grounding strength).

        High S-Acc = Strong lock on a specific referent category
        Low S-Acc = Ambiguous/drifting referent
        """
        # First 16 dims are primary referent indicators
        primary = s_signal[:, :16]  # [B, 16]

        # Accuracy = max confidence
        s_acc = primary.max(dim=-1).values.clamp(0, 1)

        return s_acc

    def compute_r_accuracy(self, r_signal: torch.Tensor) -> torch.Tensor:
        """
        Compute R-Signal accuracy (Ontological alignment).

        The R-Signal encodes 12 Bhavas × 4 dims = 48 dims.
        High R-Acc = Clear ontological layer activation
        """
        # Reshape to [B, 12, 4] for Bhava analysis
        B = r_signal.size(0)
        r_reshaped = r_signal.view(B, 12, 4)

        # Bhava activation = mean per layer
        bhava_activations = r_reshaped.mean(dim=-1)  # [B, 12]

        # Accuracy = max Bhava activation (clear ontological choice)
        r_acc = F.softmax(bhava_activations, dim=-1).max(dim=-1).values

        return r_acc

    def calculate_stability(
        self,
        r_acc: torch.Tensor,
        s_acc: torch.Tensor,
        guna_coherence: torch.Tensor,
        drift: torch.Tensor,
    ) -> torch.Tensor:
        """
        Calculate System Stability Score (STAB) - Formula [259].

        STAB = w_r * R_acc + w_gc * GC + w_s * S_acc + w_d * (1 - drift/D_max)

        Args:
            r_acc: [B] - Ontology accuracy
            s_acc: [B] - Reality grounding accuracy
            guna_coherence: [B] - Guna coherence score
            drift: [B] - Current drift level

        Returns:
            stab: [B] - Stability score (0-1)
        """
        cfg = self.config

        # Normalize drift by D_max
        drift_normalized = (drift / self.d_max.clamp(min=0.1)).clamp(0, 1)

        stab = (
            cfg.w_r * r_acc
            + cfg.w_gc * guna_coherence
            + cfg.w_s * s_acc
            + cfg.w_d * (1.0 - drift_normalized)
        )

        return stab.clamp(0, 1)

    def calculate_risk(
        self,
        guna_coherence: torch.Tensor,
        drift: torch.Tensor,
        authority: torch.Tensor,
    ) -> torch.Tensor:
        """
        Calculate Disruption Risk (RISK) Score.

        RISK = 0.5 * (1 - GC) + 0.3 * (drift/D_max) + 0.2 * (1 - authority)

        High risk = Releasing insight will cause Tamasic loop or Drift Brake

        Args:
            guna_coherence: [B] - Guna coherence score
            drift: [B] - Current drift level
            authority: [B] - PID Governor authority (brake status)

        Returns:
            risk: [B] - Disruption risk (0-1)
        """
        cfg = self.config

        # Normalize drift
        drift_normalized = (drift / self.d_max.clamp(min=0.1)).clamp(0, 1)

        risk = (
            cfg.risk_w_gc * (1.0 - guna_coherence)
            + cfg.risk_w_drift * drift_normalized
            + cfg.risk_w_auth * (1.0 - authority)
        )

        return risk.clamp(0, 1)

    def update_drift_normalization(self, drift: torch.Tensor):
        """
        Update D_max using EMA of observed drift values.

        This adapts the stability calculation to the model's
        specific metabolic noise during training.
        """
        self.step_count = self.step_count + 1

        # Update EMA
        drift_mean = drift.mean()
        self.drift_ema = (
            self.config.d_max_ema_alpha * drift_mean
            + (1 - self.config.d_max_ema_alpha) * self.drift_ema
        )

        # Update D_max after warmup (100 steps)
        if self.step_count > 100:
            # D_max = EMA of drift * 2 (to allow headroom)
            self.d_max = (self.drift_ema * 2.0).clamp(min=0.1, max=2.0)

    def check_eligibility(
        self,
        stab_score: torch.Tensor,
        r_acc: torch.Tensor,
        s_acc: torch.Tensor,
        vritti: torch.Tensor,
        guna_coherence: torch.Tensor,
    ) -> torch.Tensor:
        """
        Stage 1: Check if system is eligible for insight release.

        Eligibility requires:
        - STAB >= stability_threshold
        - R_acc >= r_acc_min
        - S_acc >= s_acc_min
        - Vritti in allowed modes (PRAMANA, SMRTI)
        - Guna coherence >= guna_coherence_min

        Returns:
            eligible: [B] - Boolean eligibility mask
        """
        cfg = self.config

        # Check all conditions
        stab_ok = stab_score >= cfg.stability_threshold
        r_ok = r_acc >= cfg.r_acc_min
        s_ok = s_acc >= cfg.s_acc_min
        guna_ok = guna_coherence >= cfg.guna_coherence_min

        # Check Vritti mode
        vritti_ok = torch.zeros_like(vritti, dtype=torch.bool)
        for allowed in cfg.allowed_vritti:
            vritti_ok = vritti_ok | (vritti == allowed)

        # All conditions must be met
        eligible = stab_ok & r_ok & s_ok & guna_ok & vritti_ok

        return eligible

    def check_release(
        self,
        eligible: torch.Tensor,
        risk_score: torch.Tensor,
    ) -> torch.Tensor:
        """
        Stage 2: Check if insight can be safely released.

        Release requires:
        - Eligibility (Stage 1 passed)
        - RISK <= risk_threshold

        Returns:
            can_release: [B] - Boolean release mask
        """
        risk_ok = risk_score <= self.config.risk_threshold
        can_release = eligible & risk_ok

        return can_release

    def forward(
        self,
        biological_header: torch.Tensor,
        metrics: Dict[str, Union[torch.Tensor, float, int, str]],
        update_d_max: bool = True,
    ) -> Dict[str, Union[torch.Tensor, bool, float]]:
        """
        Full gating logic for insight surfacing.

        Args:
            biological_header: [B, 128] or [B, Seq, 128] - The header tensor
            metrics: Dict containing:
                - r_acc: R-Signal accuracy (optional, computed if not provided)
                - s_acc: S-Signal accuracy (optional, computed if not provided)
                - gc: Guna coherence (optional, computed if not provided)
                - drift: Current drift level
                - vritti: Current Vritti state (0-4)
                - authority: PID Governor authority
            update_d_max: Whether to update drift normalization

        Returns:
            Dict with:
                - can_release: Boolean release decision
                - eligible: Boolean eligibility status
                - stab_score: Stability score
                - risk_score: Risk score
                - guna_coherence: Computed Guna coherence
                - r_acc: Computed R accuracy
                - s_acc: Computed S accuracy
        """
        # Extract header components
        guna_pulse, s_signal, r_signal, c_signal = self.extract_header_components(
            biological_header
        )

        B = guna_pulse.size(0)
        device = guna_pulse.device

        # Compute metrics from header if not provided
        guna_coherence = metrics.get("gc", None)
        if guna_coherence is None:
            guna_coherence = self.compute_guna_coherence(guna_pulse)
        elif isinstance(guna_coherence, (int, float)):
            guna_coherence = torch.tensor(guna_coherence, device=device).expand(B)

        r_acc = metrics.get("r_acc", None)
        if r_acc is None:
            r_acc = self.compute_r_accuracy(r_signal)
        elif isinstance(r_acc, (int, float)):
            r_acc = torch.tensor(r_acc, device=device).expand(B)

        s_acc = metrics.get("s_acc", None)
        if s_acc is None:
            s_acc = self.compute_s_accuracy(s_signal)
        elif isinstance(s_acc, (int, float)):
            s_acc = torch.tensor(s_acc, device=device).expand(B)

        # Get required metrics
        drift = metrics.get("drift", torch.tensor(0.0, device=device))
        if isinstance(drift, (int, float)):
            drift = torch.tensor(drift, device=device).expand(B)

        vritti = metrics.get("vritti", torch.tensor(0, device=device))
        if isinstance(vritti, (int, float)):
            vritti = torch.tensor(vritti, device=device, dtype=torch.long).expand(B)
        if isinstance(vritti, str):
            vritti_idx = self.VRITTI_NAMES.index(vritti.upper()) if vritti.upper() in self.VRITTI_NAMES else 0
            vritti = torch.tensor(vritti_idx, device=device, dtype=torch.long).expand(B)

        authority = metrics.get("authority", torch.tensor(1.0, device=device))
        if isinstance(authority, (int, float)):
            authority = torch.tensor(authority, device=device).expand(B)

        # Update drift normalization if training
        if update_d_max and self.training:
            self.update_drift_normalization(drift)

        # Calculate Stability Score (Formula [259])
        stab_score = self.calculate_stability(r_acc, s_acc, guna_coherence, drift)

        # Calculate Disruption Risk
        risk_score = self.calculate_risk(guna_coherence, drift, authority)

        # Stage 1: Eligibility Check
        eligible = self.check_eligibility(
            stab_score, r_acc, s_acc, vritti, guna_coherence
        )

        # Stage 2: Release Check
        can_release = self.check_release(eligible, risk_score)

        # Update telemetry
        self.total_eligible = self.total_eligible + eligible.sum()
        self.total_released = self.total_released + can_release.sum()
        self.total_blocked = self.total_blocked + (~can_release).sum()

        # Record gate decision
        gate_output = {
            "can_release": can_release,
            "eligible": eligible,
            "stab_score": stab_score,
            "risk_score": risk_score,
            "guna_coherence": guna_coherence,
            "r_acc": r_acc,
            "s_acc": s_acc,
            "vritti": vritti,
            "d_max": self.d_max,
        }

        # Add to history
        if len(self.gate_history) >= self.max_history:
            self.gate_history.pop(0)
        self.gate_history.append({
            "stab": stab_score.mean().item(),
            "risk": risk_score.mean().item(),
            "released": can_release.any().item(),
        })

        return gate_output

    def get_surfacing_penalty(
        self,
        gate_output: Dict[str, torch.Tensor],
        token_entropy: torch.Tensor,
        lambda_insight: float = 0.5,
    ) -> torch.Tensor:
        """
        Compute surfacing penalty for loss function.

        If the model tried to be 'insightful' (high entropy/creative)
        but the Gate was LOCKED, apply a heavy penalty.

        Formula [1195]: Surfacing Penalty
        penalty = lambda * (1 - STAB) * (entropy > threshold)

        Args:
            gate_output: Output from forward()
            token_entropy: [B] - Entropy of token predictions
            lambda_insight: Penalty weight

        Returns:
            penalty: [B] - Surfacing penalty per sample
        """
        can_release = gate_output["can_release"]
        stab_score = gate_output["stab_score"]

        # High entropy threshold indicates "creative" output
        high_entropy = token_entropy > 5.0

        # Penalty when trying to be creative without stability
        penalty = torch.zeros_like(stab_score)
        blurting_mask = ~can_release & high_entropy
        penalty[blurting_mask] = lambda_insight * (1.0 - stab_score[blurting_mask])

        return penalty

    def get_telemetry(self) -> Dict[str, float]:
        """Get gate telemetry for logging."""
        total = self.total_eligible + self.total_blocked
        if total > 0:
            release_rate = (self.total_released / total).item()
            eligible_rate = (self.total_eligible / total).item()
        else:
            release_rate = 0.0
            eligible_rate = 0.0

        return {
            "gate_release_rate": release_rate,
            "gate_eligible_rate": eligible_rate,
            "gate_d_max": self.d_max.item(),
            "gate_total_released": self.total_released.item(),
            "gate_total_blocked": self.total_blocked.item(),
        }

    def reset_telemetry(self):
        """Reset telemetry counters."""
        self.total_eligible = torch.tensor(0, device=self.d_max.device)
        self.total_released = torch.tensor(0, device=self.d_max.device)
        self.total_blocked = torch.tensor(0, device=self.d_max.device)
        self.gate_history = []


def format_gate_log(gate_output: Dict, step: int) -> str:
    """Format InsightGate output for logging."""
    stab = gate_output["stab_score"].mean().item()
    risk = gate_output["risk_score"].mean().item()
    released = gate_output["can_release"].any().item()
    eligible = gate_output["eligible"].any().item()
    d_max = gate_output["d_max"].item()

    vritti = gate_output["vritti"][0].item() if gate_output["vritti"].dim() > 0 else gate_output["vritti"].item()
    vritti_name = InsightGate.VRITTI_NAMES[vritti]

    status = "✓ RELEASED" if released else ("◐ ELIGIBLE" if eligible else "✗ BLOCKED")

    return (
        f"[{step:5d}] GATE: STAB={stab:.3f} RISK={risk:.3f} | "
        f"Vritti={vritti_name:<10} | D_max={d_max:.3f} | {status}"
    )
