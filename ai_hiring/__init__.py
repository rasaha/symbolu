"""AI-Assisted Hiring Framework — Phase 1 Foundation.

An isolated module implementing the *foundation* of the AI-Assisted Hiring
Framework: canonical data contracts, an audited workflow state machine, and the
hard, enforced separation between AI recommendations (advisory) and human
employment decisions (binding).

Core architectural invariant, enforced in types, services, persistence, and API
permissions — not merely documented:

    AI evaluates evidence and produces advisory recommendations.
    Only an authenticated human actor may create a binding employment decision.

This phase deliberately does *not* implement AI scoring, candidate ranking,
résumé evaluation, fairness models, assessment generation, or production
integrations. See ``docs/IMPLEMENTATION_STATUS.md`` for the full boundary.

Package structure (Phase 5C — direct kernel adoption): the domain-neutral
governance middleware lives in ``decision_governance`` (the DGM kernel); the
hiring domain's canonical import surface is ``domains.hiring``; and the
canonical composition root is ``applications.ai_hiring.platform``. This
``ai_hiring`` package is now primarily a **compatibility namespace** — it
re-exports the composition entry points below and preserves every historical
import path so existing callers keep working unchanged.
"""

from __future__ import annotations

from applications.ai_hiring.platform import HiringPlatform, build_in_memory_platform

__version__ = "0.1.0"

__all__ = [
    "HiringPlatform",
    "build_in_memory_platform",
    "__version__",
]
