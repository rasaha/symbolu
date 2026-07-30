"""The nine consolidated modules, grouped by customer-facing capability.

Excludes the two AI-Infrastructure modules (KVPro, Cloud Scaling Controller):
they are frozen and never govern, so they are out of scope for the control-plane
console.

Maturity labels are taken verbatim from the platform evidence discipline
(MODULE_USE_CASES.md / the Platform Architecture Overview) and are never restated
more favourably here. ``wiring`` records how the module is surfaced in THIS
prototype: ``loop`` = live in the shadow governed loop; ``standalone`` = registered
with a dedicated endpoint or reserved for a later phase; ``read-only`` = shown as
substrate/status only (research-grade or a reasoning substrate, not an
interactive governance decision).
"""

from __future__ import annotations

from ..models import ModuleInfo

MODULES: list[ModuleInfo] = [
    # ---- Layer 1 · Specialized AI Systems ---------------------------------- #
    ModuleInfo(
        key="hybrid_llm", name="Hybrid LLM", layer="Specialized AI Systems",
        capability="Governed Runtime (substrate)",
        maturity="Implemented · Internally Validated", wiring="read-only",
        question="Reasoning quality over long context."),
    ModuleInfo(
        key="steering_controller", name="LLM Steering Controller",
        layer="Specialized AI Systems", capability="Governed Runtime (substrate)",
        maturity="Implemented · Internally Validated", wiring="read-only",
        question="How does generation happen, and can each steering decision be audited?"),
    ModuleInfo(
        key="agent_runtime", name="Agent Runtime", layer="Specialized AI Systems",
        capability="Governed Runtime", maturity="Implemented · Internally Validated",
        wiring="standalone",
        question="Supervised digital execution — emits a Canonical Execution Request."),
    ModuleInfo(
        key="autonomous_runtime", name="Autonomous Runtime",
        layer="Specialized AI Systems", capability="Governed Runtime (physical)",
        maturity="Research", wiring="read-only",
        question="Supervised physical execution for robots and industrial automation."),

    # ---- Layer 2 · AI Control Plane ---------------------------------------- #
    ModuleInfo(
        key="context_minimization", name="Context Minimization",
        layer="AI Control Plane", capability="Agent Gateway",
        maturity="Implemented · Internally Validated", wiring="loop",
        question="What information may the reasoning process receive?"),
    ModuleInfo(
        key="model_selection", name="Model Selection & Governed Inference",
        layer="AI Control Plane", capability="Policy & Decision Authority",
        maturity="Reference implemented · Technically Validated", wiring="standalone",
        question="May reasoning proceed, which model is eligible, and what evidence must claims carry?"),
    ModuleInfo(
        key="tap", name="Truth Assurance Platform", layer="AI Control Plane",
        capability="Truth & Evidence", maturity="Emerging", wiring="loop",
        question="Is the completed response sufficiently supported before delivery?"),
    ModuleInfo(
        key="actiongate", name="ActionGate", layer="AI Control Plane",
        capability="Action Control", maturity="Implemented · Internally Validated · Pilot Ready",
        wiring="loop", question="May THIS exact action be executed?"),
    ModuleInfo(
        key="autonomous_control_plane", name="Autonomous Control Plane",
        layer="AI Control Plane", capability="Action Control",
        maturity="Implemented (shadow-mode) · Internally Validated", wiring="loop",
        question="Is execution operationally safe right now?"),
]

MODULES_BY_KEY = {m.key: m for m in MODULES}


def get(key: str) -> ModuleInfo:
    return MODULES_BY_KEY[key]
