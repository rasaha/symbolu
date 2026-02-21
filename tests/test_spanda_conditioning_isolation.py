#!/usr/bin/env python3
"""
Spanda Conditioning Isolation Suite.

Controlled experiment to determine whether Spanda's improvement is:
  A) Logit scale / entropy artifact
  B) Nonlinear bottleneck effect
  C) True conditioning improvement beyond scaling

Prior finding:
  PRIMARY DRIVER: projection/conditioning
  Baseline logit std (4.94) vs projected_dot (0.09) = massive scale mismatch.
  This suite isolates the causal factor.

Parts:
  1. Scale-Matched Baseline -- match logit scale via frozen scalar s
  2. Tau-Fixed Test -- disable learned temperature, use fixed tau=1.0
  3. Nonlinear Head Control -- MLP head with same architecture as psi MLP
  4. Parameter Count Parity -- ensure fair comparison within ±2%
  5. Report Required Metrics -- loss, logit std, entropy, grad norm, 3-seed stability
  6. Verdict Logic -- decision tree for causal conclusion

Usage:
  pytest tests/test_spanda_conditioning_isolation.py -v -s
  python tests/test_spanda_conditioning_isolation.py
"""

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

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
    from train_hard_probes import LocalWindowAttention
    BINDING_CACHE_AVAILABLE = True
except ImportError:
    BINDING_CACHE_AVAILABLE = False

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Spanda"))
    from spanda.state import SpandaState
    from spanda.emission import AnchorEmission, ProjectedDotEmission
    SPANDA_AVAILABLE = True
except ImportError:
    SPANDA_AVAILABLE = False


# =========================================================================
# Configuration — identical to diagnostic ablation suite
# =========================================================================

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
NUM_SEEDS = 3
SEEDS = [42, 137, 2024]


# =========================================================================
# Data structures
# =========================================================================


@dataclass
class IsolationResult:
    """Result for a single variant across multiple seeds."""
    variant: str
    param_count: int
    # Per-seed results
    final_losses: List[float] = field(default_factory=list)
    logit_stds: List[float] = field(default_factory=list)
    entropies: List[float] = field(default_factory=list)
    head_grad_norms: List[float] = field(default_factory=list)

    @property
    def mean_loss(self) -> float:
        return sum(self.final_losses) / len(self.final_losses) if self.final_losses else 0.0

    @property
    def loss_std(self) -> float:
        if len(self.final_losses) < 2:
            return 0.0
        m = self.mean_loss
        return math.sqrt(sum((x - m) ** 2 for x in self.final_losses) / (len(self.final_losses) - 1))

    @property
    def mean_logit_std(self) -> float:
        return sum(self.logit_stds) / len(self.logit_stds) if self.logit_stds else 0.0

    @property
    def mean_entropy(self) -> float:
        return sum(self.entropies) / len(self.entropies) if self.entropies else 0.0

    @property
    def mean_head_grad_norm(self) -> float:
        return sum(self.head_grad_norms) / len(self.head_grad_norms) if self.head_grad_norms else 0.0

    @property
    def perplexity(self) -> float:
        return math.exp(min(self.mean_loss, 20.0))


# =========================================================================
# Shared backbone (identical to diagnostic ablation)
# =========================================================================


class BindingCacheLMBlock_Minimal(nn.Module):
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


class _BackboneMixin:
    """Shared backbone forward pass."""

    def _get_hidden(self, input_ids):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        for layer in self.layers:
            x = layer(x)
        return self.norm(x)

    def _init_backbone(self, vocab_size, d_model, num_heads, num_layers,
                       d_ff, dropout, max_seq_len, window_size):
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


# =========================================================================
# Part 1: Scale-Matched Baseline
# =========================================================================


class SlidingWindowLM_Baseline(nn.Module, _BackboneMixin):
    """Original baseline: h @ W (weight-tied)."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size):
        super().__init__()
        self._init_backbone(vocab_size, d_model, num_heads, num_layers,
                            d_ff, dropout, max_seq_len, window_size)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
        self.lm_head.weight = self.token_emb.weight
        self._head_type = "baseline"

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        return self.lm_head(h)

    def head_parameters(self):
        return [self.lm_head.weight]


class SlidingWindowLM_ScaleMatched(nn.Module, _BackboneMixin):
    """Part 1: Baseline with frozen scalar s to match logit scale."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, scale_factor=1.0):
        super().__init__()
        self._init_backbone(vocab_size, d_model, num_heads, num_layers,
                            d_ff, dropout, max_seq_len, window_size)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
        self.lm_head.weight = self.token_emb.weight
        # Frozen scalar — registered as buffer, NOT parameter
        self.register_buffer("scale_factor", torch.tensor(scale_factor))
        self._head_type = "scale_matched"

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        logits = self.lm_head(h)
        return logits * self.scale_factor

    def head_parameters(self):
        return [self.lm_head.weight]


