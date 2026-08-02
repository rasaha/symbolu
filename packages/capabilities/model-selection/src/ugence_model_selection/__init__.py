"""Ugence Model Selection — canonical product core.

Model Selection evaluates already-approved model or provider candidates against
mandatory eligibility constraints and policy-weighted optimization criteria, then
returns a deterministic policy-bounded selection or a no-eligible-model outcome.

Two audited stages, preserved exactly from the production-shaped source
(``execution_gate``) this package canonicalizes:

    Approved candidate set
            ↓
    ExecutionGate      — mandatory eligibility, fail-closed disqualification (never ranks)
            ↓
    Eligible candidate set
            ↓
    ModelPolicy        — policy-weighted deterministic scoring / ranking (only over eligible)
            ↓
    Selected candidate or NO_ELIGIBLE_MODEL (abstain)

Hard eligibility constraints execute before soft scoring; an ineligible candidate can
never be selected by a higher aggregate score; there is no silent fallback to a
prohibited or ineligible model.

This is a **leaf capability**: it depends only on the Python standard library. It does
not import applications, domains, the control plane, the AI Control Plane, the optional
orchestrator, Agent Runtime, Hybrid LLM, the Governance Provider Framework, concrete
providers, the governed-inference pilot, the model-selection experiments, or any
benchmark harness — and it owns no model invocation, routing, retry, failover, load
balancing, action authorization, provider registration, or credential management.

Import the public surface from ``ugence_model_selection.api``. The legacy
``execution_gate`` namespace at the repository root is a logic-free compatibility surface
that re-exports the *same objects* from this package (object identity preserved).
"""
from __future__ import annotations

from .version import VERSION, __version__

__all__ = ["__version__", "VERSION"]
