"""
distillation.py — arm C objective (§ Required training arms).

Train a student gate to imitate a FROZEN supervised V2-S teacher's gate logits, then remove
teacher access and fine-tune end-to-end. Distillation is a BCE/soft-target match between the
student and teacher gate probabilities (per head, per position).

    L_distill = BCE(σ(student_logit), σ(teacher_logit).detach())
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor


@torch.no_grad()
def teacher_gate_prob(teacher, ids) -> Tensor:
    return torch.sigmoid(teacher.gate_logit(ids))          # [B,N,H]


def distill_loss(student_logit: Tensor, teacher_prob: Tensor) -> Tensor:
    return F.binary_cross_entropy(torch.sigmoid(student_logit).clamp(1e-4, 1 - 1e-4),
                                  teacher_prob.detach())
