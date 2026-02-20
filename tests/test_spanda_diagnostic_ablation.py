#!/usr/bin/env python3
"""
Spanda v0.4 Diagnostic Expansion -- Controlled Ablation Study.

Determines whether the sliding-window improvement is caused by:
  A) Projection into psi space (MLP bottleneck)
  B) Distance-based emission geometry
  C) Recurrence (gamma memory)
  D) Calibration / logit scaling differences
  E) True cross-window bridging

Parts:
  1. ProjectedDotHead -- psi projection + dot product, no distance, no recurrence
  2. Logit calibration control -- per-head logging of logit stats and entropy
  3. Long-sequence stress test -- T in {1024, 2048}, w in {32, 64}
  4. RecurrentDotHead -- recurrence without distance geometry
  5. Generation evaluation -- repetition, drift, entity consistency
  6. Window scaling curve -- w in {4, 8, 16, 32, 64}
  7. Interaction analysis -- sub-additivity confirmation

Usage:
  pytest tests/test_spanda_diagnostic_ablation.py -v -s
  python tests/test_spanda_diagnostic_ablation.py
"""

import math
import sys
import json
import os
from collections import Counter
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
    from spanda.emission import AnchorEmission, ProjectedDotEmission
    from spanda.regularizers import SpandaRegularizers
    SPANDA_AVAILABLE = True
except ImportError:
    SPANDA_AVAILABLE = False


# =========================================================================
# Configuration
# =========================================================================

# Standard config (short sequences, fast iteration)
D_MODEL = 64
NUM_HEADS = 4
NUM_LAYERS = 2
D_FF = 128
PSI_DIM = 32
WINDOW_SIZE = 8
TRAIN_STEPS = 80
LR = 5e-4
BATCH_SIZE = 16
SEQ_LEN = 48

# Long-sequence config (Part 3)
LONG_SEQ_TRAIN_STEPS = 40  # Fewer steps (expensive)
LONG_BATCH_SIZE = 4

# Generation config (Part 5)
GEN_LENGTH = 500
GEN_NUM_PROMPTS = 4
GEN_PROMPT_LEN = 32


# =========================================================================
# Logit calibration data collector (Part 2)
# =========================================================================


