"""
symbolu/fscs/mistral_gated_layer.py — FSCS gating wrapper around a frozen
Mistral decoder layer.

EXPERIMENTAL. Code-complete, not yet benchmark-validated on a live Mistral
checkpoint. Smoke test lives at tests/test_fscs_core.py; full validation
requires running scripts/r_star_sweep.py on an A100 with Mistral weights.

Strategy
--------
We do not reimplement MistralAttention. We wrap a pre-existing Mistral
decoder layer and call its attention module twice per forward pass:

    1. Once with the normal full-causal attention (uses Mistral's own
       SDPA / flash-attention path, RoPE, GQA — whatever the checkpoint
       was trained with).
    2. Once with a windowed-causal attention mask that limits attention
       to a sliding window of W most-recent positions.

The two output tensors [B, N, D] are then blended per-token according to
the FSCS coherence gate π, under layer-cap and boundary-detector
constraints. The blended attention output replaces what the decoder
layer would normally pass to its MLP.

This gives us a valid r* measurement — *"what fraction of tokens can be
routed to the windowed branch before PPL degrades?"* — without touching
Mistral's attention internals. The tradeoff is that:

    - We compute BOTH branches, so this measurement does not yield
      wall-clock savings. It measures the *quality ceiling* only. Compute
      savings are a separate Mode-3 measurement that hard-routes and only
      runs one branch per token.
    - We gate per-token, not per-head. The per-head variant from the full
      Text-FSCS spec is deferred (requires reimplementing Mistral's
      attention internals).

The FSCSGatedDecoderLayer class is a drop-in replacement for a
MistralDecoderLayer — it has the same callable signature
`(hidden_states, attention_mask, position_ids, ...) -> (output, ...)`.
MistralFSCSWrapper swaps each of Mistral's layers in place with one of
these wrappers at construction time.

Requires: transformers >= 4.36 (for MistralDecoderLayer public API).
"""

from __future__ import annotations

from typing import Any, Optional

import torch
import torch.nn as nn

from symbolu.fscs.core import (
    FSCSConfig,
    FSCSCoherenceModule,
    FSCSRoutingGate,
    FSCSBoundaryDetector,
    FSCSLayerCap,
    FSCSSurpriseDeltaSuppressor,
    FSCSEMACache,
    FSCSCoarseAdapter,
    fscs_alignment_loss,
)


