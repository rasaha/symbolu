"""
High-level COHERA model accelerators.

These wrappers compose the lower-level phase attention + ontology primitives
into drop-in accelerators for the two model families the SDK targets:

  - ``MistralCGAccelerator``: Mistral-7B backbone + CG adapter stack
    (SovereignStateProjector 4096 -> 32, IntentPhaseProjector 12 -> H,
    PhaseAdapter H -> 1024 -> 4096 with a sigmoid residual gate).

  - ``HybridOntologicalAccelerator``: 12 ontological phase-attention blocks
    (per-layer harmonic frequencies, WitnessBlock / UnifyingBlock hooks).

The accelerators are deliberately numpy-free and framework-free — callers
can drive them from PyTorch, JAX, or directly from cohera Tensors. Device
side ops are delegated to ``cohera_phase_attention_fused``,
``cohera_ontology_project_sovereign``, and friends.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .attention import AttentionConfig, PhaseAttention, phase_attention_fused
from .device import ModelDeviceContext
from .ontology import SovereignStateProjector
from .tensor import DType, KoshaMode, SovereignState


# ---------------------------------------------------------------------------
# Mistral CG
# ---------------------------------------------------------------------------

@dataclass
class MistralCGConfig:
    """
    Configuration for the mistral_cg accelerator.

    Defaults match the mistralai/Mistral-7B-v0.3 backbone plus the CG adapter
    hyperparams from ``symbolu_training/training/unified/mistral_wrapper.py``:
      - 4096 hidden, 32 heads, 8 KV heads (GQA 4x), head_dim 128
      - RoPE over the full head dim (128), base 10000
      - SovereignState intermediate_dim = 1024 (hidden // 4)
      - PhaseAdapter hidden 1024, residual gate sigmoid(-2) ~ 0.12
    """
    hidden_dim: int = 4096
    num_heads: int = 32
    num_kv_heads: int = 8
    rope_dim: int = 128
    rope_base: float = 10000.0
    window_size: int = 4096
    causal: bool = True
    dtype: DType = DType.BF16
    sync_steps: int = 3
    sync_lr: float = 0.1
    coherence_threshold: float = 0.5
    sovereign_intermediate_dim: Optional[int] = None   # default hidden // 4
    phase_adapter_hidden: int = 1024
    adapter_gate_init: float = -2.0                    # sigmoid(-2) ~= 0.12
    kosha_mode: KoshaMode = KoshaMode.SIGMOID
    ontology_layer: int = -1
    use_tcu: bool = True


class MistralCGAccelerator:
    """
    Offload the trainable CG path of mistral_cg to COHERA.

    Pipeline per forward step:
        1. SovereignStateProjector(hidden) -> 32-D state (Bhava / Kosha / Vritti
           / Guna / Reserved)
        2. IntentPhaseProjector(delta_bhava[12]) -> H per-head phase offsets
        3. fused phase attention over (Q, K, V) using the v2 AttentionConfig
           (GQA, RoPE, causal + sliding window, BF16)
        4. PhaseAdapter(intent_phase) -> 4096-D residual, gated by sigmoid(adapter_gate_init)

    The accelerator is stateless w.r.t. individual forward calls; all
    device-persistent data (RoPE table, GQA ratio, dtype) lives on the
    ``ModelDeviceContext`` built by ``initialize_for_model``.
    """

    def __init__(
        self,
        config: Optional[MistralCGConfig] = None,
        context: Optional[ModelDeviceContext] = None,
    ):
        self.config = config or MistralCGConfig()
        self.context = context

        if self.config.hidden_dim % self.config.num_heads != 0:
            raise ValueError(
                f"hidden_dim ({self.config.hidden_dim}) must be divisible by "
                f"num_heads ({self.config.num_heads})"
            )
        if self.config.num_kv_heads > 0 and self.config.num_heads % self.config.num_kv_heads != 0:
            raise ValueError(
                f"num_heads ({self.config.num_heads}) must be divisible by "
                f"num_kv_heads ({self.config.num_kv_heads})"
            )

        self.head_dim = self.config.hidden_dim // self.config.num_heads

        self.state_projector = SovereignStateProjector(
            hidden_dim=self.config.hidden_dim,
            intermediate_dim=self.config.sovereign_intermediate_dim,
            kosha_mode=self.config.kosha_mode,
        )

        # IntentPhaseProjector: 12D Bhava delta -> H scalar phase offsets.
        # Weight matrix lives on device; we only carry shape metadata here.
        self.intent_projector_shape = (12, self.config.num_heads)

        # PhaseAdapter: H -> adapter_hidden -> hidden_dim (residual), gated.
        self.phase_adapter_shape = (
            self.config.num_heads,
            self.config.phase_adapter_hidden,
            self.config.hidden_dim,
        )

        rope_freqs = (
            self.context.rope_freqs_handle if self.context is not None else None
        )

        self.phase_attn = PhaseAttention(
            dim=self.config.hidden_dim,
            heads=self.config.num_heads,
            num_kv_heads=self.config.num_kv_heads,
            sync_steps=self.config.sync_steps,
            sync_lr=self.config.sync_lr,
            ontology_layer=self.config.ontology_layer,
            use_tcu=self.config.use_tcu,
            coherence_threshold=self.config.coherence_threshold,
            causal=self.config.causal,
            dtype=self.config.dtype,
            window_size=self.config.window_size,
            rope_freqs=rope_freqs,
            rope_dim=self.config.rope_dim,
        )

    # -- individual stages ------------------------------------------------

    def project_state(self, hidden, stream=None) -> SovereignState:
        """Hidden[B, T, hidden_dim] -> 32-D Sovereign State."""
        return self.state_projector(hidden, stream=stream)

    def attention(
        self,
        query,
        key,
        value,
        position_offset: int = 0,
        stream=None,
    ) -> Tuple[Any, Any, float]:
        """
        Fused phase attention with Mistral shapes (causal + GQA + RoPE + BF16).

        position_offset wires the current step's token index for KV-cache
        continuation (advances the RoPE table and the causal window).
        """
        cfg = self._build_attention_config(position_offset)
        return phase_attention_fused(query, key, value, config=cfg, stream=stream)

    def _build_attention_config(self, position_offset: int) -> AttentionConfig:
        seq_len = (
            int(self.context.extra.get("seq_len", 0)) if self.context is not None else 0
        )
        return AttentionConfig(
            seq_len=seq_len,
            embed_dim=self.config.hidden_dim,
            num_heads=self.config.num_heads,
            num_kv_heads=self.config.num_kv_heads,
            sync_steps=self.config.sync_steps,
            sync_lr=self.config.sync_lr,
            causal=self.config.causal,
            use_tcu=self.config.use_tcu,
            ontology_layer=self.config.ontology_layer,
            coherence_threshold=self.config.coherence_threshold,
            dtype=self.config.dtype,
            window_size=self.config.window_size,
            rope_freqs=(self.context.rope_freqs_handle if self.context else None),
            rope_dim=self.config.rope_dim,
            rope_base_position=position_offset,
        )

    def apply_phase_adapter(self, intent_phase, stream=None):
        """
        Runs the H -> adapter_hidden -> hidden_dim MLP and applies the
        sigmoid residual gate. Stub: returns a zero residual so callers that
        bypass the device still see the documented zero-init behaviour.
        """
        # Runtime: cohera_phase_adapter(output, intent_phase, w_in, w_out,
        #                                gate_value, stream)
        return None

    # -- full step --------------------------------------------------------

    def forward(
        self,
        hidden,
        query,
        key,
        value,
        delta_bhava=None,
        position_offset: int = 0,
        stream=None,
    ) -> Dict[str, Any]:
        """
        One CG forward step.

        Returns a dict:
            state:        SovereignState (32-D)
            output:       attention output (same shape as query)
            coherence:    scalar per head
            state_delta:  float
            adapter:      residual adapter output (or None in the stub)
        """
        state = self.project_state(hidden, stream=stream)
        output, coherence, state_delta = self.attention(
            query, key, value, position_offset=position_offset, stream=stream,
        )
        # intent_phase = IntentPhaseProjector(delta_bhava); when delta_bhava
        # is None we skip the adapter (matches mistral_cg ablation
        # use_phase_sync=False which zeros intent_phase).
        adapter = None
        if delta_bhava is not None:
            adapter = self.apply_phase_adapter(delta_bhava, stream=stream)

        return {
            "state": state,
            "output": output,
            "coherence": coherence,
            "state_delta": state_delta,
            "adapter": adapter,
        }


# ---------------------------------------------------------------------------
# Hybrid ontological
# ---------------------------------------------------------------------------

@dataclass
class HybridOntologicalConfig:
    """
    Configuration for the 12-layer hybrid ontological accelerator.

    Defaults mirror ``symbolu/ontological/symbolu12_hybrid.py``:
      - 256 embed, 8 heads, 12 layers, GELU FFN, LayerNorm
      - Layer 9 = WitnessBlock, Layer 10 = UnifyingBlock
      - Harmonic ratios log-spaced from 1e5 Hz (layer 0) to 1 Hz (layer 11)
    """
    embed_dim: int = 256
    num_heads: int = 8
    num_layers: int = 12
    witness_layer: int = 9
    unifying_layer: int = 10
    sync_steps: int = 3
    sync_lr: float = 0.1
    causal: bool = False
    dtype: DType = DType.FP32
    coherence_threshold: float = 0.5
    use_tcu: bool = True
    layer_harmonics: Optional[Sequence[float]] = None   # filled from context if None


class HybridOntologicalAccelerator:
    """
    12-block ontological phase-attention stack.

    Each layer binds to its ontology index and its harmonic frequency so the
    ``CO_GATE`` / ``ON_ACTIVATE`` path can route by layer priority. The
    Witness and Unifying layers are marked but still executed as phase
    attention blocks on this path — their extras (coherence matrix,
    confidence estimation) are owned by the consumer.
    """

    def __init__(
        self,
        config: Optional[HybridOntologicalConfig] = None,
        context: Optional[ModelDeviceContext] = None,
    ):
        self.config = config or HybridOntologicalConfig()
        self.context = context

        harmonics = self.config.layer_harmonics
        if harmonics is None and context is not None and context.layer_harmonics:
            harmonics = context.layer_harmonics
        if harmonics is None:
            from .device import _default_layer_harmonics
            harmonics = _default_layer_harmonics(self.config.num_layers)
        if len(harmonics) != self.config.num_layers:
            raise ValueError(
                f"layer_harmonics has {len(harmonics)} entries, expected "
                f"{self.config.num_layers}"
            )
        self.layer_harmonics: Sequence[float] = tuple(harmonics)

        self.blocks: List[PhaseAttention] = [
            PhaseAttention(
                dim=self.config.embed_dim,
                heads=self.config.num_heads,
                num_kv_heads=self.config.num_heads,   # hybrid path uses MHA
                sync_steps=self.config.sync_steps,
                sync_lr=self.config.sync_lr,
                ontology_layer=i,
                use_tcu=self.config.use_tcu,
                coherence_threshold=self.config.coherence_threshold,
                causal=self.config.causal,
                dtype=self.config.dtype,
            )
            for i in range(self.config.num_layers)
        ]

    def forward_layer(
        self,
        x,
        layer_idx: int,
        stream=None,
    ) -> Tuple[Any, float, float]:
        """Run a single ontology block. Returns (x_out, coherence, state_delta)."""
        if not (0 <= layer_idx < self.config.num_layers):
            raise IndexError(f"layer_idx {layer_idx} out of range")
        return self.blocks[layer_idx](x, x, x, stream=stream)

    def forward(self, x, stream=None) -> Dict[str, Any]:
        """
        Run the 12-layer stack. Returns the final hidden plus per-layer
        coherence traces so the caller can drive WitnessBlock confidence
        and UnifyingBlock coherence matrices.
        """
        coherences: List[float] = []
        deltas: List[float] = []
        h = x
        for idx in range(self.config.num_layers):
            h, coh, delta = self.forward_layer(h, idx, stream=stream)
            coherences.append(coh)
            deltas.append(delta)

        return {
            "output": h,
            "coherence_per_layer": coherences,
            "state_delta_per_layer": deltas,
            "witness_layer_idx": self.config.witness_layer,
            "unifying_layer_idx": self.config.unifying_layer,
            "layer_harmonics": self.layer_harmonics,
        }