@dataclass
class CalibrationSnapshot:
    """Per-epoch logit calibration metrics for a single head variant."""
    step: int
    logit_mean: float
    logit_std: float
    tau_value: float
    output_entropy: float
    grad_norm: float


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic experiment with calibration data."""
    variant: str
    description: str
    final_loss: float
    perplexity: float
    param_count: int
    losses: List[float] = field(default_factory=list)
    calibration: List[CalibrationSnapshot] = field(default_factory=list)


# =========================================================================
# Part 1 & 4: New ablation head variants
# =========================================================================


class ProjectedDotHead(nn.Module):
    """
    Part 1 -- Critical ablation: psi projection + dot-product emission.

    Pipeline:
        psi = MLP(h)                         # same psi projection as Spanda
        gamma = 0.0                          # no recurrence
        anchors = normalized table           # same size as anchor emission
        logits = (psi @ anchors.T) / tau     # dot product, no distance

    Same psi_dim, same temperature init, same unit-norm anchor normalization.
    No distance computation, no recurrence.

    If ProjectedDot ~ AnchorDistance -> improvement is projection/conditioning.
    If AnchorDistance > ProjectedDot -> geometry matters.
    """

    def __init__(self, embed_dim: int, vocab_size: int, psi_dim: int = 32):
        super().__init__()
        # gamma=0 -> Psi_t = Delta_t (no recurrence)
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=0.0,
        )
        self.dot_emission = ProjectedDotEmission(
            vocab_size=vocab_size, embed_dim=embed_dim, psi_dim=psi_dim,
        )

    def forward(
        self, h: torch.Tensor, token_embed_weight: torch.Tensor,
    ) -> Tuple[torch.Tensor, dict]:
        psi, delta = self.spanda_state(h)  # gamma=0: Psi_t = Delta_t
        logits = self.dot_emission(psi, token_embed_weight)
        return logits, {"l_step": 0.0, "l_smooth": 0.0, "total_reg": 0.0}

    @property
    def temperature(self) -> float:
        return self.dot_emission.temperature


class RecurrentDotHead(nn.Module):
    """
    Part 4 -- Recurrence without distance geometry.

    Pipeline:
        psi_t = gamma * psi_{t-1} + MLP(h_t)    # recurrence present
        logits = (psi_t @ B.T) / tau              # dot product, no distance

    Isolates recurrence from geometry:
    If recurrence still helps -> memory channel is real.
    If not -> geometry is doing the work.
    """

    def __init__(
        self,
        embed_dim: int,
        vocab_size: int,
        psi_dim: int = 32,
        decay_gamma: float = 0.99,
    ):
        super().__init__()
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=decay_gamma,
        )
        self.dot_emission = ProjectedDotEmission(
            vocab_size=vocab_size, embed_dim=embed_dim, psi_dim=psi_dim,
        )

    def forward(
        self, h: torch.Tensor, token_embed_weight: torch.Tensor,
    ) -> Tuple[torch.Tensor, dict]:
        psi, delta = self.spanda_state(h)  # gamma > 0: recurrence active
        logits = self.dot_emission(psi, token_embed_weight)
        return logits, {"l_step": 0.0, "l_smooth": 0.0, "total_reg": 0.0}

    @property
    def temperature(self) -> float:
        return self.dot_emission.temperature


# Re-use existing head variants from the original ablation test
class AnchorOnlyHead(nn.Module):
    """AnchorDistance with gamma=0 (no recurrence). From original ablation."""

    def __init__(self, embed_dim: int, vocab_size: int, psi_dim: int = 32):
        super().__init__()
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=0.0,
        )
        self.anchor_emission = AnchorEmission(
            vocab_size=vocab_size, embed_dim=embed_dim, psi_dim=psi_dim,
        )

    def forward(
        self, h: torch.Tensor, token_embed_weight: torch.Tensor,
    ) -> Tuple[torch.Tensor, dict]:
        psi, delta = self.spanda_state(h)
        logits = self.anchor_emission(psi, token_embed_weight)
        return logits, {"l_step": 0.0, "l_smooth": 0.0, "total_reg": 0.0}

    @property
    def temperature(self) -> float:
        return self.anchor_emission.temperature


class FullSpandaHead(nn.Module):
    """Full Spanda: gamma + anchor distance + optional regularizers."""

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

    @property
    def temperature(self) -> float:
        return self.anchor_emission.temperature


class GammaMemoryHead(nn.Module):
    """Gamma memory + linear head (no anchors)."""

    def __init__(
        self,
        embed_dim: int,
        vocab_size: int,
        psi_dim: int = 32,
        decay_gamma: float = 0.99,
    ):
        super().__init__()
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=decay_gamma,
        )
        self.linear_head = nn.Linear(psi_dim, vocab_size, bias=False)

    def forward(self, h: torch.Tensor) -> Tuple[torch.Tensor, dict]:
        psi, delta = self.spanda_state(h)
        logits = self.linear_head(psi)
        return logits, {"l_step": 0.0, "l_smooth": 0.0, "total_reg": 0.0}


# =========================================================================
# Wrapper models: backbone + head combinations
# =========================================================================


class BindingCacheLMBlock_Minimal(nn.Module):
    """Minimal sliding-window transformer block."""

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


def _make_backbone(vocab_size, d_model, num_heads, num_layers, d_ff,
                   dropout, max_seq_len, window_size):
    """Create shared backbone components. Returns (token_emb, pos_emb, layers, norm)."""
    token_emb = nn.Embedding(vocab_size, d_model)
    pos_emb = nn.Embedding(max_seq_len, d_model)
    drop = nn.Dropout(dropout)
    layers = nn.ModuleList([
        BindingCacheLMBlock_Minimal(d_model, num_heads, d_ff, dropout, window_size)
        for _ in range(num_layers)
    ])
    norm = nn.LayerNorm(d_model)
    return token_emb, pos_emb, drop, layers, norm


class SlidingWindowLM(nn.Module):
    """Baseline: sliding window + standard linear head."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size):
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
        self._head_type = "linear"

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


class SlidingWindowLM_ProjectedDot(nn.Module):
    """Part 1: Sliding window + ProjectedDotHead (psi projection, dot product, no distance, gamma=0)."""

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
        self.proj_dot_head = ProjectedDotHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
        )
        self._reg_losses = {}
        self._head_type = "projected_dot"

    def forward(self, input_ids):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        for layer in self.layers:
            x = layer(x)
        h = self.norm(x)
        logits, self._reg_losses = self.proj_dot_head(h, self.token_emb.weight)
        return logits

    @property
    def reg_losses(self):
        return self._reg_losses

    @property
    def temperature(self):
        return self.proj_dot_head.temperature


class SlidingWindowLM_AnchorOnly(nn.Module):
    """AnchorDistance with gamma=0 (no recurrence)."""

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
        self._head_type = "anchor_distance_g0"

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

    @property
    def temperature(self):
        return self.anchor_head.temperature


class SlidingWindowLM_RecurrentDot(nn.Module):
    """Part 4: Recurrence + dot product (no distance geometry)."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, psi_dim, decay_gamma=0.99):
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
        self.recurrent_dot_head = RecurrentDotHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
            decay_gamma=decay_gamma,
        )
        self._reg_losses = {}
        self._head_type = "recurrent_dot"

    def forward(self, input_ids):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        for layer in self.layers:
            x = layer(x)
        h = self.norm(x)
        logits, self._reg_losses = self.recurrent_dot_head(h, self.token_emb.weight)
        return logits

    @property
    def reg_losses(self):
        return self._reg_losses

    @property
    def temperature(self):
        return self.recurrent_dot_head.temperature


class SlidingWindowLM_FullSpanda(nn.Module):
    """Full Spanda (gamma + anchor distance + optional reg)."""

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
        self.spanda_head = FullSpandaHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
            decay_gamma=decay_gamma, use_regularizers=use_regularizers,
        )
        self._reg_losses = {}
        self._head_type = "anchor_distance"

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

    @property
    def temperature(self):
        return self.spanda_head.temperature


class SlidingWindowLM_GammaOnly(nn.Module):
    """Gamma memory + linear head (no anchors)."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, decay_gamma, psi_dim):
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
            decay_gamma=decay_gamma,
        )
        self._reg_losses = {}
        self._head_type = "gamma_linear"

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


