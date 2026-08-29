"""Six collector arms. Each maps a batch of streams to per-cutoff summary tokens.

Interface: forward(x, dt, tau) -> tokens [B, C, n_tok, feat_dim] where C indexes
CUTOFFS, plus .state_floats(t_c) reporting carried per-stream state size.

Arm E re-implements the equations of symbolu/lightweight_phase/
reference_equations.md (Sections 2-5) conceptually at collector scale: learned
content-derived phase and amplitude projections, bounded phase pi*sin(.),
complex decayed state, query-side readout Re(q . S) with a detached normalizer.
Nothing is imported from that frozen package.
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn

from .signals import CLOCK_PERIODS, CUTOFFS, T

STAT_GAMMAS = (0.9, 0.98, 0.995)
DENOM_EPS = 0.1


def _gather_cut(seq: torch.Tensor, offset: int = 1) -> torch.Tensor:
    """seq [B, T, ...] -> [B, C, ...] at the last observable index per cutoff."""
    idx = torch.tensor([tc - offset for tc in CUTOFFS], device=seq.device)
    return seq.index_select(1, idx)


class CurrentValue(nn.Module):
    """Arm A: current value only."""
    n_tok, feat_dim = 1, 3

    def forward(self, x, dt, tau):
        cur = _gather_cut(torch.stack([x, dt, torch.ones_like(x)], dim=-1))
        return cur.unsqueeze(2)

    def state_floats(self, tc: int) -> int:
        return 2


class DecayedStats(nn.Module):
    """Arm B: decayed mean / variance / trend at three timescales (debiased)."""
    n_tok, feat_dim = len(STAT_GAMMAS), 6

    def _stats(self, x, dt):
        B, N = x.shape
        toks = []
        diff = torch.zeros_like(x)
        diff[:, 1:] = (x[:, 1:] - x[:, :-1]) / dt[:, 1:].clamp(min=1e-3)
        for gi, g in enumerate(STAT_GAMMAS):
            m = torch.zeros(B, device=x.device)   # decayed sum of x
            s2 = torch.zeros(B, device=x.device)  # decayed sum of x^2
            tr = torch.zeros(B, device=x.device)  # decayed sum of slope
            w = torch.zeros(B, device=x.device)   # decayed count
            per_t = []
            for t in range(N):
                m = g * m + x[:, t]
                s2 = g * s2 + x[:, t] ** 2
                tr = g * tr + diff[:, t]
                w = g * w + 1.0
                mean = m / w
                var = (s2 / w - mean ** 2).clamp(min=0)
                per_t.append(torch.stack(
                    [mean, var, tr / w, x[:, t], w * (1 - g), torch.full_like(mean, gi - 1.0)],
                    dim=-1))
            toks.append(_gather_cut(torch.stack(per_t, dim=1)))
        return torch.stack(toks, dim=2)  # [B, C, 3, 6]

    def forward(self, x, dt, tau):
        return self._stats(x, dt)

    def state_floats(self, tc: int) -> int:
        return len(STAT_GAMMAS) * 4 + 2  # (m, s2, tr, w) per timescale + current x, dt


class HarmonicStats(DecayedStats):
    """Arm C: stats + fixed-clock decayed complex harmonic accumulators."""
    n_tok, feat_dim = len(STAT_GAMMAS) + len(CLOCK_PERIODS), 6

    def forward(self, x, dt, tau):
        stat_toks = self._stats(x, dt)
        B, N = x.shape
        harm = []
        for P in CLOCK_PERIODS:
            g = math.exp(-1.0 / (4.0 * P))  # horizon ~ 4 periods
            ang = 2 * math.pi * tau / P
            sr = torch.zeros(B, device=x.device)
            si = torch.zeros(B, device=x.device)
            a = torch.zeros(B, device=x.device)
            per_t = []
            for t in range(N):
                sr = g * sr + x[:, t] * torch.cos(ang[:, t])
                si = g * si - x[:, t] * torch.sin(ang[:, t])
                a = g * a + 1.0
                mag = torch.sqrt(sr ** 2 + si ** 2) / a.clamp(min=1e-6)
                th = torch.atan2(si, sr)
                per_t.append(torch.stack(
                    [mag, torch.cos(th), torch.sin(th),
                     torch.cos(ang[:, t]), torch.sin(ang[:, t]),
                     torch.full_like(mag, math.log(P) / 5.0)], dim=-1))
            harm.append(_gather_cut(torch.stack(per_t, dim=1)))
        harm = torch.stack(harm, dim=2)  # [B, C, K, 6]
        return torch.cat([stat_toks, harm], dim=2)

    def state_floats(self, tc: int) -> int:
        return super().state_floats(tc) + len(CLOCK_PERIODS) * 3  # (sr, si, a) per period


class _LearnedBase(nn.Module):
    heads, dh = 8, 8
    n_tok = 8
    feat_dim = 8

    def __init__(self):
        super().__init__()
        d = self.heads * self.dh
        self.embed = nn.Linear(2, 16)
        self.gamma_logit = nn.Parameter(torch.full((d,), 3.0))  # sigmoid ~ 0.95

    def _u(self, x, dt):
        return torch.tanh(self.embed(torch.stack([x, dt], dim=-1)))  # [B, T, 16]


class RealRecurrence(_LearnedBase):
    """Arm D: gated real diagonal learned recurrence h <- g*h + a_k(u) * v(u)."""

    def __init__(self):
        super().__init__()
        d = self.heads * self.dh
        self.w_ak = nn.Linear(16, d)
        self.w_v = nn.Linear(16, d)

    def forward(self, x, dt, tau):
        u = self._u(x, dt)
        a_k = torch.sigmoid(self.w_ak(u))
        v = self.w_v(u)
        g = torch.sigmoid(self.gamma_logit)
        B, N, d = v.shape
        h = torch.zeros(B, d, device=x.device)
        outs = []
        cut_last = {tc - 1 for tc in CUTOFFS}
        for t in range(N):
            h = g * h + a_k[:, t] * v[:, t]
            if t in cut_last:
                outs.append(h)
        out = torch.stack(outs, dim=1)  # [B, C, d]
        return out.view(B, len(CUTOFFS), self.n_tok, self.feat_dim)

    def state_floats(self, tc: int) -> int:
        return self.heads * self.dh


class PhaseRecurrence(_LearnedBase):
    """Arm E: learned content-derived Phase collector (reference_equations 2-5)."""

    def __init__(self):
        super().__init__()
        d = self.heads * self.dh
        self.w_phik = nn.Linear(16, d)
        self.w_ak = nn.Linear(16, d)
        self.w_v = nn.Linear(16, d)
        self.w_phiq = nn.Linear(16, d)
        self.w_aq = nn.Linear(16, d)

    def forward(self, x, dt, tau):
        u = self._u(x, dt)
        phi_k = math.pi * torch.sin(self.w_phik(u))          # bounded phase
        a_k = torch.sigmoid(self.w_ak(u))
        v = self.w_v(u)
        g = torch.sigmoid(self.gamma_logit)
        B, N, d = v.shape
        sr = torch.zeros(B, d, device=x.device)
        si = torch.zeros(B, d, device=x.device)
        amp = torch.zeros(B, d, device=x.device)             # decayed sum of a_k
        outs = []
        cut_last = {tc - 1 for tc in CUTOFFS}
        for t in range(N):
            kv_r = a_k[:, t] * torch.cos(phi_k[:, t]) * v[:, t]   # Re(k) * v
            kv_i = -a_k[:, t] * torch.sin(phi_k[:, t]) * v[:, t]  # Im(k) * v, e^{-i phi}
            sr = g * sr + kv_r
            si = g * si + kv_i
            amp = g * amp + a_k[:, t]
            if t in cut_last:
                phi_q = math.pi * torch.sin(self.w_phiq(u[:, t]))
                a_q = torch.sigmoid(self.w_aq(u[:, t]))
                # Re(q . S), q = a_q e^{+i phi_q}
                n_t = a_q * (torch.cos(phi_q) * sr - torch.sin(phi_q) * si)
                z = (a_q * amp).clamp(min=DENOM_EPS).detach()
                outs.append(n_t / z)
        out = torch.stack(outs, dim=1)
        return out.view(B, len(CUTOFFS), self.n_tok, self.feat_dim)

    def state_floats(self, tc: int) -> int:
        return self.heads * self.dh * 3  # (sr, si, amp)


class RawHistory(nn.Module):
    """Arm F: raw tokens for quadratic attention (upper reference)."""
    n_tok = max(CUTOFFS)
    feat_dim = 3

    def forward(self, x, dt, tau):
        B, N = x.shape
        feats = torch.stack([x, dt, tau / T], dim=-1)  # [B, T, 3]
        toks = feats[:, :self.n_tok].unsqueeze(1).expand(B, len(CUTOFFS), self.n_tok, 3)
        mask = torch.zeros(B, len(CUTOFFS), self.n_tok, dtype=torch.bool, device=x.device)
        for c, tc in enumerate(CUTOFFS):
            mask[:, c, tc:] = True  # True = padding (not observable at this cutoff)
        return toks, mask

    def state_floats(self, tc: int) -> int:
        return tc * 2  # raw (x, dt) history carried to the reader


ARMS = {
    "current": CurrentValue,
    "stats": DecayedStats,
    "harmonic": HarmonicStats,
    "real_rec": RealRecurrence,
    "phase": PhaseRecurrence,
    "raw_quad": RawHistory,
}
