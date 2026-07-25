"""Decision Governance Middleware (DGM) — domain-neutral governance kernel.

The reusable core extracted from a completed reference implementation. It models
the governance chain — decision cases, recommendations, decisions, action requests,
context envelopes, authorization, execution, and reconciliation — with **no
knowledge of any particular subject domain**.

The kernel never imports a consuming application or domain package. Applications
(``applications/*``) depend on domains (``domains/*``), which depend on this
kernel; the reverse is forbidden.
"""

from __future__ import annotations

from .base import DomainModel
from .common import Clock, IdFactory, canonical_hash, new_id, utc_now
from .errors import DomainValidationError, GovernanceError
from .vocabulary import (
    REASON_CODE_CATALOG,
    ReasonCode,
    ReasonCodeSpec,
    UncertaintyLevel,
    UncertaintyRule,
    get_reason_code_spec,
    is_known_reason_code,
)

__all__ = [
    "DomainModel",
    "GovernanceError",
    "DomainValidationError",
    "Clock",
    "IdFactory",
    "new_id",
    "utc_now",
    "canonical_hash",
    "ReasonCode",
    "ReasonCodeSpec",
    "REASON_CODE_CATALOG",
    "is_known_reason_code",
    "get_reason_code_spec",
    "UncertaintyLevel",
    "UncertaintyRule",
    "__version__",
]

__version__ = "1.0.0"