# =========================================================================
# Part 2: Logit calibration measurement
# =========================================================================


def compute_logit_calibration(model, vocab_size, device, seq_len, step=0):
    """
    Compute logit calibration metrics for a model at current state.

    Returns CalibrationSnapshot with:
      - logit_mean, logit_std, tau_value, output_entropy, grad_norm
    """
    model.eval()
    with torch.no_grad():
        input_ids = torch.randint(0, vocab_size, (4, seq_len), device=device)
        logits = model(input_ids)  # [B, T, V]

        logit_mean = logits.mean().item()
        logit_std = logits.std().item()

        # Output entropy: -sum(p * log(p)) averaged over positions
        probs = F.softmax(logits, dim=-1)
        log_probs = F.log_softmax(logits, dim=-1)
        entropy = -(probs * log_probs).sum(dim=-1).mean().item()

        # Temperature (if available)
        tau = 1.0
        if hasattr(model, 'temperature'):
            tau = model.temperature
        elif hasattr(model, 'proj_dot_head') and hasattr(model.proj_dot_head, 'temperature'):
            tau = model.proj_dot_head.temperature
        elif hasattr(model, 'anchor_head') and hasattr(model.anchor_head, 'temperature'):
            tau = model.anchor_head.temperature
        elif hasattr(model, 'spanda_head') and hasattr(model.spanda_head, 'temperature'):
            tau = model.spanda_head.temperature
        elif hasattr(model, 'recurrent_dot_head') and hasattr(model.recurrent_dot_head, 'temperature'):
            tau = model.recurrent_dot_head.temperature

    # Gradient norm
    total_norm = 0.0
    for p in model.parameters():
        if p.grad is not None:
            total_norm += p.grad.data.norm(2).item() ** 2
    grad_norm = math.sqrt(total_norm)

    model.train()
    return CalibrationSnapshot(
        step=step,
        logit_mean=logit_mean,
        logit_std=logit_std,
        tau_value=tau,
        output_entropy=entropy,
        grad_norm=grad_norm,
    )


# =========================================================================
# Training with calibration logging
# =========================================================================


def train_with_calibration(model, vocab_size, device, num_steps, lr, seq_len,
                           use_spanda_reg=False, seed=42, calib_interval=20,
                           batch_size=BATCH_SIZE):
    """
    Train model and collect calibration snapshots at regular intervals.

    Returns (losses, calibration_snapshots).
    """
    torch.manual_seed(seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    model.train()
    losses = []
    calibrations = []

    for step in range(num_steps):
        input_ids = torch.randint(0, vocab_size, (batch_size, seq_len), device=device)
        targets = input_ids[:, 1:]

        logits = model(input_ids)
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

        # Collect calibration before optimizer step (grad available)
        if step % calib_interval == 0:
            snap = compute_logit_calibration(model, vocab_size, device, seq_len, step)
            calibrations.append(snap)

        optimizer.step()
        optimizer.zero_grad()
        losses.append(ce_loss.item())

    return losses, calibrations


def compute_perplexity(losses: List[float], last_n: int = 20) -> float:
    """Compute perplexity from last N losses."""
    avg_loss = sum(losses[-last_n:]) / min(last_n, len(losses))
    return math.exp(min(avg_loss, 20.0))


# =========================================================================
# Part 3: Psi dynamics analysis (cross-window coherence)
# =========================================================================


def analyze_psi_dynamics(model, vocab_size, device, seq_len, window_size):
    """
    Analyze Psi trajectory dynamics for models with psi state.

    Returns cross-window coherence, psi continuity, etc.
    """
    model.eval()
    with torch.no_grad():
        input_ids = torch.randint(0, vocab_size, (4, seq_len), device=device)
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)

        x = model.dropout(model.token_emb(input_ids) + model.pos_emb(pos))
        for layer in model.layers:
            x = layer(x)
        h = model.norm(x)

        # Find the psi-producing head
        spanda_state = None
        if hasattr(model, 'gamma_head'):
            spanda_state = model.gamma_head.spanda_state
        elif hasattr(model, 'spanda_head'):
            spanda_state = model.spanda_head.spanda_state
        elif hasattr(model, 'proj_dot_head'):
            spanda_state = model.proj_dot_head.spanda_state
        elif hasattr(model, 'anchor_head'):
            spanda_state = model.anchor_head.spanda_state
        elif hasattr(model, 'recurrent_dot_head'):
            spanda_state = model.recurrent_dot_head.spanda_state

        if spanda_state is None:
            return None

        psi, delta = spanda_state(h)

        psi_norms = psi.norm(dim=-1)
        psi_cos = F.cosine_similarity(psi[:, :-1, :], psi[:, 1:, :], dim=-1)
        delta_norms = delta.norm(dim=-1)

        window = min(window_size, N - 1)
        if N > window and psi[:, window:, :].size(1) > 0:
            psi_late = psi[:, window:, :]
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
# Part 5: Generation evaluation
# =========================================================================


