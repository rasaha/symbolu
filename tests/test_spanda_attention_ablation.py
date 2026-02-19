#!/usr/bin/env python3
"""
Spanda Sliding-Window Attention Ablation Analysis.

Isolates the contribution of each Spanda component to improvements
on sliding-window attention:

  1. Gamma memory   (Psi_t = gamma * Psi_{t-1} + Delta_t)
  2. Anchor geometry (-||Psi - A[y]||^2 / tau  vs  linear head)
  3. Smoothing regularizers (L_step + L_smooth)

Methodology:
  - Baseline:          Sliding window + linear head, no Spanda
  - Full Spanda:       Gamma memory + anchor emission + regularizers
  - Gamma-only:        Gamma memory + linear head (no anchors, no reg)
  - Anchor-only:       No gamma (gamma=0, single-step Psi) + anchor emission
  - Regularizer-only:  Gamma memory + linear head + regularizers
  - Gamma+Anchor:      Gamma memory + anchor emission, no regularizers
  - Gamma+Reg:         Gamma memory + linear head + regularizers

This lets us compute:
  - Gamma contribution:  (Gamma-only - Baseline)
  - Anchor contribution: (Anchor-only - Baseline)
  - Reg contribution:    (Regularizer-only - Gamma-only)
  - Interaction effect:  Full - sum of individual contributions

Usage:
  pytest tests/test_spanda_attention_ablation.py -v -s
  python tests/test_spanda_attention_ablation.py
"""

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

torch = pytest.importorskip("torch")
import torch.nn as nn
import torch.nn.functional as F

_HARD_PROBES_DIR = str(
    Path(__file__).resolve().parent.parent / "scripts" / "phase_probes" / "hard_probes"
)
if _HARD_PROBES_DIR not in sys.path:
    sys.path.insert(0, _HARD_PROBES_DIR)

from train_hard_probes import HardVocabulary

try:
    from train_hard_probes import (
        LocalWindowAttention,
        BindingCacheLMTransformer,
    )
    BINDING_CACHE_AVAILABLE = True
except ImportError:
    BINDING_CACHE_AVAILABLE = False

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Spanda"))
    from spanda.state import SpandaState
    from spanda.emission import AnchorEmission
    from spanda.regularizers import SpandaRegularizers
    SPANDA_AVAILABLE = True
except ImportError:
    SPANDA_AVAILABLE = False

# =========================================================================
# Configuration
# =========================================================================

D_MODEL = 64
NUM_HEADS = 4
NUM_LAYERS = 2
D_FF = 128
PSI_DIM = 32
WINDOW_SIZE = 8       # Small window to amplify context gap
TRAIN_STEPS = 80      # Enough to see learning signal differentiation
LR = 5e-4
BATCH_SIZE = 16
SEQ_LEN = 48          # Longer than window to require cross-window bridging


# =========================================================================
# Ablation model variants
# =========================================================================


class GammaMemoryHead(nn.Module):
    """
    Gamma memory (Psi trajectory) with LINEAR projection head.

    This isolates gamma memory from anchor geometry:
    - Psi_t = gamma * Psi_{t-1} + Delta_t  (gamma memory present)
    - logits = Linear(Psi_last) @ W_embed^T (standard linear, no anchor geometry)

    Used for: Gamma-only ablation, Regularizer-only ablation.
    """

    def __init__(
        self,
        embed_dim: int,
        vocab_size: int,
        psi_dim: int = 32,
        decay_gamma: float = 0.99,
        use_regularizers: bool = False,
    ):
        super().__init__()
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=decay_gamma,
        )
        self.linear_head = nn.Linear(psi_dim, vocab_size, bias=False)
        self.use_regularizers = use_regularizers
        if use_regularizers:
            self.regularizers = SpandaRegularizers(alpha=1e-4, beta=1e-4)
            self.regularizers.set_phase(3)  # Enable both L_step and L_smooth

    def forward(self, h: torch.Tensor) -> Tuple[torch.Tensor, dict]:
        psi, delta = self.spanda_state(h)  # [B, T, psi_dim]
        logits = self.linear_head(psi)     # [B, T, vocab_size]
        reg_losses = {"l_step": 0.0, "l_smooth": 0.0, "total_reg": 0.0}
        if self.use_regularizers:
            reg_losses = self.regularizers(delta)
        return logits, reg_losses


