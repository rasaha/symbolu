"""Phase-4A DecisionCase contracts — extracted to the DGM kernel in Phase 5A.

These contracts now live in ``decision_governance.decisions``. This shim re-exports
them and aliases every submodule into ``sys.modules`` so historical import paths
(``ai_hiring.decision_cases`` and ``ai_hiring.decision_cases.<sub>``) resolve to the
identical kernel objects — preserving hashes, serialization, and ``isinstance``.
"""

from __future__ import annotations

import sys as _sys

from decision_governance import decisions as _kernel
from decision_governance.decisions import *  # noqa: F401,F403
from decision_governance.decisions import __all__  # noqa: F401

_SUBMODULES = (
    "status", "subject", "authority", "recommendation", "decision",
    "review", "override", "case", "lifecycle", "validation",
)
for _name in _SUBMODULES:
    _sys.modules[f"{__name__}.{_name}"] = getattr(_kernel, _name)
