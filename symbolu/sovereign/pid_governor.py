"""
Sovereign-1 PID Governor: Control-Theoretic Gating
===================================================

The PID Governor is the "brakes" of the Sovereign-1 architecture.
It intercepts the flow between transformer layers and applies dampening
based on state dissonance (error between current and target state).

Key Features:
- Vritti-based dynamic PID tuning (adapts Kp/Ki/Kd to cognitive state)
- Authority score computation for soft gating
- Semantic body dampening when authority is low
- Streaming support via stateful PID error tracking

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 2.4.1
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class PIDGovernorConfig:
    """Configuration for PID Governor."""

    # Default PID parameters
    default_kp: float = 0.65  # Proportional gain
    default_ki: float = 0.10  # Integral gain
    default_kd: float = 0.25  # Derivative gain

    # Authority threshold for dampening
    authority_threshold: float = 0.7
    dampening_factor: float = 0.1

    # State partition layout
    semantic_dim: int = 896
    state_dim: int = 128

    # R-Signal range within state [48:96]
    r_signal_start: int = 48
    r_signal_end: int = 96


class PIDGovernor(nn.Module):
    """
    Control-theoretic gating between Quadratic and Phase layers.

    Uses Vritti-based dynamic tuning of PID parameters based on
    the R-Signal (ontological state) to adapt control behavior.

    The Governor applies "brakes" when the model's state deviates
    significantly from the target state computed by the Observer.
    """

    # Vritti → PID Parameter Lookup Table
    # Vritti types represent different cognitive modes
    VRITTI_PID_TABLE = {
        "pramana": {"Kp": 0.90, "Ki": 0.05, "Kd": 0.05},    # Valid cognition - High stiffness
        "viparyaya": {"Kp": 0.70, "Ki": 0.15, "Kd": 0.15},  # Misperception - Corrective
        "vikalpa": {"Kp": 0.30, "Ki": 0.10, "Kd": 0.60},    # Creative/imaginative - Low stiffness
        "smrti": {"Kp": 0.50, "Ki": 0.40, "Kd": 0.10},      # Memory recall - Memory-heavy
        "nidra": {"Kp": 0.20, "Ki": 0.70, "Kd": 0.10},      # Dormancy/idle - High integral
    }

    # Ontology layer to Vritti mapping (12 Bhavas × 4 dims each in R-Signal)
    # Grouped by dominant cognitive mode
    ONTOLOGY_VRITTI_MAP = {
        0: "pramana",    # FACTUAL - Valid cognition
        1: "pramana",    # ANALYTICAL - Valid cognition
        2: "viparyaya",  # EVALUATIVE - Subject to error
        3: "vikalpa",    # NARRATIVE - Creative mode
        4: "pramana",    # ARGUMENTATIVE - Logical
        5: "pramana",    # INSTRUCTIVE - Factual delivery
        6: "pramana",    # CERTAIN - High confidence
        7: "vikalpa",    # SPECULATIVE - Creative exploration
        8: "viparyaya",  # QUESTIONING - Uncertainty
        9: "smrti",      # POSITIVE - Emotional memory
        10: "smrti",     # NEGATIVE - Emotional memory
        11: "nidra",     # NEUTRAL - Low activity
    }

    def __init__(
        self,
        config: Optional[PIDGovernorConfig] = None,
        embed_dim: int = 1024,
    ):
        super().__init__()
        self.config = config or PIDGovernorConfig()
        self.embed_dim = embed_dim

        # Learnable baseline adjustments
        self.kp_adjust = nn.Parameter(torch.zeros(1))
        self.ki_adjust = nn.Parameter(torch.zeros(1))
        self.kd_adjust = nn.Parameter(torch.zeros(1))

        # Internal state (for non-streaming mode)
        self.register_buffer('_integral_error', None)
        self.register_buffer('_prev_error', None)

    def reset_state(self):
        """Reset PID internal state (for sequence boundaries)."""
        self._integral_error = None
        self._prev_error = None

    def _detect_dominant_vritti(self, r_signal: torch.Tensor) -> str:
        """
        Detect dominant Vritti from R-Signal.

        R-Signal is [B, (N,) 48] representing 12 Bhavas × 4 dims each.
        Returns the Vritti type for the dominant ontology layer.
        """
        # Handle different input shapes
        if r_signal.dim() == 3:
            # [B, N, 48] - use sequence-level representation
            r_signal = r_signal.mean(dim=1)  # [B, 48]

        # Reshape to [B, 12, 4] and get Bhava activations
        B = r_signal.shape[0]
        bhava_activations = r_signal.view(B, 12, 4).mean(dim=-1)  # [B, 12]

        # Get dominant Bhava index (batch-wise majority)
        dominant_idx = bhava_activations.mean(dim=0).argmax().item()

        # Map to Vritti
        return self.ONTOLOGY_VRITTI_MAP.get(dominant_idx, "pramana")

    def _get_pid_params(self, vritti: str) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Get PID parameters for detected Vritti with learnable adjustments."""
        params = self.VRITTI_PID_TABLE.get(vritti, {
            "Kp": self.config.default_kp,
            "Ki": self.config.default_ki,
            "Kd": self.config.default_kd,
        })

        # Apply learnable adjustments (clamped to valid range)
        kp = torch.clamp(params["Kp"] + self.kp_adjust, 0.1, 1.0)
        ki = torch.clamp(params["Ki"] + self.ki_adjust, 0.01, 0.9)
        kd = torch.clamp(params["Kd"] + self.kd_adjust, 0.01, 0.9)

        return kp, ki, kd

    def _extract_state_partition(
        self,
        x: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Extract semantic body and state partition from hidden states.

        Input: [B, N, D] where D = 1024 (896 semantic + 128 state)
        Returns: (semantic_body [B, N, 896], state [B, N, 128])
        """
        semantic_dim = self.config.semantic_dim

        if x.shape[-1] <= semantic_dim:
            # No state partition, pad with zeros
            semantic_body = x
            state = torch.zeros(
                x.shape[0], x.shape[1], self.config.state_dim,
                device=x.device, dtype=x.dtype
            )
        else:
            semantic_body = x[..., :semantic_dim]
            state = x[..., semantic_dim:]

        return semantic_body, state

    def forward(
        self,
        x: torch.Tensor,
        target_state: torch.Tensor,
        pid_state: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Apply PID control to gate attention output.

        Args:
            x: [B, N, D] - Hidden states from quadratic layers (D=1024)
            target_state: [B, N, 128] - Target state delta from Observer
            pid_state: Optional (integral_error, prev_error) for streaming

        Returns:
            x_out: [B, N, D] - Potentially dampened hidden states
            authority: [B, N] - Authority scores for telemetry
            pid_state: (integral_error, prev_error) for streaming continuity
        """
        B, N, D = x.shape
        device = x.device

        # Extract semantic body and current state
        semantic_body, current_state = self._extract_state_partition(x)

        # Ensure target_state has correct shape
        if target_state.dim() == 2:
            target_state = target_state.unsqueeze(1).expand(-1, N, -1)

        # Compute error (dissonance) as 1 - cosine similarity
        # High error = high dissonance from target
        error = 1.0 - F.cosine_similarity(
            current_state, target_state, dim=-1
        )  # [B, N]

        # Extract R-Signal for Vritti detection [48:96]
        r_start = self.config.r_signal_start
        r_end = self.config.r_signal_end
        r_signal = current_state[..., r_start:r_end]  # [B, N, 48]

        # Detect Vritti and get PID parameters
        vritti = self._detect_dominant_vritti(r_signal)
        Kp, Ki, Kd = self._get_pid_params(vritti)

        # Initialize or restore PID state
        if pid_state is not None:
            integral_error, prev_error = pid_state
        elif self._integral_error is not None:
            integral_error = self._integral_error
            prev_error = self._prev_error
        else:
            integral_error = torch.zeros(B, N, device=device)
            prev_error = torch.zeros(B, N, device=device)

        # Ensure shapes match
        if integral_error.shape != error.shape:
            integral_error = torch.zeros_like(error)
            prev_error = torch.zeros_like(error)

        # PID computation
        P = Kp * error
        I = Ki * (integral_error + error)
        D = Kd * (error - prev_error)

        # Update state for next iteration
        new_integral_error = integral_error + error
        new_prev_error = error.clone()

        # Store for non-streaming mode
        self._integral_error = new_integral_error.detach()
        self._prev_error = new_prev_error.detach()

        # Compute authority score: higher authority = more trust
        # Authority = 1 - PID_output (clamped to [0, 1])
        pid_output = (P + I + D).clamp(0, 2)  # Allow overshoot
        authority = (1.0 - pid_output / 2.0).clamp(0, 1)  # [B, N]

        # Gating mechanism: dampen semantic body when authority is low
        damping_mask = (authority < self.config.authority_threshold)  # [B, N]
        damping_mask = damping_mask.unsqueeze(-1)  # [B, N, 1]

        # Apply dampening to semantic body only (preserve state partition)
        dampened_semantic = torch.where(
            damping_mask.expand_as(semantic_body),
            semantic_body * self.config.dampening_factor,
            semantic_body,
        )

        # Reconstruct output
        if D > self.config.semantic_dim:
            x_out = torch.cat([dampened_semantic, current_state], dim=-1)
        else:
            x_out = dampened_semantic

        return x_out, authority, (new_integral_error, new_prev_error)

    def get_diagnostics(self) -> Dict[str, float]:
        """Get diagnostic information about PID state."""
        diagnostics = {}

        if self._integral_error is not None:
            diagnostics["integral_error_mean"] = self._integral_error.mean().item()
            diagnostics["integral_error_max"] = self._integral_error.max().item()

        if self._prev_error is not None:
            diagnostics["prev_error_mean"] = self._prev_error.mean().item()

        diagnostics["kp_adjust"] = self.kp_adjust.item()
        diagnostics["ki_adjust"] = self.ki_adjust.item()
        diagnostics["kd_adjust"] = self.kd_adjust.item()

        return diagnostics


class EmergencyBrake(nn.Module):
    """
    Emergency PD controller for catastrophic deviation.

    Simpler than full PID - used when model is in crisis
    (e.g., hallucination spiral, coherence collapse).
    """

    def __init__(
        self,
        kp: float = 0.8,
        kd: float = 0.3,
        emergency_threshold: float = 0.9,
    ):
        super().__init__()
        self.kp = kp
        self.kd = kd
        self.emergency_threshold = emergency_threshold
        self.register_buffer('_prev_error', None)

    def forward(
        self,
        x: torch.Tensor,
        target_state: torch.Tensor,
    ) -> Tuple[torch.Tensor, bool]:
        """
        Apply emergency braking if needed.

        Returns:
            x_out: Potentially zeroed output
            emergency_triggered: Whether emergency was triggered
        """
        # Simple error computation
        error = 1.0 - F.cosine_similarity(
            x[..., -128:], target_state, dim=-1
        ).mean()

        # Check for emergency
        emergency = error > self.emergency_threshold

        if emergency:
            # Hard brake: zero out semantic content
            x_out = x.clone()
            x_out[..., :-128] *= 0.01  # Near-zero semantic
            return x_out, True

        return x, False