# =========================================================================
# Part 2: Tau-Fixed Spanda heads
# =========================================================================


class ProjectedDotHead_TauFixed(nn.Module):
    """ProjectedDot with tau frozen at a fixed value."""

    def __init__(self, embed_dim, vocab_size, psi_dim=32, fixed_tau=1.0):
        super().__init__()
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=0.0,
        )
        self.dot_emission = ProjectedDotEmission(
            vocab_size=vocab_size, embed_dim=embed_dim, psi_dim=psi_dim,
        )
        # Freeze tau and set to fixed value
        self.dot_emission.log_temperature.requires_grad = False
        with torch.no_grad():
            self.dot_emission.log_temperature.fill_(math.log(fixed_tau))

    def forward(self, h, token_embed_weight):
        psi, delta = self.spanda_state(h)
        logits = self.dot_emission(psi, token_embed_weight)
        return logits, {"total_reg": 0.0}

    @property
    def temperature(self):
        return self.dot_emission.temperature


class AnchorDistHead_TauFixed(nn.Module):
    """AnchorDistance (gamma=0) with tau frozen at a fixed value."""

    def __init__(self, embed_dim, vocab_size, psi_dim=32, fixed_tau=1.0):
        super().__init__()
        self.spanda_state = SpandaState(
            embed_dim=embed_dim, psi_dim=psi_dim, decay_gamma=0.0,
        )
        self.anchor_emission = AnchorEmission(
            vocab_size=vocab_size, embed_dim=embed_dim, psi_dim=psi_dim,
        )
        # Freeze tau and set to fixed value
        self.anchor_emission.log_temperature.requires_grad = False
        with torch.no_grad():
            self.anchor_emission.log_temperature.fill_(math.log(fixed_tau))

    def forward(self, h, token_embed_weight):
        psi, delta = self.spanda_state(h)
        logits = self.anchor_emission(psi, token_embed_weight)
        return logits, {"total_reg": 0.0}

    @property
    def temperature(self):
        return self.anchor_emission.temperature


# =========================================================================
# Part 3: Nonlinear MLP Head Control
# =========================================================================


class MLPHead(nn.Module):
    """
    MLP head with same architecture as SpandaState's delta_mlp.

    Pipeline:
        u = MLP(h)          # Linear(d_model→d_model//2) + GELU + Linear(d_model//2→psi_dim)
        logits = u @ W2     # Linear(psi_dim→vocab_size, no bias)

    Same MLP bottleneck as Spanda, but no distance geometry,
    no anchor projection, no temperature scaling.
    """

    def __init__(self, embed_dim, vocab_size, psi_dim=32):
        super().__init__()
        # Same MLP architecture as SpandaState.delta_mlp
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, psi_dim),
        )
        self.output_proj = nn.Linear(psi_dim, vocab_size, bias=False)

    def forward(self, h):
        u = self.mlp(h)
        return self.output_proj(u), {"total_reg": 0.0}


class MLPHead_WithScale(nn.Module):
    """
    MLP head + anchor projection for parameter parity with ProjectedDot.

    Pipeline:
        u = MLP(h)                                      # same as SpandaState.delta_mlp
        anchors = normalize(anchor_proj(W_embed))        # same as ProjectedDotEmission
        logits = (u @ anchors.T) / tau                   # tau fixed

    This has the EXACT same parameter count as ProjectedDot
    but without SpandaState's gamma/psi mechanism.
    """

    def __init__(self, embed_dim, vocab_size, psi_dim=32, fixed_tau=1.0):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, psi_dim),
        )
        self.anchor_proj = nn.Linear(embed_dim, psi_dim, bias=False)
        self.fixed_tau = fixed_tau

    def forward(self, h, token_embed_weight):
        u = self.mlp(h)
        anchors = F.normalize(self.anchor_proj(token_embed_weight), dim=-1)
        logits = (u @ anchors.T) / self.fixed_tau
        return logits, {"total_reg": 0.0}


# =========================================================================
# Full model wrappers
# =========================================================================


