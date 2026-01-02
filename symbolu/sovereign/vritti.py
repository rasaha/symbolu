"""
Vritti Intent System - The 5-Mode Cognitive Controller.

The Vritti system transforms the PID Governor from a simple "throttle" into a
"mode-switch" that dynamically alters the physics of the compute graph.

The 5 Vrittis (Mental Modifications from Yoga Sutras):
- Pramāṇa (Truth): Strict logic, rigid stiffness
- Viparyaya (Error): Corrective drift, hard reset
- Vikalpa (Imagination): Creative/narrative, under-damped
- Smṛti (Memory): Contextual recall, integral-heavy
- Nidrā (Dormancy): Filler/transition, inertial
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Tuple, Optional


class VrittiState(IntEnum):
    """The 5 Cognitive Modes."""
    PRAMANA = 0    # Truth/Logic - Strict stiffness
    VIPARYAYA = 1  # Error/Reset - Hard correction
    VIKALPA = 2    # Imagination - Creative/fluid
    SMRITI = 3     # Memory - Recall-heavy
    NIDRA = 4      # Dormancy - Stable filler


@dataclass
class VrittiPhysics:
    """PID coefficients for each Vritti state."""
    kp: float  # Proportional - Stiffness/immediate correction
    ki: float  # Integral - History/accumulation
    kd: float  # Derivative - Trajectory/rate of change

    def as_tensor(self) -> torch.Tensor:
        return torch.tensor([self.kp, self.ki, self.kd])


# The PID Physics Table - Defines "stiffness" of gradients for each mode
VRITTI_PHYSICS: Dict[VrittiState, VrittiPhysics] = {
    VrittiState.PRAMANA:   VrittiPhysics(kp=0.9, ki=0.01, kd=0.01),  # Rigid lock
    VrittiState.VIPARYAYA: VrittiPhysics(kp=0.7, ki=0.2,  kd=0.2),   # Hard reset
    VrittiState.VIKALPA:   VrittiPhysics(kp=0.3, ki=0.05, kd=0.6),   # Fluid/creative
    VrittiState.SMRITI:    VrittiPhysics(kp=0.5, ki=0.4,  kd=0.1),   # Recall-heavy
    VrittiState.NIDRA:     VrittiPhysics(kp=0.2, ki=0.7,  kd=0.01),  # Inertial
}

# Pre-computed tensors for efficient lookup
KP_TABLE = torch.tensor([VRITTI_PHYSICS[VrittiState(i)].kp for i in range(5)])
KI_TABLE = torch.tensor([VRITTI_PHYSICS[VrittiState(i)].ki for i in range(5)])
KD_TABLE = torch.tensor([VRITTI_PHYSICS[VrittiState(i)].kd for i in range(5)])

# Vritti Transition Matrix - Penalty for "Ontological Teleportation"
# Rows = From state, Cols = To state
# Higher value = More penalty for that transition
TRANSITION_PENALTY_MATRIX = torch.tensor([
    #  Pra   Vip   Vik   Smr   Nid
    [0.1,  0.8,  0.9,  0.2,  0.5],  # From Pramāṇa (Truth → Error is bad)
    [0.5,  0.1,  0.5,  0.5,  0.5],  # From Viparyaya (Error can go anywhere)
    [0.7,  0.5,  0.1,  0.3,  0.2],  # From Vikalpa (Imagination → Truth needs anchor)
    [0.2,  0.4,  0.4,  0.1,  0.3],  # From Smṛti (Memory flows naturally)
    [0.9,  0.8,  0.5,  0.2,  0.1],  # From Nidrā (Sleep → Truth is a big jump)
])

# Legal transition probabilities (inverse of penalty for generation)
TRANSITION_PROB_MATRIX = 1.0 - TRANSITION_PENALTY_MATRIX


class VrittiNames:
    """Human-readable names and descriptions."""
    NAMES = {
        VrittiState.PRAMANA: "Pramāṇa",
        VrittiState.VIPARYAYA: "Viparyaya",
        VrittiState.VIKALPA: "Vikalpa",
        VrittiState.SMRITI: "Smṛti",
        VrittiState.NIDRA: "Nidrā",
    }

    DESCRIPTIONS = {
        VrittiState.PRAMANA: "Truth/Logic (Rigid Lock)",
        VrittiState.VIPARYAYA: "Error/Reset (Hard Correction)",
        VrittiState.VIKALPA: "Imagination (Creative Flow)",
        VrittiState.SMRITI: "Memory (Contextual Recall)",
        VrittiState.NIDRA: "Dormancy (Stable Transition)",
    }

    @classmethod
    def get_name(cls, state: int) -> str:
        return cls.NAMES.get(VrittiState(state), "Unknown")

    @classmethod
    def get_description(cls, state: int) -> str:
        return cls.DESCRIPTIONS.get(VrittiState(state), "Unknown")


class PIDGovernor(nn.Module):
    """
    Vritti-Driven PID Governor.

    Converts from scalar Authority to vectorized [Kp, Ki, Kd] gains
    based on the predicted cognitive mode.
    """

    def __init__(self):
        super().__init__()
        # Register as buffers so they move with the model
        self.register_buffer('kp_table', KP_TABLE.clone())
        self.register_buffer('ki_table', KI_TABLE.clone())
        self.register_buffer('kd_table', KD_TABLE.clone())

        # Error tracking for integral/derivative computation
        self.register_buffer('error_integral', torch.zeros(1))
        self.register_buffer('prev_error', torch.zeros(1))

    def get_gains(self, vritti_ids: torch.Tensor) -> torch.Tensor:
        """
        Get PID gains for given Vritti states.

        Args:
            vritti_ids: [B, N] or [B] tensor of Vritti IDs (0-4)

        Returns:
            [B, N, 3] or [B, 3] tensor of [Kp, Ki, Kd] gains
        """
        kp = self.kp_table[vritti_ids]
        ki = self.ki_table[vritti_ids]
        kd = self.kd_table[vritti_ids]

        return torch.stack([kp, ki, kd], dim=-1)

    def compute_authority(
        self,
        pred_vritti: torch.Tensor,
        target_vritti: torch.Tensor,
        error: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute vectorized Authority and control signal.

        Args:
            pred_vritti: Predicted Vritti IDs [B, N]
            target_vritti: Target Vritti IDs [B, N]
            error: Current prediction error [B, N]

        Returns:
            authority: [B, N, 3] - The [Kp, Ki, Kd] authority vector
            control: [B, N] - The PID control signal
        """
        # Get gains for target mode
        gains = self.get_gains(target_vritti)  # [B, N, 3]
        kp, ki, kd = gains[..., 0], gains[..., 1], gains[..., 2]

        # Check for mode mismatch (Emergency Brake)
        mismatch = (pred_vritti != target_vritti).float()
        brake_factor = 1.0 - (0.9 * mismatch)  # 0.1x learning when mismatched

        # Compute PID terms
        # P-term: Immediate proportional correction
        p_term = kp * error

        # I-term: Accumulated error (integral)
        self.error_integral = 0.99 * self.error_integral + error.mean()
        i_term = ki * self.error_integral

        # D-term: Rate of change (derivative)
        d_term = kd * (error.mean() - self.prev_error)
        self.prev_error = error.mean().detach()

        # Total control signal
        control = (p_term + i_term + d_term) * brake_factor

        # Authority vector (used for gradient scaling)
        authority = gains * brake_factor.unsqueeze(-1)

        return authority, control

    def reset_state(self):
        """Reset integral and derivative state."""
        self.error_integral.zero_()
        self.prev_error.zero_()


