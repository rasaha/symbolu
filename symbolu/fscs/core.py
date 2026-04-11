"""
symbolu/fscs/core.py — Text-FSCS core building blocks.

EXPERIMENTAL. Code-complete, not yet benchmark-validated.

Each class below is a standalone nn.Module that implements one mechanism
from the Text-FSCS v5.0 specification. They are designed to be composed
by MistralFSCSWrapper, or tested in isolation on synthetic tensors by
tests/test_fscs_core.py.

Spec section mapping:
    FSCSCoherenceModule       → §1 (three-signal coherence with EMA smoothing)
    FSCSRoutingGate           → §6 (pre-softmax gate with per-band params)
    FSCSBoundaryDetector      → §3 (heuristic v1 change-point suppressor)
    FSCSSurpriseDeltaSuppressor → §2 (stable-but-wrong protection)
    FSCSLayerCap              → §7 (layer-level gating cap)
    fscs_alignment_loss       → §12.2 (stopgrad coarse→full alignment)

Not in this file (deferred scope):
    - §5 head-importance weighting (applied only in the Mistral wrapper
      because it needs W_O from the wrapped layer; the *policy* lives here
      via FSCSLayerCap but the weight computation happens at wrap time)
    - §8 cross-layer caution (needs forward propagation between layers,
      handled in MistralFSCSWrapper)
    - §9 per-band coarse operators (this first-pass uses a single windowed
      coarse path; Mid-strided and Global-EMA-cache are future work)
    - §11 plateau block sparsity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import torch
import torch.nn as nn


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class FSCSConfig:
    """
    Text-FSCS configuration. Default values are from §6 of the spec.

    Most hyperparameters are bounded ranges from §6 of the spec. The defaults
    here are the spec's recommended starting point for the first experiment.
    """

    # Coherence metric (§1)
    gamma: float = 5.0              # Output delta sensitivity
    delta_residual: float = 3.0     # Residual delta sensitivity (δ in the spec)
    ema_decay: float = 0.4          # EMA smoothing ρ (spec default)
    use_attention_kl: bool = False  # Optional block-mass KL term; off by default
                                    # (requires storing attention summaries, §1.3)

    # Sequence warmup (§4)
    warmup_tokens: int = 3

    # Routing gate (§6)
    num_bands: int = 3              # Global, Mid, Local
    alpha_sharpness: float = 10.0   # Sigmoid sharpness α_b
    tau_global: float = 0.7         # Global band τ (hardest to gate)
    tau_mid: float = 0.5            # Mid band τ
    tau_local: float = 0.3          # Local band τ (easiest to gate)

    # Hard routing (Mode 3 inference)
    hard_route_threshold: float = 0.7  # θ
    use_hard_routing: bool = False

    # Surprise-delta suppressor (§2)
    surprise_eta: float = 1.0
    use_surprise_delta: bool = True

    # Boundary detector (§3 heuristic v1)
    use_boundary_detector: bool = True
    # Token IDs here are placeholders; MistralFSCSWrapper populates at construction
    # time from the tokenizer. Left empty by default so this module is
    # tokenizer-agnostic.
    boundary_token_ids: Tuple[int, ...] = ()

    # Layer cap (§7)
    beta_max_train: float = 0.3
    beta_max_inference: float = 0.5

    # Cross-layer caution (§8). Used by the wrapper, not by individual modules.
    zeta: float = 0.5
    r_threshold: float = 0.3

    # Alignment loss (§12.2)
    alignment_lambda: float = 0.1

    # Windowed coarse operator (first-pass, §9 Local-band path)
    coarse_window: int = 256


# ============================================================================
# §1 — Three-signal coherence
# ============================================================================


class FSCSCoherenceModule(nn.Module):
    """
    Computes the pre-softmax coherence score from past-step output and residual
    deltas.

    This is spec §1.1–§1.2. The per-head-per-token score is:

        C_raw = exp(-γ * ΔO_rel) * exp(-δ * ΔR_rel)
        C̄_t  = (1 - ρ) * C̄_{t-1} + ρ * C_raw_t

    Where:
        ΔO_rel = ||O(t) - O(t-1)|| / (||O(t-1)|| + ε)
        ΔR_rel = ||R(t) - R(t-1)|| / (||R(t-1)|| + ε)

    The optional attention-KL term from §1.3 (block-mass summaries) is NOT
    included in this first-pass implementation — it requires storing
    attention-mass summaries across two previous steps, which is non-trivial
    without modifying Mistral's internal attention. It is stubbed out behind
    `use_attention_kl` and can be added in a future pass.

    This module operates on POST-LAYER residual streams, which means it reads
    the *output* of the previous layer to decide how to route the *current*
    layer. That is the causal, FlashAttention-compatible design from the GCT
    paper (docs/design/GCT_GATED_COHERENCE_TRANSFORMER_DESIGN.md §2.3).

    Shape convention (first-pass, token-level gating):
        attn_output : [B, N, D]   — per-layer attention output (already
                                    output-projected)
        residual    : [B, N, D]   — residual stream entering this layer
        returns     : [B, N]      — per-token coherence in [0, 1]

    A future per-head variant would return [B, H, N] and operate on
    per-head attention outputs [B, H, N, D_h] before output projection.
    That requires reimplementing MistralAttention internals and is
    deferred.
    """

    def __init__(self, cfg: FSCSConfig):
        super().__init__()
        self.cfg = cfg
        self.gamma = cfg.gamma
        self.delta_residual = cfg.delta_residual
        self.ema_decay = cfg.ema_decay
        self.eps = 1e-6

    def forward(
        self,
        attn_output: torch.Tensor,  # [B, N, D]
        residual: torch.Tensor,     # [B, N, D]
    ) -> torch.Tensor:
        """
        Returns:
            coherence: [B, N] in [0, 1], where high = stable (safe to gate).
        """
        B, N, D = attn_output.shape

        if N < 2:
            # Not enough context for a delta — return neutral coherence.
            return torch.full((B, N), 0.5, device=attn_output.device,
                              dtype=attn_output.dtype)

        # Output delta, scale-normalized (§1.1)
        o_delta = attn_output[:, 1:] - attn_output[:, :-1]       # [B, N-1, D]
        o_norm = o_delta.norm(dim=-1)                            # [B, N-1]
        o_ref = attn_output[:, :-1].norm(dim=-1).clamp(min=self.eps)
        o_delta_rel = o_norm / o_ref                             # [B, N-1]

        # Residual delta, scale-normalized (§1.1 — catches cross-head drift)
        r_delta = residual[:, 1:] - residual[:, :-1]             # [B, N-1, D]
        r_norm = r_delta.norm(dim=-1)
        r_ref = residual[:, :-1].norm(dim=-1).clamp(min=self.eps)
        r_delta_rel = r_norm / r_ref                             # [B, N-1]

        # Raw coherence: high when deltas are small
        c_raw = torch.exp(-self.gamma * o_delta_rel) \
              * torch.exp(-self.delta_residual * r_delta_rel)    # [B, N-1]

        # Pad position 0 with neutral coherence
        c0 = torch.full((B, 1), 0.5, device=c_raw.device, dtype=c_raw.dtype)
        c_raw = torch.cat([c0, c_raw], dim=1)                    # [B, N]

        # EMA smoothing (§1.2) — causal, explicit loop so it's correct
        # Note: this is O(N) in Python but runs on CPU for the schedule; for
        # a production implementation one would fuse it into a scan kernel.
        coherence = torch.zeros_like(c_raw)
        coherence[:, 0] = c_raw[:, 0]
        rho = self.ema_decay
        for t in range(1, N):
            coherence[:, t] = (1 - rho) * coherence[:, t - 1] + rho * c_raw[:, t]

        # Sequence warmup (§4): force neutral coherence for the first
        # warmup_tokens positions. Using 0.0 here instead of 0.5 because the
        # spec says π = 0 for the warmup region, which in the sigmoid gate
        # means coherence should be far below τ. 0.0 accomplishes that.
        w = self.cfg.warmup_tokens
        if w > 0:
            warmup_end = min(w, N)
            coherence[:, :warmup_end] = 0.0

        return coherence


# ============================================================================
# §6 — Pre-softmax routing gate
# ============================================================================


class FSCSRoutingGate(nn.Module):
    """
    Pre-softmax routing gate with per-band thresholds and sharpness.

    For the first-pass token-level implementation, the gate is a single
    [B, N] probability per token. In the full per-head spec, it would be
    [B, H, N] with the band assignment selecting τ and α per head.

    In this first-pass, the three bands apply at the *layer* level: we
    partition the Mistral decoder layers into Global (earliest, highest τ),
    Mid, and Local (latest, lowest τ) bands. The wrapper decides each
    layer's band at construction time and passes the appropriate τ/α here.

    π(b, t) = σ(α_b * (Ĉ_t - τ_b))

    High π = stable → route to coarse (save compute)
    Low  π = unstable → use full attention (be careful)
    """

    def __init__(
        self,
        cfg: FSCSConfig,
        band: str = "mid",  # "global" / "mid" / "local"
    ):
        super().__init__()
        if band not in ("global", "mid", "local"):
            raise ValueError(f"band must be 'global'/'mid'/'local', got {band!r}")
        self.cfg = cfg
        self.band = band

        tau_init = {
            "global": cfg.tau_global,
            "mid": cfg.tau_mid,
            "local": cfg.tau_local,
        }[band]

        # τ and α are learnable per band (§6). Starting from spec values.
        self.tau = nn.Parameter(torch.tensor(tau_init))
        self.alpha = nn.Parameter(torch.tensor(cfg.alpha_sharpness))

    def forward(self, coherence: torch.Tensor) -> torch.Tensor:
        """
        Args:
            coherence: [B, N] in [0, 1]
        Returns:
            pi: [B, N] in [0, 1]
        """
        pi = torch.sigmoid(self.alpha * (coherence - self.tau))
        return pi


# ============================================================================
# §3 — Boundary detector (heuristic v1)
# ============================================================================


class FSCSBoundaryDetector(nn.Module):
    """
    Heuristic v1 boundary detector from §3.1.

    Flags tokens that are structural boundaries (newline, braces, semicolons,
    sentence-final punctuation, discourse markers) where full attention
    should be forced regardless of coherence.

    This is a token-ID lookup — O(1) per token. The boundary token IDs are
    populated by MistralFSCSWrapper from the tokenizer at construction time;
    if none are supplied, the detector is a no-op returning zeros.

    Spec note: v2 (trained MLP on residual stream) is explicitly deferred.
    """

    def __init__(self, cfg: FSCSConfig):
        super().__init__()
        self.cfg = cfg
        if cfg.boundary_token_ids:
            ids = torch.tensor(sorted(set(cfg.boundary_token_ids)), dtype=torch.long)
        else:
            ids = torch.zeros(0, dtype=torch.long)
        self.register_buffer("boundary_ids", ids, persistent=False)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        """
        Args:
            input_ids: [B, N] token indices
        Returns:
            B_t: [B, N] in {0, 1} — 1 where the token is a boundary
        """
        if self.boundary_ids.numel() == 0:
            return torch.zeros_like(input_ids, dtype=torch.float32)

        # Build a [B, N, |ids|] equality tensor and reduce
        #   shape: [B, N, K]
        B, N = input_ids.shape
        flat = input_ids.view(-1, 1)                    # [B*N, 1]
        ids_view = self.boundary_ids.view(1, -1)        # [1, K]
        hits = (flat == ids_view).any(dim=-1)           # [B*N]
        B_t = hits.view(B, N).to(dtype=torch.float32)
        return B_t


# ============================================================================
# §2 — Surprise-delta suppressor
# ============================================================================


class FSCSSurpriseDeltaSuppressor(nn.Module):
    """
    Stable-but-wrong suppressor from §2.

    If surprise is increasing (Δs > 0), suppress coherence to force full
    compute. If surprise is flat or decreasing, U_t = 1 and gating proceeds.

    This module is stateless — it consumes per-token log-probabilities from
    the previous forward pass and returns a multiplicative modulator.

    In an r* measurement sweep, surprise comes from the *baseline* model's
    token-level log-probabilities. MistralFSCSWrapper pre-computes these
    once on the eval set and passes them to the forward pass. For a training
    regime, they are computed from the model's own logits with .detach().
    """

    def __init__(self, cfg: FSCSConfig):
        super().__init__()
        self.cfg = cfg
        self.eta = cfg.surprise_eta

    def forward(
        self,
        token_surprise: Optional[torch.Tensor],  # [B, N] = -log p(x_t)
    ) -> torch.Tensor:
        """
        Args:
            token_surprise: [B, N] negative log-probability of each token
                            under the reference distribution. If None, this
                            module is a no-op returning all-ones.
        Returns:
            U_t: [B, N] in (0, 1]
        """
        if token_surprise is None or not self.cfg.use_surprise_delta:
            # Return ones with the right device/dtype; caller provides a
            # reference tensor via the calling site. When None, return scalar 1.
            return torch.ones(1)

        # Δs_{t-1} = s_{t-1} - s_{t-2}; only clamped positive
        B, N = token_surprise.shape
        if N < 2:
            return torch.ones_like(token_surprise)

        ds = token_surprise[:, 1:] - token_surprise[:, :-1]       # [B, N-1]
        ds = torch.clamp(ds, min=0.0)

        # Pad position 0 with zero (no prior surprise)
        z = torch.zeros(B, 1, device=token_surprise.device, dtype=token_surprise.dtype)
        ds = torch.cat([z, ds], dim=1)                            # [B, N]

        U_t = torch.exp(-self.eta * ds)
        return U_t


# ============================================================================
# §7 — Layer cap
# ============================================================================


class FSCSLayerCap(nn.Module):
    """
    Layer-level gating cap from §7.

    In the full per-head spec, this caps the fraction of heads that can be
    gated within a single layer and uses head-importance as a tiebreaker.
    In this first-pass token-level implementation, it caps the fraction of
    *tokens* within the current sequence that can be routed to coarse, and
    uses the routing probability itself as the tiebreaker (highest-π tokens
    get gated first, up to the cap).

    Enforcement order (§7.3 adapted to the token-level setting):
        Step A — per-token pi from the gate
        Step B — if fraction(pi > θ) > β_max: retain only the top
                 β_max * N tokens by pi value, set the rest to 0
        Step C — execute (blend or hard-route)
    """

    def __init__(self, cfg: FSCSConfig):
        super().__init__()
        self.cfg = cfg

    def apply(
        self,
        pi: torch.Tensor,      # [B, N] in [0, 1]
        training: bool,
    ) -> torch.Tensor:
        """
        Returns:
            pi_capped: [B, N], same shape, with low-priority entries zeroed
                       to respect the cap.
        """
        B, N = pi.shape
        beta_max = self.cfg.beta_max_train if training else self.cfg.beta_max_inference
        n_allowed = int(beta_max * N)

        if n_allowed >= N:
            return pi  # Cap is above sequence length — no change

        # For each batch row, retain the n_allowed highest pi values; zero
        # the rest. We use topk to find the threshold.
        if n_allowed <= 0:
            return torch.zeros_like(pi)

        topk_values, _ = torch.topk(pi, k=n_allowed, dim=-1)     # [B, n_allowed]
        threshold = topk_values[:, -1:].clamp(min=1e-6)          # [B, 1]
        mask = (pi >= threshold).float()                         # [B, N]
        return pi * mask


# ============================================================================
# §12.2 — Stopgrad alignment loss
# ============================================================================


def fscs_alignment_loss(
    output_full: torch.Tensor,   # [B, N, D]
    output_coarse: torch.Tensor, # [B, N, D]
    lambda_weight: float = 0.1,
) -> torch.Tensor:
    """
    L_align = λ * || stopgrad(O_full) - O_coarse ||²

    The stopgrad on O_full is critical (§12.2): it teaches the coarse path
    to track the full path, rather than the other way around. Without
    stopgrad, the full path would learn to match the cheaper coarse path,
    degrading overall model quality.

    This loss is zero-cost during inference (both paths computed anyway
    in Mode 1/Mode 2 — see §6.2 of the spec). It is only meaningful when
    the coarse path is trainable, i.e., during co-training. For the
    frozen-Mistral first-pass r* measurement it is not used.
    """
    target = output_full.detach()
    diff = target - output_coarse
    mse = (diff * diff).mean()
    return lambda_weight * mse