def _build_windowed_attention_mask(
    batch_size: int,
    seq_len: int,
    window: int,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    """
    Build an additive causal+windowed attention mask of shape
    [B, 1, N, N] suitable for Mistral's attention forward.

    Entries are 0.0 where attention is allowed, and the large-negative
    mask value where blocked, matching HuggingFace's additive-mask
    convention.

    Windowed causal: position t can attend to positions
    [max(0, t - window + 1), t].
    """
    # [N, N] — True where masked out
    row = torch.arange(seq_len, device=device).unsqueeze(1)  # [N, 1]
    col = torch.arange(seq_len, device=device).unsqueeze(0)  # [1, N]
    causal_block = col > row                                  # True above diag
    window_block = col < (row - window + 1)                   # Outside window
    blocked = causal_block | window_block                     # [N, N]

    neg_inf = torch.finfo(dtype).min
    mask = torch.zeros(seq_len, seq_len, device=device, dtype=dtype)
    mask.masked_fill_(blocked, neg_inf)
    return mask.view(1, 1, seq_len, seq_len).expand(batch_size, 1, seq_len, seq_len)


class FSCSGatedDecoderLayer(nn.Module):
    """
    Wraps a single frozen MistralDecoderLayer with per-token FSCS gating.

    This module holds a reference to the original decoder layer and
    delegates the non-attention parts (input LayerNorm, residual connection,
    MLP, post-attention LayerNorm) to it. It intercepts the attention
    computation to run both full and windowed branches and blend them.

    Parameters
    ----------
    original_layer : nn.Module
        An already-instantiated MistralDecoderLayer with its weights
        frozen. We do not replace any of its weights.
    cfg : FSCSConfig
        FSCS configuration.
    band : str
        Which band this layer belongs to — "global", "mid", or "local".
        Determines the τ/α initialization for the routing gate.
    """

    def __init__(
        self,
        original_layer: nn.Module,
        cfg: FSCSConfig,
        band: str = "mid",
    ):
        super().__init__()
        self.original_layer = original_layer
        self.cfg = cfg
        self.band = band

        # FSCS control-plane modules. These are the only trainable
        # parameters introduced by FSCS in this wrapper.
        self.coherence_module = FSCSCoherenceModule(cfg)
        self.routing_gate = FSCSRoutingGate(cfg, band=band)
        self.boundary_detector = FSCSBoundaryDetector(cfg)
        self.layer_cap = FSCSLayerCap(cfg)
        self.surprise_suppressor = FSCSSurpriseDeltaSuppressor(cfg)

        # EMA-cache coarse operator (§9.1). Three activation modes:
        #
        # 1. cfg.use_ema_cache = True (global override):
        #    ALL layers use EMA cache regardless of band. This is
        #    the mode used for the v5_ema_cache.json measurement.
        #
        # 2. cfg.use_per_band_coarse = True (recommended, spec §9):
        #    Band-differentiated coarse operators:
        #      Global band → EMA cache  (long-range context)
        #      Mid band    → EMA cache  (paragraph structure)
        #      Local band  → windowed attention (local syntax)
        #    This gives each band the operator matched to its function.
        #
        # 3. Both False (default):
        #    ALL layers use windowed attention. This is the baseline
        #    used in v3_window256.json and v3_window1024.json.
        use_per_band = bool(getattr(cfg, "use_per_band_coarse", False))
        use_global_ema = bool(getattr(cfg, "use_ema_cache", False))

        if use_global_ema:
            # Mode 1: all layers use EMA cache
            self.use_ema_cache = True
        elif use_per_band:
            # Mode 2: band-differentiated
            # Global and Mid bands get EMA cache (they handle long-range
            # and paragraph-level context). Local band gets windowed
            # attention (handles local syntax where exact recent context
            # matters more than smoothed history).
            self.use_ema_cache = (band in ("global", "mid"))
        else:
            # Mode 3: all layers use windowed attention
            self.use_ema_cache = False

        if self.use_ema_cache:
            self.ema_cache: Optional[nn.Module] = FSCSEMACache(cfg)
        else:
            self.ema_cache = None

        # Optional coarse adapter for alignment-loss co-training.
        # Disabled by default so the frozen-backbone inference path is
        # unchanged. Enable via cfg.use_coarse_adapter = True when
        # running scripts/train_fscs_alignment.py. The adapter is the
        # piece the §12.2 alignment loss actually trains — without it,
        # the "coarse path" shares all weights with the full path
        # (same Q/K/V/O projections, only the mask differs) and the
        # alignment loss has nothing to act on.
        self.use_coarse_adapter = bool(getattr(cfg, "use_coarse_adapter", False))
        if self.use_coarse_adapter:
            d_model = self._infer_d_model(original_layer)
            d_inner = int(getattr(cfg, "coarse_adapter_d_inner", 256))
            self.coarse_adapter: Optional[nn.Module] = FSCSCoarseAdapter(
                d_model=d_model,
                d_inner=d_inner,
            )
        else:
            self.coarse_adapter = None

        # Accumulated per-forward alignment loss, read by the training
        # loop via get_alignment_loss(). Zero when the adapter is
        # disabled or when forward has not run yet.
        self._last_alignment_loss: Optional[torch.Tensor] = None

        # We need to know the attention module's callable signature.
        # MistralDecoderLayer exposes .self_attn and .mlp as submodules,
        # with .input_layernorm and .post_attention_layernorm around them.
        # We read these attributes so we can reproduce the decoder layer's
        # residual flow here.
        required_attrs = (
            "self_attn",
            "mlp",
            "input_layernorm",
            "post_attention_layernorm",
        )
        for attr in required_attrs:
            if not hasattr(original_layer, attr):
                raise AttributeError(
                    f"FSCSGatedDecoderLayer expected the wrapped layer to have "
                    f"attribute {attr!r}. Got a layer of type "
                    f"{type(original_layer).__name__} with attributes "
                    f"{[a for a in dir(original_layer) if not a.startswith('_')]}. "
                    f"This wrapper assumes the HuggingFace MistralDecoderLayer "
                    f"layout. If you are using a different transformer class, "
                    f"override the forward pass accordingly."
                )

        # The current input_ids — set by MistralFSCSWrapper each forward
        # pass so the boundary detector knows which tokens are boundaries.
        # Stored as a non-persistent attribute (not a Parameter or Buffer).
        self._current_input_ids: Optional[torch.Tensor] = None

        # Cross-layer caution: this layer reads the previous layer's
        # gating fraction from the wrapper, via this attribute, and uses
        # it to raise τ (be more conservative) per §8.
        self._prev_layer_gate_fraction: float = 0.0

        # Running stats, populated each forward pass for the wrapper to
        # aggregate into per-run metrics.
        self.last_gate_fraction: float = 0.0
        self.last_mean_pi: float = 0.0

    @staticmethod
    def _infer_d_model(original_layer: nn.Module) -> int:
        """
        Infer d_model from the wrapped Mistral decoder layer. Used only
        when the coarse adapter is enabled.

        HuggingFace MistralDecoderLayer exposes `hidden_size` via
        `self_attn.head_dim * self_attn.num_heads`, but the simpler
        path is to read the output projection's in_features, which
        equals d_model by construction.
        """
        try:
            return int(original_layer.self_attn.o_proj.in_features)
        except AttributeError:
            pass
        try:
            return int(original_layer.self_attn.head_dim *
                       original_layer.self_attn.num_heads)
        except AttributeError:
            pass
        raise AttributeError(
            "Could not infer d_model from the wrapped decoder layer. "
            "Expected original_layer.self_attn.o_proj.in_features or "
            "(self_attn.head_dim * self_attn.num_heads). Layer type: "
            f"{type(original_layer).__name__}"
        )

    def get_alignment_loss(self) -> Optional[torch.Tensor]:
        """
        Return the alignment loss accumulated in the most recent
        forward pass, or None if the coarse adapter is disabled or
        forward has not been called yet.

        Called by the training loop in scripts/train_fscs_alignment.py.
        """
        return self._last_alignment_loss

    # ------------------------------------------------------------------ #
    # Interface expected by MistralFSCSWrapper
    # ------------------------------------------------------------------ #

    def set_current_input_ids(self, input_ids: torch.Tensor) -> None:
        """Called by the wrapper each forward pass for the boundary detector."""
        self._current_input_ids = input_ids

    def set_prev_layer_gate_fraction(self, fraction: float) -> None:
        """Cross-layer caution input from the previous layer."""
        self._prev_layer_gate_fraction = float(fraction)

    # ------------------------------------------------------------------ #
    # Core forward pass
    # ------------------------------------------------------------------ #

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        position_ids: Optional[torch.Tensor] = None,
        past_key_value: Optional[Any] = None,
        output_attentions: bool = False,
        use_cache: bool = False,
        **kwargs: Any,
    ) -> torch.Tensor:
        """
        MistralDecoderLayer.forward-compatible signature.

        The two attention branches (full vs windowed) share the same
        input LayerNorm, the same Q/K/V projections, and the same
        output projection. Only their attention masks differ. The
        blend happens *after* the original layer's attention output
        projection but *before* its MLP + post-attention layernorm.
        """
        # Stash the original residual exactly as the stock decoder layer does
        residual = hidden_states

        # Apply the input layernorm (same for both branches)
        normed = self.original_layer.input_layernorm(hidden_states)

        B, N, D = normed.shape
        device = normed.device
        dtype = normed.dtype

        # ---- Cache-free kwargs for both branches ---------------------
        # We call self_attn twice per forward pass (full branch, then
        # coarse branch). HF's MistralAttention writes into past_key_value
        # unconditionally if it is not None — even if use_cache=False —
        # because the .update(K, V, ...) call happens independently of
        # the use_cache flag. If we passed the same Cache object to both
        # branches, the coarse branch would see K doubled in length.
        # For eval on complete sequences the cache has no functional
        # purpose, so we strip it entirely and force use_cache=False.
        #
        # We also strip any past_key_value / past_key_values that may
        # have been threaded through **kwargs by recent HF versions —
        # the explicit parameter is defensively ignored below as well.
        _sa_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("past_key_value", "past_key_values")
        }

        # ---- Branch 1: Full attention ---------------------------------
        # Call the original self_attn with the caller-provided attention
        # mask (which is the normal causal mask from Mistral's runner).
        # past_key_value is forced to None so Mistral does not mutate any
        # cache object shared with the coarse branch below.
        attn_full_out = self.original_layer.self_attn(
            hidden_states=normed,
            attention_mask=attention_mask,
            position_ids=position_ids,
            past_key_value=None,
            output_attentions=False,
            use_cache=False,
            **_sa_kwargs,
        )
        # Mistral's self_attn returns a tuple (attn_output, attn_weights, past_kv).
        # We only need the first element; attn_weights will be None because
        # we passed output_attentions=False.
        if isinstance(attn_full_out, tuple):
            out_full = attn_full_out[0]
        else:
            out_full = attn_full_out  # Some versions return a tensor directly

        # ---- Branch 2: Coarse output ------------------------------------
        # Two modes depending on whether EMA cache is enabled:
        #
        # Mode A (EMA cache, §9.1 — preferred for Global/Mid bands):
        #   Uses a running exponential moving average of the full branch
        #   output. NO second self_attn call — O(1) compute per position.
        #   The EMA state carries a compressed summary of ALL previous
        #   positions' full-attention outputs, so the coarse branch has
        #   long-range context the windowed operator would lose.
        #
        # Mode B (windowed attention, §9 Local-band path — original):
        #   Runs self_attn a second time with a sliding-window mask.
        #   O(N·w) compute. The coarse branch sees only the last
        #   `coarse_window` tokens.
        if self.ema_cache is not None:
            # EMA cache mode: use the full-branch output to update the
            # cache, then use the cache state as the coarse output.
            # This means: out_coarse_t = β·cache_{t-1} + (1-β)·out_full_t
            # At positions where the gate routes to "coarse," the model
            # gets a smoothed, long-range-aware version of the full output
            # rather than a truncated windowed version.
            out_coarse = self.ema_cache(out_full.detach())
        else:
            # Windowed attention mode (original)
            windowed_mask = _build_windowed_attention_mask(
                B, N, self.cfg.coarse_window, device, dtype,
            )
            attn_coarse_out = self.original_layer.self_attn(
                hidden_states=normed,
                attention_mask=windowed_mask,
                position_ids=position_ids,
                past_key_value=None,
                output_attentions=False,
                use_cache=False,
                **_sa_kwargs,
            )
            if isinstance(attn_coarse_out, tuple):
                out_coarse = attn_coarse_out[0]
            else:
                out_coarse = attn_coarse_out

        # ---- Optional coarse adapter + alignment loss ---------------
        # When the coarse adapter is enabled, pass the windowed
        # attention output through a small trainable residual module.
        # This is the only place in the gated layer where §12.2
        # alignment loss has a trainable target to act on. The adapter
        # is residual-initialized (zero weights on the up-projection +
        # sigmoid gate starting near sigmoid(-2) ≈ 0.12), so at step 0
        # the adapted coarse output equals the raw coarse output and
        # the forward pass is numerically identical to the
        # adapter-disabled path.
        if self.coarse_adapter is not None:
            # Run the adapter on the raw coarse output. The adapter's
            # own dtype is whatever the optimizer configured it to
            # be; we cast inputs to that dtype for safety.
            adapter_dtype = next(self.coarse_adapter.parameters()).dtype
            out_coarse_adapted = self.coarse_adapter(
                out_coarse.to(adapter_dtype)
            )
            # Cast back to the backbone's dtype so the downstream
            # blend sees a consistent dtype.
            out_coarse = out_coarse_adapted.to(out_full.dtype)

            # Alignment loss: ||stopgrad(O_full) - O_coarse||²
            # Computed in the adapter's dtype (likely fp32) for
            # numerical stability; the lambda weight is applied
            # inside fscs_alignment_loss.
            self._last_alignment_loss = fscs_alignment_loss(
                output_full=out_full.to(adapter_dtype),
                output_coarse=out_coarse_adapted,
                lambda_weight=float(getattr(self.cfg, "alignment_lambda", 0.1)),
            )
        else:
            self._last_alignment_loss = None

        # ---- FSCS gate ------------------------------------------------
        # Compute coherence from the full branch output + residual stream.
        coherence = self.coherence_module(out_full.detach(), residual)  # [B, N]

        # Base routing probability
        pi = self.routing_gate(coherence)                               # [B, N]

        # Boundary suppression (§3): force π = 0 at structural boundaries
        if self._current_input_ids is not None and self.cfg.use_boundary_detector:
            B_t = self.boundary_detector(self._current_input_ids)       # [B, N]
            if B_t.device != pi.device:
                B_t = B_t.to(pi.device)
            pi = pi * (1.0 - B_t)

        # Surprise-delta (§2): suppress π where token surprise is climbing
        # Not used in the frozen-backbone r* measurement path because
        # surprise is pre-computed from the baseline; the wrapper can set
        # this via set_current_token_surprise() if desired.
        # (Hook left in place for future use.)

        # Cross-layer caution (§8): raise τ if the previous layer gated
        # aggressively. Implemented by multiplicatively shrinking π.
        if self._prev_layer_gate_fraction > self.cfg.r_threshold:
            penalty = 1.0 / (1.0 + self.cfg.zeta * (
                self._prev_layer_gate_fraction - self.cfg.r_threshold
            ))
            pi = pi * penalty

        # Layer cap (§7): clamp the fraction of tokens routed to coarse
        pi = self.layer_cap.apply(pi, training=self.training)

        # ---- Dtype reconciliation -------------------------------------
        # The FSCS control plane (coherence module, routing gate,
        # layer cap, boundary detector) runs in float32 by default
        # because its parameters were created without being cast to
        # the backbone dtype. The Mistral backbone is bf16. If we blend
        # a float32 pi tensor with bf16 attention outputs, PyTorch dtype
        # promotion turns the blend into float32, which then flows
        # through residual + layernorm + mlp and collides with the
        # bf16 weights of mlp.gate_proj / up_proj / down_proj.
        #
        # The fix is to cast pi back to the backbone dtype before the
        # blend. We also cast the blended attention output back to
        # residual.dtype belt-and-suspenders in case any upstream op
        # (layer cap, boundary mask) still produced a float32 value.
        target_dtype = out_full.dtype
        pi = pi.to(target_dtype)

        # ---- Blend full and coarse outputs ----------------------------
        if self.cfg.use_hard_routing and not self.training:
            # Mode 3: hard route per token
            theta = self.cfg.hard_route_threshold
            use_coarse = (pi > theta).unsqueeze(-1)  # [B, N, 1]
            attn_blended = torch.where(use_coarse, out_coarse, out_full)
            # Record the ACTUAL fraction of tokens routed (for cross-layer
            # caution on the next layer and for metrics)
            gated_frac = (pi > theta).float().mean().item()
        else:
            # Mode 1/2: soft blend per token
            pi_exp = pi.unsqueeze(-1)                # [B, N, 1]
            attn_blended = (1.0 - pi_exp) * out_full + pi_exp * out_coarse
            # Record the "effective" fraction via the mean of pi
            gated_frac = pi.float().mean().item()

        # Belt-and-suspenders: the blend may still have promoted to
        # float32 if any upstream code path mixed dtypes. Cast back to
        # the residual's dtype so the rest of the decoder layer
        # (layernorm + mlp + residual2) sees a uniform dtype.
        attn_blended = attn_blended.to(residual.dtype)

        # Stats for the wrapper / metrics
        self.last_gate_fraction = gated_frac
        self.last_mean_pi = pi.float().mean().item()

        # ---- Complete the decoder layer residual flow ----------------
        # hidden = residual + attn_blended
        # hidden = post_attention_layernorm(hidden)
        # hidden = hidden + mlp(hidden)
        hidden = residual + attn_blended
        residual2 = hidden
        hidden = self.original_layer.post_attention_layernorm(hidden)
        hidden = self.original_layer.mlp(hidden)
        hidden = residual2 + hidden

        # Return convention: modern HF transformers (>=4.46) has
        # MistralDecoderLayer.forward() return a tensor directly, not a
        # tuple. MistralModel.forward() assigns the result straight into
        # hidden_states without [0] indexing. Returning a tuple here
        # would make the NEXT layer try to layernorm a tuple, producing:
        #     AttributeError: 'tuple' object has no attribute 'dtype'
        # inside MistralRMSNorm.
        #
        # We ignore output_attentions / use_cache. FSCS intentionally
        # does not produce attention weights (we never materialized the
        # attention matrix), and we force use_cache=False in the dual-
        # branch forward to avoid KV-cache double-mutation. If a caller
        # genuinely needs those outputs we will need a separate forward
        # path. For the r* measurement (inference on complete sequences
        # with output_attentions=False, use_cache=False) this is correct.
        return hidden
