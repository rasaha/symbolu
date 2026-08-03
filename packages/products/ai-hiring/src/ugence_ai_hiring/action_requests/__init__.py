"""Phase-4B action-request contracts — extracted to the DGM kernel in Phase 5A.

Now live in ``ugence_decision_authority.actions``; this shim re-exports them and aliases
every submodule so historical ``ugence_ai_hiring.action_requests[.<sub>]`` paths resolve to
the identical kernel objects.
"""

from __future__ import annotations

import sys as _sys

from ugence_decision_authority import actions as _kernel
from ugence_decision_authority.actions import *  # noqa: F401,F403
from ugence_decision_authority.actions import __all__  # noqa: F401

_SUBMODULES = (
    "status", "action_mapping", "action_request", "cer", "authorization",
    "control_plane", "lifecycle", "validation",
)
for _name in _SUBMODULES:
    _sys.modules[f"{__name__}.{_name}"] = getattr(_kernel, _name)
