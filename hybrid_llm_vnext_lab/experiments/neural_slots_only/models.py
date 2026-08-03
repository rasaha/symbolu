"""Phase-free neural arms for the slots-only (S) attribution experiment.

Imports NO Phase anywhere (enforced by tests/boundaries). Reuses:
  * the incubated, Phase-free BindingSlots (byte-identical to experiments/phase_lc/models.py's
    slot class) for the slot path;
  * a windowed causal softmax attention identical to the historical SoftmaxAttn (Phase-free).

Arms:
  A  : sliding window only                (matched to target_params -> serves as A+)
  S  : sliding window + bounded slots      (the decisive Phase-independent slot-learning arm)
  A+ : sliding window only, matched to S's exact parameter count (near-identical to A under the
       build_matched protocol; reported separately for the added-parameter control)

Skeleton is identical to the historical LM (token+pos embedding, pre-norm blocks, GELU FFN,
tied head) so any S-A gap is attributable to the slot structure, not the surrounding machinery.
Total parameters are matched across arms by auto-tuning the FFN width (build_matched).
"""
from __future__ import annotations

import pathlib
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

# lab root on path -> import the incubated Phase-free slot class
_LAB_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))
from src.binding_slots.legacy_phase_lc_slots import BindingSlots  # noqa: E402  (Phase-free)

WINDOW = 64


class WindowSoftmaxAttn(nn.Module):
    """Windowed causal softmax attention — identical to the historical SoftmaxAttn (Phase-free).

    Uses a banded [N,N] score masked to width `window` (O(N*w) effective); this is the local
    baseline path, excluded from the no-global-N x N rule exactly as in the historical harness.
    """
    def __init__(self, d, h, window=WINDOW):
        super().__init__()
        self.d, self.h, self.dh = d, h, d // h
        self.window = window
        self.Wq = nn.Linear(d, d, bias=False)
        self.Wk = nn.Linear(d, d, bias=False)
        self.Wv = nn.Linear(d, d, bias=False)
        self.Wo = nn.Linear(d, d, bias=False)
        self.scale = self.dh ** -0.5

    def forward(self, x):
        B, N, D = x.shape
        q = self.Wq(x).view(B, N, self.h, self.dh).transpose(1, 2)
        k = self.Wk(x).view(B, N, self.h, self.dh).transpose(1, 2)
        v = self.Wv(x).view(B, N, self.h, self.dh).transpose(1, 2)
        s = (q @ k.transpose(-1, -2)) * self.scale
        i = torch.arange(N, device=x.device)
        causal = i[None, :] > i[:, None]
        too_far = (i[:, None] - i[None, :]) >= self.window
        s = s.masked_fill((causal | too_far)[None, None], float('-inf'))
        o = (s.softmax(-1) @ v).transpose(1, 2).reshape(B, N, D)
        return self.Wo(o)


class SlotsMixer(nn.Module):
    """window (always) + optional bounded slots, protected additive fusion. NO Phase."""
    def __init__(self, d, h, window, use_slots, num_slots=32):
        super().__init__()
        self.local = WindowSoftmaxAttn(d, h, window=window)
        self.slots = BindingSlots(d, num_slots=num_slots) if use_slots else None

    def forward(self, x):
        o = self.local(x)
        if self.slots is not None:
            o = o + self.slots(x)
        return o


class Block(nn.Module):
    def __init__(self, d, h, ff, mixer):
        super().__init__()
        self.n1 = nn.LayerNorm(d)
        self.mix = mixer
        self.n2 = nn.LayerNorm(d)
        self.ff = nn.Sequential(nn.Linear(d, ff), nn.GELU(), nn.Linear(ff, d))

    def forward(self, x):
        x = x + self.mix(self.n1(x))
        x = x + self.ff(self.n2(x))
        return x


def make_mixer(arm, d, h, window, num_slots=32):
    # 'A' and 'A+' are window-only; 'S' adds bounded slots. No Phase in any arm.
    use_slots = (arm == 'S')
    return SlotsMixer(d, h, window, use_slots=use_slots, num_slots=num_slots)


class LM(nn.Module):
    def __init__(self, vocab, d=128, h=4, layers=4, ff=384, arm='A', max_len=1200,
                 window=WINDOW, num_slots=32):
        super().__init__()
        self.arm = arm
        self.tok = nn.Embedding(vocab, d)
        self.pos = nn.Embedding(max_len, d)
        self.blocks = nn.ModuleList([Block(d, h, ff, make_mixer(arm, d, h, window, num_slots))
                                     for _ in range(layers)])
        self.norm = nn.LayerNorm(d)
        self.head = nn.Linear(d, vocab, bias=False)
        self.head.weight = self.tok.weight
        self.apply(self._init)

    def _init(self, m):
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, 0, 0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, 0, 0.02)

    def forward(self, ids):
        B, N = ids.shape
        p = torch.arange(N, device=ids.device)[None]
        x = self.tok(ids) + self.pos(p)
        for b in self.blocks:
            x = b(x)
        return self.head(self.norm(x))

    def slot_mixers(self):
        return [b.mix.slots for b in self.blocks
                if isinstance(b.mix, SlotsMixer) and b.mix.slots is not None]


def count_params(m):
    return sum(p.numel() for p in m.parameters())


def build_matched(arm, vocab, target_params, d=128, h=4, layers=4, max_len=1200,
                  window=WINDOW, num_slots=32):
    """Auto-tune ff so total params match target (identical protocol to the historical harness)."""
    lo, hi = 32, 4096
    best = None
    for _ in range(20):
        ff = (lo + hi) // 2
        m = LM(vocab, d=d, h=h, layers=layers, ff=ff, arm=arm, max_len=max_len,
               window=window, num_slots=num_slots)
        n = count_params(m)
        if best is None or abs(n - target_params) < abs(best[1] - target_params):
            best = (ff, n)
        if n < target_params:
            lo = ff + 1
        else:
            hi = ff - 1
        if lo > hi:
            break
    ff = best[0]
    return LM(vocab, d=d, h=h, layers=layers, ff=ff, arm=arm, max_len=max_len,
              window=window, num_slots=num_slots), best[1], ff
