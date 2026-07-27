"""
teacher.py — the AutoGateModel (token embed + frozen-arch V2-S core + focus head) and the
SUPERVISED-TEACHER upper bound.

The model uses symbolu.phase_v2_experimental.SelectivePhaseV2 UNMODIFIED; the write gate is
computed from its own logit (core.W_w) with a chosen gate type and applied via gate_override,
so S_t = S_{t-1} + B_t(k_t⊙v_t) exactly (γ=1, single bank, no C_t). Focus identity is decoded
from the EXISTING Phase readout at the PROBE position (no new selective readout).
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.phase_v2_experimental.config import cfg_v2s
from symbolu.phase_v2_experimental.selective_phase import SelectivePhaseV2, _scan
from experiments.phase_v3_selective_ssm.train import sinusoidal
from .config import EMBED_DIM, NUM_HEADS, NUM_ENTITIES
from .student_gate import gate_from_logit, FocusConditionedGate
from .matcher_gate import MatcherGate


class AutoGateModel(nn.Module):
    def __init__(self, vocab_size, gate_type="sigmoid", embed_dim=EMBED_DIM,
                 num_heads=NUM_HEADS, num_entities=NUM_ENTITIES, topk_frac=0.2,
                 gate_mode="token"):
        super().__init__()
        self.embed_dim = embed_dim
        self.gate_type = gate_type
        self.topk_frac = topk_frac
        self.gate_mode = gate_mode              # token | conditioned | cosine | bilinear
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.core = SelectivePhaseV2(cfg_v2s(embed_dim, num_heads))   # γ=1, per-head gate
        if gate_mode == "conditioned":
            self.cond_gate = FocusConditionedGate(embed_dim, num_heads)
        elif gate_mode in ("cosine", "bilinear"):
            self.matcher = MatcherGate(embed_dim, num_heads, kind=gate_mode)
        self.focus_head = nn.Linear(embed_dim, num_entities)
        nn.init.normal_(self.token_embed.weight, std=0.02)

    def embed(self, ids):
        return self.token_embed(ids) + sinusoidal(ids.shape[1], self.embed_dim, ids.device).unsqueeze(0)

    def gate_logit(self, ids, summary_override=None):
        h = self.core.norm(self.embed(ids))
        if self.gate_mode == "conditioned":
            return self.cond_gate.logit(h, summary_override=summary_override)
        if self.gate_mode in ("cosine", "bilinear"):
            return self.matcher.logit(h, summary_override=summary_override)
        return self.core.W_w(h)                                      # [B,N,H] token-only

    def match_score(self, ids, summary_override=None):
        """Relevance score s_t [B,N] for matcher gates (for ranking loss + AUROC)."""
        h = self.core.norm(self.embed(ids))
        return self.matcher.match_score(h, summary_override=summary_override)

    def matcher_projections(self, ids):
        h = self.core.norm(self.embed(ids))
        return self.matcher._project(h) + (self.matcher.event_logit(h),)   # z_f, z_h, e_logit

    def summary_rep(self, ids):
        """The causal focus summary f_t (= normalized rep at the cue position). For controls."""
        return self.core.norm(self.embed(ids))[:, 0]                 # [B,D]

    def gate(self, ids, override_logit=None):
        logit = self.gate_logit(ids) if override_logit is None else override_logit
        return gate_from_logit(logit, self.gate_type, self.topk_frac)

    def features(self, ids, gate=None):
        """Recurrent state + existing Phase readout at every position (no new selective readout)."""
        x = self.embed(ids)
        core = self.core
        xn = core.norm(x)
        phi_q, a_q, phi_k, a_k, v = core._project(xn)
        if gate is None:
            gate = self.gate(ids)
        w = gate.unsqueeze(-1)
        k_phasor = torch.polar(a_k, -phi_k)
        v_complex = torch.complex(v, torch.zeros_like(v))
        S = _scan(k_phasor * v_complex * w, core.bank_gamma(0, x.device), None)
        A = _scan(torch.complex(a_k, torch.zeros_like(a_k)) * w, core.bank_gamma(0, x.device), None).real
        q_phasor = torch.polar(a_q, phi_q)
        readout = (q_phasor * S).real / (a_q * A).clamp(min=core.config.denom_eps).detach()
        B, N, _ = x.shape
        D = self.embed_dim
        return {"state": torch.cat([S.real, S.imag], -1).reshape(B, N, 2 * D),
                "readout": readout.reshape(B, N, D)}

    def forward(self, ids, probe_pos, gate=None):
        feats = self.features(ids, gate=gate)
        ar = torch.arange(ids.shape[0], device=ids.device)
        logits = self.focus_head(feats["readout"][ar, probe_pos])
        return logits, feats

    def state_bytes(self, B=1):
        return self.core.state_bytes(B)
