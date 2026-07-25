"""Extracted to the DGM kernel in Phase 5B.

Now lives in ``decision_governance.services.reconciliation_service``; this shim aliases the historical
``ai_hiring.services.reconciliation_service`` path to the identical kernel module.
"""
from __future__ import annotations
import sys as _sys
from decision_governance.services import reconciliation_service as _kernel_module
_sys.modules[__name__] = _kernel_module
