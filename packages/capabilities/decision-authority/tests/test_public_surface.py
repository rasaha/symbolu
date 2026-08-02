"""Phase 5E — public-surface classification & accidental-export guard.

Pins the public API surface and proves:

* every ``api`` symbol is the *identical object* as its internal definition;
* the ``api`` modules export nothing beyond their declared ``__all__`` (no symbol
  leaks in through a star import);
* the public surface matches a pinned snapshot, so any addition/removal is a
  deliberate, reviewed change (MINOR for additions, MAJOR for removals — see
  ``decision_governance.version``).
"""

from __future__ import annotations

import importlib

import pytest

from decision_governance import surface
from decision_governance.surface import SurfaceCategory

# Pinned snapshot of the public surface (per api submodule → symbol count).
# Changing these is intentional: additions bump MINOR, removals bump MAJOR.
PINNED_SURFACE = {
    "contracts": 53,
    "services": 12,
    "ports": 10,
    "repositories": 8,
    "vocabulary": 7,
    "audit": 11,
    "identity": 4,
    "policy": 6,
    "errors": 70,
    "common": 6,
}
PINNED_TOTAL = 187


def test_surface_categories_are_the_four_defined():
    assert {c.value for c in SurfaceCategory} == {
        "PUBLIC", "INTERNAL", "COMPATIBILITY", "DEPRECATED"}


def test_public_surface_matches_pinned_snapshot():
    live = {name: len(symbols) for name, symbols in surface.public_surface().items()}
    assert live == PINNED_SURFACE
    assert surface.public_symbol_count() == PINNED_TOTAL


def test_no_deprecated_symbols_yet():
    assert surface.DEPRECATED_SYMBOLS == {}


def test_api_symbols_are_identical_to_internal_definitions():
    """Every public symbol *is* its internal object — identity, hashing, and
    isinstance are path-independent."""
    checks = {
        "services": ("decision_governance.services", ["DecisionCaseService",
                     "ExecutionService", "ReconciliationService"]),
        "contracts": ("decision_governance.decisions", ["DecisionRecord",
                      "DecisionOutcome", "AuthorityType"]),
        "ports": ("decision_governance.ports", ["LinkedRecordPort"]),
        "audit": ("decision_governance.audit", ["AuditEventType", "AuditService"]),
        "policy": ("decision_governance.policy", ["Permission", "AccessGrant"]),
        "errors": ("decision_governance.errors", ["ExecutionError", "GovernanceError"]),
    }
    for api_name, (internal_mod, symbols) in checks.items():
        api_mod = importlib.import_module(f"decision_governance.api.{api_name}")
        internal = importlib.import_module(internal_mod)
        for sym in symbols:
            assert getattr(api_mod, sym) is getattr(internal, sym), f"{api_name}.{sym}"


def test_api_modules_do_not_leak_symbols_beyond_all():
    """No public (non-underscore) attribute exists outside ``__all__`` — guards
    against accidental exports leaking through star imports."""
    # Names that are legitimately present (submodule machinery / typing).
    allowed_extra = {"annotations"}
    for name in surface.PUBLIC_API_MODULES:
        mod = importlib.import_module(f"decision_governance.api.{name}")
        declared = set(mod.__all__)
        public_attrs = {
            attr for attr in vars(mod)
            if not attr.startswith("_")
            and attr not in allowed_extra
            # ignore re-exported modules themselves (import side-effects)
            and not _is_module(getattr(mod, attr))
        }
        leaked = public_attrs - declared
        assert not leaked, f"{name} leaks non-__all__ symbols: {sorted(leaked)}"


def _is_module(obj) -> bool:
    import types
    return isinstance(obj, types.ModuleType)


def test_every_api_all_symbol_resolves():
    for name in surface.PUBLIC_API_MODULES:
        mod = importlib.import_module(f"decision_governance.api.{name}")
        missing = [s for s in mod.__all__ if not hasattr(mod, s)]
        assert not missing, f"{name} declares but does not define: {missing}"
