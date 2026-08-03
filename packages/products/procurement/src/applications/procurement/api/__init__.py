"""COMPATIBILITY-ONLY legacy namespace for the Procurement callable API facade.

Canonical module: ``ugence_procurement.routes``. This shim re-exports the *same*
``ProcurementAPI`` / ``ProcurementRunResult`` objects (identity preserved) and aliases
``applications.procurement.api.routes`` onto ``ugence_procurement.routes`` so existing
``from applications.procurement.api.routes import ProcurementAPI`` statements keep
working unchanged. No business logic lives here.
"""

from __future__ import annotations

import sys as _sys

import ugence_procurement.routes as _routes

# Alias the canonical routes module under the legacy deep path.
_sys.modules[__name__ + ".routes"] = _routes

from ugence_procurement.routes import ProcurementAPI, ProcurementRunResult  # noqa: E402

routes = _routes

__all__ = ["ProcurementAPI", "ProcurementRunResult"]
