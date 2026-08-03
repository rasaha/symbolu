"""COMPATIBILITY-ONLY legacy namespace for the AI Hiring product.

Canonical package: ``ugence_ai_hiring`` (distribution ``ugence-ai-hiring``).

This ``ai_hiring`` namespace, **as shipped in the ``ugence-ai-hiring`` wheel**, is
a *logic-free compatibility surface*: every public symbol and every submodule
re-exports the **same object** from the canonical package (object identity
preserved), so existing ``import ai_hiring...`` and ``from ai_hiring... import ...``
statements keep working unchanged — with identical serialization, hashes,
errors, and behavior. No product implementation lives here.

Mechanism: an explicit, eager alias of the canonical package's submodules into
``sys.modules`` under the legacy dotted names (mirroring the ``decision_governance``
/ ``governance_providers`` shims). Consumers deep-import submodules
(``ai_hiring.domain.evaluation``, ``ai_hiring.services.*``, ``ai_hiring.api.*`` …)
and rely on object identity across the tree; per-file stubs could not preserve
identity for non-``__all__`` attributes. Aliasing an already-imported module
object never re-executes it, so no extra import side effects are introduced.

Note on the monorepo: inside the ``symbolu`` source tree the *original* historical
``ai_hiring`` package (the implementation retained for import stability and the
platform freeze) is what resolves; this facade only takes effect for consumers
who install the independent ``ugence-ai-hiring`` wheel into a clean environment.
The facade converges on the identical canonical objects either way.

Removal / review target: the redundant original ``ai_hiring`` source is removed in
a later cleanup PR, once all monorepo consumers have migrated and the platform
freeze is re-cut.
"""

from __future__ import annotations

import importlib as _il
import pkgutil as _pkgutil
import sys as _sys

import ugence_ai_hiring as _canon

_CANON = _canon.__name__
_LEGACY = __name__

# Alias every canonical submodule to the SAME module object under the legacy
# dotted name so ``import ai_hiring.<path>`` resolves to the identical object as
# ``import ugence_ai_hiring.<path>``. Skip the canonical package's own test tree
# and its bundled ``ai_hiring`` facade name (there is none under the canonical
# package, but guard defensively).
for _finder, _modname, _ispkg in _pkgutil.walk_packages(_canon.__path__, _CANON + "."):
    if ".tests" in _modname:
        continue
    try:
        _mod = _il.import_module(_modname)
    except Exception:  # pragma: no cover - optional submodule (e.g. api needs extras)
        continue
    _sys.modules[_LEGACY + _modname[len(_CANON):]] = _mod

# Bind direct-child submodules as attributes of this package for attribute access.
for _name in list(_sys.modules):
    if _name.startswith(_LEGACY + ".") and "." not in _name[len(_LEGACY) + 1:]:
        setattr(_sys.modules[_LEGACY], _name[len(_LEGACY) + 1:], _sys.modules[_name])

# Curated public re-exports (identity preserved) — mirror the canonical top level.
from ugence_ai_hiring import (  # noqa: E402
    PRODUCT_VERSION,
    VersionInfo,
    __version__,
    version_info,
)

__all__ = [
    "HiringPlatform",
    "build_in_memory_platform",
    "version_info",
    "VersionInfo",
    "PRODUCT_VERSION",
    "__version__",
]


def __getattr__(name: str):
    # Lazy composition entry points, resolved from the canonical package.
    if name in ("HiringPlatform", "build_in_memory_platform"):
        return getattr(_canon, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
