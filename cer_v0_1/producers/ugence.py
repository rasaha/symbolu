"""Native Ugence Agent Runtime CER producer.

The runtime OWNS: goal understanding, planning, tool selection, proposal
generation (and, after execution, observation + reflection — see observation.py).
It MUST NOT own: authorization, operational safety, execution eligibility, or
execution tokens. So this producer emits a CER *before* any execution and returns
it; it never authorizes and never executes.

It is a faithful minimal producer for the frozen kubernetes.scale surface: the
"planning" for this narrow task is a deterministic decomposition, but it is a real
runtime code path (goal -> plan -> tool selection -> proposal) that is independent
of the LangGraph adapter's path. Both must converge on the same CER identity.
"""
from __future__ import annotations

from typing import Dict

from ..actuation import ActuationRequest


class UgenceCERProducer:
    """Emits CER V0.1 natively from the Ugence runtime's own plan."""

    RUNTIME = "ugence-agent-runtime"
    RUNTIME_VERSION = "0.1.0"
    MODEL = "mistral-cg"
    MODEL_PROVIDER = "ugence"
    ADAPTER_VERSION = "native"

    def __init__(self, *, governed_mode: bool = True) -> None:
        # governed_mode: no governed action may execute directly; the producer
        # only proposes. Compatibility (ungoverned) behavior is a separate path
        # that is NOT used when governed_mode is True.
        self.governed_mode = governed_mode

    # --- runtime-owned reasoning (does NOT authorize) ---
    def _understand_goal(self, req: ActuationRequest) -> str:
        return (f"raise availability of deployment {req.namespace}/{req.deployment} "
                f"from {req.from_replicas} to {req.to_replicas} replicas")

    def _plan(self, goal: str, req: ActuationRequest) -> list:
        # single-step plan for the scale task
        return [{"step": "scale", "interface": "kubernetes.scale",
                 "target": f"{req.namespace}/{req.deployment}",
                 "to": req.to_replicas}]

    def _select_tool(self, plan: list) -> str:
        # tool SELECTION (which tool) — not authorization (whether allowed)
        assert plan and plan[0]["interface"] == "kubernetes.scale"
        return "kubernetes.scale"

    # --- proposal generation ---
    def propose(self, req: ActuationRequest) -> Dict:
        """Return a CER V0.1 dict. Emits BEFORE execution; never executes."""
        goal = self._understand_goal(req)
        plan = self._plan(goal, req)
        self._select_tool(plan)
        cer = {
            "cer_version": "0.1",
            "profile": "cer.k8s.scale/0.1",
            "risk_tier": req.risk_tier,  # policy/tool-profile controlled, not model-asserted
            "identity": req.identity_block(),
            "provenance": {
                "runtime": self.RUNTIME,
                "runtime_version": self.RUNTIME_VERSION,
                "model_provider": self.MODEL_PROVIDER,
                "model": self.MODEL,
                "planner": "ugence.deterministic.htn",
                "objective": goal,  # Ugence's own objective prose (non-identity)
                "reasoning_trace_ref": "ugence://trace/scale",
                "adapter_version": self.ADAPTER_VERSION,
                "explanation": (
                    f"Proposed scaling {req.deployment} to {req.to_replicas} replicas "
                    f"to improve availability."),
            },
        }
        if req.attach_evidence:
            cer["evidence"] = {"kinds": ["signed_artifact", "simulation"]}
        return cer
