"""
MistralHybridWrapper — Frozen Mistral backbone + trainable Phase attention layers.

Uses a pre-trained Mistral model (via HuggingFace Transformers) as the language
modeling backbone, with trainable Phase attention layers added on top.  Unlike
MistralCGWrapper this wrapper does NOT include Conscious Generation modules,
Sovereign State projection, or Bhava/Intent phase rotation.  It is the Mistral
equivalent of ``--model_type hybrid``.

Architecture:
    Mistral-7B (frozen, optional 4-bit) → hidden_states [B, T, D_mistral]
        ↓
    Trainable Phase Attention Layers (Local + Phase hybrid blocks)
        ↓
    LM Head (Mistral's, frozen)

The Phase layers learn long-range O(n) temporal context on top of Mistral's
pretrained representations.  Only Phase parameters are trained (~5-20M depending
on configuration), keeping the 7B backbone frozen.

Usage:
    python train_unified_llm.py \\
        --model_type mistral_hybrid \\
        --mistral_model_name mistralai/Mistral-7B-v0.3 \\
        --mistral_quantize 4bit
"""

from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torch.utils.checkpoint import checkpoint as torch_checkpoint

from symbolu.phase_transformer import (
    TransformerConfig,
    HybridBlock,
    LocalTransformerBlock,
)