class SlidingWindowLM_ProjectedDot(nn.Module, _BackboneMixin):
    """ProjectedDot (gamma=0) with learnable tau."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, psi_dim):
        super().__init__()
        self._init_backbone(vocab_size, d_model, num_heads, num_layers,
                            d_ff, dropout, max_seq_len, window_size)
        from test_spanda_diagnostic_ablation import ProjectedDotHead
        self.proj_dot_head = ProjectedDotHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
        )
        self._reg_losses = {}
        self._head_type = "projected_dot"

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        logits, self._reg_losses = self.proj_dot_head(h, self.token_emb.weight)
        return logits

    def head_parameters(self):
        return list(self.proj_dot_head.parameters())

    @property
    def reg_losses(self):
        return self._reg_losses

    @property
    def temperature(self):
        return self.proj_dot_head.temperature


class SlidingWindowLM_AnchorDist(nn.Module, _BackboneMixin):
    """AnchorDistance (gamma=0) with learnable tau."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, psi_dim):
        super().__init__()
        self._init_backbone(vocab_size, d_model, num_heads, num_layers,
                            d_ff, dropout, max_seq_len, window_size)
        from test_spanda_diagnostic_ablation import AnchorOnlyHead
        self.anchor_head = AnchorOnlyHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
        )
        self._reg_losses = {}
        self._head_type = "anchor_dist"

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        logits, self._reg_losses = self.anchor_head(h, self.token_emb.weight)
        return logits

    def head_parameters(self):
        return list(self.anchor_head.parameters())

    @property
    def reg_losses(self):
        return self._reg_losses

    @property
    def temperature(self):
        return self.anchor_head.temperature


class SlidingWindowLM_ProjectedDot_TauFixed(nn.Module, _BackboneMixin):
    """ProjectedDot with tau frozen."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, psi_dim, fixed_tau=1.0):
        super().__init__()
        self._init_backbone(vocab_size, d_model, num_heads, num_layers,
                            d_ff, dropout, max_seq_len, window_size)
        self.proj_dot_head = ProjectedDotHead_TauFixed(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
            fixed_tau=fixed_tau,
        )
        self._reg_losses = {}
        self._head_type = "projected_dot_tau_fixed"

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        logits, self._reg_losses = self.proj_dot_head(h, self.token_emb.weight)
        return logits

    def head_parameters(self):
        return list(self.proj_dot_head.parameters())

    @property
    def temperature(self):
        return self.proj_dot_head.temperature


class SlidingWindowLM_AnchorDist_TauFixed(nn.Module, _BackboneMixin):
    """AnchorDistance (gamma=0) with tau frozen."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, psi_dim, fixed_tau=1.0):
        super().__init__()
        self._init_backbone(vocab_size, d_model, num_heads, num_layers,
                            d_ff, dropout, max_seq_len, window_size)
        self.anchor_head = AnchorDistHead_TauFixed(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
            fixed_tau=fixed_tau,
        )
        self._reg_losses = {}
        self._head_type = "anchor_dist_tau_fixed"

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        logits, self._reg_losses = self.anchor_head(h, self.token_emb.weight)
        return logits

    def head_parameters(self):
        return list(self.anchor_head.parameters())

    @property
    def temperature(self):
        return self.anchor_head.temperature


