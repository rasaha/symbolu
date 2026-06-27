"""Training objectives for Symbol-U.

Signatures + reference implementations for the standard losses; the
research-dependent ones (recall helpfulness, DHA preference) are left as
documented stubs because they require labels/signals that do not yet exist
(see SPEC §12 MRQ-6/8). Full training loop is intentionally out of scope.

Loss table (see README):
  L_lm      next-token CE                       — always on
  L_typed   Vritti/aspect supervision CE        — REQUIRED for grounding
  L_entcal  entropy calibration                 — correlate H with error
  L_recall  memory recall/helpfulness           — needs helpfulness signal (stub)
  L_dha     DHA preference/style                — needs preference labels (stub)
  L_stab    stability/convergence (ponder+delta)— from refinement core
"""
from __future__ import annotations

from typing import Dict, Optional

import torch
import torch.nn.functional as F


def next_token_loss(logits: torch.Tensor, target_ids: torch.Tensor,
                    ignore_index: int = -100) -> torch.Tensor:
    """logits:[B,L,V], target_ids:[B,L] -> scalar CE (shifted)."""
    sl = logits[:, :-1].reshape(-1, logits.size(-1))
    tg = target_ids[:, 1:].reshape(-1)
    return F.cross_entropy(sl, tg, ignore_index=ignore_index)


def typed_supervision_loss(
    log_p_v: torch.Tensor, vritti_labels: torch.Tensor,
    log_p_w_syl: torch.Tensor, aspect_labels: torch.Tensor,
    ignore_index: int = -100,
) -> torch.Tensor:
    """NLL of the typed heads against syllable-level labels (masked).

    log_p_v:[B,n,5], vritti_labels:[B,n]; log_p_w_syl:[B,n,10], aspect_labels:[B,n].
    THIS is the loss that grounds the latents; without it the heads are
    uninterpretable (kill criterion #1).
    """
    lv = F.nll_loss(log_p_v.reshape(-1, log_p_v.size(-1)),
                    vritti_labels.reshape(-1), ignore_index=ignore_index)
    la = F.nll_loss(log_p_w_syl.reshape(-1, log_p_w_syl.size(-1)),
                    aspect_labels.reshape(-1), ignore_index=ignore_index)
    return lv + la


def entropy_calibration_loss(
    entropy_norm: torch.Tensor, per_example_error: torch.Tensor,
) -> torch.Tensor:
    """Encourage normalized entropy to track predictive error.

    entropy_norm:[B] in [0,1], per_example_error:[B] (e.g. per-example NLL,
    detached + min-max normalized). Pearson-style alignment via 1 - corr.
    """
    e = entropy_norm - entropy_norm.mean()
    u = per_example_error - per_example_error.mean()
    corr = (e * u).mean() / (e.std().clamp_min(1e-6) * u.std().clamp_min(1e-6))
    return 1.0 - corr


def stability_loss(ponder_cost: torch.Tensor, final_delta: torch.Tensor,
                   ponder_weight: float = 1e-2) -> torch.Tensor:
    """Refinement-core regularizer: cheap compute + converged final step."""
    return ponder_weight * ponder_cost + final_delta


def memory_recall_loss(*args, **kwargs) -> torch.Tensor:
    """STUB. Requires a helpfulness signal: does readiness-gated recall improve
    task quality vs. no-recall? Implement as paired-rollout reward once a
    helpfulness label / counterfactual is available (SPEC §12 MRQ-8)."""
    raise NotImplementedError("memory_recall_loss needs a helpfulness signal")


def dha_preference_loss(*args, **kwargs) -> torch.Tensor:
    """STUB. Requires human preference over tonal modes (CE on preferred mode,
    or pairwise ranking). Out of scope until a preference set exists."""
    raise NotImplementedError("dha_preference_loss needs preference labels")


def safety_supervision_loss(
    soft_scores: torch.Tensor, labels: torch.Tensor,
) -> torch.Tensor:
    """BCE for the safety scorers (risk/compliance/...). labels:[B,n_scorers]."""
    return F.binary_cross_entropy(soft_scores, labels.float())


def total_loss(aux: Dict[str, torch.Tensor], batch: Dict[str, torch.Tensor],
               weights: Optional[Dict[str, float]] = None) -> Dict[str, torch.Tensor]:
    """Compose the active losses given model `aux` and a `batch` of targets.

    Only computes a term when both the model produced its inputs and the batch
    carries the needed labels — so the same function works across the ablation
    ladder. Returns a dict including 'total'.
    """
    w = {"lm": 1.0, "typed": 1.0, "entcal": 0.1, "stab": 0.1, "safety": 1.0}
    if weights:
        w.update(weights)
    out: Dict[str, torch.Tensor] = {}
    if "logits" in aux and "target_ids" in batch:
        out["lm"] = next_token_loss(aux["logits"], batch["target_ids"])
    if "log_p_v" in aux and "vritti_labels" in batch:
        out["typed"] = typed_supervision_loss(
            aux["log_p_v"], batch["vritti_labels"],
            aux["log_p_w_syl"], batch["aspect_labels"])
    if "H_D" in aux and "per_example_error" in batch:
        H = aux["H_D"] / torch.log(torch.tensor(10.0))
        out["entcal"] = entropy_calibration_loss(H, batch["per_example_error"])
    if "ponder_cost" in aux:
        out["stab"] = stability_loss(aux["ponder_cost"], aux["final_delta"])
    if "safety_scores" in aux and "safety_labels" in batch:
        out["safety"] = safety_supervision_loss(
            aux["safety_scores"], batch["safety_labels"])
    out["total"] = sum(w.get(k, 1.0) * v for k, v in out.items())
    return out
