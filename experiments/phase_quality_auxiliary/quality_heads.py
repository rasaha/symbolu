"""
quality_heads.py — deterministic + bounded-quadratic + frozen-Phase branches, late-fused into
per-target information-health heads. Arms A0–A6 select which branches feed the health head.

Responsibility boundary (enforced structurally):
  * deterministic features come from `dataset.deterministic_quality_features` (schema/index only)
  * the quadratic branch attends the query over the BOUNDED deterministic packet only (never N×N,
    never the full stream); it emits the evidence-comparison rep + contradiction + chain scores +
    the selected evidence IDs (the ONLY source of supporting_evidence_ids)
  * the Phase branch scans the full ordered stream O(N) via the FROZEN recurrence and yields a small
    AUXILIARY representation — it never touches deterministic joins, evidence admission, the
    quadratic keys, or the supporting-evidence IDs.
Fusion happens ONLY in the health head (late fusion).
"""
from __future__ import annotations

import torch
import torch.nn as nn

from experiments.phase_iterative_quadratic.bounded_attention import BoundedRoutedSoftmaxAttention
from experiments.phase_iterative_quadratic.hybrid_blocks import PhaseFeature
from experiments.phase_v3_selective_ssm.train import sinusoidal
from .dataset import Schema, CAT_FIELDS, field_dims, DET_FEAT_DIM, TARGETS
from .baselines import make_temporal

EMBED_DIM = 48
NUM_HEADS = 4
TEMP_DIM = 32           # matched temporal-state dim (Phase aux / mean / ema / gru all → TEMP_DIM)


class EventEncoder(nn.Module):
    def __init__(self, schema: Schema, D=EMBED_DIM):
        super().__init__()
        dims = field_dims(schema)
        self.embs = nn.ModuleDict({f: nn.Embedding(dims[f], D) for f in CAT_FIELDS})
        self.num_proj = nn.Linear(3, D)
        self.D = D

    def forward(self, cats, num):
        """cats: {field: [B,N] long}; num: [B,N,3] → [B,N,D]."""
        N = num.shape[1]
        x = sum(self.embs[f](cats[f]) for f in CAT_FIELDS) + self.num_proj(num)
        return x + sinusoidal(N, self.D, num.device).unsqueeze(0)


class QuadraticBranch(nn.Module):
    """Bounded quadratic comparison over the candidate packet. The query token plus the ≤K packet
    records self-attend (exact softmax over K+1 ≤ 17 tokens — bounded, NEVER over the N-stream and
    NEVER an N×N tensor); the query slot reads out the evidence-comparison rep + contradiction +
    chain-completeness. Record-vs-record comparison is what lets it catch local contradictions."""
    def __init__(self, D=EMBED_DIM, heads=NUM_HEADS):
        super().__init__()
        self.layer = nn.TransformerEncoderLayer(D, heads, dim_feedforward=2 * D,
                                                batch_first=True, dropout=0.0)
        self.contradiction = nn.Linear(D, 1)
        self.completeness = nn.Linear(D, 1)
        self.out = nn.Linear(D, TEMP_DIM)

    def forward(self, x, query_pos, packet, valid_len):
        B, N, D = x.shape
        K = packet.shape[1]
        qrep = x.gather(1, query_pos.view(B, 1, 1).expand(B, 1, D))          # [B,1,D]
        prep = x.gather(1, packet.unsqueeze(-1).expand(B, K, D))             # [B,K,D]
        tokens = torch.cat([qrep, prep], dim=1)                             # [B,K+1,D]  (bounded)
        h = self.layer(tokens)                                             # bounded self-attention
        o = h[:, 0]                                                         # query slot readout
        return {"rep": self.out(o),
                "contradiction": self.contradiction(o).squeeze(-1),
                "completeness": self.completeness(o).squeeze(-1)}