class AnchorOnlyHead(nn.Module):
    """
    Anchor geometry with NO gamma memory (gamma=0, single-step).

    This isolates anchor geometry from gamma memory:
    - Delta_t = MLP(h_t)  (computed but no recurrence)
    - Psi_t = Delta_t     (no gamma accumulation, each step independent)
    - logits = -||Psi_t - A[y]||^2 / tau  (anchor geometry present)

    Used for: Anchor-only ablation.
    """

    def __init__(
        self,
        embed_dim: int,
        vocab_size: int,
        psi_dim: int = 32,
    ):
        super().__init__()
        # Use SpandaState with gamma=0.0 to get the MLP but no memory
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=0.0,
        )
        self.anchor_emission = AnchorEmission(
            vocab_size=vocab_size, embed_dim=embed_dim, psi_dim=psi_dim,
        )

    def forward(
        self, h: torch.Tensor, token_embed_weight: torch.Tensor,
    ) -> Tuple[torch.Tensor, dict]:
        psi, delta = self.spanda_state(h)  # gamma=0: Psi_t = Delta_t
        logits = self.anchor_emission(psi, token_embed_weight)
        return logits, {"l_step": 0.0, "l_smooth": 0.0, "total_reg": 0.0}


class FullSpandaHead(nn.Module):
    """
    Full Spanda: gamma memory + anchor emission + regularizers.

    - Psi_t = gamma * Psi_{t-1} + Delta_t  (gamma memory)
    - logits = -||Psi_t - A[y]||^2 / tau   (anchor geometry)
    - L_step + L_smooth                     (smoothing regularizers)
    """

    def __init__(
        self,
        embed_dim: int,
        vocab_size: int,
        psi_dim: int = 32,
        decay_gamma: float = 0.99,
        use_regularizers: bool = True,
    ):
        super().__init__()
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=decay_gamma,
        )
        self.anchor_emission = AnchorEmission(
            vocab_size=vocab_size, embed_dim=embed_dim, psi_dim=psi_dim,
        )
        self.use_regularizers = use_regularizers
        if use_regularizers:
            self.regularizers = SpandaRegularizers(alpha=1e-4, beta=1e-4)
            self.regularizers.set_phase(3)

    def forward(
        self, h: torch.Tensor, token_embed_weight: torch.Tensor,
    ) -> Tuple[torch.Tensor, dict]:
        psi, delta = self.spanda_state(h)
        logits = self.anchor_emission(psi, token_embed_weight)
        reg_losses = {"l_step": 0.0, "l_smooth": 0.0, "total_reg": 0.0}
        if self.use_regularizers:
            reg_losses = self.regularizers(delta)
        return logits, reg_losses


# =========================================================================
# Wrapper models that combine backbone + head
# =========================================================================


class SlidingWindowLM(nn.Module):
    """Baseline sliding-window LM with standard linear head."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, decay_gamma):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            BindingCacheLMBlock_Minimal(d_model, num_heads, d_ff, dropout, window_size)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
        self.lm_head.weight = self.token_emb.weight
        self._reg_losses = {}

    def _get_hidden(self, input_ids):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        for layer in self.layers:
            x = layer(x)
        return self.norm(x)

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        return self.lm_head(h)

    @property
    def reg_losses(self):
        return self._reg_losses


class SlidingWindowLM_GammaOnly(nn.Module):
    """Sliding window + Gamma memory + linear head (no anchors, no reg)."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, decay_gamma,
                 psi_dim, use_regularizers=False):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            BindingCacheLMBlock_Minimal(d_model, num_heads, d_ff, dropout, window_size)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.gamma_head = GammaMemoryHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
            decay_gamma=decay_gamma, use_regularizers=use_regularizers,
        )
        self._reg_losses = {}

    def forward(self, input_ids):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        for layer in self.layers:
            x = layer(x)
        h = self.norm(x)
        logits, self._reg_losses = self.gamma_head(h)
        return logits

    @property
    def reg_losses(self):
        return self._reg_losses


