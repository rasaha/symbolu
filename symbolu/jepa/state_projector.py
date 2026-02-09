"""
Sovereign State Projector for Phase-JEPA.

Projects hidden representations to the 32D Sovereign State space with
component-wise normalization constraints.

References:
    - HYBRID_PHASE_JEPA_DESIGN.md §3.2
    - ONTOLOGICAL_STATE_DELTA_DESIGN.md (32D State Structure)
"""

import torch
import torch.nn as nn
from typing import Optional, Dict, Tuple

# Import from existing sovereign module for constants
try:
    from symbolu.sovereign.reasoning_kernel import (
        SOVEREIGN_STATE_DIM,
        BHAVA_NAMES,
        KOSHA_NAMES,
        VRITTI_NAMES,
        GUNA_NAMES,
    )
except ImportError:
    # Fallback definitions
    SOVEREIGN_STATE_DIM = 32
    BHAVA_NAMES = ['POT', 'IDN', 'EXE', 'STR', 'COG', 'AGY', 'RSN', 'PRP', 'WIT', 'UNI', 'INT', 'ABS']
    KOSHA_NAMES = ['ANNA', 'PRANA', 'MANO', 'VIJNANA', 'ANANDA']
    VRITTI_NAMES = ['PRAMANA', 'VIPARYAYA', 'VIKALPA', 'NIDRA', 'SMRITI']
    GUNA_NAMES = ['SATTVA', 'RAJAS', 'TAMAS', 'VELOCITY', 'ACCEL', 'STABLE']


