"""
structured_reasoning.py — the Quadratic stage emits a TYPED structured finding (not only a latent
vector). It reuses the FROZEN P5 binding-slot pool + bounded full slot-to-slot quadratic; on top it
predicts the typed fields (budget/policy/approval status, material conflict, evidence complete) that
the transparent output mappers consume. Every typed field is traceable to the slot evidence IDs.
"""
from __future__ import annotations

import torch
import torch.nn as nn

from experiments.enterprise_slots_quadratic.schema import DomainCfg, CAT_FIELDS
from experiments.enterprise_slots_quadratic.models import EvidenceEncoder, working_set
from experiments.enterprise_slots_quadratic.bounded_quadratic import SlotSelfAttention
from .outcome_contract import N_OUTCOME

EMBED_DIM = 48
NUM_HEADS = 4
POLICY = "P5"           # frozen validated policy
FIELD_DIMS = {"budget_status": 3, "policy_status": 3, "approval_status": 2,
              "material_conflict": 2, "evidence_complete": 2}


def _feat(e, cfg):
    cats = {f: getattr(e, f) for f in CAT_FIELDS}
    num = [e.timestamp / 200.0, e.version / cfg.n_versions, float(e.source_authority),
           e.section_id / max(1, cfg.n_sections)]
    return cats, num


def collate(batch, cfg: DomainCfg, K, device="cpu"):
    B = len(batch)
    wss = [working_set(ex, "S3", K, POLICY) for ex in batch]
    M = max(1, max(len(w["ids"]) for w in wss))
    ws_cats = {f: torch.zeros(B, M, dtype=torch.long, device=device) for f in CAT_FIELDS}
    ws_num = torch.zeros(B, M, 4, device=device); ws_mask = torch.zeros(B, M, dtype=torch.bool, device=device)
    q_cats = {f: torch.zeros(B, dtype=torch.long, device=device) for f in CAT_FIELDS}
    q_num = torch.zeros(B, 4, device=device)
    fields = {k: torch.zeros(B, dtype=torch.long, device=device) for k in FIELD_DIMS}
    outcome = torch.zeros(B, dtype=torch.long, device=device)
    meta = []
    for i, (ex, w) in enumerate(zip(batch, wss)):
        id_of = {e.evidence_id: e for e in ex["events"]}
        for j, eid in enumerate(w["ids"][:M]):
            e = id_of.get(eid)
            if e is None:
                continue
            c, nu = _feat(e, cfg)
            for f in CAT_FIELDS:
                ws_cats[f][i, j] = c[f]
            ws_num[i, j] = torch.tensor(nu, device=device); ws_mask[i, j] = True
        qc, qn = _feat(ex["events"][ex["query_pos"]], cfg)
        for f in CAT_FIELDS:
            q_cats[f][i] = qc[f]
        q_num[i] = torch.tensor(qn, device=device)
        for k in FIELD_DIMS:
            fields[k][i] = ex["finding"][k]
        outcome[i] = ex["outcome"]
        unauth = any(not (id_of[eid].tenant_id == ex["tenant"] and id_of[eid].readable_by(ex["role_idx"]))
                     for eid in w["ids"] if eid in id_of)
        dup_occ = sum(1 for eid in w["ids"] if eid in id_of and id_of[eid].tag.startswith("dup_"))
        meta.append({"ids": w["ids"], "required_survived": w.get("required_survived", False),
                     "unauthorized_included": unauth, "ids_resolve": all(eid in id_of for eid in w["ids"]),
                     "dup_occupancy": dup_occ / max(1, len(w["ids"]))})
    return (ws_cats, ws_num, ws_mask, q_cats, q_num), fields, outcome, meta


class StructuredReasoner(nn.Module):
    def __init__(self, cfg: DomainCfg, K=4, D=EMBED_DIM, heads=NUM_HEADS):
        super().__init__()
        self.cfg = cfg; self.K = K
        self.encoder = EvidenceEncoder(cfg, D)
        self.reason = SlotSelfAttention(D, heads)              # frozen-style bounded quadratic
        self.field_heads = nn.ModuleDict({k: nn.Linear(2 * D, v) for k, v in FIELD_DIMS.items()})
        self.latent_outcome = nn.Linear(2 * D, N_OUTCOME)      # O0: current learned head (latent→outcome)

    def forward(self, ws_cats, ws_num, ws_mask, q_cats, q_num):
        ws = self.encoder(ws_cats, ws_num)
        query = self.encoder({f: q_cats[f].unsqueeze(1) for f in q_cats}, q_num.unsqueeze(1))
        o = self.reason(query, ws, ws_mask)
        h = torch.cat([query[:, 0], o], dim=-1)
        return {"field_logits": {k: self.field_heads[k](h) for k in FIELD_DIMS},
                "latent_outcome": self.latent_outcome(h), "h": h}

    def trainable_params(self):
        return int(sum(p.numel() for p in self.parameters() if p.requires_grad))