class PhaseBranch(nn.Module):
    """Frozen Phase scans the full stream O(N); trainable adapter → small auxiliary features."""
    def __init__(self, D=EMBED_DIM, heads=NUM_HEADS):
        super().__init__()
        self.phase = PhaseFeature(D, heads)                 # frozen core + trainable proj
        self.adapter = nn.Linear(2 * D, TEMP_DIM)

    def forward(self, x, query_pos, mode="normal"):
        B, N, D = x.shape
        xin = x
        if mode == "reverse":
            xin = torch.flip(x, dims=[1])
        elif mode == "shuffle_time":
            perm = torch.randperm(N, device=x.device)
            xin = x[:, perm]
        r = self.phase(xin, zero=(mode == "zero"), shuffle=(mode == "shuffle_batch"))   # [B,N,D]
        at_q = r.gather(1, query_pos.view(B, 1, 1).expand(B, 1, D)).squeeze(1)
        pooled = r.mean(1)
        aux = self.adapter(torch.cat([at_q, pooled], dim=-1))
        conf = torch.sigmoid(aux.abs().mean(-1))            # crude auxiliary confidence
        return {"aux": aux, "confidence": conf}


ARMS = {
    "A0": {"quad": False, "temporal": None},               # deterministic only
    "A1": {"quad": True, "temporal": None},                # + bounded quadratic
    "A2": {"quad": False, "temporal": "phase"},            # + Phase
    "A3": {"quad": True, "temporal": "phase"},             # + quadratic + Phase
    "A4": {"quad": True, "temporal": "mean"},
    "A5": {"quad": True, "temporal": "ema"},
    "A6": {"quad": True, "temporal": "gru"},
}


class HealthModel(nn.Module):
    def __init__(self, schema: Schema, arm="A3", D=EMBED_DIM, heads=NUM_HEADS):
        super().__init__()
        self.arm = arm; self.cfg = ARMS[arm]; self.schema = schema
        self.encoder = EventEncoder(schema, D)
        self.quad = QuadraticBranch(D, heads) if self.cfg["quad"] else None
        self.temporal_kind = self.cfg["temporal"]
        if self.temporal_kind == "phase":
            self.temporal = PhaseBranch(D, heads)
        elif self.temporal_kind in ("mean", "ema", "gru"):
            self.temporal = make_temporal(self.temporal_kind, D, TEMP_DIM)
        else:
            self.temporal = None
        in_dim = DET_FEAT_DIM + (TEMP_DIM + 2 if self.quad else 0) + (TEMP_DIM if self.temporal else 0)
        self.in_dim = in_dim
        self.heads = nn.ModuleDict({t: nn.Sequential(nn.Linear(in_dim, D), nn.ReLU(), nn.Linear(D, 1))
                                    for t in TARGETS})

    def forward(self, cats, num, det_feats, query_pos, packet, valid_len, phase_mode="normal"):
        x = self.encoder(cats, num)                          # [B,N,D]
        parts = [det_feats]
        extra = {"selected_evidence_ids": packet.tolist() if self.quad else [],
                 "phase_auxiliary_used": self.temporal_kind == "phase"}
        if self.quad is not None:
            qd = self.quad(x, query_pos, packet, valid_len)
            parts += [qd["rep"], qd["contradiction"].unsqueeze(-1), qd["completeness"].unsqueeze(-1)]
            extra["contradiction"] = qd["contradiction"]; extra["completeness"] = qd["completeness"]
        if self.temporal_kind == "phase":
            pb = self.temporal(x, query_pos, mode=phase_mode)
            parts.append(pb["aux"]); extra["phase_signal_confidence"] = pb["confidence"]
        elif self.temporal is not None:
            parts.append(self.temporal(x, query_pos, valid_len))
        h = torch.cat(parts, dim=-1)
        logits = {t: self.heads[t](h).squeeze(-1) for t in TARGETS}
        return logits, extra

    def trainable_params(self):
        return int(sum(p.numel() for p in self.parameters() if p.requires_grad))

    def phase_state_bytes(self, B=1):
        if self.temporal_kind == "phase":
            return self.temporal.phase.core.state_bytes(B)
        return 0