class SlidingWindowLM_AnchorOnly(nn.Module):
    """Sliding window + Anchor geometry (gamma=0, no memory accumulation)."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, psi_dim):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            BindingCacheLMBlock_Minimal(d_model, num_heads, d_ff, dropout, window_size)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.anchor_head = AnchorOnlyHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
        )
        self._reg_losses = {}

    def forward(self, input_ids):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        for layer in self.layers:
            x = layer(x)
        h = self.norm(x)
        logits, self._reg_losses = self.anchor_head(h, self.token_emb.weight)
        return logits

    @property
    def reg_losses(self):
        return self._reg_losses


class SlidingWindowLM_FullSpanda(nn.Module):
    """Sliding window + Full Spanda (gamma + anchors + optional regularizers)."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, decay_gamma,
                 psi_dim, use_regularizers=True):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            BindingCacheLMBlock_Minimal(d_model, num_heads, d_ff, dropout, window_size)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.spanda_head = FullSpandaHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
            decay_gamma=decay_gamma, use_regularizers=use_regularizers,
        )
        self._reg_losses = {}

    def forward(self, input_ids):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        for layer in self.layers:
            x = layer(x)
        h = self.norm(x)
        logits, self._reg_losses = self.spanda_head(h, self.token_emb.weight)
        return logits

    @property
    def reg_losses(self):
        return self._reg_losses


# =========================================================================
# Minimal sliding-window block (avoids full BindingCache complexity)
# =========================================================================


class BindingCacheLMBlock_Minimal(nn.Module):
    """
    Minimal sliding-window transformer block.

    Uses only LocalWindowAttention + FFN. No phase state or quad attention.
    This isolates the sliding-window limitation that Spanda is meant to address.
    """

    def __init__(self, embed_dim, num_heads, ff_dim, dropout, window_size):
        super().__init__()
        self.local_attn = LocalWindowAttention(
            embed_dim=embed_dim, num_heads=num_heads,
            window_size=window_size, dropout=dropout,
        )
        self.norm_ff = nn.LayerNorm(embed_dim)
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, ff_dim),
            nn.GELU(),
            nn.Linear(ff_dim, embed_dim),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        x = x + self.local_attn(x)
        x = x + self.ff(self.norm_ff(x))
        return x


# =========================================================================
# Training utilities
# =========================================================================


