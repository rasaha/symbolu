"""COMPATIBILITY-ONLY legacy namespace for the Decision Authority capability.

Canonical package: ``ugence_decision_authority`` (distribution
``ugence-decision-authority``). Decision Authority is the bounded capability that
governs when an AI recommendation may become a binding business decision.

This ``decision_governance`` namespace is a **logic-free compatibility surface**:
every public symbol and every submodule re-exports the *same object* from the
canonical package (object identity preserved), so existing
``import decision_governance...`` and ``from decision_governance... import ...``
statements keep working unchanged, with identical serialization, hashes, and
behavior. No business logic lives here.

Mechanism: an explicit, eager alias of the canonical package's submodules into
``sys.modules`` under the legacy dotted names — not a meta-path import hook. This
is required (rather than one hand-written stub per module) because consumers import
deep kernel paths and rely on object identity across the whole tree; per-file stubs
could not preserve identity for non-``__all__`` attributes.

Removal / review target: ``decision_governance`` 2.0.0.
"""
from __future__ import annotations


def _ensure_decision_authority_importable() -> None:
    """Source-checkout bootstrap (mirrors ``governance_providers``): put
    ``packages/capabilities/decision-authority/src`` on ``sys.path`` only when the
    canonical package is not already importable. Installed as a wheel dependency it
    is already importable and this is a no-op; only a bare source checkout needs it.
    """
    import importlib.util

    if importlib.util.find_spec("ugence_decision_authority") is not None:
        return
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "packages" / "capabilities" / "decision-authority" / "src"
        if (cand / "ugence_decision_authority" / "__init__.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return


_ensure_decision_authority_importable()

import importlib as _il  # noqa: E402
import pkgutil as _pkgutil  # noqa: E402
import sys as _sys  # noqa: E402

import ugence_decision_authority as _canon  # noqa: E402

_CANON = _canon.__name__
_LEGACY = __name__

# Alias every canonical submodule to the SAME module object under the legacy
# dotted name so ``import decision_governance.<path>`` resolves to the identical
# object as ``import ugence_decision_authority.<path>``.
for _finder, _modname, _ispkg in _pkgutil.walk_packages(_canon.__path__, _CANON + "."):
    if ".tests" in _modname:
        continue
    _sys.modules[_LEGACY + _modname[len(_CANON):]] = _il.import_module(_modname)

# Bind direct-child submodules as attributes of this package for attribute access.
for _name in list(_sys.modules):
    if _name.startswith(_LEGACY + ".") and "." not in _name[len(_LEGACY) + 1:]:
        setattr(_sys.modules[_LEGACY], _name[len(_LEGACY) + 1:], _sys.modules[_name])

# Curated public re-exports (identity preserved) — mirror the canonical top level.
from ugence_decision_authority import (  # noqa: E402,F401
    REASON_CODE_CATALOG,
    Clock,
    DomainModel,
    DomainValidationError,
    GovernanceError,
    IdFactory,
    ReasonCode,
    ReasonCodeSpec,
    UncertaintyLevel,
    UncertaintyRule,
    __version__,
    canonical_hash,
    get_reason_code_spec,
    is_known_reason_code,
    new_id,
    utc_now,
)

__all__ = list(_canon.__all__)
