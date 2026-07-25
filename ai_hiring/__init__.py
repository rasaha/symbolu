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

from typing import TYPE_CHECKING

__version__ = "0.1.0"

__all__ = [
    "HiringPlatform",
    "build_in_memory_platform",
    "__version__",
]

# The composition root lives in ``applications.ai_hiring.platform`` and imports
# ``domains.hiring`` (which re-exports hiring implementation from this package).
# Re-exporting it *eagerly* here would form an import cycle when
# ``applications.ai_hiring`` is imported before ``ai_hiring``. Resolve the two
# entry points lazily (PEP 562) so this module imports with no forward
# dependency, while ``ai_hiring.HiringPlatform`` / ``ai_hiring.build_in_memory_platform``
# keep resolving to the identical canonical objects.
if TYPE_CHECKING:  # pragma: no cover - typing only
    from applications.ai_hiring.platform import (
        HiringPlatform,
        build_in_memory_platform,
    )


def __getattr__(name: str):
    if name in ("HiringPlatform", "build_in_memory_platform"):
        from applications.ai_hiring import platform

        return getattr(platform, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
