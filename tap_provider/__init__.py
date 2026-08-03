"""COMPATIBILITY-ONLY legacy namespace for the TAP assertion-governance provider.

Canonical package: ``ugence_tap_provider`` (distribution ``ugence-tap-provider``,
``packages/providers/tap``). TAP evaluates whether a material assertion is
supported by supplied evidence and returns a structured, component-level result.
It owns **no** authorization or execution authority.

This ``tap_provider`` namespace is a **logic-free compatibility surface**: every
public symbol and every submodule re-exports the *same object* from the canonical
package (object identity preserved), so existing ``import tap_provider...`` and
``from tap_provider... import ...`` statements keep working unchanged — with
identical serialization, fingerprints, errors, and behavior. No TAP evaluation
logic and no second implementation lives here.

Mechanism: an explicit, eager alias of the canonical package's submodules into
``sys.modules`` under the legacy dotted names — not a meta-path import hook. This
is required (rather than one hand-written stub per module) because consumers deep-
import TAP submodules (``.api``, ``.core``, ``.client``, ``.configuration``,
``.mapping[.controls|.request|.result]``, ``.conformance``, ``.health``,
``.observability``, ``.errors``, ``.version``, ``.provider``) and rely on object
identity across the whole tree; per-file stubs could not preserve identity for
non-``__all__`` attributes. Aliasing an already-imported module object never
re-executes it, so no extra import side effects are introduced beyond importing
the canonical package.

TAP is a peer of ActionGate and never imports or invokes it; neither does this
facade. Removal / review target: aligned with the ``tap_provider`` 0.2.0
compatibility-shim removal.
"""
from __future__ import annotations


def _ensure_canonical_tap_importable() -> None:
    """Source-checkout bootstrap (mirrors the ``governance_providers`` shim): put
    ``packages/providers/tap/src`` on ``sys.path`` only when the canonical package
    is not already importable. Installed as a wheel dependency it is already
    importable and this is a no-op; only a bare source checkout needs it.
    """
    import importlib.util

    if importlib.util.find_spec("ugence_tap_provider") is not None:
        return
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "packages" / "providers" / "tap" / "src"
        if (cand / "ugence_tap_provider" / "__init__.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return


_ensure_canonical_tap_importable()

import importlib as _il  # noqa: E402
import pkgutil as _pkgutil  # noqa: E402
import sys as _sys  # noqa: E402

import ugence_tap_provider as _canon  # noqa: E402

_CANON = _canon.__name__
_LEGACY = __name__

# Alias every canonical submodule to the SAME module object under the legacy
# dotted name so ``import tap_provider.<path>`` resolves to the identical object as
# ``import ugence_tap_provider.<path>``. The CLI entry points (``cli``, ``__main__``)
# are packaging surfaces, not part of the legacy import contract, so they are not
# aliased into the legacy namespace.
for _finder, _modname, _ispkg in _pkgutil.walk_packages(_canon.__path__, _CANON + "."):
    _leaf = _modname[len(_CANON) + 1:]
    if _leaf in ("cli", "__main__") or _leaf.startswith("cli.") or ".tests" in _modname:
        continue
    _sys.modules[_LEGACY + _modname[len(_CANON):]] = _il.import_module(_modname)

# Bind direct-child submodules as attributes of this package for attribute access
# (e.g. ``tap_provider.api`` after ``import tap_provider``).
for _name in list(_sys.modules):
    if _name.startswith(_LEGACY + ".") and "." not in _name[len(_LEGACY) + 1:]:
        setattr(_sys.modules[_LEGACY], _name[len(_LEGACY) + 1:], _sys.modules[_name])

# Curated top-level re-exports (identity preserved) — mirror the canonical package.
from ugence_tap_provider import __version__, version_info  # noqa: E402,F401

__all__ = list(getattr(_canon, "__all__", ["__version__", "version_info"]))
