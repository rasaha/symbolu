"""
AttentionAblationConfig — Toggle flags for Stage 9 ablation audit.

Each flag independently enables/disables one attention modulation mechanism.
When disabled, the mechanism falls back to its unmodulated equivalent
(standard dot-product, base temperature, unbiased embedding, etc.).

Reference: CONSCIOUS_GENERATION_DESIGN.md, F.14.2
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class AttentionAblationConfig:
    """Toggle flags for attention mechanism ablation testing."""

    # U3/U4 phase synchronization in PhaseAttentionBlock / SovereignPhaseAttention
    use_phase_sync: bool = True

    # Cognitive mode gating (temperature / magnitude / position bias)
    use_vritti_modulation: bool = True

    # Top-down directional embedding bias from Guna state
    use_guna_bias: bool = True

    # Multiplicative intent alignment (disabled by default — experimental)
    use_dual_channel_intent: bool = False

    # --- Logging knobs (active during training, not just ablation) ---

    # Log mechanism strength signals every N steps (0 = disabled)
    log_mechanism_strength_every: int = 0

    def active_mechanisms(self) -> Dict[str, bool]:
        """Return a dict of mechanism name -> enabled status."""
        return {
            "phase_sync": self.use_phase_sync,
            "vritti_modulation": self.use_vritti_modulation,
            "guna_bias": self.use_guna_bias,
            "dual_channel_intent": self.use_dual_channel_intent,
        }

    def label(self) -> str:
        """Human-readable label for this configuration."""
        parts = []
        if self.use_phase_sync:
            parts.append("Phase")
        if self.use_vritti_modulation:
            parts.append("Vritti")
        if self.use_guna_bias:
            parts.append("Guna")
        if self.use_dual_channel_intent:
            parts.append("Intent")
        return "+".join(parts) if parts else "AllOFF"

    @classmethod
    def baseline(cls) -> "AttentionAblationConfig":
        """Full system reference (all on except intent)."""
        return cls()

    @classmethod
    def all_off(cls) -> "AttentionAblationConfig":
        """Pure transformer baseline — all mechanisms disabled."""
        return cls(
            use_phase_sync=False,
            use_vritti_modulation=False,
            use_guna_bias=False,
            use_dual_channel_intent=False,
        )
