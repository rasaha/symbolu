"""Extracted to the DGM kernel in Phase 5B.

Now lives in ``ugence_decision_authority.services.reconciliation_service``; this shim aliases the historical
``ugence_ai_hiring.services.reconciliation_service`` path to the identical kernel module.
"""
from __future__ import annotations
import sys as _sys
from ugence_decision_authority.services import reconciliation_service as _kernel_module
_sys.modules[__name__] = _kernel_module
