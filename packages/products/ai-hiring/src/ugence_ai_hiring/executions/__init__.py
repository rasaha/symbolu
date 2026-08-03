"""Phase-4C execution contracts — extracted to the DGM kernel in Phase 5A.

Now live in ``ugence_decision_authority.execution``; this shim re-exports them and aliases
every submodule so historical ``ugence_ai_hiring.executions[.<sub>]`` paths resolve to the
identical kernel objects.
"""

from __future__ import annotations

import sys as _sys

from ugence_decision_authority import execution as _kernel
from ugence_decision_authority.execution import *  # noqa: F401,F403
from ugence_decision_authority.execution import __all__  # noqa: F401

_SUBMODULES = (
    "status", "execution_intent", "execution_attempt", "execution_record",
    "reconciliation", "compensation", "external_system", "lifecycle", "validation",
)
for _name in _SUBMODULES:
    _sys.modules[f"{__name__}.{_name}"] = getattr(_kernel, _name)