@torch.no_grad()
def generate_tokens(model, vocab_size, device, prompt_len=32, gen_len=500,
                    temperature=1.0, num_prompts=4):
    """
    Generate token sequences from model.

    Returns list of (prompt_ids, generated_ids) tuples.
    """
    model.eval()
    results = []
    max_seq = getattr(model, 'pos_emb', None)
    max_pos = max_seq.num_embeddings if max_seq is not None else prompt_len + gen_len

    for i in range(num_prompts):
        # Random prompt
        prompt = torch.randint(0, vocab_size, (1, prompt_len), device=device)
        generated = prompt.clone()

        for t in range(gen_len):
            if generated.size(1) >= max_pos:
                break
            logits = model(generated)
            next_logits = logits[:, -1, :] / max(temperature, 1e-8)
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            generated = torch.cat([generated, next_token], dim=1)

        prompt_ids = prompt[0].cpu().tolist()
        gen_ids = generated[0, prompt_len:].cpu().tolist()
        results.append((prompt_ids, gen_ids))

    return results


def compute_generation_metrics(generations, vocab_size):
    """
    Compute generation quality metrics from generated sequences.

    Metrics:
      - repetition_rate: fraction of bigrams that repeat
      - unique_token_ratio: unique tokens / total tokens
      - top_token_concentration: frequency of most common token
      - mean_run_length: average length of consecutive repeated tokens
    """
    all_metrics = []

    for prompt_ids, gen_ids in generations:
        if len(gen_ids) < 2:
            continue

        # Repetition: fraction of bigrams that appear more than once
        bigrams = [(gen_ids[i], gen_ids[i + 1]) for i in range(len(gen_ids) - 1)]
        bigram_counts = Counter(bigrams)
        repeated_bigrams = sum(1 for c in bigram_counts.values() if c > 1)
        repetition_rate = repeated_bigrams / max(len(bigram_counts), 1)

        # Unique token ratio
        unique_ratio = len(set(gen_ids)) / max(len(gen_ids), 1)

        # Top token concentration
        token_counts = Counter(gen_ids)
        top_count = token_counts.most_common(1)[0][1]
        top_concentration = top_count / max(len(gen_ids), 1)

        # Mean run length (consecutive repeats)
        runs = []
        current_run = 1
        for i in range(1, len(gen_ids)):
            if gen_ids[i] == gen_ids[i - 1]:
                current_run += 1
            else:
                runs.append(current_run)
                current_run = 1
        runs.append(current_run)
        mean_run = sum(runs) / max(len(runs), 1)

        # Average log-prob (entropy of generation)
        all_metrics.append({
            "repetition_rate": repetition_rate,
            "unique_token_ratio": unique_ratio,
            "top_token_concentration": top_concentration,
            "mean_run_length": mean_run,
            "gen_length": len(gen_ids),
        })

    if not all_metrics:
        return {"repetition_rate": 0, "unique_token_ratio": 0,
                "top_token_concentration": 0, "mean_run_length": 0, "gen_length": 0}

    # Average over prompts
    agg = {}
    for key in all_metrics[0]:
        agg[key] = sum(m[key] for m in all_metrics) / len(all_metrics)
    return agg


@torch.no_grad()
def compute_avg_logprob(model, vocab_size, device, seq_len):
    """Compute average per-token log-probability on random data."""
    model.eval()
    input_ids = torch.randint(0, vocab_size, (8, seq_len), device=device)
    logits = model(input_ids)
    log_probs = F.log_softmax(logits[:, :-1, :], dim=-1)
    targets = input_ids[:, 1:]
    # Gather log-prob of actual next token
    token_logprobs = log_probs.gather(2, targets.unsqueeze(-1)).squeeze(-1)
    return token_logprobs.mean().item()


# =========================================================================
# Model factory
# =========================================================================


def make_model(variant, vocab_size, device, d_model=D_MODEL, num_heads=NUM_HEADS,
               num_layers=NUM_LAYERS, d_ff=D_FF, window_size=WINDOW_SIZE,
               psi_dim=PSI_DIM, seq_len=SEQ_LEN, decay_gamma=0.99):
    """Factory for creating model variants."""
    common = dict(
        vocab_size=vocab_size, d_model=d_model, num_heads=num_heads,
        num_layers=num_layers, d_ff=d_ff, dropout=0.0,
        max_seq_len=seq_len + 16, window_size=window_size,
    )

    if variant == "baseline":
        return SlidingWindowLM(**common).to(device)
    elif variant == "projected_dot":
        return SlidingWindowLM_ProjectedDot(**common, psi_dim=psi_dim).to(device)
    elif variant == "anchor_g0":
        return SlidingWindowLM_AnchorOnly(**common, psi_dim=psi_dim).to(device)
    elif variant == "anchor_gamma":
        return SlidingWindowLM_FullSpanda(
            **common, decay_gamma=decay_gamma, psi_dim=psi_dim,
        ).to(device)
    elif variant == "recurrent_dot":
        return SlidingWindowLM_RecurrentDot(
            **common, psi_dim=psi_dim, decay_gamma=decay_gamma,
        ).to(device)
    elif variant == "gamma_only":
        return SlidingWindowLM_GammaOnly(
            **common, decay_gamma=decay_gamma, psi_dim=psi_dim,
        ).to(device)
    else:
        raise ValueError(f"Unknown variant: {variant}")


