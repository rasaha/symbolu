"""COMPATIBILITY-ONLY legacy namespace for the Ugence Procurement product (domain).

Canonical package: ``ugence_procurement`` (distribution ``ugence-procurement``).
Ugence Procurement is the governed purchase-approval and authorized-supplier-action
product built on the Decision Authority kernel.

This ``domains.procurement`` namespace is a **logic-free compatibility surface**:
every public symbol and every submodule re-exports the *same object* from the
canonical package (object identity preserved), so existing
``import domains.procurement...`` and ``from domains.procurement... import ...``
statements keep working unchanged — with identical serialization, hashes, errors,
and behavior. No business logic lives here.

Mechanism: an explicit, eager alias of the canonical package's **domain** submodules
into ``sys.modules`` under the legacy dotted names (mirroring the
``decision_governance`` shim). Consumers deep-import submodules
(``domains.procurement.requests.contracts``, ``domains.procurement.policies.assessment`` …)
and rely on object identity across the tree; per-file stubs could not preserve
identity for non-``__all__`` attributes. Aliasing an already-imported module object
never re-executes it, so no extra import side effects are introduced.

The application-composition submodules (``configuration``, ``platform``, ``api``) are
exposed under the separate ``applications.procurement`` legacy namespace, matching the
original domain/application split.

Removal / review target: ``domains.procurement`` 1.0.0.
"""

from __future__ import annotations


def _ensure_canonical_importable() -> None:
    """Source-checkout bootstrap (mirrors ``decision_governance``): put
    ``packages/products/procurement/src`` on ``sys.path`` only when the canonical
    package is not already importable. Installed as a wheel dependency it is already
    importable and this is a no-op; only a bare source checkout needs it.
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

import importlib as _il  # noqa: E402
import pkgutil as _pkgutil  # noqa: E402
import sys as _sys  # noqa: E402

import ugence_procurement as _canon  # noqa: E402

_CANON = _canon.__name__
_LEGACY = __name__

# The canonical top-level submodules that make up the procurement *domain* (as
# opposed to the application-composition submodules exposed under
# ``applications.procurement``). Only these subtrees are aliased here.
_DOMAIN_ROOTS = frozenset({
    "errors", "requests", "validation", "policies", "approvals", "actions",
    "suppliers", "adapters",
})

# Alias every canonical *domain* submodule to the SAME module object under the
# legacy dotted name so ``import domains.procurement.<path>`` resolves to the
# identical object as ``import ugence_procurement.<path>``.
for _finder, _modname, _ispkg in _pkgutil.walk_packages(_canon.__path__, _CANON + "."):
    _suffix = _modname[len(_CANON) + 1:]
    if _suffix.split(".")[0] not in _DOMAIN_ROOTS:
        continue
    if ".tests" in _modname:
        continue
    try:
        _mod = _il.import_module(_modname)
    except Exception:  # pragma: no cover - defensive
        continue
    _sys.modules[_LEGACY + "." + _suffix] = _mod

# Bind direct-child submodules as attributes of this package for attribute access.
for _name in list(_sys.modules):
    if _name.startswith(_LEGACY + ".") and "." not in _name[len(_LEGACY) + 1:]:
        setattr(_sys.modules[_LEGACY], _name[len(_LEGACY) + 1:], _sys.modules[_name])

# Curated public re-export (identity preserved) — mirror the original domain package.
from ugence_procurement import errors  # noqa: E402,F401

__all__ = ["errors"]
