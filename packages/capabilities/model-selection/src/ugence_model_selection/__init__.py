"""Ugence Model Authority — canonical product core.

Model Authority determines which model, *if any*, is authorized to execute a specific
request under the current policy, capability, jurisdiction, security, cost, and runtime
conditions. It does not merely recommend a model — it issues a binding authorization
decision. (This capability evolved from "Model Selection": the semantic contract moved
from "choose the best model" to "determine the eligible set and issue a binding
authorization for execution". The prior distribution name ``ugence-model-selection`` and
its selection/eligibility symbols are retained as a compatibility surface.)

Audited stages, preserved exactly from the production-shaped source (``execution_gate``)
this package canonicalizes, with Model Authority as the binding external contract:

    Approved candidate set
            ↓
    ExecutionGate      — mandatory eligibility, fail-closed disqualification (never ranks)
            ↓
    Eligible candidate set
            ↓
    ModelPolicy        — policy-weighted deterministic scoring / ranking (only over eligible)
            ↓
    ModelAuthority     — binding decision: ALLOW / DENY / HOLD / ESCALATE
            ↓
    Authorized model (+ governed fallback) or NO_ELIGIBLE_MODEL

Hard eligibility constraints execute before soft scoring; an ineligible candidate can
never be authorized by a higher aggregate score; there is no silent fallback to a
prohibited or ineligible model — every governed fallback candidate is itself eligible.

This is a **leaf capability**: it depends only on the Python standard library. It does
not import applications, domains, the control plane, the AI Control Plane, the optional
orchestrator, Agent Runtime, Hybrid LLM, the Governance Provider Framework, concrete
providers, the governed-inference pilot, the model-selection experiments, or any
benchmark harness — and it owns no model invocation, routing, retry, failover, load
balancing, action authorization, provider registration, or credential management.

Import the public surface from ``ugence_model_selection.api`` (Model Authority contract:
``ModelAuthority``, ``ModelAuthorizationDecision``, ``ModelAuthorizationDisposition``).
The legacy ``execution_gate`` namespace at the repository root is a logic-free
compatibility surface that re-exports the *same objects* from this package (object
identity preserved).
"""
from __future__ import annotations

from .version import VERSION, __version__

__all__ = ["__version__", "VERSION"]
