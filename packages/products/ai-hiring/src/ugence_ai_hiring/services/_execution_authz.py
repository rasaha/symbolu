"""Extracted to the DGM kernel in Phase 5B.

Now lives in ``ugence_decision_authority.services._execution_authz``; this shim aliases the historical
``ugence_ai_hiring.services._execution_authz`` path to the identical kernel module.
"""
from __future__ import annotations
import sys as _sys
from ugence_decision_authority.services import _execution_authz as _kernel_module
_sys.modules[__name__] = _kernel_module
