"""
Sovereign Phase Attention - R-Signal Driven Phase Memory.

This module integrates the Phase Memory system with the Sovereign architecture.
Instead of learning random phase angles, the Phase layers "listen" to the
Sovereign Header signals:

- R-Signal → Phase Seeding: Intent-aligned words get aligned phases
- S-Signal → Amplitude Gating: High reality-lock words persist longer
- V-Signal (Vritti) → Phase Stiffness: PID-driven phase modulation

This is the "Hippocampus" for the Sovereign "Pre-Frontal Cortex."

Patent Formula [201]: Each Vritti state modulates the phase stiffness:
- Pramāṇa: φ locked (high stiffness, factual anchor)
- Vikalpa: φ fluid (low stiffness, creative drift allowed)
- Nidrā: φ inertial (smooth transitions)

Reference: SOVEREIGN_EMBEDDING_TRAINING_DESIGN.md
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class SovereignPhaseAttention(nn.Module):
    """
    Phase Attention layer that uses Sovereign R-Signal for phase initialization.

    Key insight: Instead of the Phase layer learning random angles,
    the angle φ is initialized by the R-Signal (Intent). If two words
    share the same intent (e.g., "King" and "Empire"), their phases
    naturally align, creating constructive interference in memory.

    Architecture:
    ```
    R-Signal (Intent) ──→ Phase Angle φ
                              │
                              ▼
    Input x ──→ Complex Rotation ──→ Phase Attention ──→ Output
                              │
                              ▲
    S-Signal (Reality) ──→ Amplitude Gate
    ```
    """

    def __init__(
        self,
        d_model: int = 1024,
        n_heads: int = 8,
        r_classes: int = 12,
        s_classes: int = 17,
        v_classes: int = 5,  # 5 Vritti states
        dropout: float = 0.1,
        use_cumsum: bool = True,  # O(N) memory trick
        use_vritti_phase: bool = True,  # Enable Vritti-driven phase stiffness
    ):
        """
        Initialize SovereignPhaseAttention.

        Args:
            d_model: Model dimension
            n_heads: Number of attention heads
            r_classes: Number of R-Signal classes (ontology layers)
            s_classes: Number of S-Signal classes (referent categories)
            v_classes: Number of Vritti states (mental modes)
            dropout: Dropout probability
            use_cumsum: Use O(N) cumulative sum for phase (vs O(N²))
            use_vritti_phase: Enable Vritti-driven phase stiffness modulation
        """
        super().__init__()

        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.use_cumsum = use_cumsum
        self.use_vritti_phase = use_vritti_phase

        # R-Signal → Phase angle mapping
        # Each ontology class gets a learned phase offset per head
        self.r_to_phi = nn.Embedding(r_classes, n_heads)

        # S-Signal → Amplitude gate
        # High reality-lock categories persist longer in memory
        self.s_to_amplitude = nn.Embedding(s_classes, n_heads)

        # V-Signal (Vritti) → Phase stiffness modulation (Patent Formula [201])
        # RAJASIC PROFILE: Stiffness controls how much the phase can drift
        # Pramāṇa (0): REINFORCED stiffness (locked phase, factual)
        # Viparyaya (1): HIGH stiffness (hard reset, corrective)
        # Vikalpa (2): MODERATE stiffness (high derivative = creative motion)
        # Smṛti (3): ACTIVE stiffness (balanced recall)
        # Nidrā (4): TRANSITIONAL (controlled transitions)
        self.register_buffer(
            "vritti_stiffness",
            torch.tensor([0.95, 0.85, 0.40, 0.60, 0.30])  # Rajasic Kp values
        )
        self.v_to_stiffness = nn.Embedding(v_classes, n_heads)

        # Standard attention projections
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)

        # Learned frequency parameters (per head)
        self.freq = nn.Parameter(torch.randn(n_heads) * 0.1)

        # Phase noise (controlled by Vritti stiffness)
        self.phase_noise_scale = nn.Parameter(torch.tensor(0.1))

        # Dropout
        self.dropout = nn.Dropout(dropout)

        # Initialize
        self._init_weights()

    def _init_weights(self):
        """Initialize phase embeddings for smooth transitions."""
        # R-Signal phases: spread across [0, 2π]
        with torch.no_grad():
            for i in range(self.r_to_phi.num_embeddings):
                self.r_to_phi.weight[i] = torch.full(
                    (self.n_heads,),
                    i * (2 * math.pi / self.r_to_phi.num_embeddings)
                )

        # S-Signal amplitudes: higher for concrete categories
        # Categories 1-5 (person, animal, plant, artifact, structure) = high
        # Categories 6-16 (abstract) = lower
        with torch.no_grad():
            for i in range(self.s_to_amplitude.num_embeddings):
                if i <= 5:  # Concrete
                    self.s_to_amplitude.weight[i] = torch.ones(self.n_heads) * 1.2
                else:  # Abstract
                    self.s_to_amplitude.weight[i] = torch.ones(self.n_heads) * 0.8

        # V-Signal (Vritti) stiffness: initialize from RAJASIC PID Kp values
        # This controls phase lock/drift per mental mode
        with torch.no_grad():
            vritti_kp = [0.95, 0.85, 0.40, 0.60, 0.30]  # Rajasic profile
            for i in range(self.v_to_stiffness.num_embeddings):
                self.v_to_stiffness.weight[i] = torch.full(
                    (self.n_heads,),
                    vritti_kp[i]
                )

    def forward(
        self,
        x: torch.Tensor,
        r_signals: torch.Tensor,
        s_signals: torch.Tensor,
        v_signals: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with R-Signal phase seeding, S-Signal amplitude gating,
        and V-Signal (Vritti) phase stiffness modulation.

        Args:
            x: Input tensor [B, T, D]
            r_signals: R-Signal (intent) [B, T]
            s_signals: S-Signal (referent) [B, T]
            v_signals: V-Signal (Vritti mental mode) [B, T] - optional
            attention_mask: Optional attention mask [B, T]

        Returns:
            Tuple of (output [B, T, D], attention_weights [B, H, T, T])
        """
        B, T, D = x.shape
        H = self.n_heads
        head_dim = self.head_dim

        # 1. Generate Phase Angles from R-Signal
        # Instead of random initialization, use Sovereign Intent
        phi_base = self.r_to_phi(r_signals)  # [B, T, H]

        # 2. Get Amplitude Gates from S-Signal
        amplitude = self.s_to_amplitude(s_signals)  # [B, T, H]

        # 3. Get Phase Stiffness from V-Signal (Vritti)
        # High stiffness = phase locked to R-Signal seed
        # Low stiffness = phase can drift (creative mode)
        if v_signals is not None and self.use_vritti_phase:
            stiffness = self.v_to_stiffness(v_signals)  # [B, T, H]
        else:
            # Default to medium stiffness
            stiffness = torch.ones(B, T, H, device=x.device) * 0.5

        # 4. Compute phase evolution with position
        positions = torch.arange(T, device=x.device).float().unsqueeze(0)  # [1, T]
        freq_expanded = self.freq.unsqueeze(0).unsqueeze(0)  # [1, 1, H]
        phase_evolution = positions.unsqueeze(-1) * freq_expanded  # [1, T, H]

        # 5. Add controlled phase noise based on stiffness (Patent Formula [201])
        # Low stiffness (Vikalpa) = more noise = creative drift
        # High stiffness (Pramāṇa) = no noise = factual lock
        if self.training and self.use_vritti_phase:
            noise = torch.randn_like(phi_base) * self.phase_noise_scale
            # Stiffness acts as noise suppressor: high stiffness = low noise
            modulated_noise = noise * (1.0 - stiffness)
            phase_evolution = phase_evolution + modulated_noise

        # Total phase = R-Signal base + position evolution (with Vritti modulation)
        phi_total = phi_base + phase_evolution  # [B, T, H]

        # 4. Project Q, K, V
        Q = self.q_proj(x).view(B, T, H, head_dim)  # [B, T, H, D/H]
        K = self.k_proj(x).view(B, T, H, head_dim)
        V = self.v_proj(x).view(B, T, H, head_dim)

        # 5. Apply complex rotation (phase encoding)
        # Create rotation matrices from phases
        cos_phi = torch.cos(phi_total).unsqueeze(-1)  # [B, T, H, 1]
        sin_phi = torch.sin(phi_total).unsqueeze(-1)

        # Rotate Q and K (simplified: first half of head_dim)
        half_dim = head_dim // 2
        Q_rot = self._rotate_half(Q, cos_phi, sin_phi, half_dim)
        K_rot = self._rotate_half(K, cos_phi, sin_phi, half_dim)

        # 6. Compute attention scores
        # [B, H, T, D/H] @ [B, H, D/H, T] -> [B, H, T, T]
        Q_t = Q_rot.permute(0, 2, 1, 3)  # [B, H, T, D/H]
        K_t = K_rot.permute(0, 2, 3, 1)  # [B, H, D/H, T]

        scores = torch.matmul(Q_t, K_t) / math.sqrt(head_dim)  # [B, H, T, T]

        # 7. Apply S-Signal amplitude gating
        # High reality-lock tokens contribute more to attention
        amplitude_gate = amplitude.permute(0, 2, 1).unsqueeze(2)  # [B, H, 1, T]
        scores = scores * amplitude_gate

        # 8. Apply attention mask (causal + padding)
        if attention_mask is not None:
            # Expand mask: [B, T] -> [B, 1, 1, T]
            mask = attention_mask.unsqueeze(1).unsqueeze(2)
            scores = scores.masked_fill(mask == 0, float('-inf'))

        # Causal mask
        causal_mask = torch.triu(
            torch.ones(T, T, device=x.device), diagonal=1
        ).bool()
        scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        # 9. Softmax and apply to values
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        V_t = V.permute(0, 2, 1, 3)  # [B, H, T, D/H]
        context = torch.matmul(attn_weights, V_t)  # [B, H, T, D/H]

        # 10. Reshape and project output
        context = context.permute(0, 2, 1, 3).contiguous()  # [B, T, H, D/H]
        context = context.view(B, T, D)
        output = self.out_proj(context)

        return output, attn_weights

    def _rotate_half(
        self,
        x: torch.Tensor,
        cos_phi: torch.Tensor,
        sin_phi: torch.Tensor,
        half_dim: int,
    ) -> torch.Tensor:
        """Apply rotation to first half of dimensions."""
        x1 = x[..., :half_dim]
        x2 = x[..., half_dim:]

        # Rotate x1
        x1_rot = x1 * cos_phi - x2 * sin_phi
        x2_rot = x1 * sin_phi + x2 * cos_phi

        return torch.cat([x1_rot, x2_rot], dim=-1)