class SovereignStateProjector(nn.Module):
    """
    Projects hidden states to 32D Sovereign State with MLP architecture.

    V11.0.0: Still projects full 32D. Consumers separate into planes:
      Phase Plane:    [0:12]  Bhavas → ΔBhava → phase rotation (12D)
      Control Plane:  [12:28] Koshas + Vrittis + Gunas → CTM+/Sentinel (16D)
      Learning Plane: [28:32] Reserved → training feedback (4D)

    Structure (32D):
        [0:12]  - 12 Bhavas (Ontological Aspects) - Softmax normalized
        [12:17] - 5 Koshas (Consciousness Sheaths) - Softmax OR Sigmoid (v2.2.5)
        [17:22] - 5 Vrittis (Mental Modifications) - Softmax normalized
        [22:28] - 6 Gunas/Dynamics (Energy States) - Sigmoid independent
        [28:32] - 4 Reserved (Toroidal Feedback) - Tanh bounded

    v2.2.5 Geometric Expansion Mode:
        When kosha_mode='sigmoid', Koshas are treated as INDEPENDENT sheaths
        (not mutually exclusive classes). This allows the model to be:
        - HIGH Physical AND HIGH Intellectual simultaneously
        - Proper ontological modeling (sheaths coexist, not compete)
        - Compatible with Gemini's v2.2.4 threshold design (0.75 trap_threshold)

    This MLP architecture provides higher capacity than simple linear projection,
    matching the JEPA design specification for unified projector architecture.

    Args:
        hidden_dim: Input hidden dimension (e.g., 768 for transformer)
        state_dim: Output Sovereign State dimension (default 32)
        intermediate_dim: Intermediate MLP dimension (default hidden_dim // 2)
        dropout: Dropout probability
        use_layer_norm: Whether to apply LayerNorm before projection
        kosha_mode: 'softmax' (legacy, zero-sum) or 'sigmoid' (v2.2.5, independent)
    """

    # Dimension ranges for component normalization
    BHAVA_RANGE = (0, 12)
    KOSHA_RANGE = (12, 17)
    VRITTI_RANGE = (17, 22)
    GUNA_RANGE = (22, 28)
    RESERVED_RANGE = (28, 32)

    def __init__(
        self,
        hidden_dim: int = 768,
        state_dim: int = SOVEREIGN_STATE_DIM,
        intermediate_dim: Optional[int] = None,
        dropout: float = 0.1,
        use_layer_norm: bool = True,
        kosha_mode: str = 'sigmoid',  # v2.2.5: 'sigmoid' for independent sheaths, 'softmax' for legacy
    ):
        super().__init__()

        self.hidden_dim = hidden_dim
        self.state_dim = state_dim
        self.intermediate_dim = intermediate_dim or (hidden_dim // 2)
        self.kosha_mode = kosha_mode

        if kosha_mode not in ('softmax', 'sigmoid'):
            raise ValueError(f"kosha_mode must be 'softmax' or 'sigmoid', got '{kosha_mode}'")

        # Optional pre-normalization
        self.layer_norm = nn.LayerNorm(hidden_dim) if use_layer_norm else nn.Identity()

        # MLP Projection (matches JEPA design spec)
        self.projector = nn.Sequential(
            nn.Linear(hidden_dim, self.intermediate_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(self.intermediate_dim, state_dim),
        )

        # Initialize to produce near-uniform distributions initially
        self._init_weights()

    def _init_weights(self):
        """Initialize weights for stable initial state distributions."""
        # Initialize final layer with variance to prevent Qualia collapse (33/33/33 bug)
        # Using Xavier/Glorot initialization for better gradient flow
        with torch.no_grad():
            nn.init.xavier_normal_(self.projector[-1].weight, gain=0.5)
            self.projector[-1].bias.fill_(0.0)

            # Bias Bhavas toward ABS (Absolute) initially for Sattvic anchor
            # Index 11 is ABS in BHAVA_NAMES
            self.projector[-1].bias[11] = 0.1

            # Add slight bias diversity to Gunas (indices 22-24: Sattva, Rajas, Tamas)
            # to prevent softmax collapse to uniform 33/33/33
            self.projector[-1].bias[22] = 0.05   # Sattva slight preference
            self.projector[-1].bias[23] = -0.02  # Rajas
            self.projector[-1].bias[24] = -0.03  # Tamas

    def forward(
        self,
        h: torch.Tensor,
        apply_constraints: bool = True,
        return_raw: bool = False,
    ) -> torch.Tensor:
        """
        Project hidden states to Sovereign State.

        Args:
            h: Hidden states [B, T, D] or [B, D]
            apply_constraints: Whether to apply component-wise normalization
            return_raw: If True, also return raw (pre-normalized) projection

        Returns:
            S: Sovereign State [B, T, 32] or [B, 32]
            (raw: Optional raw projection if return_raw=True)
        """
        # Pre-normalization
        h_norm = self.layer_norm(h)

        # MLP projection
        raw = self.projector(h_norm)

        if not apply_constraints:
            if return_raw:
                return raw, raw
            return raw

        # Apply component-wise constraints
        S = self._apply_constraints(raw)

        if return_raw:
            return S, raw
        return S

    def _apply_constraints(self, raw: torch.Tensor) -> torch.Tensor:
        """
        Apply normalization constraints per component group.

        - Bhavas: Softmax (probability distribution)
        - Koshas: Sigmoid (v2.2.5 independent) or Softmax (legacy zero-sum)
        - Vrittis: Softmax (probability distribution)
        - Gunas: Sigmoid (independent activations [0, 1])
        - Reserved: Tanh (bounded [-1, 1])

        v2.2.5 Geometric Expansion:
            When kosha_mode='sigmoid', Koshas become independent [0,1] activations.
            This allows "Full-Spectrum" awareness where model can be:
            - HIGH Physical AND HIGH Intellectual simultaneously
            - Enables Gemini's v2.2.4 threshold design (trap=0.75, gate=0.30)
        """
        # Extract component ranges
        bhava = raw[..., 0:12]
        kosha = raw[..., 12:17]
        vritti = raw[..., 17:22]
        guna = raw[..., 22:28]
        reserved = raw[..., 28:32]

        # Apply constraints
        bhava_norm = torch.softmax(bhava, dim=-1)

        # v2.2.5: Kosha normalization mode
        if self.kosha_mode == 'sigmoid':
            # Independent sheaths - can all be high/low simultaneously
            kosha_norm = torch.sigmoid(kosha)
        else:
            # Legacy softmax - zero-sum competition between sheaths
            kosha_norm = torch.softmax(kosha, dim=-1)

        vritti_norm = torch.softmax(vritti, dim=-1)
        guna_norm = torch.sigmoid(guna)
        reserved_norm = torch.tanh(reserved)

        # Concatenate back
        return torch.cat([
            bhava_norm,
            kosha_norm,
            vritti_norm,
            guna_norm,
            reserved_norm,
        ], dim=-1)

    def get_component(
        self,
        S: torch.Tensor,
        component: str,
    ) -> torch.Tensor:
        """
        Extract a specific component from the Sovereign State.

        Args:
            S: Sovereign State [B, ..., 32]
            component: One of 'bhava', 'kosha', 'vritti', 'guna', 'reserved'

        Returns:
            Component tensor
        """
        ranges = {
            'bhava': self.BHAVA_RANGE,
            'kosha': self.KOSHA_RANGE,
            'vritti': self.VRITTI_RANGE,
            'guna': self.GUNA_RANGE,
            'reserved': self.RESERVED_RANGE,
        }
        start, end = ranges[component.lower()]
        return S[..., start:end]

    def get_state_summary(self, S: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Get human-readable summary of state components.

        Args:
            S: Sovereign State [B, 32] (single state, not sequence)

        Returns:
            Dict with component names and their dominant values
        """
        if S.dim() == 3:
            # Take last position if sequence
            S = S[:, -1, :]

        summary = {}

        # Dominant Bhava
        bhava = S[..., 0:12]
        bhava_idx = bhava.argmax(dim=-1)
        summary['dominant_bhava'] = [BHAVA_NAMES[i] for i in bhava_idx.tolist()]
        summary['bhava_values'] = bhava

        # Dominant Kosha
        kosha = S[..., 12:17]
        kosha_idx = kosha.argmax(dim=-1)
        summary['dominant_kosha'] = [KOSHA_NAMES[i] for i in kosha_idx.tolist()]
        summary['kosha_values'] = kosha

        # Dominant Vritti
        vritti = S[..., 17:22]
        vritti_idx = vritti.argmax(dim=-1)
        summary['dominant_vritti'] = [VRITTI_NAMES[i] for i in vritti_idx.tolist()]
        summary['vritti_values'] = vritti

        # Guna activations
        guna = S[..., 22:28]
        summary['guna_values'] = guna
        summary['sattva'] = guna[..., 0]
        summary['rajas'] = guna[..., 1]
        summary['tamas'] = guna[..., 2]

        return summary


class DeltaStateProjector(nn.Module):
    """
    Projects hidden state changes to State Deltas.

    Computes ΔS = S(t+1) - S(t) from consecutive hidden states,
    used for state transition prediction in JEPA.

    Args:
        hidden_dim: Input hidden dimension
        state_dim: Sovereign State dimension
    """

    def __init__(
        self,
        hidden_dim: int = 768,
        state_dim: int = SOVEREIGN_STATE_DIM,
    ):
        super().__init__()

        self.state_projector = SovereignStateProjector(
            hidden_dim=hidden_dim,
            state_dim=state_dim,
        )

    def forward(
        self,
        h_current: torch.Tensor,
        h_next: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Compute state delta from consecutive hidden states.

        Args:
            h_current: Current hidden state [B, D]
            h_next: Next hidden state [B, D]

        Returns:
            delta_S: State delta [B, 32]
            S_current: Current state [B, 32]
            S_next: Next state [B, 32]
        """
        S_current = self.state_projector(h_current)
        S_next = self.state_projector(h_next)
        delta_S = S_next - S_current

        return delta_S, S_current, S_next

    def forward_sequence(
        self,
        h_sequence: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute state deltas for a sequence.

        Args:
            h_sequence: Hidden state sequence [B, T, D]

        Returns:
            delta_S: State deltas [B, T-1, 32]
            S: Full state sequence [B, T, 32]
        """
        S = self.state_projector(h_sequence)  # [B, T, 32]
        delta_S = S[:, 1:, :] - S[:, :-1, :]  # [B, T-1, 32]

        return delta_S, S
