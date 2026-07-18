"""Per-run diagnostics for the CG wrapper (Task 6).

Torch is imported lazily. These helpers turn a wrapper forward result + base logits into the
scalar diagnostics the plan requires:

    adapter_gate, phase_adapter output norm, correction norm, hidden-state norm and their ratio,
    ΔBhava norm, logit KL (base vs wrapper), top-1 flip rate.

The logit metrics here operate on torch tensors for efficiency on GPU; the pure-Python
equivalents in metrics.py are used by the CPU tests.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def tensor_logit_kl(base_logits, wrapper_logits) -> float:
    """Mean per-token KL(softmax(base) || softmax(wrapper)) over the last-token-free [B,T,V]."""
    import torch
    import torch.nn.functional as F

    logp_base = F.log_softmax(base_logits.float(), dim=-1)
    logp_wrap = F.log_softmax(wrapper_logits.float(), dim=-1)
    p_base = logp_base.exp()
    kl = (p_base * (logp_base - logp_wrap)).sum(dim=-1)  # [B, T]
    return float(kl.mean().item())


def tensor_top1_flip(base_logits, wrapper_logits) -> float:
    """Fraction of positions where argmax(base) != argmax(wrapper) over [B,T,V]."""
    import torch

    b = base_logits.argmax(dim=-1)
    w = wrapper_logits.argmax(dim=-1)
    return float((b != w).float().mean().item())


def correction_diagnostics(wrapper: Any, result: Dict[str, Any]) -> Dict[str, float]:
    """Extract gate / correction / hidden-norm diagnostics from a wrapper forward ``result``.

    ``result`` is the dict returned by MistralCGWrapper.forward (with return_last_hidden=True).
    correction norm is approximated as gate * adapter_output_norm (the residual magnitude that
    was added to ``hidden``); ratio is correction / hidden_norm.
    """
    gate = float(result.get("adapter_gate", 0.0) or 0.0)
    adapter_norm = float(result.get("adapter_output_norm", 0.0) or 0.0)
    hidden_norm = float(result.get("hidden_norm", 0.0) or 0.0)
    correction_norm = gate * adapter_norm
    ratio = (correction_norm / hidden_norm) if hidden_norm > 0 else 0.0
    dbhava = result.get("delta_bhava")
    if dbhava is not None:
        try:
            dbhava_norm = float(dbhava.float().norm(dim=-1).mean().item())
        except Exception:
            dbhava_norm = 0.0
    else:
        dbhava_norm = 0.0
    return {
        "adapter_gate": gate,
        "adapter_output_norm": adapter_norm,
        "correction_norm": correction_norm,
        "hidden_norm": hidden_norm,
        "correction_to_hidden_ratio": ratio,
        "delta_bhava_norm": dbhava_norm,
    }


def full_diagnostics(wrapper, arm_result: Dict[str, Any], base_logits, wrapper_logits) -> Dict[str, float]:
    """Combine correction diagnostics with base-vs-wrapper logit KL + flip rate."""
    diag = correction_diagnostics(wrapper, arm_result)
    diag["logit_kl_vs_base"] = tensor_logit_kl(base_logits, wrapper_logits)
    diag["top1_flip_rate_vs_base"] = tensor_top1_flip(base_logits, wrapper_logits)
    return diag