class VrittiHead(nn.Module):
    """
    Auxiliary head that predicts the Vritti cognitive mode.

    Takes the R-Signal (Ontological Intent) from the Biological Header
    and predicts one of 5 Vritti states.
    """

    def __init__(self, input_dim: int = 48, hidden_dim: int = 24):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, 5),  # 5 Vritti states
        )

    def forward(self, r_signal: torch.Tensor) -> torch.Tensor:
        """
        Predict Vritti state from R-Signal.

        Args:
            r_signal: [B, N, 48] - The Ontological Intent signal

        Returns:
            vritti_logits: [B, N, 5] - Logits for each Vritti state
        """
        return self.net(r_signal)


def format_vritti_status(
    step: int,
    tokens: list,
    vritti_ids: torch.Tensor,
    gains: torch.Tensor,
) -> str:
    """
    Format a detailed Vritti status display for the terminal.

    Shows the cognitive mode and PID gains for each token.
    """
    lines = [
        "",
        "=" * 70,
        f"  VRITTI STATUS (Step {step})",
        "=" * 70,
        f"  {'Token':<15} {'Mode':<12} {'Kp':>6} {'Ki':>6} {'Kd':>6}  Action",
        "-" * 70,
    ]

    for i, (token, vid) in enumerate(zip(tokens, vritti_ids.tolist())):
        if i >= len(gains):
            break
        g = gains[i]
        name = VrittiNames.get_name(vid)

        # Determine action based on mode
        if vid == VrittiState.PRAMANA:
            action = "Rigid Lock"
        elif vid == VrittiState.VIPARYAYA:
            action = "RESET TRIGGERED"
        elif vid == VrittiState.VIKALPA:
            action = "Creative Flow"
        elif vid == VrittiState.SMRITI:
            action = "Recall"
        else:
            action = "Pass-through"

        lines.append(
            f"  {token:<15} {name:<12} {g[0]:>6.2f} {g[1]:>6.2f} {g[2]:>6.2f}  {action}"
        )

    lines.extend([
        "=" * 70,
        "",
    ])

    return "\n".join(lines)
