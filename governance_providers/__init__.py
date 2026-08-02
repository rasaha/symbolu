"""COMPATIBILITY-ONLY legacy namespace for the Governance Provider Framework.

Canonical package: ``ugence_governance_provider_framework`` (distribution
``ugence-governance-provider-framework``). The Governance Provider Framework is
the capability-neutral mechanism for registering, resolving, invoking, observing,
and testing governance providers. It owns **no** governance authority.

This ``governance_providers`` namespace is a **logic-free compatibility surface**:
every public symbol and every submodule re-exports the *same object* from the
canonical package (object identity preserved), so existing
``import governance_providers...`` and ``from governance_providers... import ...``
statements keep working unchanged — with identical serialization, hashes, errors,
and behavior. No business logic and no framework implementation lives here.

Mechanism: an explicit, eager alias of the canonical package's submodules into
``sys.modules`` under the legacy dotted names — not a meta-path import hook. This
is required (rather than one hand-written stub per module) because consumers deep-
import framework submodules (``.api``, ``.contracts[.action]``, ``.reference.*``,
``.conformance``, ``.version``, ``.registry`` …) and rely on object identity across
the whole tree; per-file stubs could not preserve identity for non-``__all__``
attributes. Aliasing an already-imported module object never re-executes it, so no
extra import side effects are introduced beyond importing the canonical package.

Removal / review target: aligned with the ``governance_providers`` 0.2.0
contract-shim removal.
"""
from __future__ import annotations


def _ensure_canonical_framework_importable() -> None:
    """Source-checkout bootstrap (mirrors the ``decision_governance`` shim): put
    ``packages/governance-provider-framework/src`` on ``sys.path`` only when the
    canonical package is not already importable. Installed as a wheel dependency it
    is already importable and this is a no-op; only a bare source checkout needs it.
    """
    import importlib.util

    if importlib.util.find_spec("ugence_governance_provider_framework") is not None:
        return
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "packages" / "governance-provider-framework" / "src"
        if (cand / "ugence_governance_provider_framework" / "__init__.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return


_ensure_canonical_framework_importable()

import importlib as _il  # noqa: E402
import pkgutil as _pkgutil  # noqa: E402
import sys as _sys  # noqa: E402

import ugence_governance_provider_framework as _canon  # noqa: E402

_CANON = _canon.__name__
_LEGACY = __name__

# Alias every canonical submodule to the SAME module object under the legacy
# dotted name so ``import governance_providers.<path>`` resolves to the identical
# object as ``import ugence_governance_provider_framework.<path>``. Tests are not
# part of the installed package and are skipped.
for _finder, _modname, _ispkg in _pkgutil.walk_packages(_canon.__path__, _CANON + "."):
    if ".tests" in _modname or _modname.endswith(".tests"):
        continue
    _sys.modules[_LEGACY + _modname[len(_CANON):]] = _il.import_module(_modname)

# Bind direct-child submodules as attributes of this package for attribute access
# (e.g. ``governance_providers.api`` after ``import governance_providers``).
for _name in list(_sys.modules):
    if _name.startswith(_LEGACY + ".") and "." not in _name[len(_LEGACY) + 1:]:
        setattr(_sys.modules[_LEGACY], _name[len(_LEGACY) + 1:], _sys.modules[_name])

# Curated top-level re-exports (identity preserved) — mirror the canonical package.
from ugence_governance_provider_framework import __version__  # noqa: E402,F401

__all__ = list(getattr(_canon, "__all__", ["__version__"]))
