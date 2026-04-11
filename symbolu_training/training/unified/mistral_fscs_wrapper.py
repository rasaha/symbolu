"""
MistralFSCSWrapper — Frozen Mistral backbone + FSCS per-token gating on
every decoder layer.

EXPERIMENTAL. Code-complete, not yet benchmark-validated on a live Mistral
checkpoint. Requires operator execution on A100-80GB to measure r*.

This wrapper is modeled on MistralHybridWrapper (the *basic* Mistral
wrapper, i.e., no Conscious Generation modules, no Sovereign State
projection, no Bhava/Intent phase rotation). It differs in exactly one
way: instead of running Mistral as a feature extractor and adding
trainable layers on top, it *replaces each decoder layer in place* with
an FSCSGatedDecoderLayer that runs full + windowed attention per layer
and blends them per-token under the FSCS gate.

Architecture
------------
    input_ids
        │
        ▼
    Mistral embedding (frozen)
        │
        ▼
    [FSCSGatedDecoderLayer] × 32   ← FSCS gating per layer, per token
        │     each layer: full attn + windowed attn → per-token blend
        │     under coherence gate with boundary + layer cap +
        │     cross-layer caution
        ▼
    Mistral final norm (frozen)
        │
        ▼
    Mistral LM head (frozen)
        │
        ▼
    logits

Trainable parameters (only these are trained if you co-train):
    - Per-layer FSCS gate τ and α (3 bands × 2 params = 6 scalars per band,
      plus layer assignment — typically a few dozen floats total)
    - Nothing else

All ~7B Mistral parameters are frozen. The FSCS wrapper adds a negligible
number of trainable parameters (~0.001% of Mistral).

Usage
-----
    from symbolu_training.training.unified.mistral_fscs_wrapper \\
        import MistralFSCSWrapper
    from symbolu.fscs.core import FSCSConfig

    cfg = FSCSConfig(coarse_window=256, use_hard_routing=False)
    wrapper = MistralFSCSWrapper(
        model_name="mistralai/Mistral-7B-v0.3",
        quantize="4bit",
        fscs_cfg=cfg,
    )

    input_ids = tokenizer("Hello world", return_tensors="pt").input_ids
    outputs = wrapper(input_ids=input_ids)
    logits = outputs["logits"]

For a full r* sweep, see scripts/r_star_sweep.py.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn

from symbolu.fscs.core import FSCSConfig
from symbolu.fscs.mistral_gated_layer import FSCSGatedDecoderLayer


# Heuristic v1 boundary tokens (§3.1). These are ASCII / punctuation
# characters that commonly mark structural boundaries in code and prose.
# MistralFSCSWrapper resolves them to token IDs via the tokenizer at
# construction time. Falls back to empty list if any token is missing.
_DEFAULT_BOUNDARY_CHARS = [
    "\n",           # newline
    "\n\n",         # paragraph break
    "{", "}",       # braces
    "(", ")",       # parens
    "[", "]",       # brackets
    ";",            # semicolon
    ".", "!", "?",  # sentence-final punctuation
]


class MistralFSCSWrapper(nn.Module):
    """
    Frozen Mistral-7B backbone with FSCS gating installed on every
    decoder layer. No Conscious Generation plumbing.

    This wrapper loads the Mistral checkpoint the same way MistralHybridWrapper
    does (same _load_mistral static method signature), but instead of adding
    trainable Phase layers on top, it walks over Mistral's decoder layers and
    replaces each one with an FSCSGatedDecoderLayer that wraps the original.

    The wrapping is *in-place on the model.model.layers ModuleList*. The
    underlying Mistral parameters are not modified or copied — the gated
    layers hold references to the original layers.
    """

    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-v0.3",
        quantize: Optional[str] = None,  # None, "4bit", "8bit"
        fscs_cfg: Optional[FSCSConfig] = None,
        device_map: str = "auto",
        trust_remote_code: bool = False,
        pretrained_model: Optional[nn.Module] = None,
        pretrained_tokenizer: Optional[object] = None,
    ):
        super().__init__()

        # ── Load or accept Mistral backbone (same pattern as MistralHybridWrapper)
        if pretrained_model is not None:
            self.backbone = pretrained_model
            self.tokenizer = pretrained_tokenizer
        else:
            self.backbone, self.tokenizer = self._load_mistral(
                model_name, quantize, device_map, trust_remote_code,
            )

        # Freeze the backbone entirely
        for p in self.backbone.parameters():
            p.requires_grad = False

        # Extract model dimensions
        mistral_config = self.backbone.config
        self.num_layers = mistral_config.num_hidden_layers
        self.num_heads = mistral_config.num_attention_heads
        self.hidden_dim = mistral_config.hidden_size
        self.vocab_size = mistral_config.vocab_size

        # FSCS config — defaults if not supplied
        if fscs_cfg is None:
            fscs_cfg = FSCSConfig()
        self.fscs_cfg = fscs_cfg

        # Resolve boundary token IDs from the tokenizer (§3.1 heuristic v1)
        if self.tokenizer is not None:
            fscs_cfg.boundary_token_ids = tuple(
                self._resolve_boundary_tokens(self.tokenizer)
            )

        # ── Install FSCS gated layers in place ────────────────────────
        # Walk the decoder layer list and wrap each one. We assign bands
        # based on layer depth:
        #     first third  → global  (hardest to gate, most conservative)
        #     middle third → mid
        #     last third   → local   (easiest to gate, most aggressive)
        layers = self._get_decoder_layers(self.backbone)
        num_layers = len(layers)
        self.num_layers = num_layers

        gated_layers = nn.ModuleList()
        for i, original in enumerate(layers):
            band = self._assign_band(i, num_layers)
            gated = FSCSGatedDecoderLayer(
                original_layer=original,
                cfg=fscs_cfg,
                band=band,
            )
            gated_layers.append(gated)

        # Splice the gated layers back into the Mistral model in place.
        # This makes Mistral's own forward pass call our gated layers.
        self._install_gated_layers(self.backbone, gated_layers)
        self.gated_layers = gated_layers  # Keep a reference for metric extraction

        # Sync trainable FSCS params to backbone device
        self._sync_fscs_device()

    # ------------------------------------------------------------------ #
    # Mistral model loading (mirrors MistralHybridWrapper._load_mistral)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_mistral(
        model_name: str,
        quantize: Optional[str],
        device_map: str,
        trust_remote_code: bool,
    ) -> Tuple[nn.Module, object]:
        """Load Mistral from HuggingFace, mirroring MistralHybridWrapper."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "transformers package required for MistralFSCSWrapper. "
                "Install with: pip install transformers"
            ) from e

        load_kwargs: Dict[str, Any] = {
            "device_map": device_map,
            "trust_remote_code": trust_remote_code,
            "torch_dtype": torch.bfloat16,
            "output_hidden_states": False,
            # Text-FSCS relies on SDPA rather than flash_attention_2 because
            # we call self_attn twice per layer with different masks, and
            # SDPA handles arbitrary additive masks while flash_attention_2
            # has stricter mask-layout requirements.
            "attn_implementation": "sdpa",
        }

        if quantize in ("4bit", "8bit"):
            # Preflight: bitsandbytes quantization paths in recent
            # transformers versions call model.set_submodule(), which was
            # only added to torch.nn.Module in PyTorch 2.5. Older torch +
            # newer transformers produces a confusing deep stack trace:
            #     AttributeError: 'MistralForCausalLM' object has no
            #     attribute 'set_submodule'. Did you mean: 'get_submodule'?
            # Catch it here and either auto-fall-back to bf16 (when the
            # operator has not explicitly requested 4-bit) or raise a
            # clear diagnostic pointing at the torch upgrade path.
            import torch.nn as _nn
            _has_set_submodule = hasattr(_nn.Module, "set_submodule")
            if not _has_set_submodule:
                _msg = (
                    f"[MistralFSCSWrapper] torch {torch.__version__} does not "
                    f"provide torch.nn.Module.set_submodule, which recent "
                    f"transformers versions require for bitsandbytes "
                    f"{quantize} quantization. You have three options:\n"
                    f"  1. Upgrade torch: pip install --upgrade 'torch>=2.5'\n"
                    f"  2. Downgrade transformers: pip install 'transformers==4.44.*'\n"
                    f"  3. Run without quantization (bf16, ~14GB VRAM):\n"
                    f"     ./scripts/run_fscs_rstar_measurement.sh --sanity --quantize bf16"
                )
                print(_msg, file=sys.stderr)
                raise RuntimeError(
                    f"bitsandbytes {quantize} quantization requires "
                    f"torch>=2.5 with this transformers version; "
                    f"current torch is {torch.__version__}."
                )
            try:
                from transformers import BitsAndBytesConfig
                import bitsandbytes as _bnb  # noqa: F401
            except ImportError as e:
                raise ImportError(
                    "bitsandbytes required for quantization. "
                    "Install with: pip install -U bitsandbytes>=0.46.1"
                ) from e
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

        print(f"[MistralFSCSWrapper] Loading backbone: {model_name}")
        print(f"[MistralFSCSWrapper] Quantization: {quantize or 'none (bf16)'}")
        print(f"[MistralFSCSWrapper] Device map: {device_map}")

        tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=trust_remote_code,
        )
        model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)

        total_params = sum(p.numel() for p in model.parameters())
        print(f"[MistralFSCSWrapper] Backbone loaded: "
              f"{total_params / 1e9:.2f}B parameters (frozen)")
        return model, tokenizer

    # ------------------------------------------------------------------ #
    # Structural helpers — finding and replacing Mistral decoder layers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_decoder_layers(backbone: nn.Module) -> nn.ModuleList:
        """
        Locate the decoder layer list in a Mistral model.

        HuggingFace MistralForCausalLM exposes layers at
        ``backbone.model.layers`` (the outer ``backbone`` is the top-level
        CausalLM, and its ``.model`` is the MistralModel). We handle both
        that canonical layout and a fallback where ``backbone.layers``
        exists directly, for maximum compatibility.
        """
        # Canonical layout: MistralForCausalLM → .model → .layers
        if hasattr(backbone, "model") and hasattr(backbone.model, "layers"):
            return backbone.model.layers
        if hasattr(backbone, "layers"):
            return backbone.layers
        raise AttributeError(
            "Could not find a decoder layer list on the backbone. Expected "
            "backbone.model.layers (MistralForCausalLM) or backbone.layers."
        )

    @staticmethod
    def _install_gated_layers(
        backbone: nn.Module, gated_layers: nn.ModuleList,
    ) -> None:
        """
        Replace backbone.model.layers (or backbone.layers) with the
        FSCS-wrapped layer list, in place.
        """
        if hasattr(backbone, "model") and hasattr(backbone.model, "layers"):
            backbone.model.layers = gated_layers
            return
        if hasattr(backbone, "layers"):
            backbone.layers = gated_layers
            return
        raise AttributeError(
            "Could not install gated layers — backbone.model.layers not found."
        )

    # ------------------------------------------------------------------ #
    # Band assignment and boundary-token resolution
    # ------------------------------------------------------------------ #

    @staticmethod
    def _assign_band(layer_idx: int, num_layers: int) -> str:
        """
        Assign each decoder layer to one of three FSCS bands based on depth.

        Early layers (first third)  → global: highest τ, most conservative
                                      gating, best at long-range context.
        Middle layers (middle third) → mid: intermediate τ, paragraph
                                       structure.
        Late layers (last third)    → local: lowest τ, easiest to gate,
                                      local syntax and short-range fluency.

        This is a first-pass heuristic. Empirically, late Mistral layers
        tend to be more specialized and less redundant than early ones,
        so the opposite mapping is also plausible and is explicitly one
        of the ablations called out in scripts/r_star_sweep.py.
        """
        third = num_layers // 3
        if layer_idx < third:
            return "global"
        if layer_idx < 2 * third:
            return "mid"
        return "local"

    @staticmethod
    def _resolve_boundary_tokens(tokenizer: Any) -> List[int]:
        """
        Turn the heuristic boundary characters into Mistral tokenizer IDs.
        Skips any character that doesn't resolve to a single-token ID.
        """
        ids: List[int] = []
        for ch in _DEFAULT_BOUNDARY_CHARS:
            try:
                encoded = tokenizer.encode(ch, add_special_tokens=False)
            except Exception:
                continue
            if len(encoded) == 1:
                ids.append(int(encoded[0]))
        # Deduplicate but preserve order
        seen = set()
        out = []
        for tid in ids:
            if tid not in seen:
                seen.add(tid)
                out.append(tid)
        return out

    # ------------------------------------------------------------------ #
    # Device sync
    # ------------------------------------------------------------------ #

    def _sync_fscs_device(self) -> None:
        """Move FSCS trainable params to the backbone's device / dtype."""
        try:
            bp = next(self.backbone.parameters())
        except StopIteration:
            return
        device, dtype = bp.device, bp.dtype
        for gl in self.gated_layers:
            # Only move the FSCS control-plane submodules, not the wrapped
            # original layer (which is already on the right device).
            gl.coherence_module.to(device=device, dtype=dtype)
            gl.routing_gate.to(device=device, dtype=dtype)
            gl.boundary_detector.to(device=device, dtype=dtype)
            gl.layer_cap.to(device=device, dtype=dtype)
            gl.surprise_suppressor.to(device=device, dtype=dtype)

    # ------------------------------------------------------------------ #
    # Forward pass — runs the backbone with gated layers installed
    # ------------------------------------------------------------------ #

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Forward pass through the FSCS-gated Mistral backbone.

        Before the backbone forward call, we push the current input_ids
        into each gated layer so its boundary detector can see them.

        After the backbone forward call, we collect per-layer gate
        fractions and propagate them forward for cross-layer caution on
        the next forward pass (this is a stateful approximation of §8 —
        strictly, cross-layer caution should propagate *within* a
        forward pass, which requires a manual layer loop; the stateful
        approximation is sufficient for the r* measurement and is
        simpler to implement correctly on top of HF's backbone forward).
        """
        # Push input_ids into each gated layer for boundary detection
        for gl in self.gated_layers:
            gl.set_current_input_ids(input_ids)

        # Strip cache-related kwargs before the backbone call.
        # The FSCS dual-branch forward calls self_attn twice per layer,
        # and any cache object created by MistralModel.forward would be
        # mutated twice (K and V both doubled in length) because HF's
        # MistralAttention.forward writes into past_key_value regardless
        # of the use_cache flag. For eval on complete sequences the
        # cache is pure overhead anyway.
        _bb_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("past_key_values", "past_key_value", "use_cache")
        }

        # Run the backbone forward pass — the gated layers are already
        # installed inside backbone.model.layers, so this call dispatches
        # to them layer by layer.
        backbone_out = self.backbone(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
            output_hidden_states=False,
            use_cache=False,
            past_key_values=None,
            **_bb_kwargs,
        )

        # Collect per-layer metrics
        layer_metrics: List[Dict[str, float]] = []
        prev_frac = 0.0
        for i, gl in enumerate(self.gated_layers):
            layer_metrics.append({
                "layer": i,
                "band": gl.band,
                "gate_fraction": gl.last_gate_fraction,
                "mean_pi": gl.last_mean_pi,
            })
            # Propagate this layer's gate fraction into the next layer for
            # the next forward pass (stateful cross-layer caution)
            if i + 1 < len(self.gated_layers):
                self.gated_layers[i + 1].set_prev_layer_gate_fraction(
                    gl.last_gate_fraction
                )
            prev_frac = gl.last_gate_fraction  # for the wraparound on next call

        # Aggregate metrics
        gate_fractions = [m["gate_fraction"] for m in layer_metrics]
        mean_gate_fraction = sum(gate_fractions) / max(1, len(gate_fractions))

        out: Dict[str, Any] = {
            "logits": backbone_out.logits,
            "layer_metrics": layer_metrics,
            "mean_gate_fraction": mean_gate_fraction,
        }
        if hasattr(backbone_out, "loss") and backbone_out.loss is not None:
            out["loss"] = backbone_out.loss
        return out

    # ------------------------------------------------------------------ #
    # Mode switching
    # ------------------------------------------------------------------ #

    def set_hard_routing(self, enabled: bool) -> None:
        """Switch all gated layers between Mode 2 (soft) and Mode 3 (hard)."""
        self.fscs_cfg.use_hard_routing = enabled
        for gl in self.gated_layers:
            gl.cfg = self.fscs_cfg  # cfg is shared by reference, but be explicit

    def set_coarse_window(self, window: int) -> None:
        """Change the windowed coarse operator width for all layers."""
        self.fscs_cfg.coarse_window = int(window)
        for gl in self.gated_layers:
            gl.cfg = self.fscs_cfg

    def set_band_thresholds(
        self,
        tau_global: float,
        tau_mid: float,
        tau_local: float,
    ) -> None:
        """
        Explicitly set the per-band τ values across all gated layers.
        Used by the r* sweep to walk the gating threshold.
        """
        self.fscs_cfg.tau_global = tau_global
        self.fscs_cfg.tau_mid = tau_mid
        self.fscs_cfg.tau_local = tau_local
        with torch.no_grad():
            for gl in self.gated_layers:
                if gl.band == "global":
                    gl.routing_gate.tau.fill_(tau_global)
                elif gl.band == "mid":
                    gl.routing_gate.tau.fill_(tau_mid)
                else:
                    gl.routing_gate.tau.fill_(tau_local)

    # ------------------------------------------------------------------ #
    # Convenience: trainable parameter count
    # ------------------------------------------------------------------ #

    def fscs_trainable_parameters(self) -> int:
        """Number of trainable parameters introduced by FSCS (excluding backbone)."""
        return sum(
            p.numel()
            for gl in self.gated_layers
            for p in gl.parameters()
            if p.requires_grad
        )