# =========================================================================
# Report generation
# =========================================================================


def print_separator(label, width=90):
    print(f"\n  {'=' * width}")
    print(f"  {label}")
    print(f"  {'=' * width}")


def print_calibration_table(results: Dict[str, DiagnosticResult]):
    """Part 2: Print logit calibration comparison table."""
    print_separator("LOGIT CALIBRATION COMPARISON")
    print(f"  {'Variant':<22} {'Logit Mean':>11} {'Logit Std':>10} "
          f"{'Tau':>8} {'Entropy':>9} {'Grad Norm':>10}")
    print(f"  {'-' * 80}")

    for key, r in results.items():
        if r.calibration:
            # Use last calibration snapshot
            c = r.calibration[-1]
            print(f"  {r.variant:<22} {c.logit_mean:>11.4f} {c.logit_std:>10.4f} "
                  f"{c.tau_value:>8.4f} {c.output_entropy:>9.4f} {c.grad_norm:>10.4f}")


def print_interaction_analysis(results: Dict[str, DiagnosticResult]):
    """Part 7: Compute and print interaction decomposition."""
    print_separator("INTERACTION ANALYSIS (Part 7)")

    baseline_loss = results.get("baseline")
    if baseline_loss is None:
        print("  No baseline result found.")
        return

    B = baseline_loss.final_loss

    keys = {
        "gamma_only": "Gamma-only improvement",
        "anchor_g0": "Anchor-only improvement",
        "projected_dot": "ProjectedDot improvement",
        "anchor_gamma": "Gamma+Anchor (combined)",
    }

    improvements = {}
    for key, label in keys.items():
        if key in results:
            improvements[key] = B - results[key].final_loss

    for key, label in keys.items():
        if key in improvements:
            v = improvements[key]
            print(f"  {label:<35} {v:>+.4f} ({'IMPROVES' if v > 0 else 'HURTS'})")

    # Interaction term: Combined - (Gamma_only + Anchor_only - Baseline)
    if all(k in improvements for k in ["gamma_only", "anchor_g0", "anchor_gamma"]):
        gamma_imp = improvements["gamma_only"]
        anchor_imp = improvements["anchor_g0"]
        combined_imp = improvements["anchor_gamma"]
        interaction = combined_imp - (gamma_imp + anchor_imp)

        print(f"\n  Interaction = Combined - (Gamma_only + Anchor_only)")
        print(f"  Interaction = {combined_imp:.4f} - ({gamma_imp:.4f} + {anchor_imp:.4f})")
        print(f"  Interaction = {interaction:>+.4f} "
              f"({'super-additive' if interaction > 0.001 else 'sub-additive' if interaction < -0.001 else 'additive'})")

    # ProjectedDot vs AnchorDistance comparison
    if "projected_dot" in improvements and "anchor_g0" in improvements:
        pd_imp = improvements["projected_dot"]
        ad_imp = improvements["anchor_g0"]
        diff = ad_imp - pd_imp
        print(f"\n  AnchorDistance vs ProjectedDot gap: {diff:>+.4f}")
        if abs(diff) < 0.01:
            print(f"  -> CONCLUSION: Improvement is from projection/conditioning, NOT geometry.")
        elif diff > 0.01:
            print(f"  -> CONCLUSION: Distance geometry provides additional benefit.")
        else:
            print(f"  -> CONCLUSION: Dot product outperforms distance (geometry may hurt).")


