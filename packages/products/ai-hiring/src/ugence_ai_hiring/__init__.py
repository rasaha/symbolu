"""Ugence AI Hiring — canonical independent distribution.

An AI-assisted hiring **governance** product: canonical data contracts, an
audited workflow state machine, deterministic evidence normalization and
assessment, decision cases, governed action-request preparation, and — enforced
in types, services, persistence, and API permissions, not merely documented —
the hard separation between AI recommendations (advisory) and human employment
decisions (binding):

    AI evaluates evidence and produces advisory recommendations.
    Only an authenticated, authorized human actor may create a binding
    employment decision. An AI actor never can.

This distribution ships **no** AI scoring model, candidate-ranking algorithm,
résumé-evaluation model, fairness/bias model, LLM inference, or production HRIS/
ATS/offer/payroll adapter. It ships deterministic, offline, in-memory adapters
only and makes **no** production, scale, fairness, or legal-compliance claim
(see :func:`version_info` — ``production_certified`` is always ``False``).

Canonical import surface: :mod:`ugence_ai_hiring`. The legacy top-level
``ai_hiring`` import path is preserved by a logic-free compatibility facade that
re-exports from this package (object identity preserved).

Two version numbers are kept deliberately distinct (see :mod:`ugence_ai_hiring.version`):

* :data:`__version__` — the **distribution** (wheel packaging) version.
* :data:`PRODUCT_VERSION` — the **AI Hiring product** capability-maturity version.

The composition root is :mod:`ugence_ai_hiring.platform`; the domain-neutral
governance kernel is the ``ugence-decision-authority`` distribution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .version import (
    DISTRIBUTION_VERSION as __version__,
    PRODUCT_VERSION,
    VersionInfo,
    version_info,
)

__all__ = [
    "HiringPlatform",
    "build_in_memory_platform",
    "version_info",
    "VersionInfo",
    "PRODUCT_VERSION",
    "__version__",
]

# The composition root lives in :mod:`ugence_ai_hiring.platform`. Resolve the two
# entry points lazily (PEP 562) so importing this top-level module does no heavy
# wiring and forms no import cycle; ``ugence_ai_hiring.HiringPlatform`` /
# ``ugence_ai_hiring.build_in_memory_platform`` still resolve to the identical
# canonical objects.
if TYPE_CHECKING:  # pragma: no cover - typing only
    from .platform import HiringPlatform, build_in_memory_platform


def __getattr__(name: str):
    if name in ("HiringPlatform", "build_in_memory_platform"):
        from . import platform

        return getattr(platform, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
