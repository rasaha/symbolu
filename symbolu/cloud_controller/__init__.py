"""Neural Cloud Scaling Controller.

Coherence-aware adaptive control for cloud infrastructure.
Ported from the CG ExperientialController (12-parameter minimal controller).

Core equation:
    Action_t = d_t * G_t * P_t * S_t

Where:
    P_t = sigmoid(k_r * R_t - k_m * M_t + b_p)     # plasticity gate
    G_t = clip(G_base * f_phase * f_coh, G_min, G_max)  # adaptive gain
    d_t = exp(-k_dv * V_excess - k_dc * U_t)        # damping
    S_t = weighted pressure from normalized metrics   # signal
"""

from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.controller import Controller
from symbolu.cloud_controller.orchestrator import (
    OrchestratorConfig,
    ProductionOrchestrator,
)

__all__ = [
    "Controller",
    "InfraControllerConfig",
    "OrchestratorConfig",
    "ProductionOrchestrator",
]
