"""COMPATIBILITY-ONLY legacy namespace for Ugence Procurement (application layer).

Canonical package: ``ugence_procurement`` (distribution ``ugence-procurement``).

This ``applications.procurement`` namespace is a **logic-free compatibility surface**:
the composition root (``platform``), configuration, and callable API facade all
re-export the *same objects* from the canonical package (object identity preserved),
so existing ``import applications.procurement...`` and
``from applications.procurement... import ...`` statements keep working unchanged —
with identical behavior. No business logic lives here.

Mechanism: alias the canonical application submodules
(``ugence_procurement.configuration`` / ``ugence_procurement.platform``) into
``sys.modules`` under the legacy dotted names; the callable API facade is handled by
the sibling ``applications/procurement/api/__init__.py`` shim, which aliases
``applications.procurement.api.routes`` onto ``ugence_procurement.routes``.

The procurement *domain* submodules are exposed under the separate
``domains.procurement`` legacy namespace.

Removal / review target: ``applications.procurement`` 1.0.0.
"""

from __future__ import annotations


def _ensure_canonical_importable() -> None:
    """Source-checkout bootstrap: put ``packages/products/procurement/src`` on
    ``sys.path`` only when the canonical package is not already importable.
    """
    import importlib.util

    if importlib.util.find_spec("ugence_procurement") is not None:
        return
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "packages" / "products" / "procurement" / "src"
        if (cand / "ugence_procurement" / "__init__.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return


_ensure_canonical_importable()

import sys as _sys  # noqa: E402

import ugence_procurement.configuration as _configuration  # noqa: E402
import ugence_procurement.platform as _platform  # noqa: E402

# Alias the canonical application submodules under the legacy dotted names so
# ``applications.procurement.configuration`` / ``applications.procurement.platform``
# resolve to the identical canonical module objects.
_sys.modules[__name__ + ".configuration"] = _configuration
_sys.modules[__name__ + ".platform"] = _platform

# Curated public re-exports (identity preserved) — mirror the original application.
from ugence_procurement.configuration import ProcurementConfiguration  # noqa: E402
from ugence_procurement.platform import (  # noqa: E402
    ProcurementPlatform,
    build_in_memory_platform,
)

__all__ = ["ProcurementPlatform", "build_in_memory_platform", "ProcurementConfiguration"]
