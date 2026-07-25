"""Phase-4B action-request contracts — extracted to the DGM kernel in Phase 5A.

Now live in ``decision_governance.actions``; this shim re-exports them and aliases
every submodule so historical ``ai_hiring.action_requests[.<sub>]`` paths resolve to
the identical kernel objects.
"""

from __future__ import annotations

import sys as _sys

from decision_governance import actions as _kernel
from decision_governance.actions import *  # noqa: F401,F403
from decision_governance.actions import __all__  # noqa: F401

_SUBMODULES = (
    "status", "action_mapping", "action_request", "cer", "authorization",
    "control_plane", "lifecycle", "validation",
)
for _name in _SUBMODULES:
    _sys.modules[f"{__name__}.{_name}"] = getattr(_kernel, _name)