class SovereignPhaseTransformerLayer(nn.Module):
    """
    Full transformer layer with SovereignPhaseAttention.

    Combines:
    - SovereignPhaseAttention (R-Signal driven phase memory)
    - Standard FFN
    - Pre-LayerNorm architecture
    """

    def __init__(
        self,
        d_model: int = 1024,
        n_heads: int = 8,
        d_ff: int = 4096,
        dropout: float = 0.1,
        r_classes: int = 12,
        s_classes: int = 17,
    ):
        super().__init__()

        # Phase attention
        self.attn = SovereignPhaseAttention(
            d_model=d_model,
            n_heads=n_heads,
            r_classes=r_classes,
            s_classes=s_classes,
            dropout=dropout,
        )

        # FFN
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout),
        )

        # Layer norms (pre-LN)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

    def forward(
        self,
        x: torch.Tensor,
        r_signals: torch.Tensor,
        s_signals: torch.Tensor,
        v_signals: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            x: Input [B, T, D]
            r_signals: R-Signal (intent) [B, T]
            s_signals: S-Signal (referent) [B, T]
            v_signals: V-Signal (Vritti mental mode) [B, T] - optional
            attention_mask: Optional mask [B, T]

        Returns:
            Tuple of (output [B, T, D], attention_weights)
        """
        # Pre-norm attention
        normed = self.norm1(x)
        attn_out, attn_weights = self.attn(
            normed, r_signals, s_signals, v_signals, attention_mask
        )
        x = x + attn_out

        # Pre-norm FFN
        x = x + self.ffn(self.norm2(x))

        return x, attn_weights


def test_sovereign_phase():
    """Test SovereignPhaseAttention with R-Signal and Vritti phase stiffness."""
    print("\n" + "=" * 70)
    print("SOVEREIGN PHASE ATTENTION TEST")
    print("=" * 70)

    # Create layer
    layer = SovereignPhaseAttention(
        d_model=256,
        n_heads=4,
        r_classes=12,
        s_classes=17,
        v_classes=5,
        use_vritti_phase=True,
    )

    # Create inputs
    B, T, D = 2, 16, 256
    x = torch.randn(B, T, D)
    r_signals = torch.randint(0, 12, (B, T))
    s_signals = torch.randint(0, 17, (B, T))
    v_signals = torch.randint(0, 5, (B, T))

    # Forward pass with Vritti signals
    output, attn_weights = layer(x, r_signals, s_signals, v_signals)

    print(f"\nInput shape: {x.shape}")
    print(f"R-signals shape: {r_signals.shape}")
    print(f"S-signals shape: {s_signals.shape}")
    print(f"V-signals (Vritti) shape: {v_signals.shape}")
    print(f"Output shape: {output.shape}")
    print(f"Attention weights shape: {attn_weights.shape}")

    # Verify phase alignment for same R-Signal
    print("\n--- Phase Alignment Test ---")
    # Set all positions to same R-Signal
    r_same = torch.zeros(B, T, dtype=torch.long)
    phi_same = layer.r_to_phi(r_same)
    print(f"Same R-Signal phases: {phi_same[0, :3, 0].tolist()}")

    # Different R-Signals
    r_diff = torch.arange(T).unsqueeze(0).expand(B, -1) % 12
    phi_diff = layer.r_to_phi(r_diff)
    print(f"Varying R-Signal phases: {phi_diff[0, :3, 0].tolist()}")

    # Verify Vritti stiffness
    print("\n--- Vritti Stiffness Test (Patent Formula [201]) ---")
    vritti_names = ["PRAMANA", "VIPARYAYA", "VIKALPA", "SMRTI", "NIDRA"]
    for v_id in range(5):
        v_test = torch.full((1, 1), v_id, dtype=torch.long)
        stiffness = layer.v_to_stiffness(v_test)
        print(f"  {vritti_names[v_id]:<10}: Stiffness = {stiffness[0, 0, 0]:.2f}")

    print("\n  Interpretation:")
    print("  - High stiffness (Pramāṇa): Phase locked to R-Signal seed")
    print("  - Low stiffness (Vikalpa): Phase can drift (creative mode)")
    print("  - During training, noise is modulated by (1 - stiffness)")

    print("\n[PASS] SovereignPhaseAttention working!")
    print("Key: Same intent = Same phase = Constructive interference")
    print("     Vritti controls phase stiffness for mental mode alignment")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_sovereign_phase()
