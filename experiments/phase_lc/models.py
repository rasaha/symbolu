"""
Matched-architecture LM arms for the Phase-attention long-context falsification study.

All arms share an identical Transformer skeleton (token+pos embedding, pre-norm blocks,
GELU FFN, tied LM head). They differ ONLY in the token-mixing operator inside the
attention sublayer, so any performance gap is attributable to the mixer, not the
surrounding machinery. Total parameter count is matched across arms by auto-tuning the
FFN width (see build_matched()).

Arms
----
Q  : full causal softmax attention (quadratic baseline)
L  : sliding-window causal softmax attention (local baseline)
R  : gated real-valued diagonal linear recurrence (conventional linear/RWKV/Mamba-diagonal
     baseline) -- structurally identical to Phase but with a REAL learned decay gate and
     no phase angle. This is the decisive control: it isolates what the complex phase buys.
P  : Phase attention -- complex diagonal linear recurrence, faithful to the repo's
     PhaseAttentionLayer / BindingCachePhaseState core:
         q = a_q * exp(+i phi_q),  k = a_k * exp(-i phi_k)
         state_t = sum_{s<=t} (k_s * v_s)        [elementwise per channel, O(n)]
         out_t   = Re(q_t * state_t)
     with bounded phase phi = pi*sin(.) and per-head learned decay (matches repo).
PL : Local+Phase -- the P mixer PLUS a sliding-window softmax path (disclosed hybrid;
     the strongest honest "Phase" arm per the investigation's arm definitions).
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class SoftmaxAttn(nn.Module):
    def __init__(self, d, h, window=None):
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
        mask = causal
        if self.window is not None:
            too_far = (i[:, None] - i[None, :]) >= self.window
            mask = causal | too_far
        s = s.masked_fill(mask[None, None], float('-inf'))
        a = s.softmax(-1)
        o = (a @ v).transpose(1, 2).reshape(B, N, D)
        return self.Wo(o)


class GatedLinearRec(nn.Module):
    """R arm: real gated diagonal linear recurrence (no phase).

    state_t = decay * state_{t-1} + g_k_t * v_t ; out_t = q_t * state_t
    Implemented with a stable log-space cumulative scan (parallel prefix via cumsum of
    log-decays). Per-head learned decay in [0.90, 0.9995], matching the repo's timescale
    initialisation range.
    """
    def __init__(self, d, h):
        super().__init__()
        self.d, self.h, self.dh = d, h, d // h
        self.Wq = nn.Linear(d, d, bias=False)
        self.Wk = nn.Linear(d, d, bias=False)   # gate on keys (amplitude)
        self.Wv = nn.Linear(d, d, bias=False)
        self.Wo = nn.Linear(d, d, bias=False)
        log_ts = torch.linspace(math.log(2.0), math.log(512.0), h)
        gamma = torch.clamp(1.0 - 1.0 / torch.exp(log_ts), 0.90, 0.9995)
        self.decay_logit = nn.Parameter(torch.log(gamma / (1 - gamma)))

    def forward(self, x):
        B, N, D = x.shape
        q = self.Wq(x).view(B, N, self.h, self.dh)
        gk = torch.sigmoid(self.Wk(x)).view(B, N, self.h, self.dh)
        v = self.Wv(x).view(B, N, self.h, self.dh)
        gamma = 0.90 + 0.0995 * torch.sigmoid(self.decay_logit)   # [h]
        logg = torch.log(gamma)[None, None, :, None]              # [1,1,h,1]
        t = torch.arange(N, device=x.device).float()[None, :, None, None]
        # state_t = sum_{s<=t} gamma^{t-s} (gk_s v_s) = gamma^t * cumsum(gamma^{-s} gk_s v_s)
        # use log-space normalisation for stability
        kv = gk * v
        # scale-safe: factor gamma^t out via prefix in float32
        w = torch.exp(-t * logg)            # gamma^{-s}
        pref = torch.cumsum(w * kv, dim=1)
        state = torch.exp(t * logg) * pref
        o = (q * state).reshape(B, N, D)
        return self.Wo(o)


class PhaseAttn(nn.Module):
    """P arm: complex diagonal linear recurrence (faithful to repo Phase core)."""
    def __init__(self, d, h, learned_decay=True):
        super().__init__()
        self.d, self.h, self.dh = d, h, d // h
        self.Wq_amp = nn.Linear(d, d, bias=False)
        self.Wq_phase = nn.Linear(d, d, bias=False)
        self.Wk_amp = nn.Linear(d, d, bias=False)
        self.Wk_phase = nn.Linear(d, d, bias=False)
        self.Wv = nn.Linear(d, d, bias=False)
        self.Wo = nn.Linear(d, d, bias=False)
        self.learned_decay = learned_decay
        if learned_decay:
            log_ts = torch.linspace(math.log(2.0), math.log(512.0), h)
            gamma = torch.clamp(1.0 - 1.0 / torch.exp(log_ts), 0.90, 0.9995)
            self.decay_logit = nn.Parameter(torch.log(gamma / (1 - gamma)))
        # diagnostics (populated in forward under no_grad)
        self.diag = {}
        # ablation hooks
        self.ablate = None   # None | 'zero' | 'shuffle_pos' | 'no_phase'

    def forward(self, x):
        B, N, D = x.shape
        a_q = torch.sigmoid(self.Wq_amp(x)).view(B, N, self.h, self.dh)
        phi_q = math.pi * torch.sin(self.Wq_phase(x)).view(B, N, self.h, self.dh)
        a_k = torch.sigmoid(self.Wk_amp(x)).view(B, N, self.h, self.dh)
        phi_k = math.pi * torch.sin(self.Wk_phase(x)).view(B, N, self.h, self.dh)
        v = self.Wv(x).view(B, N, self.h, self.dh)
        if self.ablate == 'no_phase':
            phi_q = torch.zeros_like(phi_q); phi_k = torch.zeros_like(phi_k)
        q = torch.polar(a_q.float(), phi_q.float())
        k = torch.polar(a_k.float(), -phi_k.float())
        vv = torch.complex(v.float(), torch.zeros_like(v.float()))
        kv = k * vv
        if self.learned_decay:
            gamma = (0.90 + 0.0995 * torch.sigmoid(self.decay_logit)).float()  # [h]
            logg = torch.log(gamma)[None, None, :, None]
            t = torch.arange(N, device=x.device).float()[None, :, None, None]
            w = torch.exp(-t * logg)
            pref = torch.cumsum(w * kv, dim=1)
            state = torch.exp(t * logg) * pref
        else:
            state = torch.cumsum(kv, dim=1)
        if self.ablate == 'zero':
            state = torch.zeros_like(state)
        elif self.ablate == 'shuffle_pos':
            perm = torch.randperm(N, device=x.device)
            state = state[:, perm]
        out = (q * state).real.to(x.dtype)
        with torch.no_grad():
            self.diag = {
                'state_norm_mean': state.abs().mean().item(),
                'phase_angle_std': phi_k.std().item(),
                # head diversity: 1 - mean pairwise cosine of per-head mean phase vectors
                'amp_k_mean': a_k.mean().item(),
            }
        out = out.reshape(B, N, D)
        return self.Wo(out)


class PhaseLocal(nn.Module):
    """PL arm: Phase + sliding-window softmax (summed)."""
    def __init__(self, d, h, window=64):
        super().__init__()
        self.phase = PhaseAttn(d, h)
        self.local = SoftmaxAttn(d, h, window=window)

    def forward(self, x):
        return self.phase(x) + self.local(x)


class BindingSlots(nn.Module):
    """Bounded, causal, content-addressed key-value slot memory. O(N*M*d) — NO N x N.

    M fixed slots with learnable address keys. Each token is content-routed to slots via
    softmax over the M keys, gated by a novelty gate, and its value is accumulated into the
    causal running slot state (parallel prefix-sum for training; the DEPLOYED state is M*d,
    the [N,M,d] tensor is a training-time scan artifact, exactly like Phase's [N,H,Dh]).
    Reads route the query through the SAME address space and gather slot content, so an
    entity written to slot m is retrieved from slot m. No full sequence score matrix exists.

        addr_t   = softmax( (W_wk x_t) . SlotKeys^T )          # [.,M]  content routing
        w_t      = sigmoid(gate(x_t)) * addr_t                 # [.,M]  gated write mass
        slot_t   = cumsum_{s<=t}(w_s v_s) / cumsum_{s<=t}(w_s) # [.,M,d] bounded state
        radd_t   = softmax( (W_rq x_t) . SlotKeys^T )          # [.,M]  read routing
        out_t    = W_o ( sum_m radd_{t,m} slot_{t,m} )
    """
    def __init__(self, d, num_slots=32, key_dim=None, top_k=None):
        super().__init__()
        self.d = d
        self.M = num_slots
        kd = key_dim or (d // 2)
        self.kd = kd
        self.top_k = top_k
        keys = torch.randn(num_slots, kd)
        if num_slots <= kd:
            nn.init.orthogonal_(keys)
        self.slot_keys = nn.Parameter(F.normalize(keys, dim=-1))
        self.W_wk = nn.Linear(d, kd, bias=False)
        self.W_rq = nn.Linear(d, kd, bias=False)
        self.W_wv = nn.Linear(d, d, bias=False)
        self.gate = nn.Linear(d, 1)
        self.W_o = nn.Linear(d, d, bias=False)
        self.norm = nn.LayerNorm(d)
        nn.init.constant_(self.gate.bias, 1.0)
        self.scale = kd ** -0.5
        self.diag = {}
        self.ablate = None  # None | 'zero' | 'shuffle_val' | 'rand_keys'

    def _route(self, proj_x):
        s = (proj_x @ self.slot_keys.t()) * self.scale   # [B,N,M]
        if self.top_k is not None and self.top_k < self.M:
            v, i = s.topk(self.top_k, dim=-1)
            s = torch.full_like(s, float('-inf')).scatter(-1, i, v)
        return s.softmax(-1)

    def forward(self, x):
        B, N, D = x.shape
        xn = self.norm(x)
        waddr = self._route(self.W_wk(xn))               # [B,N,M]
        g = torch.sigmoid(self.gate(xn))                 # [B,N,1]
        v = self.W_wv(xn)                                # [B,N,D]
        w = (g * waddr)                                  # [B,N,M]
        weighted = w.unsqueeze(-1) * v.unsqueeze(2)      # [B,N,M,D]
        num = torch.cumsum(weighted, dim=1)              # [B,N,M,D] causal
        den = torch.cumsum(w, dim=1).unsqueeze(-1) + 1e-6
        slots = num / den                                # [B,N,M,D] slot content @ t
        if self.ablate == 'zero':
            slots = torch.zeros_like(slots)
        elif self.ablate == 'shuffle_val':
            slots = slots[:, :, torch.randperm(self.M, device=x.device)]
        raddr = self._route(self.W_rq(xn))               # [B,N,M]
        if self.ablate == 'rand_keys':
            raddr = torch.rand_like(raddr).softmax(-1)
        read = torch.einsum('bnm,bnmd->bnd', raddr, slots)   # [B,N,D]
        with torch.no_grad():
            util = waddr.mean(dim=(0, 1))                # [M] mean write mass per slot
            self.diag = {
                'slot_write_gate_mean': g.mean().item(),
                'slot_util_entropy': float(-(util * (util + 1e-9).log()).sum().item()),
                'slot_util_max': util.max().item(),
                'read_addr_max_mean': raddr.max(-1).values.mean().item(),
                'num_slots': self.M,
            }
        return self.W_o(read)


class ABCMixer(nn.Module):
    """Unified A/B/C token mixer: window (always) + optional Phase + optional bounded slots,
    protected additive fusion. A=window; B=window+phase; C=window+phase+slots."""
    def __init__(self, d, h, window, use_phase, use_slots, num_slots=32):
        super().__init__()
        self.local = SoftmaxAttn(d, h, window=window)
        self.phase = PhaseAttn(d, h) if use_phase else None
        self.slots = BindingSlots(d, num_slots=num_slots) if use_slots else None

    def forward(self, x):
        o = self.local(x)
        if self.phase is not None:
            o = o + self.phase(x)
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
    if arm == 'Q':
        return SoftmaxAttn(d, h)
    if arm == 'L':
        return SoftmaxAttn(d, h, window=window)
    if arm == 'R':
        return GatedLinearRec(d, h)
    if arm == 'P':
        return PhaseAttn(d, h)
    if arm == 'PL':
        return PhaseLocal(d, h, window=window)
    # A/B/C ladder (no quadratic attention anywhere)
    if arm == 'A':
        return ABCMixer(d, h, window, use_phase=False, use_slots=False)
    if arm == 'B':
        return ABCMixer(d, h, window, use_phase=True, use_slots=False)
    if arm == 'C':
        return ABCMixer(d, h, window, use_phase=True, use_slots=True, num_slots=num_slots)
    raise ValueError(arm)


class LM(nn.Module):
    def __init__(self, vocab, d=128, h=4, layers=4, ff=384, arm='Q', max_len=2048, window=64, num_slots=32):
        super().__init__()
        self.arm = arm
        self.tok = nn.Embedding(vocab, d)
        self.pos = nn.Embedding(max_len, d)
        self.blocks = nn.ModuleList([Block(d, h, ff, make_mixer(arm, d, h, window, num_slots)) for _ in range(layers)])
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

    def phase_mixers(self):
        out = []
        for b in self.blocks:
            if isinstance(b.mix, PhaseAttn):
                out.append(b.mix)
            elif isinstance(b.mix, PhaseLocal):
                out.append(b.mix.phase)
            elif isinstance(b.mix, ABCMixer) and b.mix.phase is not None:
                out.append(b.mix.phase)
        return out

    def slot_mixers(self):
        out = []
        for b in self.blocks:
            if isinstance(b.mix, ABCMixer) and b.mix.slots is not None:
                out.append(b.mix.slots)
        return out


def count_params(m):
    return sum(p.numel() for p in m.parameters())


def build_matched(arm, vocab, target_params, d=128, h=4, layers=4, max_len=2048, window=64, num_slots=32):
    """Auto-tune ff width so total (non-embedding-dominated) param count matches target."""
    lo, hi = 32, 4096
    best = None
    for _ in range(20):
        ff = (lo + hi) // 2
        m = LM(vocab, d=d, h=h, layers=layers, ff=ff, arm=arm, max_len=max_len, window=window, num_slots=num_slots)
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
    return LM(vocab, d=d, h=h, layers=layers, ff=ff, arm=arm, max_len=max_len, window=window, num_slots=num_slots), best[1]
