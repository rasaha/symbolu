"""Extracted to the DGM kernel in Phase 5B.

Now lives in ``ugence_decision_authority.services._action_authz``; this shim aliases the historical
``ugence_ai_hiring.services._action_authz`` path to the identical kernel module.
"""
from __future__ import annotations
import sys as _sys
from ugence_decision_authority.services import _action_authz as _kernel_module
_sys.modules[__name__] = _kernel_module
