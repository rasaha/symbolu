"""
learned_mapper.py — learned output mappers.

    O0 — current learned head: latent Quadratic vector → outcome directly (the baseline to beat).
    O3 — small learned mapper over the TYPED field probabilities only (no latent vector).
    O4 — hybrid: deterministic HARD GATES first; a learned head ranks only among the legally-valid
         remaining outcomes (APPROVE / REJECT / REVIEW_REQUIRED). Gates can never be overridden.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .outcome_contract import (N_OUTCOME, APPROVE, REJECT, REVIEW_REQUIRED,
                               ABSTAIN_INCOMPLETE_EVIDENCE, ABSTAIN_MATERIAL_CONFLICT)
from .structured_reasoning import FIELD_DIMS
from .policy_mapper import fields_argmax
from .constrained_mapper import hard_gate

FIELD_PROB_DIM = sum(FIELD_DIMS.values())
NON_GATED = [APPROVE, REJECT, REVIEW_REQUIRED]        # outcomes a learned head may choose among


def o0_latent_map(reasoner_out, meta, device="cpu"):
    return reasoner_out["latent_outcome"].argmax(-1)


class TypedMapper(nn.Module):
    """O3: MLP over concatenated typed-field probabilities → outcome."""
    def __init__(self, hidden=32):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(FIELD_PROB_DIM, hidden), nn.ReLU(), nn.Linear(hidden, N_OUTCOME))

    def _feats(self, field_logits):
        return torch.cat([F.softmax(field_logits[k], -1) for k in FIELD_DIMS], dim=-1)

    def forward(self, reasoner_out):
        return self.net(self._feats(reasoner_out["field_logits"]))


class HybridMapper(nn.Module):
    """O4: hard gates decide abstention/conflict; a learned head ranks the NON-gated outcomes."""
    def __init__(self, hidden=32):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(FIELD_PROB_DIM, hidden), nn.ReLU(), nn.Linear(hidden, len(NON_GATED)))

    def _feats(self, field_logits):
        return torch.cat([F.softmax(field_logits[k], -1) for k in FIELD_DIMS], dim=-1)

    def rank_logits(self, reasoner_out):
        return self.net(self._feats(reasoner_out["field_logits"]))          # [B, |NON_GATED|]

    @torch.no_grad()
    def predict(self, reasoner_out, meta, device="cpu"):
        fields = fields_argmax(reasoner_out["field_logits"])
        rank = self.rank_logits(reasoner_out)
        B = rank.shape[0]; out = torch.zeros(B, dtype=torch.long, device=device)
        for i in range(B):
            g = hard_gate(fields, i, meta[i])
            if g is not None:
                out[i] = max(g, 0)
            else:
                out[i] = NON_GATED[int(rank[i].argmax())]
        return out
