"""Public-surface classification for the Decision Governance kernel.

Every exported symbol belongs to exactly one category:

* **PUBLIC** — reachable through ``decision_governance.api.*``. Covered by the
  versioning guarantees in ``decision_governance.version``. This is what
  consumers should import.
* **INTERNAL** — implementation modules (e.g.
  ``decision_governance.services.case_decision_service``). Importable, but not
  contractual: they may change in a MINOR release. Prefer the ``api`` surface.
* **COMPATIBILITY** — historical import paths retained for backward
  compatibility that resolve to the identical objects (e.g. the ``ai_hiring.*``
  kernel shims). Owned by the consuming layer, not the kernel.
* **DEPRECATED** — public symbols scheduled for removal in a future MAJOR
  release. Currently empty.

The ``api`` package's ``__all__`` lists are the single source of truth for the
PUBLIC set; :func:`public_surface` derives it live, and the stabilization tests
pin a snapshot so any change to the public surface is intentional and reviewed.
"""

from __future__ import annotations

import importlib
from enum import Enum

#: The public API submodules, in classification order.
PUBLIC_API_MODULES: tuple[str, ...] = (
    "contracts",
    "services",
    "ports",
    "repositories",
    "vocabulary",
    "audit",
    "identity",
    "policy",
    "errors",
    "common",
)

#: Symbols scheduled for removal (name → the version that removes them).
DEPRECATED_SYMBOLS: dict[str, str] = {}


class SurfaceCategory(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    COMPATIBILITY = "COMPATIBILITY"
    DEPRECATED = "DEPRECATED"


def public_surface() -> dict[str, tuple[str, ...]]:
    """The live public surface: ``api`` submodule name → its exported symbols."""
    surface: dict[str, tuple[str, ...]] = {}
    for name in PUBLIC_API_MODULES:
        module = importlib.import_module(f"decision_governance.api.{name}")
        surface[name] = tuple(module.__all__)
    return surface


def public_symbol_count() -> int:
    return sum(len(names) for names in public_surface().values())


def is_deprecated(symbol: str) -> bool:
    return symbol in DEPRECATED_SYMBOLS
