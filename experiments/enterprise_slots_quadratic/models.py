"""
models.py — arms S0–S6 over a bounded working set (fresh packet or binding slots).

The working set is chosen DETERMINISTICALLY (fresh retrieval or slot admission under a policy); the
model only encodes and reasons over it. Exact evidence_ids ride alongside the learned reps so every
output resolves to the ledger and unauthorized records never enter. No arm uses Phase.

    S0 fresh + pooling      S1 fresh + quadratic      S2 slots + pooling
    S3 slots + quadratic    S4 oracle slots + quad    S5 slots + full self-attn   S6 slots + query→slot
"""
from __future__ import annotations

import torch
import torch.nn as nn

from .schema import DomainCfg, CAT_FIELDS, field_dims, N_ROLE, N_STATUS
from .dataset import ABSTAIN, N_TIERS
from .bounded_quadratic import QueryToSlot, SlotSelfAttention
from .binding_slots import fresh_packet, simulate_slots

EMBED_DIM = 48
NUM_HEADS = 4
N_ANSWER = N_ROLE + 1                        # roles + ABSTAIN

ARMS = {
    "S0": {"source": "fresh", "attn": "pool"},
    "S1": {"source": "fresh", "attn": "self"},
    "S2": {"source": "slots", "attn": "pool"},
    "S3": {"source": "slots", "attn": "self"},
    "S4": {"source": "oracle", "attn": "self"},
    "S5": {"source": "slots", "attn": "self"},
    "S6": {"source": "slots", "attn": "q2s"},
}


def working_set(ex, arm, K, policy="P2"):
    cfg = ARMS[arm]
    if cfg["source"] == "fresh":
        r = fresh_packet(ex); r["required_survived"] = all(
            (i < 0) or (i in r["ids"]) for i in ex["required_ids"]); return r
    return simulate_slots(ex, K, policy=policy, oracle=(cfg["source"] == "oracle"))


class EvidenceEncoder(nn.Module):
    def __init__(self, cfg: DomainCfg, D=EMBED_DIM):
        super().__init__()
        dims = field_dims(cfg)
        self.embs = nn.ModuleDict({f: nn.Embedding(dims[f], D) for f in CAT_FIELDS})
        self.num_proj = nn.Linear(4, D)
        self.cfg = cfg; self.D = D

    def forward(self, cats, num):
        # cats: {f:[B,M]}, num:[B,M,4] -> [B,M,D]
        return sum(self.embs[f](cats[f]) for f in CAT_FIELDS) + self.num_proj(num)


class SlotQuadModel(nn.Module):
    def __init__(self, cfg: DomainCfg, arm="S3", K=8, D=EMBED_DIM, heads=NUM_HEADS):
        super().__init__()
        self.arm = arm; self.K = K; self.cfg = cfg; self.acfg = ARMS[arm]
        self.encoder = EvidenceEncoder(cfg, D)
        self.attn_kind = self.acfg["attn"]
        if self.attn_kind == "self":
            self.reason = SlotSelfAttention(D, heads)
        elif self.attn_kind == "q2s":
            self.reason = QueryToSlot(D, heads)
        else:
            self.reason = None                       # pooling
        self.answer_head = nn.Linear(2 * D, N_ANSWER)
        self.conflict_head = nn.Linear(2 * D, 1)
        self.abstain_head = nn.Linear(2 * D, 1)
        self.version_head = nn.Linear(2 * D, cfg.n_versions)

    def forward(self, ws_cats, ws_num, ws_mask, q_cats, q_num):
        ws = self.encoder(ws_cats, ws_num)                          # [B,M,D]
        query = self.encoder({f: q_cats[f].unsqueeze(1) for f in q_cats},
                             q_num.unsqueeze(1))                    # [B,1,D]
        if self.reason is None:                                     # pooling
            m = ws_mask.float().unsqueeze(-1)
            pooled = (ws * m).sum(1) / m.sum(1).clamp(min=1)
            o = pooled
        else:
            o = self.reason(query, ws, ws_mask)
        h = torch.cat([query[:, 0], o], dim=-1)                     # [B,2D]
        return {"answer": self.answer_head(h), "conflict": self.conflict_head(h).squeeze(-1),
                "abstain": self.abstain_head(h).squeeze(-1), "version": self.version_head(h)}

    def trainable_params(self):
        return int(sum(p.numel() for p in self.parameters() if p.requires_grad))

    def slot_state_bytes(self, D=EMBED_DIM):
        # exact SlotRecord (~14 int/float fields) + learned rep (D floats) per slot
        return self.K * (14 * 4 + D * 4) if self.acfg["source"] in ("slots", "oracle") else 0
