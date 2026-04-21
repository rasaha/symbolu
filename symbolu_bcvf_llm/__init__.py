"""BCVF LLM — LLM-domain port of the autonomy BCVF kernel.

Phase 1 kernel (pure NumPy) per
``docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md`` §2.8.

Parallel implementation of ``symbolu_robotics/bcvf_autonomous``; no
cross-import. The public API surfaces the kernel only — source
framework, trust-weighting, and benchmark harness live in later
phases (§4/§5/§6) and are not imported here.
"""

from __future__ import annotations

from .core import (
    BCVFLLMConfig,
    BCVFLLMResult,
    CostOrder,
    compute_bcvf_cost,
    compute_bcvf_cost_batch,
    compute_disagreement,
    compute_disagreement_acceleration,
    compute_disagreement_velocity,
    pseudo_huber,
    smooth_gate,
)

__all__ = [
    "BCVFLLMConfig",
    "BCVFLLMResult",
    "CostOrder",
    "compute_bcvf_cost",
    "compute_bcvf_cost_batch",
    "compute_disagreement",
    "compute_disagreement_acceleration",
    "compute_disagreement_velocity",
    "pseudo_huber",
    "smooth_gate",
]

__version__ = "0.1.0"
