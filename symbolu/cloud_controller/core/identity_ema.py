"""Identity EMA — adaptive baseline learning.

Ported from IdentityEMA (minimal_controller.py:382-440) and
SelfModel.consolidate_identity() (identity_layer.py:163-222).

Removed: torch tensors, nn.functional.
Replaced with: numpy arrays.

Key property preserved: conditional update rate.
    alpha_eff = alpha_base * stability * agreement
    - stability = 1 / (1 + var(accumulator))
    - agreement = mapped cosine_similarity(accumulator, baseline) in [0, 1]
    - Floor: alpha_eff >= 0.1 * alpha_base (never zero)

This means the baseline only updates when the system is stable
AND the new signal agrees with current identity. Anomalous periods
don't corrupt the baseline.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class IdentityResult:
    updated: bool           # Whether consolidation happened
    alpha_eff: float        # Effective learning rate used
    agreement: float        # Cosine agreement with current baseline
    stability: float        # Signal stability score
    baseline_norm: float    # L2 norm of current baseline


class IdentityEMA:
    """Learns what "normal" looks like for infrastructure over time.

    Fast loop: accumulate metric snapshots with salience weighting.
    Slow loop: consolidate accumulated signal into baseline (only when
    system is stable and signal agrees with existing identity).
    """

    def __init__(self, dim: int = 16, alpha_base: float = 0.01, ema_decay: float = 0.99):
        self.dim = dim
        self.alpha_base = alpha_base
        self.ema_decay = ema_decay
        self.baseline = np.random.randn(dim) * 0.01
        self.baseline = self.baseline / (np.linalg.norm(self.baseline) + 1e-8) * np.sqrt(dim)
        self.accumulator = np.zeros(dim)
        self.count = 0
        self.consolidation_count = 0

    def accumulate(self, signal: np.ndarray, salience: float = 0.5) -> None:
        """Fast loop: accumulate an infrastructure state snapshot.

        Only high-salience signals are accumulated (salience > 0.3).
        Matches minimal_controller.py lines 402-410.

        Args:
            signal: Normalized metric vector of length `dim`.
            salience: Importance weight in [0, 1]. Low salience = routine, ignored.
        """
        if salience <= 0.3:
            return
        if len(signal) != self.dim:
            raise ValueError(f"Signal dim {len(signal)} != identity dim {self.dim}")

        # A_t = decay * A_{t-1} + (1 - decay) * salience * signal
        # Matches minimal_controller.py lines 407-408
        self.accumulator = (
            self.ema_decay * self.accumulator
            + (1 - self.ema_decay) * salience * signal
        )
        self.count += 1

    def consolidate(self) -> IdentityResult:
        """Slow loop: revise baseline from accumulated signals.

        Only updates when:
        - Enough signals accumulated (count > 0)
        - Accumulator has meaningful magnitude (norm > 1e-6)
        - alpha_eff is modulated by stability AND agreement

        Matches identity_layer.py lines 163-222 and
        minimal_controller.py lines 412-433.

        Returns:
            IdentityResult with update details.
        """
        if self.count == 0 or np.linalg.norm(self.accumulator) < 1e-6:
            return IdentityResult(
                updated=False,
                alpha_eff=0.0,
                agreement=0.0,
                stability=0.0,
                baseline_norm=float(np.linalg.norm(self.baseline)),
            )

        # Normalize accumulator before blending
        # Matches identity_layer.py line 192
        A_norm = np.linalg.norm(self.accumulator)
        A_normalized = (self.accumulator / max(A_norm, 1e-8)) * np.sqrt(self.dim)

        # Agreement: cosine similarity mapped from [-1,1] to [0,1]
        # Matches identity_layer.py lines 196-199
        baseline_norm = np.linalg.norm(self.baseline)
        if baseline_norm > 1e-8 and A_norm > 1e-8:
            cos_sim = float(np.dot(A_normalized, self.baseline) / (
                np.linalg.norm(A_normalized) * baseline_norm
            ))
        else:
            cos_sim = 0.0
        agreement = max(0.0, (cos_sim + 1.0) / 2.0)

        # Stability: low variance in accumulator = stable signal
        # Matches identity_layer.py lines 202-203
        accumulator_var = float(np.var(self.accumulator))
        stability = 1.0 / (1.0 + accumulator_var)

        # Effective alpha: base * stability * agreement, floored
        # Matches identity_layer.py line 206
        alpha_eff = max(
            self.alpha_base * stability * agreement,
            self.alpha_base * 0.1,
        )

        # I_t = (1 - alpha_eff) * I_{t-1} + alpha_eff * A_normalized
        # Matches identity_layer.py line 209
        self.baseline = (1.0 - alpha_eff) * self.baseline + alpha_eff * A_normalized

        # Re-normalize to prevent magnitude drift
        # Matches identity_layer.py lines 212-215
        b_norm = np.linalg.norm(self.baseline)
        if b_norm > 1e-8:
            self.baseline = (self.baseline / b_norm) * np.sqrt(self.dim)

        # Reset accumulator
        self.accumulator = np.zeros(self.dim)
        self.count = 0
        self.consolidation_count += 1

        return IdentityResult(
            updated=True,
            alpha_eff=alpha_eff,
            agreement=agreement,
            stability=stability,
            baseline_norm=float(np.linalg.norm(self.baseline)),
        )

    def deviation(self, current_state: np.ndarray) -> float:
        """Compute how far current state is from baseline identity.

        Returns cosine distance in [0, 1]. 0 = identical, 1 = orthogonal/opposite.
        """
        if len(current_state) != self.dim:
            raise ValueError(f"State dim {len(current_state)} != identity dim {self.dim}")
        c_norm = np.linalg.norm(current_state)
        b_norm = np.linalg.norm(self.baseline)
        if c_norm < 1e-8 or b_norm < 1e-8:
            return 1.0
        cos_sim = float(np.dot(current_state, self.baseline) / (c_norm * b_norm))
        return 1.0 - max(0.0, (cos_sim + 1.0) / 2.0)

    def reset(self) -> None:
        self.baseline = np.random.randn(self.dim) * 0.01
        self.baseline = self.baseline / (np.linalg.norm(self.baseline) + 1e-8) * np.sqrt(self.dim)
        self.accumulator = np.zeros(self.dim)
        self.count = 0
        self.consolidation_count = 0