def train_lm_model(model, vocab_size, device, num_steps, lr, seq_len,
                   use_spanda_reg=False, seed=42):
    """Train an LM model and return per-step losses."""
    torch.manual_seed(seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    model.train()
    losses = []

    for step in range(num_steps):
        input_ids = torch.randint(0, vocab_size, (BATCH_SIZE, seq_len), device=device)
        targets = input_ids[:, 1:]  # Next-token prediction
        input_ids_shifted = input_ids[:, :-1]

        logits = model(input_ids)
        # Use all positions for loss (LM objective)
        ce_loss = F.cross_entropy(
            logits[:, :-1, :].contiguous().view(-1, vocab_size),
            targets.contiguous().view(-1),
        )

        total_loss = ce_loss
        if use_spanda_reg and hasattr(model, 'reg_losses'):
            reg = model.reg_losses.get("total_reg", 0.0)
            if isinstance(reg, torch.Tensor):
                total_loss = ce_loss + reg

        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        optimizer.zero_grad()
        losses.append(ce_loss.item())

    return losses


def compute_perplexity(losses: List[float], last_n: int = 20) -> float:
    """Compute perplexity from last N losses."""
    avg_loss = sum(losses[-last_n:]) / min(last_n, len(losses))
    return math.exp(min(avg_loss, 20.0))  # Clamp to avoid overflow


@dataclass
class AblationResult:
    """Result of a single ablation experiment."""
    variant: str
    description: str
    final_loss: float
    perplexity: float
    param_count: int
    losses: List[float] = field(default_factory=list)


# =========================================================================
# Diagnostic utilities for deeper analysis
# =========================================================================


def analyze_psi_dynamics(model, vocab_size, device, seq_len=48):
    """
    Analyze Psi trajectory dynamics for models with gamma memory.

    Returns metrics about how Psi evolves across positions, which
    directly measures the gamma memory's cross-window bridging effect.
    """
    model.eval()
    with torch.no_grad():
        input_ids = torch.randint(0, vocab_size, (4, seq_len), device=device)
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)

        # Get hidden states from backbone
        x = model.dropout(model.token_emb(input_ids) + model.pos_emb(pos))
        for layer in model.layers:
            x = layer(x)
        h = model.norm(x)

        # Extract Psi trajectory if model has gamma memory
        if hasattr(model, 'gamma_head'):
            psi, delta = model.gamma_head.spanda_state(h)
        elif hasattr(model, 'spanda_head'):
            psi, delta = model.spanda_head.spanda_state(h)
        else:
            return None

        # Psi norms across positions
        psi_norms = psi.norm(dim=-1)  # [B, T]

        # Psi continuity (cosine similarity between consecutive positions)
        psi_cos = F.cosine_similarity(psi[:, :-1, :], psi[:, 1:, :], dim=-1)

        # Delta norms (magnitude of state changes)
        delta_norms = delta.norm(dim=-1)

        # Cross-window information flow: compare Psi at positions beyond window
        # to Psi within window (does gamma memory carry information?)
        window = min(WINDOW_SIZE, N - 1)
        psi_early = psi[:, :window, :]       # Within first window
        psi_late = psi[:, window:, :]         # Beyond first window

        # Mutual information proxy: cosine similarity of Psi across window boundary
        if psi_late.size(1) > 0:
            cross_window_cos = F.cosine_similarity(
                psi[:, window - 1:window, :].expand_as(psi_late),
                psi_late, dim=-1,
            )
            cross_window_mean = cross_window_cos.mean().item()
        else:
            cross_window_mean = 0.0

        return {
            "mean_psi_norm": psi_norms.mean().item(),
            "max_psi_norm": psi_norms.max().item(),
            "psi_norm_growth": (psi_norms[:, -1].mean() - psi_norms[:, 0].mean()).item(),
            "mean_psi_continuity": psi_cos.mean().item(),
            "mean_delta_norm": delta_norms.mean().item(),
            "cross_window_coherence": cross_window_mean,
        }


# =========================================================================
# Main ablation test
# =========================================================================