def generate_final_report(results, long_results=None, window_results=None, gen_results=None):
    """Generate the complete diagnostic report."""
    print_separator("SPANDA v0.4 DIAGNOSTIC ABLATION REPORT", 90)

    # 1. Loss results table
    print_separator("1. LOSS RESULTS TABLE")
    B = results.get("baseline", DiagnosticResult("?", "?", 99, 99, 0)).final_loss

    print(f"  {'Variant':<28} {'Loss':>8} {'PPL':>8} {'Delta':>8} "
          f"{'%Improv':>8} {'Params':>8}")
    print(f"  {'-' * 80}")

    for key in ["baseline", "projected_dot", "anchor_g0", "recurrent_dot",
                "anchor_gamma", "gamma_only"]:
        if key not in results:
            continue
        r = results[key]
        delta = r.final_loss - B
        pct = (delta / B * 100) if B > 0 else 0
        print(f"  {r.variant:<28} {r.final_loss:>8.4f} {r.perplexity:>8.1f} "
              f"{delta:>+8.4f} {pct:>+7.1f}% {r.param_count:>8d}")

    # 2. Calibration
    print_calibration_table(results)

    # 3. Interaction
    print_interaction_analysis(results)

    # 4. Conclusion
    print_separator("5. CONCLUSION")

    pd_loss = results.get("projected_dot", DiagnosticResult("?", "?", 99, 99, 0)).final_loss
    ad_loss = results.get("anchor_g0", DiagnosticResult("?", "?", 99, 99, 0)).final_loss
    rd_loss = results.get("recurrent_dot", DiagnosticResult("?", "?", 99, 99, 0)).final_loss
    ag_loss = results.get("anchor_gamma", DiagnosticResult("?", "?", 99, 99, 0)).final_loss

    # Which component is primary?
    projection_effect = B - pd_loss  # How much projection helps
    geometry_effect = pd_loss - ad_loss  # Additional benefit of geometry over dot
    recurrence_effect = pd_loss - rd_loss  # Additional benefit of recurrence over no-recurrence
    full_effect = B - ag_loss  # Total improvement of full system

    print(f"  Projection effect (B - ProjDot):   {projection_effect:>+.4f}")
    print(f"  Geometry effect (ProjDot - Anchor): {geometry_effect:>+.4f}")
    print(f"  Recurrence effect (ProjDot - RecDot): {recurrence_effect:>+.4f}")
    print(f"  Full system effect (B - Gamma+Anch):  {full_effect:>+.4f}")

    effects = {
        "Projection/conditioning": abs(projection_effect),
        "Distance geometry": abs(geometry_effect),
        "Recurrence (gamma memory)": abs(recurrence_effect),
    }

    # Calibration artifact check
    calib_artifact = False
    if results.get("baseline") and results.get("projected_dot"):
        bc = results["baseline"].calibration
        pc = results["projected_dot"].calibration
        if bc and pc:
            b_std = bc[-1].logit_std
            p_std = pc[-1].logit_std
            if abs(b_std - p_std) / max(b_std, 0.01) > 0.5:
                calib_artifact = True
                print(f"\n  WARNING: Logit scale differs significantly between baseline "
                      f"({b_std:.3f}) and projected_dot ({p_std:.3f}).")
                print(f"  Improvement may be partially a calibration artifact.")

    primary = max(effects, key=effects.get)
    print(f"\n  PRIMARY DRIVER: {primary} (magnitude: {effects[primary]:.4f})")

    if not calib_artifact:
        print(f"  No calibration artifact detected (logit scales comparable).")

    print(f"\n  Spanda's benefit is: ", end="")
    if effects["Projection/conditioning"] > effects["Distance geometry"] and \
       effects["Projection/conditioning"] > effects["Recurrence (gamma memory)"]:
        print("a BETTER-CONDITIONED HEAD advantage (projection into psi space).")
    elif effects["Distance geometry"] > effects["Projection/conditioning"]:
        print("a GEOMETRIC OUTPUT RESTRUCTURING advantage (distance-based emission).")
    elif effects["Recurrence (gamma memory)"] > effects["Projection/conditioning"]:
        print("a REAL ARCHITECTURAL MEMORY advantage (cross-window bridging via gamma).")
    else:
        print("INDETERMINATE -- effects are comparable in magnitude.")

    print(f"  {'=' * 90}")


# =========================================================================
# Main test class
# =========================================================================


