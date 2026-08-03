"""Phase-4A DecisionCase contracts — extracted to the DGM kernel in Phase 5A.

These contracts now live in ``ugence_decision_authority.decisions``. This shim re-exports
them and aliases every submodule into ``sys.modules`` so historical import paths
(``ugence_ai_hiring.decision_cases`` and ``ugence_ai_hiring.decision_cases.<sub>``) resolve to the
identical kernel objects — preserving hashes, serialization, and ``isinstance``.
"""

from __future__ import annotations

import sys as _sys

from ugence_decision_authority import decisions as _kernel
from ugence_decision_authority.decisions import *  # noqa: F401,F403
from ugence_decision_authority.decisions import __all__  # noqa: F401

_SUBMODULES = (
    "status", "subject", "authority", "recommendation", "decision",
    "review", "override", "case", "lifecycle", "validation",
)
for _name in _SUBMODULES:
    _sys.modules[f"{__name__}.{_name}"] = getattr(_kernel, _name)