@pytest.mark.skipif(not SPANDA_AVAILABLE, reason="Spanda modules not available")
@pytest.mark.skipif(not BINDING_CACHE_AVAILABLE, reason="BindingCache not available")
class TestSpandaSlidingWindowAblation:
    """
    Ablation study: which Spanda component drives improvement on sliding-window attention?

    Components under test:
      1. Gamma memory:      Psi_t = gamma * Psi_{t-1} + Delta_t (cross-window bridging)
      2. Anchor geometry:   -||Psi - A[y]||^2 / tau  (distance-based emission)
      3. Smoothing regularizers: L_step + L_smooth (trajectory smoothness)
    """

    @pytest.fixture(scope="class")
    def vocab(self):
        return HardVocabulary()

    @pytest.fixture(scope="class")
    def device(self):
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _make_baseline(self, vocab_size, device):
        return SlidingWindowLM(
            vocab_size=vocab_size, d_model=D_MODEL, num_heads=NUM_HEADS,
            num_layers=NUM_LAYERS, d_ff=D_FF, dropout=0.0,
            max_seq_len=SEQ_LEN + 16, window_size=WINDOW_SIZE,
            decay_gamma=0.9,
        ).to(device)

    def _make_gamma_only(self, vocab_size, device, use_reg=False):
        return SlidingWindowLM_GammaOnly(
            vocab_size=vocab_size, d_model=D_MODEL, num_heads=NUM_HEADS,
            num_layers=NUM_LAYERS, d_ff=D_FF, dropout=0.0,
            max_seq_len=SEQ_LEN + 16, window_size=WINDOW_SIZE,
            decay_gamma=0.99, psi_dim=PSI_DIM,
            use_regularizers=use_reg,
        ).to(device)

    def _make_anchor_only(self, vocab_size, device):
        return SlidingWindowLM_AnchorOnly(
            vocab_size=vocab_size, d_model=D_MODEL, num_heads=NUM_HEADS,
            num_layers=NUM_LAYERS, d_ff=D_FF, dropout=0.0,
            max_seq_len=SEQ_LEN + 16, window_size=WINDOW_SIZE,
            psi_dim=PSI_DIM,
        ).to(device)

    def _make_full_spanda(self, vocab_size, device, use_reg=True):
        return SlidingWindowLM_FullSpanda(
            vocab_size=vocab_size, d_model=D_MODEL, num_heads=NUM_HEADS,
            num_layers=NUM_LAYERS, d_ff=D_FF, dropout=0.0,
            max_seq_len=SEQ_LEN + 16, window_size=WINDOW_SIZE,
            decay_gamma=0.99, psi_dim=PSI_DIM,
            use_regularizers=use_reg,
        ).to(device)

    def test_full_ablation_study(self, vocab, device):
        """
        Run the complete ablation study across all component combinations.

        Variants:
          (A) Baseline:        Sliding window + linear head
          (B) Gamma-only:      + gamma memory, linear head
          (C) Anchor-only:     + anchor geometry, gamma=0
          (D) Gamma+Anchor:    + gamma memory + anchor geometry
          (E) Gamma+Reg:       + gamma memory + linear head + regularizers
          (F) Full Spanda:     + gamma memory + anchor geometry + regularizers
        """
        V = vocab.vocab_size
        results: Dict[str, AblationResult] = {}

        # (A) Baseline
        print("\n  Training (A) Baseline: Sliding window + linear head...")
        model_a = self._make_baseline(V, device)
        losses_a = train_lm_model(model_a, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42)
        results["baseline"] = AblationResult(
            variant="(A) Baseline",
            description="Sliding window + linear head",
            final_loss=sum(losses_a[-20:]) / 20,
            perplexity=compute_perplexity(losses_a),
            param_count=sum(p.numel() for p in model_a.parameters()),
            losses=losses_a,
        )

        # (B) Gamma-only: gamma memory + linear head (no anchors, no reg)
        print("  Training (B) Gamma-only: + gamma memory, linear head...")
        model_b = self._make_gamma_only(V, device, use_reg=False)
        losses_b = train_lm_model(model_b, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42)
        results["gamma_only"] = AblationResult(
            variant="(B) Gamma-only",
            description="+ gamma memory (Psi recurrence), linear head",
            final_loss=sum(losses_b[-20:]) / 20,
            perplexity=compute_perplexity(losses_b),
            param_count=sum(p.numel() for p in model_b.parameters()),
            losses=losses_b,
        )

        # (C) Anchor-only: anchor geometry, gamma=0 (no memory)
        print("  Training (C) Anchor-only: anchor geometry, gamma=0...")
        model_c = self._make_anchor_only(V, device)
        losses_c = train_lm_model(model_c, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42)
        results["anchor_only"] = AblationResult(
            variant="(C) Anchor-only",
            description="+ anchor geometry (gamma=0, no memory)",
            final_loss=sum(losses_c[-20:]) / 20,
            perplexity=compute_perplexity(losses_c),
            param_count=sum(p.numel() for p in model_c.parameters()),
            losses=losses_c,
        )

        # (D) Gamma+Anchor: gamma memory + anchor geometry (no regularizers)
        print("  Training (D) Gamma+Anchor: gamma memory + anchor geometry...")
        model_d = self._make_full_spanda(V, device, use_reg=False)
        losses_d = train_lm_model(model_d, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42)
        results["gamma_anchor"] = AblationResult(
            variant="(D) Gamma+Anchor",
            description="+ gamma memory + anchor geometry, no regularizers",
            final_loss=sum(losses_d[-20:]) / 20,
            perplexity=compute_perplexity(losses_d),
            param_count=sum(p.numel() for p in model_d.parameters()),
            losses=losses_d,
        )

        # (E) Gamma+Reg: gamma memory + linear head + regularizers
        print("  Training (E) Gamma+Reg: gamma memory + regularizers...")
        model_e = self._make_gamma_only(V, device, use_reg=True)
        losses_e = train_lm_model(model_e, V, device, TRAIN_STEPS, LR, SEQ_LEN,
                                   use_spanda_reg=True, seed=42)
        results["gamma_reg"] = AblationResult(
            variant="(E) Gamma+Reg",
            description="+ gamma memory + regularizers, linear head",
            final_loss=sum(losses_e[-20:]) / 20,
            perplexity=compute_perplexity(losses_e),
            param_count=sum(p.numel() for p in model_e.parameters()),
            losses=losses_e,
        )

        # (F) Full Spanda: gamma + anchors + regularizers
        print("  Training (F) Full Spanda: gamma + anchors + regularizers...")
        model_f = self._make_full_spanda(V, device, use_reg=True)
        losses_f = train_lm_model(model_f, V, device, TRAIN_STEPS, LR, SEQ_LEN,
                                   use_spanda_reg=True, seed=42)
        results["full_spanda"] = AblationResult(
            variant="(F) Full Spanda",
            description="+ gamma memory + anchor geometry + regularizers",
            final_loss=sum(losses_f[-20:]) / 20,
            perplexity=compute_perplexity(losses_f),
            param_count=sum(p.numel() for p in model_f.parameters()),
            losses=losses_f,
        )

        # ---- Print results table ----
        baseline_loss = results["baseline"].final_loss

        print(f"\n  {'='*85}")
        print(f"  SPANDA SLIDING-WINDOW ABLATION STUDY")
        print(f"  Window size: {WINDOW_SIZE} | Seq length: {SEQ_LEN} | Steps: {TRAIN_STEPS}")
        print(f"  {'='*85}")
        print(f"  {'Variant':<25} {'Loss':>8} {'PPL':>8} {'Delta':>8} "
              f"{'%Improv':>8} {'Params':>8} {'Components'}")
        print(f"  {'-'*85}")

        for key in ["baseline", "gamma_only", "anchor_only", "gamma_anchor",
                     "gamma_reg", "full_spanda"]:
            r = results[key]
            delta = r.final_loss - baseline_loss
            pct = (delta / baseline_loss * 100) if baseline_loss > 0 else 0
            components = ""
            if key == "baseline":
                components = "none"
            elif key == "gamma_only":
                components = "gamma"
            elif key == "anchor_only":
                components = "anchor"
            elif key == "gamma_anchor":
                components = "gamma+anchor"
            elif key == "gamma_reg":
                components = "gamma+reg"
            elif key == "full_spanda":
                components = "gamma+anchor+reg"

            print(f"  {r.variant:<25} {r.final_loss:>8.4f} {r.perplexity:>8.1f} "
                  f"{delta:>+8.4f} {pct:>+7.1f}% {r.param_count:>8d} {components}")

        # ---- Attribution analysis ----
        gamma_contrib = results["gamma_only"].final_loss - baseline_loss
        anchor_contrib = results["anchor_only"].final_loss - baseline_loss
        gamma_anchor_synergy = (
            results["gamma_anchor"].final_loss - baseline_loss
            - gamma_contrib - anchor_contrib
        )
        reg_contrib = results["gamma_reg"].final_loss - results["gamma_only"].final_loss
        full_residual = (
            results["full_spanda"].final_loss - baseline_loss
            - gamma_contrib - anchor_contrib - reg_contrib
        )

        print(f"\n  {'='*85}")
        print(f"  COMPONENT ATTRIBUTION (negative = improvement)")
        print(f"  {'='*85}")
        print(f"  Gamma memory contribution:     {gamma_contrib:>+.4f} "
              f"({'IMPROVES' if gamma_contrib < 0 else 'HURTS'} loss)")
        print(f"  Anchor geometry contribution:   {anchor_contrib:>+.4f} "
              f"({'IMPROVES' if anchor_contrib < 0 else 'HURTS'} loss)")
        print(f"  Gamma+Anchor synergy:           {gamma_anchor_synergy:>+.4f} "
              f"({'super-additive' if gamma_anchor_synergy < 0 else 'sub-additive'})")
        print(f"  Regularizer contribution:       {reg_contrib:>+.4f} "
              f"({'IMPROVES' if reg_contrib < 0 else 'HURTS'} loss)")
        print(f"  Full system residual:           {full_residual:>+.4f} "
              f"(interaction effects)")
        print(f"  {'='*85}")

        # ---- Determine primary driver ----
        contributions = {
            "Gamma memory": gamma_contrib,
            "Anchor geometry": anchor_contrib,
            "Smoothing regularizers": reg_contrib,
        }
        sorted_contribs = sorted(contributions.items(), key=lambda x: x[0])
        best_component = min(contributions, key=contributions.get)
        worst_component = max(contributions, key=contributions.get)

        print(f"\n  VERDICT:")
        if contributions[best_component] < -0.01:
            print(f"  Primary improvement driver: {best_component} "
                  f"({contributions[best_component]:+.4f})")
        else:
            print(f"  No component shows clear improvement (all deltas near zero)")

        if gamma_anchor_synergy < -0.01:
            print(f"  Gamma+Anchor show super-additive synergy ({gamma_anchor_synergy:+.4f})")
        elif gamma_anchor_synergy > 0.01:
            print(f"  Gamma+Anchor are partially redundant ({gamma_anchor_synergy:+.4f})")

        print(f"  {'='*85}")

        # ---- Psi dynamics analysis for gamma models ----
        print(f"\n  {'='*85}")
        print(f"  PSI TRAJECTORY DYNAMICS (cross-window bridging analysis)")
        print(f"  {'='*85}")

        for name, model in [
            ("Gamma-only", model_b),
            ("Gamma+Reg", model_e),
            ("Full Spanda", model_f),
        ]:
            dynamics = analyze_psi_dynamics(model, V, device, SEQ_LEN)
            if dynamics:
                print(f"\n  {name}:")
                print(f"    Mean ||Psi||:              {dynamics['mean_psi_norm']:.4f}")
                print(f"    Max ||Psi||:               {dynamics['max_psi_norm']:.4f}")
                print(f"    Psi norm growth (T=0->T):  {dynamics['psi_norm_growth']:+.4f}")
                print(f"    Mean Psi continuity:       {dynamics['mean_psi_continuity']:.4f}")
                print(f"    Mean ||Delta||:            {dynamics['mean_delta_norm']:.4f}")
                print(f"    Cross-window coherence:    {dynamics['cross_window_coherence']:.4f}")

        print(f"  {'='*85}")

        # ---- Validation ----
        for key, r in results.items():
            assert math.isfinite(r.final_loss), f"{key} loss not finite: {r.final_loss}"
            assert r.perplexity > 0, f"{key} perplexity not positive: {r.perplexity}"

    def test_gamma_ablation_across_values(self, vocab, device):
        """
        Test gamma memory contribution across different decay values.

        gamma=0.0:  No memory (single-step, equivalent to MLP projection)
        gamma=0.9:  Short memory (fast decay)
        gamma=0.99: Medium memory (standard)
        gamma=0.999: Long memory (slow decay)

        Higher gamma should help more on longer sequences where cross-window
        bridging is critical.
        """
        V = vocab.vocab_size

        print(f"\n  {'='*70}")
        print(f"  GAMMA ABLATION: Memory retention vs sliding-window improvement")
        print(f"  {'='*70}")
        print(f"  {'Gamma':>8} {'Loss':>8} {'PPL':>8} {'Delta vs 0.0':>12} {'Effective window'}")
        print(f"  {'-'*70}")

        gamma_results = {}
        for gamma in [0.0, 0.9, 0.99, 0.999]:
            model = SlidingWindowLM_GammaOnly(
                vocab_size=V, d_model=D_MODEL, num_heads=NUM_HEADS,
                num_layers=NUM_LAYERS, d_ff=D_FF, dropout=0.0,
                max_seq_len=SEQ_LEN + 16, window_size=WINDOW_SIZE,
                decay_gamma=gamma, psi_dim=PSI_DIM,
            ).to(device)
            losses = train_lm_model(model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42)
            final_loss = sum(losses[-20:]) / 20
            ppl = compute_perplexity(losses)
            gamma_results[gamma] = (final_loss, ppl)

            # Effective memory window: number of steps where gamma^t > 0.01
            if gamma > 0:
                eff_window = int(math.log(0.01) / math.log(gamma)) if gamma < 1 else float('inf')
            else:
                eff_window = 0

            delta = final_loss - gamma_results[0.0][0] if 0.0 in gamma_results else 0
            print(f"  {gamma:>8.3f} {final_loss:>8.4f} {ppl:>8.1f} "
                  f"{delta:>+12.4f} ~{eff_window} tokens")

        print(f"  {'='*70}")

        # Validate
        for gamma, (loss, ppl) in gamma_results.items():
            assert math.isfinite(loss), f"gamma={gamma} loss not finite"

    def test_window_size_interaction(self, vocab, device):
        """
        Test how Spanda's benefit changes with window size.

        Hypothesis: Spanda benefit is inversely proportional to window size.
        - Small window (w=4):  Maximum benefit (severe context limitation)
        - Medium window (w=16): Moderate benefit
        - Large window (w=48): Minimal benefit (nearly full context)
        """
        V = vocab.vocab_size

        print(f"\n  {'='*70}")
        print(f"  WINDOW SIZE INTERACTION: Spanda benefit vs context capacity")
        print(f"  {'='*70}")
        print(f"  {'Window':>8} {'Base Loss':>10} {'Spanda Loss':>12} "
              f"{'Delta':>8} {'%Improv':>8}")
        print(f"  {'-'*70}")

        for window in [4, 8, 16, 32]:
            # Baseline
            base = SlidingWindowLM(
                vocab_size=V, d_model=D_MODEL, num_heads=NUM_HEADS,
                num_layers=NUM_LAYERS, d_ff=D_FF, dropout=0.0,
                max_seq_len=SEQ_LEN + 16, window_size=window,
                decay_gamma=0.9,
            ).to(device)
            base_losses = train_lm_model(base, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42)
            base_final = sum(base_losses[-20:]) / 20

            # Full Spanda
            spanda = SlidingWindowLM_FullSpanda(
                vocab_size=V, d_model=D_MODEL, num_heads=NUM_HEADS,
                num_layers=NUM_LAYERS, d_ff=D_FF, dropout=0.0,
                max_seq_len=SEQ_LEN + 16, window_size=window,
                decay_gamma=0.99, psi_dim=PSI_DIM,
            ).to(device)
            spanda_losses = train_lm_model(
                spanda, V, device, TRAIN_STEPS, LR, SEQ_LEN,
                use_spanda_reg=True, seed=42,
            )
            spanda_final = sum(spanda_losses[-20:]) / 20

            delta = spanda_final - base_final
            pct = (delta / base_final * 100) if base_final > 0 else 0
            print(f"  w={window:<5} {base_final:>10.4f} {spanda_final:>12.4f} "
                  f"{delta:>+8.4f} {pct:>+7.1f}%")

        print(f"  {'='*70}")
        print(f"  Expected: Benefit decreases as window size increases")
        print(f"  {'='*70}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