class SlidingWindowLM_MLPHead(nn.Module, _BackboneMixin):
    """Nonlinear MLP head — same bottleneck as Spanda, no Spanda mechanism."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, psi_dim):
        super().__init__()
        self._init_backbone(vocab_size, d_model, num_heads, num_layers,
                            d_ff, dropout, max_seq_len, window_size)
        self.mlp_head = MLPHead(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
        )
        self._reg_losses = {}
        self._head_type = "mlp_head"

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        logits, self._reg_losses = self.mlp_head(h)
        return logits

    def head_parameters(self):
        return list(self.mlp_head.parameters())


class SlidingWindowLM_MLPHead_WithScale(nn.Module, _BackboneMixin):
    """MLP head with anchor projection — parameter-matched to ProjectedDot."""

    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff,
                 dropout, max_seq_len, window_size, psi_dim, fixed_tau=1.0):
        super().__init__()
        self._init_backbone(vocab_size, d_model, num_heads, num_layers,
                            d_ff, dropout, max_seq_len, window_size)
        self.mlp_head = MLPHead_WithScale(
            embed_dim=d_model, vocab_size=vocab_size, psi_dim=psi_dim,
            fixed_tau=fixed_tau,
        )
        self._reg_losses = {}
        self._head_type = "mlp_head_scaled"

    def forward(self, input_ids):
        h = self._get_hidden(input_ids)
        logits, self._reg_losses = self.mlp_head(h, self.token_emb.weight)
        return logits

    def head_parameters(self):
        return list(self.mlp_head.parameters())


# =========================================================================
# Measurement utilities
# =========================================================================


@torch.no_grad()
def measure_logit_stats(model, vocab_size, device, seq_len, batch_size=16):
    """Measure logit std and entropy on a calibration batch."""
    model.eval()
    input_ids = torch.randint(0, vocab_size, (batch_size, seq_len), device=device)
    logits = model(input_ids)
    logit_std = logits.std().item()
    probs = F.softmax(logits, dim=-1)
    log_probs = F.log_softmax(logits, dim=-1)
    entropy = -(probs * log_probs).sum(dim=-1).mean().item()
    model.train()
    return logit_std, entropy


def compute_scale_factor(baseline_model, projdot_model, vocab_size, device,
                         seq_len, seed=42):
    """
    Part 1: Compute frozen scale factor s.

    s = projected_dot_logit_std / baseline_logit_std
    """
    torch.manual_seed(seed)
    baseline_std, _ = measure_logit_stats(baseline_model, vocab_size, device, seq_len)
    projdot_std, _ = measure_logit_stats(projdot_model, vocab_size, device, seq_len)
    s = projdot_std / max(baseline_std, 1e-8)
    return s, baseline_std, projdot_std


def compute_head_grad_norm(model):
    """Compute gradient norm for head parameters only."""
    total_norm = 0.0
    if hasattr(model, 'head_parameters'):
        for p in model.head_parameters():
            if p.grad is not None:
                total_norm += p.grad.data.norm(2).item() ** 2
    else:
        for p in model.parameters():
            if p.grad is not None:
                total_norm += p.grad.data.norm(2).item() ** 2
    return math.sqrt(total_norm)


def train_and_measure(model, vocab_size, device, num_steps, lr, seq_len,
                      batch_size=BATCH_SIZE, seed=42):
    """
    Train model and return final metrics.

    Returns: (final_loss, logit_std, entropy, head_grad_norm)
    """
    torch.manual_seed(seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    model.train()
    losses = []

    for step in range(num_steps):
        input_ids = torch.randint(0, vocab_size, (batch_size, seq_len), device=device)
        targets = input_ids[:, 1:]
        logits = model(input_ids)
        ce_loss = F.cross_entropy(
            logits[:, :-1, :].contiguous().view(-1, vocab_size),
            targets.contiguous().view(-1),
        )
        total_loss = ce_loss
        if hasattr(model, '_reg_losses'):
            reg = model._reg_losses.get("total_reg", 0.0)
            if isinstance(reg, torch.Tensor):
                total_loss = ce_loss + reg

        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

        # Capture head grad norm at last step
        if step == num_steps - 1:
            head_gn = compute_head_grad_norm(model)

        optimizer.step()
        optimizer.zero_grad()
        losses.append(ce_loss.item())

    final_loss = sum(losses[-20:]) / min(20, len(losses))
    logit_std, entropy = measure_logit_stats(model, vocab_size, device, seq_len)

    tau = 1.0
    if hasattr(model, 'temperature'):
        tau = model.temperature

    return final_loss, logit_std, entropy, head_gn, tau


# =========================================================================
# Model factory
# =========================================================================


def _common_kwargs(vocab_size, d_model=D_MODEL, num_heads=NUM_HEADS,
                   num_layers=NUM_LAYERS, d_ff=D_FF, window_size=WINDOW_SIZE,
                   seq_len=SEQ_LEN):
    return dict(
        vocab_size=vocab_size, d_model=d_model, num_heads=num_heads,
        num_layers=num_layers, d_ff=d_ff, dropout=0.0,
        max_seq_len=seq_len + 16, window_size=window_size,
    )


def make_model(variant, vocab_size, device, scale_factor=1.0, fixed_tau=1.0,
               psi_dim=PSI_DIM, **kwargs):
    common = _common_kwargs(vocab_size, **{k: v for k, v in kwargs.items()
                                           if k in ('d_model', 'num_heads', 'num_layers',
                                                    'd_ff', 'window_size', 'seq_len')})

    if variant == "baseline":
        return SlidingWindowLM_Baseline(**common).to(device)
    elif variant == "scale_matched":
        return SlidingWindowLM_ScaleMatched(**common, scale_factor=scale_factor).to(device)
    elif variant == "projected_dot":
        return SlidingWindowLM_ProjectedDot(**common, psi_dim=psi_dim).to(device)
    elif variant == "anchor_dist":
        return SlidingWindowLM_AnchorDist(**common, psi_dim=psi_dim).to(device)
    elif variant == "projected_dot_tau_fixed":
        return SlidingWindowLM_ProjectedDot_TauFixed(
            **common, psi_dim=psi_dim, fixed_tau=fixed_tau).to(device)
    elif variant == "anchor_dist_tau_fixed":
        return SlidingWindowLM_AnchorDist_TauFixed(
            **common, psi_dim=psi_dim, fixed_tau=fixed_tau).to(device)
    elif variant == "mlp_head":
        return SlidingWindowLM_MLPHead(**common, psi_dim=psi_dim).to(device)
    elif variant == "mlp_head_scaled":
        return SlidingWindowLM_MLPHead_WithScale(
            **common, psi_dim=psi_dim, fixed_tau=fixed_tau).to(device)
    else:
        raise ValueError(f"Unknown variant: {variant}")


# =========================================================================
# Report formatting
# =========================================================================


def print_separator(label, width=90):
    print(f"\n  {'=' * width}")
    print(f"  {label}")
    print(f"  {'=' * width}")


def print_results_table(results: Dict[str, IsolationResult], title: str):
    print_separator(title)
    print(f"  {'Variant':<28} {'Loss':>8} {'±Std':>7} {'PPL':>8} "
          f"{'LogitStd':>9} {'Entropy':>8} {'HeadGN':>8} {'Params':>8}")
    print(f"  {'-' * 90}")

    for key, r in results.items():
        print(f"  {r.variant:<28} {r.mean_loss:>8.4f} {r.loss_std:>7.4f} "
              f"{r.perplexity:>8.1f} {r.mean_logit_std:>9.4f} "
              f"{r.mean_entropy:>8.4f} {r.mean_head_grad_norm:>8.4f} "
              f"{r.param_count:>8d}")


# =========================================================================
# Main test class
# =========================================================================


@pytest.mark.skipif(not SPANDA_AVAILABLE, reason="Spanda modules not available")
@pytest.mark.skipif(not BINDING_CACHE_AVAILABLE, reason="BindingCache not available")
class TestSpandaConditioningIsolation:
    """
    Conditioning Isolation Suite.

    Determines whether Spanda's improvement is:
      A) Logit scale / entropy artifact
      B) Nonlinear bottleneck effect
      C) True conditioning improvement beyond scaling
    """

    @pytest.fixture(scope="class")
    def vocab(self):
        return HardVocabulary()

    @pytest.fixture(scope="class")
    def device(self):
        return "cuda" if torch.cuda.is_available() else "cpu"

    def test_part1_scale_matched_baseline(self, vocab, device):
        """
        Part 1: Scale-Matched Baseline.

        Match logit scale between baseline and ProjectedDot via frozen scalar s.
        If scale-matched baseline closes the gap -> improvement was scaling artifact.
        """
        V = vocab.vocab_size
        results: Dict[str, IsolationResult] = {}

        # Step 1: Compute scale factor from untrained models
        print_separator("PART 1: SCALE-MATCHED BASELINE")

        baseline_cal = make_model("baseline", V, device)
        projdot_cal = make_model("projected_dot", V, device)
        s, base_std, pd_std = compute_scale_factor(
            baseline_cal, projdot_cal, V, device, SEQ_LEN, seed=42,
        )
        del baseline_cal, projdot_cal

        print(f"  Calibration:")
        print(f"    Baseline logit std:      {base_std:.6f}")
        print(f"    ProjectedDot logit std:  {pd_std:.6f}")
        print(f"    Scale factor s:          {s:.6f}")
        print(f"    s is FROZEN (not learned)")

        # Step 2: Train all variants across 3 seeds
        variants = [
            ("baseline", "Baseline (original)"),
            ("scale_matched", "Baseline (scale-matched)"),
            ("projected_dot", "ProjectedDot (g=0)"),
            ("anchor_dist", "AnchorDist (g=0)"),
        ]

        for var_key, var_name in variants:
            result = IsolationResult(variant=var_name, param_count=0)

            for seed in SEEDS:
                model = make_model(var_key, V, device, scale_factor=s)
                if result.param_count == 0:
                    result.param_count = sum(p.numel() for p in model.parameters())

                loss, logit_std, entropy, head_gn, tau = train_and_measure(
                    model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=seed,
                )
                result.final_losses.append(loss)
                result.logit_stds.append(logit_std)
                result.entropies.append(entropy)
                result.head_grad_norms.append(head_gn)
                del model

            results[var_key] = result

        print_results_table(results, "PART 1 RESULTS")

        # Analysis
        bl = results["baseline"].mean_loss
        sm = results["scale_matched"].mean_loss
        pd = results["projected_dot"].mean_loss

        gap_original = bl - pd
        gap_after_scaling = sm - pd

        print(f"\n  Gap analysis:")
        print(f"    Original gap  (Baseline - ProjDot):       {gap_original:>+.4f}")
        print(f"    After scaling (ScaleMatch - ProjDot):     {gap_after_scaling:>+.4f}")

        if gap_original > 0.001:
            fraction_closed = 1.0 - (gap_after_scaling / gap_original)
            print(f"    Fraction of gap closed by scaling:        {fraction_closed:>+.1%}")
        else:
            fraction_closed = 0.0
            print(f"    Original gap negligible — no scaling effect to measure.")

        # Assertions
        for key, r in results.items():
            assert math.isfinite(r.mean_loss), f"{key} loss not finite"
            assert r.perplexity > 0, f"{key} PPL not positive"

    def test_part2_tau_fixed(self, vocab, device):
        """
        Part 2: Tau-Fixed Test.

        Disable learnable tau, use fixed tau=1.0 for all heads.
        If ProjectedDot still wins -> not a tau-learning artifact.
        """
        V = vocab.vocab_size
        results: Dict[str, IsolationResult] = {}

        print_separator("PART 2: TAU-FIXED TEST (tau=1.0 for all)")

        # Compute scale factor for scale-matched baseline
        baseline_cal = make_model("baseline", V, device)
        projdot_cal = make_model("projected_dot_tau_fixed", V, device, fixed_tau=1.0)
        s, _, _ = compute_scale_factor(
            baseline_cal, projdot_cal, V, device, SEQ_LEN,
        )
        del baseline_cal, projdot_cal

        variants = [
            ("scale_matched", "ScaleMatched (s frozen)"),
            ("projected_dot_tau_fixed", "ProjDot (tau=1.0 fixed)"),
            ("anchor_dist_tau_fixed", "AnchorDist (tau=1.0 fixed)"),
        ]

        for var_key, var_name in variants:
            result = IsolationResult(variant=var_name, param_count=0)

            for seed in SEEDS:
                model = make_model(var_key, V, device, scale_factor=s, fixed_tau=1.0)
                if result.param_count == 0:
                    result.param_count = sum(p.numel() for p in model.parameters())

                loss, logit_std, entropy, head_gn, tau = train_and_measure(
                    model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=seed,
                )
                result.final_losses.append(loss)
                result.logit_stds.append(logit_std)
                result.entropies.append(entropy)
                result.head_grad_norms.append(head_gn)
                del model

            results[var_key] = result

        print_results_table(results, "PART 2 RESULTS (all tau=1.0)")

        sm = results["scale_matched"].mean_loss
        pd = results["projected_dot_tau_fixed"].mean_loss
        ad = results["anchor_dist_tau_fixed"].mean_loss

        print(f"\n  With tau fixed at 1.0:")
        print(f"    ScaleMatched loss:    {sm:.4f}")
        print(f"    ProjDot loss:         {pd:.4f}")
        print(f"    AnchorDist loss:      {ad:.4f}")
        print(f"    Gap (SM - PD):        {sm - pd:>+.4f}")

        if sm - pd > 0.01:
            print(f"    -> ProjDot still wins with fixed tau. NOT a tau-learning artifact.")
        elif abs(sm - pd) <= 0.01:
            print(f"    -> Gap closed. Tau learning WAS the differentiator.")
        else:
            print(f"    -> ScaleMatched outperforms ProjDot with fixed tau.")

        for key, r in results.items():
            assert math.isfinite(r.mean_loss), f"{key} loss not finite"

    def test_part3_nonlinear_head_control(self, vocab, device):
        """
        Part 3: Nonlinear Head Control.

        MLP head with same architecture as psi MLP.
        If MLP head ≈ ProjectedDot -> gain is from nonlinear bottleneck.
        If ProjectedDot still better -> conditioning difference remains.
        """
        V = vocab.vocab_size
        results: Dict[str, IsolationResult] = {}

        print_separator("PART 3: NONLINEAR HEAD CONTROL")

        # Compute scale factor
        baseline_cal = make_model("baseline", V, device)
        projdot_cal = make_model("projected_dot", V, device)
        s, _, _ = compute_scale_factor(
            baseline_cal, projdot_cal, V, device, SEQ_LEN,
        )
        del baseline_cal, projdot_cal

        variants = [
            ("baseline", "Baseline (linear)"),
            ("scale_matched", "ScaleMatched"),
            ("mlp_head", "MLP Head (bottleneck)"),
            ("mlp_head_scaled", "MLP+AnchorProj (param-matched)"),
            ("projected_dot", "ProjectedDot"),
            ("anchor_dist", "AnchorDist"),
        ]

        for var_key, var_name in variants:
            result = IsolationResult(variant=var_name, param_count=0)

            for seed in SEEDS:
                model = make_model(var_key, V, device, scale_factor=s)
                if result.param_count == 0:
                    result.param_count = sum(p.numel() for p in model.parameters())

                loss, logit_std, entropy, head_gn, tau = train_and_measure(
                    model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=seed,
                )
                result.final_losses.append(loss)
                result.logit_stds.append(logit_std)
                result.entropies.append(entropy)
                result.head_grad_norms.append(head_gn)
                del model

            results[var_key] = result

        print_results_table(results, "PART 3 RESULTS")

        # Part 4: Parameter count parity check
        print_separator("PART 4: PARAMETER COUNT PARITY")
        pd_params = results["projected_dot"].param_count
        for key, r in results.items():
            pct_diff = abs(r.param_count - pd_params) / max(pd_params, 1) * 100
            status = "OK" if pct_diff <= 2.0 else f"MISMATCH ({pct_diff:.1f}%)"
            print(f"  {r.variant:<28} {r.param_count:>8d}  vs ProjDot {pd_params:>8d}  "
                  f"diff={pct_diff:.1f}%  [{status}]")

        # Analysis
        bl = results["baseline"].mean_loss
        sm = results["scale_matched"].mean_loss
        mlp = results["mlp_head"].mean_loss
        mlp_s = results["mlp_head_scaled"].mean_loss
        pd = results["projected_dot"].mean_loss
        ad = results["anchor_dist"].mean_loss

        print(f"\n  Nonlinear head analysis:")
        print(f"    Baseline:                {bl:.4f}")
        print(f"    ScaleMatched:            {sm:.4f}")
        print(f"    MLP Head:                {mlp:.4f}")
        print(f"    MLP+AnchorProj:          {mlp_s:.4f}")
        print(f"    ProjectedDot:            {pd:.4f}")
        print(f"    AnchorDist:              {ad:.4f}")
        print(f"    Gap MLP - ProjDot:       {mlp - pd:>+.4f}")
        print(f"    Gap MLP+Anch - ProjDot:  {mlp_s - pd:>+.4f}")

        for key, r in results.items():
            assert math.isfinite(r.mean_loss), f"{key} loss not finite"

    def test_part6_verdict(self, vocab, device):
        """
        Part 6: Verdict.

        Runs the full suite and applies the decision tree:

        IF scale-matched baseline ≈ ProjectedDot
          -> Improvement = calibration artifact.
        ELSE IF MLP head ≈ ProjectedDot
          -> Improvement = nonlinear bottleneck effect.
        ELSE IF ProjectedDot > all baselines
          -> Improvement = conditioning advantage beyond scale.
        ELSE
          -> Ambiguous.
        """
        V = vocab.vocab_size

        print_separator("FULL CONDITIONING ISOLATION — VERDICT RUN")

        # Step 1: Compute scale factor
        baseline_cal = make_model("baseline", V, device)
        projdot_cal = make_model("projected_dot", V, device)
        s, base_std, pd_std = compute_scale_factor(
            baseline_cal, projdot_cal, V, device, SEQ_LEN,
        )
        del baseline_cal, projdot_cal

        print(f"  Scale factor s = {s:.6f}  (baseline_std={base_std:.4f}, pd_std={pd_std:.4f})")

        # Step 2: Train all variants across 3 seeds
        all_variants = [
            ("baseline", "Baseline (linear)"),
            ("scale_matched", "ScaleMatched (s frozen)"),
            ("projected_dot", "ProjectedDot (learnable tau)"),
            ("projected_dot_tau_fixed", "ProjDot (tau=1.0 fixed)"),
            ("anchor_dist", "AnchorDist (learnable tau)"),
            ("anchor_dist_tau_fixed", "AnchorDist (tau=1.0 fixed)"),
            ("mlp_head", "MLP Head (bottleneck)"),
            ("mlp_head_scaled", "MLP+AnchorProj"),
        ]

        results: Dict[str, IsolationResult] = {}

        for var_key, var_name in all_variants:
            result = IsolationResult(variant=var_name, param_count=0)
            print(f"  Training {var_name}...", end="", flush=True)

            for seed in SEEDS:
                model = make_model(var_key, V, device, scale_factor=s, fixed_tau=1.0)
                if result.param_count == 0:
                    result.param_count = sum(p.numel() for p in model.parameters())

                loss, logit_std, entropy, head_gn, tau = train_and_measure(
                    model, V, device, TRAIN_STEPS, LR, SEQ_LEN, seed=seed,
                )
                result.final_losses.append(loss)
                result.logit_stds.append(logit_std)
                result.entropies.append(entropy)
                result.head_grad_norms.append(head_gn)
                del model

            results[var_key] = result
            print(f" loss={result.mean_loss:.4f} ±{result.loss_std:.4f}")

        # Part 5: Full metrics table
        print_results_table(results, "PART 5: COMPLETE METRICS TABLE")

        # Part 4: Parameter parity
        print_separator("PART 4: PARAMETER COUNT PARITY")
        pd_params = results["projected_dot"].param_count
        for key, r in results.items():
            pct_diff = abs(r.param_count - pd_params) / max(pd_params, 1) * 100
            status = "OK" if pct_diff <= 2.0 else f"DIFF {pct_diff:.1f}%"
            print(f"  {r.variant:<28} {r.param_count:>8d}  [{status}]")

        # Part 6: Verdict
        print_separator("PART 6: VERDICT")

        bl = results["baseline"].mean_loss
        sm = results["scale_matched"].mean_loss
        pd = results["projected_dot"].mean_loss
        pd_tf = results["projected_dot_tau_fixed"].mean_loss
        ad = results["anchor_dist"].mean_loss
        ad_tf = results["anchor_dist_tau_fixed"].mean_loss
        mlp = results["mlp_head"].mean_loss
        mlp_s = results["mlp_head_scaled"].mean_loss

        THRESHOLD = 0.02  # Within this = "approximately equal"

        print(f"\n  Decision inputs:")
        print(f"    Baseline:             {bl:.4f}")
        print(f"    ScaleMatched:         {sm:.4f}")
        print(f"    ProjDot:              {pd:.4f}")
        print(f"    ProjDot (tau=1):      {pd_tf:.4f}")
        print(f"    AnchorDist:           {ad:.4f}")
        print(f"    AnchorDist (tau=1):   {ad_tf:.4f}")
        print(f"    MLP Head:             {mlp:.4f}")
        print(f"    MLP+AnchorProj:       {mlp_s:.4f}")

        gap_scale = sm - pd
        gap_mlp = mlp_s - pd
        gap_full = sm - pd

        print(f"\n  Decision tree:")
        print(f"    Gap (ScaleMatched - ProjDot):     {gap_scale:>+.4f}")
        print(f"    Gap (MLP+Anchor  - ProjDot):      {gap_mlp:>+.4f}")

        if abs(gap_scale) <= THRESHOLD:
            verdict = "CALIBRATION ARTIFACT"
            print(f"\n  VERDICT: {verdict}")
            print(f"  Scale-matched baseline ≈ ProjectedDot (gap={gap_scale:+.4f} ≤ {THRESHOLD})")
            print(f"  Spanda's improvement is a logit scaling / entropy shaping artifact.")
        elif abs(gap_mlp) <= THRESHOLD:
            verdict = "NONLINEAR BOTTLENECK EFFECT"
            print(f"\n  VERDICT: {verdict}")
            print(f"  MLP+AnchorProj ≈ ProjectedDot (gap={gap_mlp:+.4f} ≤ {THRESHOLD})")
            print(f"  Spanda's improvement is from the nonlinear MLP reparameterization,")
            print(f"  not from distance geometry or psi-specific conditioning.")
        elif pd < sm and pd < mlp_s:
            verdict = "CONDITIONING ADVANTAGE BEYOND SCALE"
            print(f"\n  VERDICT: {verdict}")
            print(f"  ProjectedDot outperforms all baselines including MLP+AnchorProj.")
            print(f"  Spanda provides true representational conditioning beyond scaling")
            print(f"  and nonlinear reparameterization.")

            # Sub-diagnosis: is it tau or structure?
            if abs(pd - pd_tf) > THRESHOLD:
                print(f"  NOTE: Learnable tau contributes ({pd:.4f} vs {pd_tf:.4f} fixed).")
            else:
                print(f"  NOTE: Advantage holds even with fixed tau — structural, not tau-driven.")
        else:
            verdict = "AMBIGUOUS"
            print(f"\n  VERDICT: {verdict}")
            print(f"  Results do not clearly distinguish between hypotheses.")
            print(f"  Consider increasing TRAIN_STEPS or using structured data.")

        print(f"\n  {'=' * 90}")

        # Assertions
        for key, r in results.items():
            assert math.isfinite(r.mean_loss), f"{key} loss not finite: {r.mean_loss}"
            assert r.perplexity > 0, f"{key} PPL not positive"

        # Stability check
        for key, r in results.items():
            assert r.loss_std < 1.0, (
                f"{key} unstable across seeds: std={r.loss_std:.4f}"
            )


# =========================================================================
# Standalone entry point
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
