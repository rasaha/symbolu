"""
MistralCGWrapper — Frozen Mistral backbone + trainable Conscious Generation modules.

Uses a pre-trained Mistral model (via HuggingFace Transformers) as the language
modeling backbone, with all CG modules (ontological state, kosha routing, bliss
gate, curriculum) layered on top as trainable parameters.

Architecture:
    Mistral-7B (frozen, optional 4-bit) → hidden_states [B, T, D_mistral]
        ↓
    State Projector [D_mistral → 32D Sovereign State]  (trainable)
        ↓
    Bhava Delta [12D] → Intent Phase Projector → phase offsets  (trainable)
        ↓
    Phase-Conditioned Projection Head  (trainable)
        ↓
    LM Head (Mistral's, frozen)

The CG modules (ontological loss, kosha routing, bliss coherence, etc.) are
attached via model.conscious_gen exactly as for ontological_hybrid, so the
existing training loop works without modification.

Usage:
    python train_unified_llm.py \\
        --model_type mistral_cg \\
        --mistral_model_name mistralai/Mistral-7B-v0.3 \\
        --mistral_quantize 4bit \\
        --enable_conscious_generation \\
        --lambda_ont 0.01 \\
        --lambda_kosha_routing 0.01 \\
        --lambda_bliss_token 0.01
"""

from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn

from symbolu.phase_transformer import (
    IntentPhaseProjector,
    SOVEREIGN_STATE_DIM,
    PHASE_STATE_DIM,
    BHAVA_SLICE,
)


