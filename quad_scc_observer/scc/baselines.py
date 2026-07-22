"""Baselines A (confidence), B (entailment proxy), C (evidence grounding) — read-only.

USE must not claim credit for functionality these already provide. SCC's four hypotheses are
tested for value BEYOND these.

A — confidence: reuses the confidence signals from the USE package (token prob, log-prob, output
    entropy, margin, sequence confidence, attention entropy).
B — entailment proxy: representation-level support for the predicted value. In closed-world MQAR a
    faithful entailment check reduces to either confidence (intrinsic support) or grounding (the
    symbolic binding); we implement a soft attention-support proxy and DOCUMENT that overlap.
C — grounding: the symbolic evidence verifier (adjacency binding support + value/key presence).
    In a closed world this is a near-oracle for correctness — that is the point of separating
    grounded verification from intrinsic coherence.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import torch
import torch.nn.functional as F

from . import _paths  # noqa: F401
from use.baselines import baseline_signals as _use_confidence
from . import features_E

CONFIDENCE = ["token_prob", "logprob", "neg_entropy", "margin", "seq_confidence", "attn_neg_entropy"]


def confidence(rec: Dict, records: List[Dict]) -> Dict[str, np.ndarray]:
    b = torch.tensor([r["b"] for r in records])
    q = torch.tensor([r["q"] for r in records])
    sig = _use_confidence(rec, (b, q))
    return {f"A::{k}": v.numpy() for k, v in sig.items() if k in CONFIDENCE}


@torch.no_grad()
def entailment(records: List[Dict], rec: Dict, model) -> Dict[str, np.ndarray]:
    """Soft entailment proxy: attention-support mass on the retrieved key + pred/retrieval
    agreement. Documented to overlap with confidence (support strength) and grounding."""
    qscore = rec["quad_score"][rec["num_layers"] - 1].mean(dim=1)     # [B,N,N]
    mass, agree = [], []
    for r in records:
        b, q, rk = r["b"], r["q"], r["retrieved_kp"]
        cand = torch.zeros(qscore.shape[-1], dtype=torch.bool)
        for kp in r["key_positions"]:
            if kp < q:
                cand[kp] = True
        row = qscore[b, q].masked_fill(~cand, float("-inf"))
        p = F.softmax(row, dim=-1)
        mass.append(float(p[rk]))                                     # support mass on retrieved key
        agree.append(1.0 if r["v_pred"] == r["v_retrieved"] else 0.0)  # claim entailed by retrieval
    return {"B::attn_support_mass": np.array(mass), "B::pred_retrieval_agree": np.array(agree)}


def grounding(records: List[Dict], rec: Dict, model) -> Dict[str, np.ndarray]:
    """Symbolic evidence grounding (near-oracle in closed world): adjacency binding + presence."""
    E = features_E.compute(records, rec, model)
    return {
        "C::adjacency_support": E["E_adjacency_support"],
        "C::value_present": E["E_value_supported"],
        "C::key_present": E["E_key_supported"],
        "C::support_count": E["E_support_count"],
    }