class MistralHybridWrapper(nn.Module):
    """
    Wraps a frozen HuggingFace Mistral model with trainable Phase attention layers.

    The backbone is frozen (requires_grad=False).  Only the Phase hybrid layers
    and the adapter projection are trained.

    Returns outputs in the same dict format as HybridPhaseTransformer, so the
    existing training loop works without modification.
    """

    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-v0.3",
        quantize: Optional[str] = None,  # None, "4bit", "8bit"
        # Phase layer configuration
        num_phase_layers: int = 4,
        local_layers: int = 2,  # First N phase layers use local attention only
        window_size: int = 256,
        local_backend: str = "auto",
        alpha_local: float = 0.8,
        alpha_phase: float = 0.2,
        decay_gamma: float = 0.99,
        learned_decay: bool = True,
        protected_phase: bool = True,
        phase_adapter_hidden: int = 1024,
        # HuggingFace loading options
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
        self.embed_dim = self.mistral_hidden_dim  # alias for compatibility

        # Store phase config
        self.num_phase_layers = num_phase_layers
        self.local_layers = local_layers
        self.gradient_checkpointing = False

        # ── Trainable Phase attention layers ─────────────────────────
        head_dim = self.mistral_hidden_dim // self.num_heads

        phase_config = TransformerConfig(
            vocab_size=self.vocab_size,
            embed_dim=self.mistral_hidden_dim,
            num_layers=num_phase_layers,
            num_heads=self.num_heads,
            ff_dim=self.mistral_hidden_dim * 4,
            max_seq_len=mistral_config.max_position_embeddings,
            dropout=0.1,
            decay_gamma=decay_gamma,
        )

        self.phase_blocks = nn.ModuleList()
        for i in range(num_phase_layers):
            if i < local_layers:
                # Early phase layers: Local attention only
                self.phase_blocks.append(
                    LocalTransformerBlock(
                        phase_config,
                        window_size=window_size,
                        backend=local_backend,
                    )
                )
            else:
                # Later phase layers: Hybrid (Local + Phase) attention
                self.phase_blocks.append(
                    HybridBlock(
                        phase_config,
                        window_size=window_size,
                        local_backend=local_backend,
                        alpha_local=alpha_local,
                        alpha_phase=alpha_phase,
                        learned_decay=learned_decay,
                        protected_phase=protected_phase,
                    )
                )

        # Layer norm before Phase blocks (matches Mistral's output norm)
        self.phase_input_norm = nn.LayerNorm(self.mistral_hidden_dim)

        # Output projection: Phase output → residual correction
        # Start near zero so adapter doesn't disrupt Mistral initially
        self.phase_output_proj = nn.Sequential(
            nn.Linear(self.mistral_hidden_dim, phase_adapter_hidden),
            nn.GELU(),
            nn.Linear(phase_adapter_hidden, self.mistral_hidden_dim),
        )
        nn.init.zeros_(self.phase_output_proj[-1].weight)
        nn.init.zeros_(self.phase_output_proj[-1].bias)

        # Adapter gate (learnable scalar)
        # sigmoid(-2) ≈ 0.12: starts with minimal Phase influence
        self.adapter_gate = nn.Parameter(torch.tensor([-2.0]))

        # Ablation support
        self.ablation_config = None

    def set_ablation_config(self, config) -> None:
        """Set ablation config for post-training ablation audit."""
        self.ablation_config = config

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
                "transformers package required for mistral_hybrid. "
                "Install with: pip install transformers"
            )

        load_kwargs = {
            "device_map": device_map,
            "trust_remote_code": trust_remote_code,
            "torch_dtype": torch.bfloat16,
            "output_hidden_states": True,
            "attn_implementation": "flash_attention_2",
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

    def get_input_embeddings(self) -> nn.Module:
        """Return backbone's input embeddings."""
        return self.backbone.get_input_embeddings()

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
        return_decorr_loss: bool = False,
        **kwargs,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass: frozen Mistral backbone + trainable Phase layers.

        Returns dict compatible with HybridPhaseTransformer:
            - 'logits': [B, T, V]
            - 'last_hidden_state': [B, T, D] (if return_last_hidden=True)
            - 'hidden_states': list (if return_hidden=True)
            - 'decorr_loss': scalar (if return_decorr_loss=True)
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
        B, T, D = hidden.shape

        # ── Trainable Phase attention layers ─────────────────────────
        phase_input = self.phase_input_norm(hidden)

        x = phase_input
        hidden_states = [] if (return_hidden or extract_layers is not None) else None
        extract_set = set(extract_layers) if extract_layers is not None else None
        decorr_losses = [] if return_decorr_loss else None

        for i, block in enumerate(self.phase_blocks):
            is_hybrid_block = i >= self.local_layers

            use_ckpt = self.gradient_checkpointing and self.training and not return_decorr_loss
            if use_ckpt:
                x = torch_checkpoint(block, x, True, use_reentrant=True)
            else:
                if is_hybrid_block and return_decorr_loss:
                    x, decorr_loss = block(x, causal_mask=True, return_decorr_loss=True)
                    decorr_losses.append(decorr_loss)
                else:
                    x = block(x, causal_mask=True)

            if hidden_states is not None:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        # Project Phase output to residual correction
        phase_correction = self.phase_output_proj(x)  # [B, T, D]

        # Gated residual addition
        gate = torch.sigmoid(self.adapter_gate)
        adapted_hidden = hidden + gate * phase_correction  # [B, T, D]

        # ── Compute logits through Mistral's LM head (frozen) ────────
        if hasattr(self.backbone, 'lm_head'):
            logits = self.backbone.lm_head(adapted_hidden)  # [B, T, V]
        else:
            # Fallback: use backbone's own logits (no Phase adaptation)
            logits = backbone_out.logits

        # ── Build output dict (HybridPhaseTransformer compatible) ────
        result = {
            'logits': logits,
            'adapter_gate': gate.item() if isinstance(gate, torch.Tensor) else gate,
        }

        if hidden_states is not None:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = adapted_hidden

        if return_decorr_loss and decorr_losses:
            result['decorr_loss'] = torch.stack(decorr_losses).mean()
        elif return_decorr_loss:
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
        print(f"    Trainable: {trainable/1e6:.1f}M (Phase layers + adapter)")
        print(f"    Ratio:     {100*trainable/total:.2f}% trainable")

        # Breakdown by module
        for name, module in [
            ("phase_blocks", self.phase_blocks),
            ("phase_input_norm", self.phase_input_norm),
            ("phase_output_proj", self.phase_output_proj),
        ]:
            params = sum(p.numel() for p in module.parameters())
            print(f"      {name}: {params/1e3:.1f}K params")