class MistralCGWrapper(nn.Module):
    """
    Wraps a frozen HuggingFace Mistral model with trainable CG modules.

    The backbone is frozen (requires_grad=False). Only the CG adapter layers
    (state_projector, intent_projector, phase_adapter) are trained.

    Returns outputs in the same dict format as OntologicalHybridTransformer,
    so the existing training loop and CG loss computation work unchanged.
    """

    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-v0.3",
        quantize: Optional[str] = None,  # None, "4bit", "8bit"
        state_dim: int = SOVEREIGN_STATE_DIM,
        project_per_head_dim: bool = False,
        phase_adapter_hidden: int = 1024,
        device_map: str = "auto",
        trust_remote_code: bool = False,
        # Allow passing pre-loaded model (for testing / custom loading)
        pretrained_model: Optional[nn.Module] = None,
        pretrained_tokenizer: Optional[object] = None,
    ):
        super().__init__()

        # ── Load or accept Mistral backbone ──────────────────────────
        if pretrained_model is not None:
            self.backbone = pretrained_model
            self.tokenizer = pretrained_tokenizer
        else:
            self.backbone, self.tokenizer = self._load_mistral(
                model_name, quantize, device_map, trust_remote_code,
            )

        # Freeze backbone
        for param in self.backbone.parameters():
            param.requires_grad = False

        # Extract dimensions from the loaded model
        mistral_config = self.backbone.config
        self.mistral_hidden_dim = mistral_config.hidden_size  # typically 4096
        self.vocab_size = mistral_config.vocab_size
        self.num_heads = mistral_config.num_attention_heads

        # ── Trainable CG adapter layers ──────────────────────────────

        # State projector: Mistral hidden → 32D Sovereign State
        self.state_projector = nn.Sequential(
            nn.Linear(self.mistral_hidden_dim, self.mistral_hidden_dim // 4),
            nn.GELU(),
            nn.Linear(self.mistral_hidden_dim // 4, state_dim),
        )
        self._init_absolute_potential_bias()

        # Intent phase projector: 12D Bhava delta → per-head phase offsets
        head_dim = self.mistral_hidden_dim // self.num_heads
        self.intent_projector = IntentPhaseProjector(
            state_dim=PHASE_STATE_DIM,  # 12D Bhava-only
            num_heads=self.num_heads,
            head_dim=head_dim,
            project_per_head_dim=project_per_head_dim,
        )

        # Phase-conditioned adapter: mixes phase signal into hidden states
        # before the frozen LM head, so CG can influence token prediction
        self.phase_adapter = nn.Sequential(
            nn.Linear(self.mistral_hidden_dim + self.num_heads, phase_adapter_hidden),
            nn.GELU(),
            nn.Linear(phase_adapter_hidden, self.mistral_hidden_dim),
        )
        # Initialize adapter output near zero (residual start)
        nn.init.zeros_(self.phase_adapter[-1].weight)
        nn.init.zeros_(self.phase_adapter[-1].bias)

        # Adapter gate (learnable scalar, starts at 0 = pure Mistral)
        self.adapter_gate = nn.Parameter(torch.zeros(1))

        # Store config
        self.state_dim = state_dim
        self.embed_dim = self.mistral_hidden_dim  # alias for CG module compatibility

        # Previous state for delta computation
        self.register_buffer('prev_state', None, persistent=False)
        self.register_buffer('prev_bhava', None, persistent=False)

    @staticmethod
    def _load_mistral(
        model_name: str,
        quantize: Optional[str],
        device_map: str,
        trust_remote_code: bool,
    ) -> Tuple[nn.Module, object]:
        """Load Mistral model from HuggingFace with optional quantization."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            raise ImportError(
                "transformers package required for mistral_cg. "
                "Install with: pip install transformers"
            )

        load_kwargs = {
            "device_map": device_map,
            "trust_remote_code": trust_remote_code,
            "torch_dtype": torch.bfloat16,
            "output_hidden_states": True,
        }

        if quantize in ("4bit", "8bit"):
            try:
                from transformers import BitsAndBytesConfig
                import bitsandbytes as _bnb  # noqa: F401
            except ImportError:
                raise ImportError(
                    "bitsandbytes required for quantization. "
                    "Install with: pip install -U bitsandbytes>=0.46.1"
                )
            if quantize == "4bit":
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            else:
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_8bit=True,
                )

        # PyTorch < 2.1 lacks set_submodule, required by transformers' bnb integration
        if not hasattr(torch.nn.Module, "set_submodule"):
            def _set_submodule(self, target, module):
                atoms = target.split(".")
                mod = self
                for item in atoms[:-1]:
                    mod = getattr(mod, item)
                setattr(mod, atoms[-1], module)
            torch.nn.Module.set_submodule = _set_submodule

        print(f"  Loading Mistral backbone: {model_name}")
        print(f"  Quantization: {quantize or 'none (bf16)'}")
        print(f"  Device map: {device_map}")

        tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=trust_remote_code
        )
        model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)

        total_params = sum(p.numel() for p in model.parameters())
        print(f"  Backbone loaded: {total_params/1e9:.2f}B parameters (frozen)")

        return model, tokenizer

    def _init_absolute_potential_bias(self):
        """Bias state projector toward Absolute Potential (O12_ABS + Material)."""
        with torch.no_grad():
            final_layer = self.state_projector[-1]
            if hasattr(final_layer, 'bias') and final_layer.bias is not None:
                final_layer.bias.fill_(0.0)
                if final_layer.bias.shape[0] > 11:
                    final_layer.bias[11] = 1.0   # O12_ABS
                if final_layer.bias.shape[0] > 12:
                    final_layer.bias[12] = 0.8   # Material
                if final_layer.bias.shape[0] > 17:
                    final_layer.bias[17] = 0.3   # Fact

    def get_input_embeddings(self) -> nn.Module:
        """Return backbone's input embeddings (needed for CG token cache)."""
        return self.backbone.get_input_embeddings()

    def compute_state_delta(
        self,
        hidden: torch.Tensor,
        reset_state: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Compute 32D Sovereign State, full delta, and Bhava-only delta.

        Same interface as OntologicalHybridTransformer.compute_state_delta().
        """
        # Pool hidden states (mean over sequence)
        pooled = hidden.mean(dim=1)  # [B, D_mistral]

        # Project to 32D Sovereign State
        state = self.state_projector(pooled)  # [B, state_dim]

        # Extract Bhava slice
        bhava = state[:, BHAVA_SLICE]  # [B, 12]

        # Full state delta
        batch_changed = (
            self.prev_state is not None
            and self.prev_state.shape[0] != state.shape[0]
        )
        if reset_state or self.prev_state is None or batch_changed:
            delta_S = torch.zeros_like(state)
        else:
            delta_S = state - self.prev_state

        # Bhava-only delta
        bhava_changed = (
            self.prev_bhava is not None
            and self.prev_bhava.shape[0] != bhava.shape[0]
        )
        if reset_state or self.prev_bhava is None or bhava_changed:
            delta_bhava = torch.zeros_like(bhava)
        else:
            delta_bhava = bhava - self.prev_bhava

        # Update previous states
        self.prev_state = state.detach()
        self.prev_bhava = bhava.detach()

        return state, delta_S, delta_bhava

    def gradient_checkpointing_enable(self, **kwargs):
        """Enable gradient checkpointing on the backbone."""
        self.backbone.gradient_checkpointing_enable(**kwargs)
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self):
        """Disable gradient checkpointing on the backbone."""
        self.backbone.gradient_checkpointing_disable()
        self.gradient_checkpointing = False

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
        reset_state: bool = False,
        return_decorr_loss: bool = False,
        **kwargs,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass: frozen Mistral backbone + trainable CG adapter.

        Returns dict compatible with OntologicalHybridTransformer:
            - 'logits': [B, T, V]
            - 'state': [B, 32]
            - 'delta_S': [B, 32]
            - 'delta_bhava': [B, 12]
            - 'intent_phase': [B, H]
            - 'last_hidden_state': [B, T, D] (if return_last_hidden=True)
        """
        # ── Pass through frozen Mistral backbone ─────────────────────
        with torch.no_grad():
            backbone_out = self.backbone(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
            )

        # Extract hidden states (last layer)
        hidden = backbone_out.hidden_states[-1]  # [B, T, D_mistral]

        # ── Compute CG state delta (trainable) ───────────────────────
        state, delta_S, delta_bhava = self.compute_state_delta(hidden, reset_state)

        # Convert Bhava delta to phase rotation
        intent_phase = self.intent_projector(delta_bhava)  # [B, H]

        # ── Phase-conditioned adapter ────────────────────────────────
        # Expand intent_phase to match sequence length for concatenation
        B, T, D = hidden.shape
        phase_expanded = intent_phase.unsqueeze(1).expand(B, T, -1)  # [B, T, H]

        # Mix phase signal into hidden states
        adapter_input = torch.cat([hidden, phase_expanded], dim=-1)  # [B, T, D+H]
        adapter_output = self.phase_adapter(adapter_input)  # [B, T, D]

        # Gated residual: at init gate=0, so output = pure Mistral logits
        gate = torch.sigmoid(self.adapter_gate)
        adapted_hidden = hidden + gate * adapter_output  # [B, T, D]

        # ── Compute logits through Mistral's LM head (frozen) ────────
        # The LM head is part of the CausalLM model, extract it
        if hasattr(self.backbone, 'lm_head'):
            logits = self.backbone.lm_head(adapted_hidden)  # [B, T, V]
        else:
            # Fallback: use backbone's own logits (no phase adaptation)
            logits = backbone_out.logits

        # ── Build output dict ────────────────────────────────────────
        result = {
            'logits': logits,
            'state': state,
            'delta_S': delta_S,
            'delta_bhava': delta_bhava,
            'intent_phase': intent_phase,
        }

        if return_last_hidden:
            result['last_hidden_state'] = adapted_hidden

        if return_hidden and backbone_out.hidden_states is not None:
            result['hidden_states'] = backbone_out.hidden_states

        if return_decorr_loss:
            # Not applicable for frozen backbone, return zero
            result['decorr_loss'] = torch.tensor(0.0, device=input_ids.device)

        return result

    def trainable_parameters(self):
        """Yield only the trainable (non-frozen) parameters."""
        for name, param in self.named_parameters():
            if param.requires_grad:
                yield param

    def print_trainable_summary(self):
        """Print summary of trainable vs frozen parameters."""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        frozen = total - trainable
        print(f"\n  Parameter Summary:")
        print(f"    Total:     {total/1e6:.1f}M")
        print(f"    Frozen:    {frozen/1e6:.1f}M (Mistral backbone)")
        print(f"    Trainable: {trainable/1e6:.1f}M (CG adapter + state projector)")
        print(f"    Ratio:     {100*trainable/total:.2f}% trainable")

        # Breakdown by module
        for name, module in [
            ("state_projector", self.state_projector),
            ("intent_projector", self.intent_projector),
            ("phase_adapter", self.phase_adapter),
        ]:
            params = sum(p.numel() for p in module.parameters())
            print(f"      {name}: {params/1e3:.1f}K params")

        # CG modules (if attached)
        if hasattr(self, 'conscious_gen'):
            cg_params = sum(
                p.numel() for p in self.conscious_gen.parameters()
            )
            print(f"      conscious_gen: {cg_params/1e3:.1f}K params")
