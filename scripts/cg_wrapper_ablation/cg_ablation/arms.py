"""Ablation arms for the CG-wrapper generation-quality experiment.

Each arm is a clean, reproducible configuration expressed as an ``AttentionAblationConfig``
(or the BASE sentinel = raw backbone logits, no CG). Torch is imported lazily so this module
can be imported on a CPU box without torch; only the functions that actually run a forward
need it.

Arms (RESEARCH_PLAN.md §2):
    A_base       base model, no wrapper        -> raw lm_head(hidden)
    B_full       full CG wrapper               -> ablation = None (phase+vritti+guna on)
    C_phase_off  phase signal into adapter off -> use_phase_sync=False
    D_gate0      adapter_gate forced to 0      -> use_guna_bias=False  (== base, sanity K0)
    E_csr        CSR on/off                    -> N/A unless CSR is wired into the forward
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

BASE = "BASE"  # sentinel: run the raw backbone, no CG correction


@dataclass(frozen=True)
class Arm:
    name: str
    description: str
    # Either BASE (raw backbone) or a kwargs dict for AttentionAblationConfig, or None (full CG).
    ablation: Any
    requires_csr: bool = False


ARMS: List[Arm] = [
    Arm("A_base", "Base model, no wrapper (raw lm_head(hidden))", BASE),
    Arm("B_full", "Full CG wrapper (phase + vritti + guna on)", None),
    Arm("C_phase_off", "Wrapper, phase signal into adapter disabled (use_phase_sync=False)",
        {"use_phase_sync": False}),
    Arm("D_gate0", "Wrapper, adapter_gate forced 0 (use_guna_bias=False) — must equal base",
        {"use_guna_bias": False}),
    Arm("E_csr", "CSR ON vs OFF — only if CSR is wired into the generation path",
        {"use_phase_sync": True}, requires_csr=True),
]

ARMS_BY_NAME: Dict[str, Arm] = {a.name: a for a in ARMS}


def active_arms(csr_present: bool) -> List[Arm]:
    """Return the arms to run. Arm E is included only when a CSR stage is in the path."""
    return [a for a in ARMS if (a.requires_csr is False) or csr_present]


def _make_ablation_config(arm: Arm):
    """Build the AttentionAblationConfig for an arm (None for full/BASE)."""
    if arm.ablation is BASE or arm.ablation is None:
        return None
    from symbolu_training.training.conscious_generation.ablation.config import (
        AttentionAblationConfig,
    )
    # Start from the baseline (phase+vritti+guna on) and override per the arm.
    return AttentionAblationConfig(**arm.ablation)


def apply_arm(wrapper: Any, arm: Arm) -> None:
    """Configure ``wrapper`` for ``arm`` via set_ablation_config.

    For BASE we still set all_off so a single code path (wrapper.forward) can produce the base
    logits; ``run_arm_logits`` instead reads the raw backbone for BASE to be maximally faithful.
    """
    if arm.ablation is BASE:
        from symbolu_training.training.conscious_generation.ablation.config import (
            AttentionAblationConfig,
        )
        wrapper.set_ablation_config(AttentionAblationConfig.all_off())
    else:
        wrapper.set_ablation_config(_make_ablation_config(arm))


def run_arm_logits(wrapper: Any, arm: Arm, input_ids, attention_mask=None) -> Dict[str, Any]:
    """Run one forward for ``arm`` and return logits + the diagnostics dict.

    For ``A_base`` the raw frozen backbone is used directly (lm_head(hidden), no CG), giving the
    ground-truth base logits. For all other arms the wrapper.forward is used with the arm's
    ablation config. Returns a dict with at least ``logits`` plus CG diagnostics.
    """
    import torch

    with torch.no_grad():
        if arm.ablation is BASE:
            out = wrapper.backbone(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
            )
            hidden = out.hidden_states[-1]
            logits = (
                wrapper.backbone.lm_head(hidden)
                if hasattr(wrapper.backbone, "lm_head")
                else out.logits
            )
            return {
                "logits": logits,
                "state": None,
                "delta_bhava": None,
                "adapter_gate": 0.0,
                "adapter_output_norm": 0.0,
                "hidden_norm": float(hidden.float().norm(dim=-1).mean().item()),
            }

        apply_arm(wrapper, arm)
        result = wrapper(
            input_ids=input_ids,
            attention_mask=attention_mask,
            reset_state=True,
            return_last_hidden=True,
        )
        hidden_norm = (
            float(result["last_hidden_state"].float().norm(dim=-1).mean().item())
            if "last_hidden_state" in result
            else 0.0
        )
        result["hidden_norm"] = hidden_norm
        return result
