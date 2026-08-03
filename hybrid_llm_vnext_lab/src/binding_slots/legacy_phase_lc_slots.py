# Incubated from: experiments/phase_lc/models.py  (class BindingSlots, lines 200-273)
# Source commit: 8b4ec6e71666282384a4e23f78c724f8df4ba767
# Source blob: 76b5af69f12b23f6c94e66727b790028bc0fc26e
# Extraction status: SEMANTIC_EXTRACTION
#   - The BindingSlots class body below is BYTE-IDENTICAL to the source (lines 200-273).
#   - Only the surrounding file changed: the source models.py also defines Phase arms and
#     imports the real PhaseAttentionLayer; NONE of that Phase code is copied here. This file
#     contains the slot class in isolation with just its torch imports. This is the exact
#     implementation that produced the measured phase_lc A/B/C positive slot result
#     (results/abc.json): seed-0 needle@d96 0.467, slots-off 0.017, rand-keys 0.050,
#     phase-off unchanged 0.475.
# Packaging status: NOT_PACKAGED
# Runtime status: RESOURCE_BLOCKED in this environment (PyTorch not installed). The discrete
#   mechanics are reproduced and tested by ../binding_slots/slot_reference.py (stdlib).
#
# The built-in `ablate` hook ('zero' | 'shuffle_val' | 'rand_keys') is preserved verbatim —
# it is exactly how the harness performed the causal slots-off / randomized-address ablations.

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


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