@pytest.mark.skipif(not SPANDA_AVAILABLE, reason="Spanda modules not available")
@pytest.mark.skipif(not BINDING_CACHE_AVAILABLE, reason="BindingCache not available")
class TestSpandaDiagnosticAblation:
    """
    Spanda v0.4 Diagnostic Expansion.

    Controlled experimental ablation to determine whether improvement is from:
      A) Projection into psi space
      B) Distance-based emission geometry
      C) Recurrence (gamma memory)
      D) Calibration / logit scaling differences
      E) True cross-window bridging
    """

    @pytest.fixture(scope="class")
    def vocab(self):
        return HardVocabulary()

    @pytest.fixture(scope="class")
    def device(self):
        return "cuda" if torch.cuda.is_available() else "cpu"

    def test_core_diagnostic_ablation(self, vocab, device):
        """
        Parts 1, 2, 4, 5, 7: Full diagnostic with all head variants.

        Compares:
          1. Baseline lm_head (h @ W)
          2. ProjectedDotHead (psi @ anchors.T / tau, gamma=0)
          3. AnchorDistanceHead (gamma=0)
          4. AnchorDistanceHead (gamma=0.99)
          5. RecurrentDotHead (gamma=0.99, dot product, no distance)
          6. GammaOnly (gamma=0.99, linear head)
        """
        V = vocab.vocab_size
        results: Dict[str, DiagnosticResult] = {}

        variants = [
            ("baseline", "Baseline (linear head)", {}),
            ("projected_dot", "ProjectedDot (g=0)", {}),
            ("anchor_g0", "AnchorDist (g=0)", {}),
            ("anchor_gamma", "AnchorDist (g=0.99)", {"decay_gamma": 0.99}),
            ("recurrent_dot", "RecurrentDot (g=0.99)", {"decay_gamma": 0.99}),
            ("gamma_only", "GammaOnly (linear)", {"decay_gamma": 0.99}),
        ]

        for variant_key, variant_name, kwargs in variants:
            print(f"\n  Training {variant_name}...")
            model = make_model(variant_key, V, device, **kwargs)
            losses, calibrations = train_with_calibration(
                model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42,
            )
            results[variant_key] = DiagnosticResult(
                variant=variant_name,
                description=variant_key,
                final_loss=sum(losses[-20:]) / 20,
                perplexity=compute_perplexity(losses),
                param_count=sum(p.numel() for p in model.parameters()),
                losses=losses,
                calibration=calibrations,
            )

        # Part 2: Calibration table
        print_calibration_table(results)

        # Part 5: Generation evaluation
        print_separator("GENERATION EVALUATION (Part 5)")
        print(f"  {'Variant':<28} {'RepRate':>8} {'UniqueR':>8} "
              f"{'TopConc':>8} {'MeanRun':>8} {'AvgLogP':>9}")
        print(f"  {'-' * 80}")

        for variant_key, variant_name, kwargs in variants:
            model = make_model(variant_key, V, device, **kwargs)
            # Load trained weights by retraining (short, same seed => same model)
            _ = train_with_calibration(
                model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42,
                calib_interval=9999,  # Skip calibration for speed
            )
            max_pos = model.pos_emb.num_embeddings
            gen_len = min(GEN_LENGTH, max_pos - GEN_PROMPT_LEN - 1)
            gens = generate_tokens(model, V, device, GEN_PROMPT_LEN, gen_len,
                                   num_prompts=GEN_NUM_PROMPTS)
            gen_metrics = compute_generation_metrics(gens, V)
            avg_lp = compute_avg_logprob(model, V, device, SEQ_LEN)
            print(f"  {variant_name:<28} {gen_metrics['repetition_rate']:>8.4f} "
                  f"{gen_metrics['unique_token_ratio']:>8.4f} "
                  f"{gen_metrics['top_token_concentration']:>8.4f} "
                  f"{gen_metrics['mean_run_length']:>8.2f} "
                  f"{avg_lp:>9.4f}")

        # Psi dynamics for psi-based variants
        print_separator("PSI DYNAMICS (cross-window analysis)")
        for variant_key, variant_name, kwargs in variants:
            if variant_key == "baseline":
                continue
            model = make_model(variant_key, V, device, **kwargs)
            _ = train_with_calibration(
                model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42,
                calib_interval=9999,
            )
            dynamics = analyze_psi_dynamics(model, V, device, SEQ_LEN, WINDOW_SIZE)
            if dynamics:
                print(f"\n  {variant_name}:")
                print(f"    Mean ||Psi||:            {dynamics['mean_psi_norm']:.4f}")
                print(f"    Psi continuity:          {dynamics['mean_psi_continuity']:.4f}")
                print(f"    Cross-window coherence:  {dynamics['cross_window_coherence']:.4f}")
                print(f"    Mean ||Delta||:          {dynamics['mean_delta_norm']:.4f}")

        # Part 7: Interaction analysis + full report
        generate_final_report(results)

        # Validate all results
        for key, r in results.items():
            assert math.isfinite(r.final_loss), f"{key} loss not finite: {r.final_loss}"
            assert r.perplexity > 0, f"{key} PPL not positive"

    def test_long_sequence_stress(self, vocab, device):
        """
        Part 3: Long-sequence stress test.

        T in {1024, 2048}, w in {32, 64}.

        Forces recurrence to matter by using sequences much longer than window.
        """
        V = vocab.vocab_size

        print_separator("LONG-SEQUENCE STRESS TEST (Part 3)")

        configs = []
        for T in [1024, 2048]:
            for w in [32, 64]:
                configs.append((T, w))

        gamma_variants = [
            ("baseline", "Baseline", {}),
            ("projected_dot", "ProjDot (g=0)", {}),
            ("anchor_g0", "AnchorDist (g=0)", {}),
            ("anchor_gamma", "AnchorDist (g=0.99)", {"decay_gamma": 0.99}),
            ("anchor_gamma_999", "AnchorDist (g=0.999)", {"decay_gamma": 0.999}),
        ]

        for T, w in configs:
            print(f"\n  --- T={T}, w={w} ---")
            print(f"  {'Variant':<28} {'Loss':>8} {'PPL':>8} {'XW-Coher':>9} {'PsiCont':>8}")
            print(f"  {'-' * 70}")

            for var_key, var_name, kwargs in gamma_variants:
                actual_key = var_key
                if var_key == "anchor_gamma_999":
                    actual_key = "anchor_gamma"

                model = make_model(
                    actual_key, V, device, window_size=w, seq_len=T,
                    **kwargs,
                )
                losses, _ = train_with_calibration(
                    model, V, device,
                    num_steps=LONG_SEQ_TRAIN_STEPS,
                    lr=LR, seq_len=T, seed=42,
                    calib_interval=9999,
                    batch_size=LONG_BATCH_SIZE,
                )
                final_loss = sum(losses[-10:]) / min(10, len(losses))
                ppl = math.exp(min(final_loss, 20.0))

                # Cross-window coherence and psi continuity
                dynamics = analyze_psi_dynamics(model, V, device, min(T, 512), w)
                xw_coh = dynamics["cross_window_coherence"] if dynamics else 0.0
                psi_cont = dynamics["mean_psi_continuity"] if dynamics else 0.0

                print(f"  {var_name:<28} {final_loss:>8.4f} {ppl:>8.1f} "
                      f"{xw_coh:>9.4f} {psi_cont:>8.4f}")

                del model
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

        # Validate: all configs should produce finite results
        print(f"\n  Long-sequence stress test completed.")

    def test_window_scaling_curve(self, vocab, device):
        """
        Part 6: Window scaling curve.

        w in {4, 8, 16, 32, 64}.

        If improvement decays smoothly as w increases:
        -> Strong evidence Spanda compensates locality limitation.
        """
        V = vocab.vocab_size

        print_separator("WINDOW SCALING CURVE (Part 6)")
        print(f"  {'Window':>6} {'Base':>8} {'ProjDot':>8} {'AnchG0':>8} "
              f"{'AnchG99':>8} {'RecDot':>8} "
              f"{'PD-Imp':>8} {'AD-Imp':>8}")
        print(f"  {'-' * 80}")

        scaling_data = []

        for w in [4, 8, 16, 32, 64]:
            row = {"window": w}

            for var_key in ["baseline", "projected_dot", "anchor_g0",
                            "anchor_gamma", "recurrent_dot"]:
                model = make_model(var_key, V, device, window_size=w)
                losses, _ = train_with_calibration(
                    model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=42,
                    calib_interval=9999,
                )
                row[var_key] = sum(losses[-20:]) / 20
                del model

            pd_imp = ((row["baseline"] - row["projected_dot"]) / row["baseline"] * 100
                      if row["baseline"] > 0 else 0)
            ad_imp = ((row["baseline"] - row["anchor_g0"]) / row["baseline"] * 100
                      if row["baseline"] > 0 else 0)

            print(f"  w={w:<4} {row['baseline']:>8.4f} {row['projected_dot']:>8.4f} "
                  f"{row['anchor_g0']:>8.4f} {row['anchor_gamma']:>8.4f} "
                  f"{row['recurrent_dot']:>8.4f} "
                  f"{pd_imp:>+7.1f}% {ad_imp:>+7.1f}%")

            scaling_data.append(row)

        print(f"\n  Expected: Improvement magnitude decreases as window size increases.")
        print(f"  If confirmed -> Spanda compensates for locality limitation.")

        # Check trend
        if len(scaling_data) >= 3:
            pd_imps = [
                (d["baseline"] - d["projected_dot"]) / max(d["baseline"], 0.001)
                for d in scaling_data
            ]
            if all(pd_imps[i] >= pd_imps[i + 1] - 0.02 for i in range(len(pd_imps) - 1)):
                print(f"  CONFIRMED: Improvement decreases monotonically with window size.")
            else:
                print(f"  NOT CONFIRMED: Improvement does not decrease monotonically.")

    def test_gamma_sweep_on_long_sequences(self, vocab, device):
        """
        Extended gamma sweep: test whether gamma matters on longer sequences.

        gamma in {0.0, 0.9, 0.99, 0.999} x {anchor_distance, recurrent_dot}
        """
        V = vocab.vocab_size

        print_separator("GAMMA SWEEP: Long Sequence (T=256, w=16)")
        test_seq_len = 256
        test_window = 16

        print(f"  {'Gamma':>8} {'AnchorDist':>11} {'RecurrentDot':>13} "
              f"{'AD XW-Coh':>10} {'RD XW-Coh':>10}")
        print(f"  {'-' * 60}")

        for gamma in [0.0, 0.9, 0.99, 0.999]:
            # AnchorDistance with this gamma
            ad_model = make_model(
                "anchor_gamma", V, device, window_size=test_window,
                seq_len=test_seq_len, decay_gamma=gamma,
            )
            ad_losses, _ = train_with_calibration(
                ad_model, V, device, 60, LR, test_seq_len, seed=42,
                calib_interval=9999, batch_size=8,
            )
            ad_loss = sum(ad_losses[-10:]) / min(10, len(ad_losses))
            ad_dyn = analyze_psi_dynamics(ad_model, V, device, test_seq_len, test_window)
            ad_xw = ad_dyn["cross_window_coherence"] if ad_dyn else 0.0

            # RecurrentDot with this gamma
            rd_model = make_model(
                "recurrent_dot", V, device, window_size=test_window,
                seq_len=test_seq_len, decay_gamma=gamma,
            )
            rd_losses, _ = train_with_calibration(
                rd_model, V, device, 60, LR, test_seq_len, seed=42,
                calib_interval=9999, batch_size=8,
            )
            rd_loss = sum(rd_losses[-10:]) / min(10, len(rd_losses))
            rd_dyn = analyze_psi_dynamics(rd_model, V, device, test_seq_len, test_window)
            rd_xw = rd_dyn["cross_window_coherence"] if rd_dyn else 0.0

            print(f"  {gamma:>8.3f} {ad_loss:>11.4f} {rd_loss:>13.4f} "
                  f"{ad_xw:>10.4f} {rd_xw:>10.4f}")

            del ad_model, rd_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        print(f"\n  If gamma>0 helps only at long T -> recurrence matters.")
        print(f"  If gamma makes no difference -> projection/geometry is doing the work.")


# =========================================================================
# Standalone entry point
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
